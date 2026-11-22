"""Evidence-backed, append-only review of market observations."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select

from rfinance.domain.eligibility.observation import (
    ObservationCandidate,
    ObservationQuality,
    SourcePolicyStatus,
)
from rfinance.storage.models.data_ingestion import (
    MarketObservationRecord,
    SourceRegistryRecord,
)
from rfinance.storage.models.instrument_registry import InstrumentRegistryRecord
from rfinance.storage.models.observation_review import ObservationReviewEventRecord

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session, sessionmaker


_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
MAX_REVIEW_EVIDENCE_BYTES = 25 * 1024 * 1024
_COPY_CHUNK_BYTES = 1024 * 1024


class ObservationReviewDecision(StrEnum):
    """Allowed manual outcomes; there is deliberately no AI outcome."""

    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class ObservationReviewResult:
    observation_id: str
    previous_quality: str
    decision: str
    review_id: str
    reviewed_at_utc: str
    evidence_reference: str
    evidence_sha256: str


@dataclass(frozen=True, slots=True)
class ObservationReviewCandidate:
    observation_id: str
    instrument_id: str
    source_id: str
    observed_at_utc: str
    acquired_at_utc: str
    close: str
    currency: str
    raw_quality: str
    effective_quality: str


@dataclass(frozen=True, slots=True)
class ObservationReviewHistoryItem:
    review_id: str
    observation_id: str
    previous_quality: str
    decision: str
    reviewed_at_utc: str
    reviewer_label: str
    evidence_reference: str
    evidence_sha256: str
    notes: str


def _text(value: object, name: str, *, maximum: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise ValueError(f"{name} must contain 1 to {maximum} characters")
    return normalized


def _digest(value: object) -> str:
    normalized = _text(value, "evidence_sha256", maximum=64).lower()
    if not _SHA256_PATTERN.fullmatch(normalized):
        raise ValueError("evidence_sha256 must be a 64-character SHA-256 hex digest")
    return normalized


def _latest_decisions(session: Session) -> dict[str, str]:
    events = session.scalars(
        select(ObservationReviewEventRecord).order_by(
            ObservationReviewEventRecord.observation_id,
            ObservationReviewEventRecord.reviewed_at_utc.desc(),
            ObservationReviewEventRecord.review_id.desc(),
        )
    ).all()
    latest: dict[str, str] = {}
    for event in events:
        latest.setdefault(event.observation_id, event.decision)
    return latest


class ObservationReviewService:
    """Promote or reject a price only through explicit, auditable evidence."""

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

    def effective_quality(self, observation_id: str) -> str:
        """Return the quality currently visible to downstream gates."""

        normalized_id = _text(observation_id, "observation_id", maximum=36)
        with self._sessions() as session:
            return self._effective_quality(session, normalized_id)

    def _effective_quality(self, session: Session, observation_id: str) -> str:
        observation = session.get(MarketObservationRecord, observation_id)
        if observation is None:
            raise ValueError("observation must exist before it can be reviewed")
        latest = session.scalar(
            select(ObservationReviewEventRecord.decision)
            .where(ObservationReviewEventRecord.observation_id == observation_id)
            .order_by(
                ObservationReviewEventRecord.reviewed_at_utc.desc(),
                ObservationReviewEventRecord.review_id.desc(),
            )
            .limit(1)
        )
        return latest if latest is not None else observation.quality_status

    def list_candidates(self, *, limit: int = 500) -> tuple[ObservationReviewCandidate, ...]:
        """Return recent observations with raw and effective quality side by side."""

        if limit <= 0 or limit > 2_000:
            raise ValueError("limit must be between 1 and 2000")
        with self._sessions() as session:
            latest = _latest_decisions(session)
            records = session.scalars(
                select(MarketObservationRecord)
                .order_by(
                    MarketObservationRecord.observed_at_utc.desc(),
                    MarketObservationRecord.observation_id.desc(),
                )
                .limit(limit)
            ).all()
        return tuple(
            ObservationReviewCandidate(
                observation_id=record.observation_id,
                instrument_id=record.instrument_id,
                source_id=record.source_id,
                observed_at_utc=record.observed_at_utc,
                acquired_at_utc=record.acquired_at_utc,
                close=record.close,
                currency=record.currency,
                raw_quality=record.quality_status,
                effective_quality=latest.get(record.observation_id, record.quality_status),
            )
            for record in records
        )

    def review_history(
        self,
        observation_id: str,
        *,
        limit: int = 100,
    ) -> tuple[ObservationReviewHistoryItem, ...]:
        """Return immutable audit history for one observation."""

        normalized_id = _text(observation_id, "observation_id", maximum=36)
        if limit <= 0 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        with self._sessions() as session:
            records = session.scalars(
                select(ObservationReviewEventRecord)
                .where(ObservationReviewEventRecord.observation_id == normalized_id)
                .order_by(
                    ObservationReviewEventRecord.reviewed_at_utc.desc(),
                    ObservationReviewEventRecord.review_id.desc(),
                )
                .limit(limit)
            ).all()
        return tuple(
            ObservationReviewHistoryItem(
                review_id=record.review_id,
                observation_id=record.observation_id,
                previous_quality=record.previous_quality,
                decision=record.decision,
                reviewed_at_utc=record.reviewed_at_utc,
                reviewer_label=record.reviewer_label,
                evidence_reference=record.evidence_reference,
                evidence_sha256=record.evidence_sha256,
                notes=record.notes,
            )
            for record in records
        )

    def candidates_for_eligibility(
        self,
        *,
        limit: int = 500,
    ) -> tuple[ObservationCandidate, ...]:
        """Build domain gate inputs using effective, review-adjusted quality."""

        candidates: list[ObservationCandidate] = []
        for item in self.list_candidates(limit=limit):
            quality = ObservationQuality(item.effective_quality)
            candidates.append(
                ObservationCandidate(
                    instrument_id=item.instrument_id,
                    observed_at=datetime.fromisoformat(item.observed_at_utc),
                    acquired_at=datetime.fromisoformat(item.acquired_at_utc),
                    close=Decimal(item.close),
                    currency=item.currency,
                    source_id=item.source_id,
                    quality=quality,
                )
            )
        return tuple(candidates)

    def review_observation_from_file(
        self,
        observation_id: str,
        *,
        decision: ObservationReviewDecision,
        reviewer_label: str,
        evidence_file: Path,
        notes: str,
        reviewed_at: datetime | None = None,
    ) -> ObservationReviewResult:
        """Archive a user-selected evidence file, hash it, and record the review."""

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
        evidence_directory = documents_directory / "ObservationReviewEvidence"
        evidence_directory.mkdir(parents=True, exist_ok=True)
        resolved_directory = evidence_directory.resolve()
        if not resolved_directory.is_relative_to(data_root):
            raise ValueError("the observation evidence archive resolves outside RFinance storage")

        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", source_path.name)[:120] or "evidence"
        review_file_id = str(uuid4())
        destination_name = f"{review_file_id}_{safe_name}"
        destination_path = resolved_directory / destination_name
        temporary_path = resolved_directory / f".{destination_name}.part"

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
            return self.review_observation(
                observation_id,
                decision=decision,
                reviewer_label=reviewer_label,
                evidence_reference=destination_path.relative_to(data_root).as_posix(),
                evidence_sha256=digest.hexdigest(),
                notes=notes,
                reviewed_at=reviewed_at,
            )
        except Exception:
            temporary_path.unlink(missing_ok=True)
            destination_path.unlink(missing_ok=True)
            raise

    def review_observation(
        self,
        observation_id: str,
        *,
        decision: ObservationReviewDecision,
        reviewer_label: str,
        evidence_reference: str,
        evidence_sha256: str,
        notes: str,
        reviewed_at: datetime | None = None,
    ) -> ObservationReviewResult:
        """Append a review decision after checking identity, policy and evidence gates."""

        if not isinstance(decision, ObservationReviewDecision):
            raise TypeError("decision must be an explicit ObservationReviewDecision")
        normalized_id = _text(observation_id, "observation_id", maximum=36)
        normalized_reviewer = _text(reviewer_label, "reviewer_label", maximum=256)
        normalized_reference = _text(evidence_reference, "evidence_reference", maximum=1024)
        normalized_digest = _digest(evidence_sha256)
        normalized_notes = _text(notes, "notes", maximum=2048)

        review_time = reviewed_at or datetime.now(UTC)
        if review_time.tzinfo is None or review_time.utcoffset() is None:
            raise ValueError("reviewed_at must be timezone-aware")
        reviewed_at_utc = review_time.astimezone(UTC).isoformat()
        review_id = str(uuid4())

        with self._sessions.begin() as session:
            observation = session.get(MarketObservationRecord, normalized_id)
            if observation is None:
                raise ValueError("observation must exist before it can be reviewed")
            previous_quality = self._effective_quality(session, normalized_id)

            if decision is ObservationReviewDecision.VERIFIED:
                if previous_quality == ObservationReviewDecision.VERIFIED.value:
                    raise ValueError("observation is already verified")
                if observation.quality_status != "UNVERIFIED":
                    raise ValueError(
                        "only a raw UNVERIFIED observation can be promoted to VERIFIED"
                    )
                instrument = session.get(InstrumentRegistryRecord, observation.instrument_id)
                if instrument is None or instrument.verification_status != "VERIFIED":
                    raise ValueError(
                        "instrument identity must be VERIFIED before a price can be verified"
                    )
                source = session.get(SourceRegistryRecord, observation.source_id)
                if source is None:
                    raise ValueError("observation source is missing from the source registry")
                try:
                    policy_status = SourcePolicyStatus(source.policy_status)
                except ValueError as error:
                    raise ValueError("observation source has an unknown policy status") from error
                if policy_status in (SourcePolicyStatus.BLOCKED, SourcePolicyStatus.RESTRICTED):
                    raise ValueError("source policy does not permit price verification")

            reviewed_metadata_json = json.dumps(
                {
                    "observed_at_utc": observation.observed_at_utc,
                    "acquired_at_utc": observation.acquired_at_utc,
                    "close": observation.close,
                    "currency": observation.currency,
                    "source_id": observation.source_id,
                    "batch_id": observation.batch_id,
                },
                sort_keys=True,
            )
            session.add(
                ObservationReviewEventRecord(
                    review_id=review_id,
                    observation_id=normalized_id,
                    instrument_id=observation.instrument_id,
                    source_id=observation.source_id,
                    previous_quality=previous_quality,
                    decision=decision.value,
                    reviewed_at_utc=reviewed_at_utc,
                    reviewer_label=normalized_reviewer,
                    evidence_reference=normalized_reference,
                    evidence_sha256=normalized_digest,
                    notes=normalized_notes,
                    reviewed_metadata_json=reviewed_metadata_json,
                )
            )

        return ObservationReviewResult(
            observation_id=normalized_id,
            previous_quality=previous_quality,
            decision=decision.value,
            review_id=review_id,
            reviewed_at_utc=reviewed_at_utc,
            evidence_reference=normalized_reference,
            evidence_sha256=normalized_digest,
        )
