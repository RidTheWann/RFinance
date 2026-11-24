# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Evidence-backed recording and review of financial statement metrics."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select

from rfinance.data.contracts import FinancialMetricContract, ReportingBasis
from rfinance.storage.models.data_ingestion import SourceRegistryRecord
from rfinance.storage.models.financial_statement import (
    FinancialMetricRecord,
    FinancialMetricReviewRecord,
)
from rfinance.storage.models.instrument_registry import InstrumentRegistryRecord

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session, sessionmaker

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
MAX_EVIDENCE_BYTES = 25 * 1024 * 1024
_CHUNK = 1024 * 1024


class FinancialReviewDecision(StrEnum):
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class FinancialMetricRecordResult:
    metric_id: str
    instrument_id: str
    source_id: str
    metric_name: str
    quality: str


@dataclass(frozen=True, slots=True)
class FinancialMetricCandidate:
    metric_id: str
    instrument_id: str
    source_id: str
    metric_name: str
    value: Decimal
    unit: str
    currency: str
    period_start: date
    period_end: date
    reporting_basis: ReportingBasis
    raw_quality: str
    effective_quality: str


@dataclass(frozen=True, slots=True)
class FinancialReviewResult:
    metric_id: str
    decision: str
    review_id: str
    evidence_reference: str
    evidence_sha256: str


