"""Evidence-backed instrument review and immutable audit history."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select

from rfinance.storage.models.instrument_registry import (
    InstrumentRegistryRecord,
    InstrumentReviewEventRecord,
)

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session, sessionmaker

    from rfinance.data.contracts import InstrumentContract


_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
MAX_REVIEW_EVIDENCE_BYTES = 25 * 1024 * 1024
_COPY_CHUNK_BYTES = 1024 * 1024


class InstrumentReviewDecision(StrEnum):
    """Allowed manual review outcomes; there is deliberately no AI outcome."""

    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class InstrumentReviewResult:
    instrument_id: str
    previous_status: str
    verification_status: str
    review_id: str
    reviewed_at_utc: str
    evidence_reference: str
    evidence_sha256: str


@dataclass(frozen=True, slots=True)
class InstrumentReviewCandidate:
    instrument_id: str
    ticker: str | None
    exchange: str | None
    company_name: str | None
    currency: str | None
    instrument_type: str | None
    verification_status: str
    created_at_utc: str
    last_reviewed_at_utc: str | None


@dataclass(frozen=True, slots=True)
class InstrumentReviewHistoryItem:
    review_id: str
    instrument_id: str
    previous_status: str
    decision: str
    reviewed_at_utc: str
    reviewer_label: str
    evidence_reference: str
    evidence_sha256: str
    notes: str


class InstrumentReviewService:
    """Promote or reject a placeholder only through an explicit evidence-backed review."""

    def __init__(
        self,
        sessions: sessionmaker[Session],
        *,
        data_directory: Path | None = None,
        max_evidence_bytes: int = MAX_REVIEW_EVIDENCE_BYTES,
    ) -> None:
        if max_evidence_bytes <= 0:
            raise ValueError("max_evidence_bytes must be positive")
        self._sessions = sessions
        self._data_directory = (
            None if data_directory is None else data_directory.expanduser().resolve()
        )
        self._max_evidence_bytes = max_evidence_bytes

    def list_instruments(self, *, limit: int = 500) -> tuple[InstrumentReviewCandidate, ...]:
        """Return instrument master rows for an operator review queue."""

        if limit <= 0 or limit > 2_000:
            raise ValueError("limit must be between 1 and 2000")

        with self._sessions() as session:
            records = session.scalars(
                select(InstrumentRegistryRecord)
                .order_by(
                    InstrumentRegistryRecord.verification_status,
                    InstrumentRegistryRecord.instrument_id,
                )
                .limit(limit)
            ).all()

        return tuple(
            InstrumentReviewCandidate(
                instrument_id=record.instrument_id,
                ticker=record.ticker,
                exchange=record.exchange,
                company_name=record.company_name,
                currency=record.currency,
                instrument_type=record.instrument_type,
                verification_status=record.verification_status,
                created_at_utc=record.created_at_utc,
                last_reviewed_at_utc=record.last_reviewed_at_utc,
            )
            for record in records
        )

    def review_history(
        self,
        instrument_id: str,
        *,
        limit: int = 100,
    ) -> tuple[InstrumentReviewHistoryItem, ...]:
        """Return immutable audit history for one instrument."""

        normalized_id = instrument_id.strip()
        if not normalized_id or len(normalized_id) > 128:
            raise ValueError("instrument_id must contain 1 to 128 characters")
        if limit <= 0 or limit > 500:
            raise ValueError("limit must be between 1 and 500")

        with self._sessions() as session:
            records = session.scalars(
                select(InstrumentReviewEventRecord)
                .where(InstrumentReviewEventRecord.instrument_id == normalized_id)
                .order_by(
                    InstrumentReviewEventRecord.reviewed_at_utc.desc(),
                    InstrumentReviewEventRecord.review_id.desc(),
                )
                .limit(limit)
            ).all()

        return tuple(
            InstrumentReviewHistoryItem(
                review_id=record.review_id,
                instrument_id=record.instrument_id,
                previous_status=record.previous_status,
                decision=record.decision,
                reviewed_at_utc=record.reviewed_at_utc,
                reviewer_label=record.reviewer_label,
                evidence_reference=record.evidence_reference,
                evidence_sha256=record.evidence_sha256,
                notes=record.notes,
            )
            for record in records
        )

    def review_instrument_from_file(
        self,
        instrument_id: str,
        *,
        decision: InstrumentReviewDecision,
        reviewer_label: str,
        evidence_file: Path,
        notes: str,
        verified_instrument: InstrumentContract | None = None,
        reviewed_at: datetime | None = None,
    ) -> InstrumentReviewResult:
        """Archive a user-selected evidence file, hash it, and record the review.

        The evidence is copied under the configured RFinance data directory.
        The source file is never modified. If the database review fails, the
        just-created archive is removed. A committed audit event retains the
        archived relative path and SHA-256 digest.
        """

        if self._data_directory is None:
            raise RuntimeError(
                "a persistent RFinance data directory is required for evidence review"
            )

        try:
            source_path = evidence_file.expanduser().resolve(strict=True)
        except OSError as error:
            raise ValueError(f"selected evidence file is unavailable: {error}") from error
        if not source_path.is_file():
            raise ValueError("selected evidence path is not a regular file")
        if source_path.stat().st_size > self._max_evidence_bytes:
            raise ValueError(
                f"evidence file exceeds the {self._max_evidence_bytes // (1024 * 1024)} MiB limit"
            )

        data_root = self._data_directory
        data_root.mkdir(parents=True, exist_ok=True)
        documents_directory = data_root / "Documents"
        documents_directory.mkdir(parents=True, exist_ok=True)
        if not documents_directory.resolve().is_relative_to(data_root):
            raise ValueError("the Documents directory resolves outside RFinance data storage")

        evidence_directory = documents_directory / "InstrumentReviewEvidence"
        evidence_directory.mkdir(parents=True, exist_ok=True)
        resolved_evidence_directory = evidence_directory.resolve()
        if not resolved_evidence_directory.is_relative_to(data_root):
            raise ValueError(
                "the instrument evidence archive resolves outside RFinance data storage"
            )

        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", source_path.name)[:120]
        if not safe_name:
            safe_name = "evidence"
        review_file_id = str(uuid4())
        destination_name = f"{review_file_id}_{safe_name}"
        destination_path = resolved_evidence_directory / destination_name
        temporary_path = resolved_evidence_directory / f".{destination_name}.part"

        digest = hashlib.sha256()
        copied_bytes = 0
        try:
            with source_path.open("rb") as source, temporary_path.open("xb") as target:
                while chunk := source.read(_COPY_CHUNK_BYTES):
                    copied_bytes += len(chunk)
                    if copied_bytes > self._max_evidence_bytes:
                        raise ValueError("evidence file grew beyond the configured size limit")
                    digest.update(chunk)
                    target.write(chunk)
                target.flush()
                os.fsync(target.fileno())
            temporary_path.replace(destination_path)

            relative_reference = destination_path.relative_to(data_root).as_posix()
            result = self.review_instrument(
                instrument_id,
                decision=decision,
                reviewer_label=reviewer_label,
                evidence_reference=relative_reference,
                evidence_sha256=digest.hexdigest(),
                notes=notes,
                verified_instrument=verified_instrument,
                reviewed_at=reviewed_at,
            )
        except Exception:
            temporary_path.unlink(missing_ok=True)
            destination_path.unlink(missing_ok=True)
            raise

        return result

    def review_instrument(
        self,
        instrument_id: str,
        *,
        decision: InstrumentReviewDecision,
        reviewer_label: str,
        evidence_reference: str,
        evidence_sha256: str,
        notes: str,
        verified_instrument: InstrumentContract | None = None,
        reviewed_at: datetime | None = None,
    ) -> InstrumentReviewResult:
        """Record a review and update current registry status in one transaction.

        A VERIFIED decision requires a complete, validated InstrumentContract that
        matches the placeholder ID. REJECTED requires no replacement metadata.
        Evidence references and SHA-256 fingerprints are preserved in the audit
        event; callers should prefer review_instrument_from_file for UI workflows.
        """

        if not isinstance(decision, InstrumentReviewDecision):
            raise TypeError("decision must be an explicit InstrumentReviewDecision")
        normalized_id = instrument_id.strip()
        if not normalized_id or len(normalized_id) > 128:
            raise ValueError("instrument_id must contain 1 to 128 characters")

        normalized_reviewer = reviewer_label.strip()
        if not normalized_reviewer or len(normalized_reviewer) > 256:
            raise ValueError("reviewer_label must contain 1 to 256 characters")
        normalized_reference = evidence_reference.strip()
        if not normalized_reference or len(normalized_reference) > 1024:
            raise ValueError("evidence_reference must contain 1 to 1024 characters")
        normalized_digest = evidence_sha256.strip().lower()
        if not _SHA256_PATTERN.fullmatch(normalized_digest):
            raise ValueError("evidence_sha256 must be a 64-character SHA-256 hex digest")
        normalized_notes = notes.strip()
        if not normalized_notes or len(normalized_notes) > 2048:
            raise ValueError("notes must contain 1 to 2048 characters")

        if decision is InstrumentReviewDecision.VERIFIED:
            if verified_instrument is None:
                raise ValueError("VERIFIED decisions require a complete InstrumentContract")
            if verified_instrument.instrument_id != normalized_id:
                raise ValueError("verified InstrumentContract ID does not match the reviewed ID")
        elif verified_instrument is not None:
            raise ValueError("REJECTED decisions cannot replace instrument metadata")

        review_time = reviewed_at or datetime.now(UTC)
        if review_time.tzinfo is None or review_time.utcoffset() is None:
            raise ValueError("reviewed_at must be timezone-aware")
        reviewed_at_utc = review_time.astimezone(UTC).isoformat()
        review_id = str(uuid4())
        reviewed_metadata_json = (
            None if verified_instrument is None else verified_instrument.model_dump_json()
        )

        with self._sessions.begin() as session:
            instrument = session.get(InstrumentRegistryRecord, normalized_id)
            if instrument is None:
                raise ValueError("instrument must exist in the registry before it can be reviewed")

            previous_status = instrument.verification_status
            event = InstrumentReviewEventRecord(
                review_id=review_id,
                instrument_id=normalized_id,
                previous_status=previous_status,
                decision=decision.value,
                reviewed_at_utc=reviewed_at_utc,
                reviewer_label=normalized_reviewer,
                evidence_reference=normalized_reference,
                evidence_sha256=normalized_digest,
                notes=normalized_notes,
                reviewed_metadata_json=reviewed_metadata_json,
            )
            session.add(event)

            instrument.verification_status = decision.value
            instrument.updated_at_utc = reviewed_at_utc
            instrument.last_reviewed_at_utc = reviewed_at_utc
            instrument.last_review_id = review_id

            if verified_instrument is not None:
                instrument.ticker = verified_instrument.ticker
                instrument.exchange = verified_instrument.exchange
                instrument.instrument_type = verified_instrument.instrument_type.value
                instrument.company_name = verified_instrument.company_name
                instrument.currency = verified_instrument.currency
                instrument.sector = verified_instrument.sector
                instrument.active = verified_instrument.active
                instrument.lot_size = verified_instrument.lot_size
                instrument.minimum_investment = (
                    None
                    if verified_instrument.minimum_investment is None
                    else format(verified_instrument.minimum_investment, "f")
                )

        return InstrumentReviewResult(
            instrument_id=normalized_id,
            previous_status=previous_status,
            verification_status=decision.value,
            review_id=review_id,
            reviewed_at_utc=reviewed_at_utc,
            evidence_reference=normalized_reference,
            evidence_sha256=normalized_digest,
        )