def _text(value: object, name: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{name} must be a non-empty string of at most {maximum} characters")
    return value.strip()


def _digest(value: object) -> str:
    normalized = _text(value, "evidence_sha256", 64).lower()
    if not _DIGEST.fullmatch(normalized):
        raise ValueError("evidence_sha256 must be a 64-character hex digest")
    return normalized


def _latest_decisions(session: Session) -> dict[str, str]:
    events = session.scalars(
        select(FinancialMetricReviewRecord).order_by(
            FinancialMetricReviewRecord.metric_id,
            FinancialMetricReviewRecord.reviewed_at_utc.desc(),
            FinancialMetricReviewRecord.review_id.desc(),
        )
    ).all()
    latest: dict[str, str] = {}
    for event in events:
        latest.setdefault(event.metric_id, event.decision)
    return latest


class FinancialStatementService:
    """Record raw reported metrics and promote them only with evidence."""

    def __init__(
        self,
        sessions: sessionmaker[Session],
        *,
        data_directory: Path | None = None,
    ) -> None:
        self._sessions = sessions
        self._data_directory = (
            None if data_directory is None else data_directory.expanduser().resolve()
        )

    @staticmethod
    def _ensure_source(session: Session, label: str) -> str:
        name = _text(label, "source_label", 256)
        existing = session.scalar(
            select(SourceRegistryRecord.source_id).where(
                SourceRegistryRecord.display_name == name,
                SourceRegistryRecord.access_method == "MANUAL",
            )
        )
        if existing is not None:
            return existing
        source_id = str(uuid4())
        session.add(
            SourceRegistryRecord(
                source_id=source_id,
                display_name=name,
                access_method="MANUAL",
                policy_status="UNREVIEWED",
                description="User-supplied financial statement document.",
                terms_url=None,
                reviewed_at_utc=None,
                automated_access_allowed=False,
                redistribution_allowed=False,
                created_at_utc=datetime.now(UTC).isoformat(),
            )
        )
        return source_id

    def record_metric(
        self,
        contract: FinancialMetricContract,
        *,
        recorded_at: datetime | None = None,
    ) -> FinancialMetricRecordResult:
        """Append one raw reported metric; ingestion never certifies truth."""

        if not isinstance(contract, FinancialMetricContract):
            raise TypeError("contract must be a FinancialMetricContract")
        moment = recorded_at or datetime.now(UTC)
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("recorded_at must be timezone-aware")
        with self._sessions.begin() as session:
            if session.get(InstrumentRegistryRecord, contract.instrument_id) is None:
                raise ValueError("instrument does not exist in the local registry")
            source_id = self._ensure_source(session, contract.source_label)
            metric_id = str(uuid4())
            session.add(
                FinancialMetricRecord(
                    metric_id=metric_id,
                    instrument_id=contract.instrument_id,
                    source_id=source_id,
                    metric_name=contract.metric_name,
                    value=format(contract.value, "f"),
                    unit=contract.unit,
                    currency=contract.currency,
                    period_start=contract.period_start.isoformat(),
                    period_end=contract.period_end.isoformat(),
                    reporting_basis=contract.reporting_basis.value,
                    quality_status=contract.quality_status.value,
                    acquired_at_utc=contract.acquired_at.astimezone(UTC).isoformat(),
                    source_document_ref=contract.source_document_ref,
                    notes=contract.notes,
                    transformation_version=contract.transformation_version,
                    created_at_utc=moment.astimezone(UTC).isoformat(),
                )
            )
        return FinancialMetricRecordResult(
            metric_id=metric_id,
            instrument_id=contract.instrument_id,
            source_id=source_id,
            metric_name=contract.metric_name,
            quality=contract.quality_status.value,
        )

    def list_metrics(self, *, limit: int = 500) -> tuple[FinancialMetricCandidate, ...]:
        if limit <= 0 or limit > 2_000:
            raise ValueError("limit must be between 1 and 2000")
        with self._sessions() as session:
            latest = _latest_decisions(session)
            records = session.scalars(
                select(FinancialMetricRecord)
                .order_by(FinancialMetricRecord.period_end.desc(), FinancialMetricRecord.metric_id)
                .limit(limit)
            ).all()
        return tuple(
            FinancialMetricCandidate(
                metric_id=record.metric_id,
                instrument_id=record.instrument_id,
                source_id=record.source_id,
                metric_name=record.metric_name,
                value=Decimal(record.value),
                unit=record.unit,
                currency=record.currency,
                period_start=date.fromisoformat(record.period_start),
                period_end=date.fromisoformat(record.period_end),
                reporting_basis=ReportingBasis(record.reporting_basis),
                raw_quality=record.quality_status,
                effective_quality=latest.get(record.metric_id, record.quality_status),
            )
            for record in records
        )

    def effective_quality(self, metric_id: str) -> str:
        with self._sessions() as session:
            return self._effective_quality(session, metric_id)

    def _effective_quality(self, session: Session, metric_id: str) -> str:
        record = session.get(FinancialMetricRecord, metric_id)
        if record is None:
            raise ValueError("financial metric does not exist")
        latest = session.scalar(
            select(FinancialMetricReviewRecord.decision)
            .where(FinancialMetricReviewRecord.metric_id == metric_id)
            .order_by(
                FinancialMetricReviewRecord.reviewed_at_utc.desc(),
                FinancialMetricReviewRecord.review_id.desc(),
            )
            .limit(1)
        )
        return latest if latest is not None else record.quality_status

    def review_metric(
        self,
        metric_id: str,
        *,
        decision: FinancialReviewDecision,
        reviewer_label: str,
        evidence_reference: str,
        evidence_sha256: str,
        notes: str,
        reviewed_at: datetime | None = None,
    ) -> FinancialReviewResult:
        if not isinstance(decision, FinancialReviewDecision):
            raise TypeError("decision must be a FinancialReviewDecision")
        reviewer = _text(reviewer_label, "reviewer_label", 256)
        reference = _text(evidence_reference, "evidence_reference", 1024)
        digest = _digest(evidence_sha256)
        note_text = _text(notes, "notes", 2048)
        moment = reviewed_at or datetime.now(UTC)
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("reviewed_at must be timezone-aware")
        reviewed_at_utc = moment.astimezone(UTC).isoformat()

        with self._sessions.begin() as session:
            record = session.get(FinancialMetricRecord, metric_id)
            if record is None:
                raise ValueError("financial metric does not exist")
            previous = self._effective_quality(session, metric_id)
            if decision is FinancialReviewDecision.VERIFIED:
                if previous != "UNVERIFIED" or record.quality_status != "UNVERIFIED":
                    raise ValueError("only a raw UNVERIFIED metric can be promoted")
                instrument = session.get(InstrumentRegistryRecord, record.instrument_id)
                if instrument is None or instrument.verification_status != "VERIFIED":
                    raise ValueError("instrument identity must be VERIFIED")
                source = session.get(SourceRegistryRecord, record.source_id)
                if source is None or source.policy_status in {"BLOCKED", "RESTRICTED"}:
                    raise ValueError("source policy does not permit metric verification")
            review_id = str(uuid4())
            session.add(
                FinancialMetricReviewRecord(
                    review_id=review_id,
                    metric_id=metric_id,
                    previous_quality=previous,
                    decision=decision.value,
                    reviewed_at_utc=reviewed_at_utc,
                    reviewer_label=reviewer,
                    evidence_reference=reference,
                    evidence_sha256=digest,
                    notes=note_text,
                )
            )
        return FinancialReviewResult(
            metric_id=metric_id,
            decision=decision.value,
            review_id=review_id,
            evidence_reference=reference,
            evidence_sha256=digest,
        )

    def review_metric_from_file(
        self,
        metric_id: str,
        *,
        decision: FinancialReviewDecision,
        reviewer_label: str,
        evidence_file: Path,
        notes: str,
        reviewed_at: datetime | None = None,
    ) -> FinancialReviewResult:
        if self._data_directory is None:
            raise RuntimeError("a persistent RFinance data directory is required")
        source_path = evidence_file.expanduser().resolve(strict=True)
        if not source_path.is_file() or source_path.stat().st_size > MAX_EVIDENCE_BYTES:
            raise ValueError("evidence file is missing or exceeds the size limit")
        directory = self._data_directory / "Documents" / "FinancialEvidence"
        directory.mkdir(parents=True, exist_ok=True)
        resolved = directory.resolve()
        if not resolved.is_relative_to(self._data_directory):
            raise ValueError("evidence archive resolves outside RFinance storage")
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", source_path.name)[:120] or "evidence"
        destination = resolved / f"{uuid4()}_{safe_name}"
        temporary = resolved / f".{destination.name}.part"
        digest = hashlib.sha256()
        try:
            with source_path.open("rb") as source, temporary.open("xb") as target:
                while chunk := source.read(_CHUNK):
                    digest.update(chunk)
                    target.write(chunk)
                target.flush()
                os.fsync(target.fileno())
            temporary.replace(destination)
            return self.review_metric(
                metric_id,
                decision=decision,
                reviewer_label=reviewer_label,
                evidence_reference=destination.relative_to(self._data_directory).as_posix(),
                evidence_sha256=digest.hexdigest(),
                notes=notes,
                reviewed_at=reviewed_at,
            )
        except Exception:
            temporary.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            raise

    def verified_inputs(
        self,
        instrument_id: str,
        *,
        as_of: datetime | None = None,
        reporting_basis: ReportingBasis | None = None,
    ) -> dict[str, Decimal]:
        """Return the newest verified value per metric name, excluding future periods.

        Candidates are never blended across reporting bases. With an explicit
        ``reporting_basis`` only that basis is eligible. Without one the most
        complete basis available wins (`ANNUAL`, then `TTM`, then `QUARTERLY`),
        so a newer quarter cannot replace an annual figure and feed a three-month
        denominator into an annual formula; within the selected basis the newest
        period wins. Callers of the persisted-fundamentals path must still declare
        the basis their formula version expects.
        """

        moment = as_of or datetime.now(UTC)
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        cutoff = moment.astimezone(UTC).date()
        basis_rank = {
            ReportingBasis.ANNUAL: 0,
            ReportingBasis.TTM: 1,
            ReportingBasis.QUARTERLY: 2,
        }
        chosen: dict[str, tuple[int, date, Decimal]] = {}
        for item in self.list_metrics(limit=2_000):
            if item.instrument_id != instrument_id or item.effective_quality != "VERIFIED":
                continue
            if item.period_end > cutoff:
                continue
            if reporting_basis is not None and item.reporting_basis is not reporting_basis:
                continue
            rank = basis_rank[item.reporting_basis]
            current = chosen.get(item.metric_name)
            if (
                current is None
                or rank < current[0]
                or (rank == current[0] and item.period_end > current[1])
            ):
                chosen[item.metric_name] = (rank, item.period_end, item.value)
        return {name: value for name, (_, _, value) in sorted(chosen.items())}
