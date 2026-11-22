# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Dividend event recording, evidence-backed review, calendar and analytics."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

from sqlalchemy import select

from rfinance.analysis.dividend import analytics as dividend_analytics
from rfinance.data.contracts import (
    CASH_DIVIDEND_TYPES,
    OBSERVED_DIVIDEND_STATUSES,
    DataQualityStatus,
    DividendEventContract,
    DividendEventStatus,
)
from rfinance.domain.eligibility.observation import SourcePolicyStatus
from rfinance.storage.models.data_ingestion import SourceRegistryRecord
from rfinance.storage.models.dividend import DividendEventRecord, DividendReviewEventRecord
from rfinance.storage.models.instrument_registry import InstrumentRegistryRecord

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session, sessionmaker

    from rfinance.analysis.dividend.analytics import DividendConsistency, LabeledYield

_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
MAX_REVIEW_EVIDENCE_BYTES = 25 * 1024 * 1024
_COPY_CHUNK_BYTES = 1024 * 1024


class DividendReviewDecision(StrEnum):
    """Explicit operator outcomes. There is deliberately no automatic or AI outcome."""

    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class DividendRecordResult:
    event_id: str
    instrument_id: str
    source_id: str
    source_label: str
    raw_quality: str
    event_status: str


@dataclass(frozen=True, slots=True)
class DividendEventCandidate:
    event_id: str
    event_key: str
    instrument_id: str
    source_id: str
    source_label: str
    dividend_type: str
    event_status: str
    amount_per_share: Decimal | None
    currency: str
    ex_date: date
    cum_date: date | None
    record_date: date | None
    payment_date: date | None
    raw_quality: str
    effective_quality: str
    acquired_at_utc: str
    unit: str


@dataclass(frozen=True, slots=True)
class DividendReviewResult:
    event_id: str
    previous_quality: str
    decision: str
    review_id: str
    reviewed_at_utc: str
    evidence_reference: str
    evidence_sha256: str


@dataclass(frozen=True, slots=True)
class DividendReviewHistoryItem:
    review_id: str
    event_id: str
    previous_quality: str
    decision: str
    reviewed_at_utc: str
    reviewer_label: str
    evidence_reference: str
    evidence_sha256: str
    notes: str


@dataclass(frozen=True, slots=True)
class DividendCalendarEntry:
    event_id: str
    instrument_id: str
    event_date: date
    date_kind: Literal["EX_DATE", "PAYMENT_DATE"]
    dividend_type: str
    event_status: str
    amount_per_share: Decimal | None
    currency: str
    effective_quality: str
    source_label: str
    is_confirmed_cash: bool
    is_estimate: bool


@dataclass(frozen=True, slots=True)
class DividendAnalyticsReport:
    instrument_id: str
    as_of: date
    currency: str
    window_days: int
    trailing_dividend_per_share: Decimal | None
    trailing_yield: LabeledYield | None
    forward_yield: LabeledYield | None
    withholding_rate: Decimal | None
    net_trailing_per_share: Decimal | None
    consistency: DividendConsistency
    annual_dividends: dict[int, Decimal]
    verified_cash_event_count: int
    methodology_version: str = dividend_analytics.FORMULA_VERSION


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


def _parse_date(value: str, name: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"stored {name} is not an ISO calendar date") from error


def _optional_date(value: str | None, name: str) -> date | None:
    return None if value is None else _parse_date(value, name)


def _decimal(value: str | None, name: str) -> Decimal | None:
    if value is None:
        return None
    try:
        amount = Decimal(value)
    except Exception as error:
        raise ValueError(f"stored {name} is not a valid decimal amount") from error
    if not amount.is_finite() or amount <= 0:
        raise ValueError(f"stored {name} must be finite and positive")
    return amount


def _latest_decisions(session: Session) -> dict[str, str]:
    events = session.scalars(
        select(DividendReviewEventRecord).order_by(
            DividendReviewEventRecord.event_id,
            DividendReviewEventRecord.reviewed_at_utc.desc(),
            DividendReviewEventRecord.review_id.desc(),
        )
    ).all()
    latest: dict[str, str] = {}
    for event in events:
        latest.setdefault(event.event_id, event.decision)
    return latest


class DividendEventService:
    """Record and review dividend events without ever inventing cash receipts."""

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

    # -- Ingestion ---------------------------------------------------------

    @staticmethod
    def _ensure_manual_source(session: Session, label: str) -> str:
        """Find or create the local MANUAL source inside an active transaction."""

        source_name = _text(label, "source_label", maximum=256)
        existing = session.scalar(
            select(SourceRegistryRecord.source_id).where(
                SourceRegistryRecord.display_name == source_name,
                SourceRegistryRecord.access_method == "MANUAL",
            )
        )
        if existing is not None:
            return existing
        source_id = str(uuid4())
        session.add(
            SourceRegistryRecord(
                source_id=source_id,
                display_name=source_name,
                access_method="MANUAL",
                policy_status="UNREVIEWED",
                description="User-supplied dividend document entered into the local ledger.",
                terms_url=None,
                reviewed_at_utc=None,
                automated_access_allowed=False,
                redistribution_allowed=False,
                created_at_utc=datetime.now(UTC).isoformat(),
            )
        )
        return source_id

    def register_manual_source(self, label: str) -> str:
        """Find or create the local MANUAL source used for user-supplied documents."""

        with self._sessions.begin() as session:
            return self._ensure_manual_source(session, label)

    def record_event(
        self,
        contract: DividendEventContract,
        *,
        recorded_at: datetime | None = None,
    ) -> DividendRecordResult:
        """Append one raw dividend event; ingestion quality is never promoted."""

        if not isinstance(contract, DividendEventContract):
            raise TypeError("contract must be a DividendEventContract")
        recorded_time = recorded_at or datetime.now(UTC)
        if recorded_time.tzinfo is None or recorded_time.utcoffset() is None:
            raise ValueError("recorded_at must be timezone-aware")
        created_at_utc = recorded_time.astimezone(UTC).isoformat()

        with self._sessions.begin() as session:
            source_id = self._ensure_manual_source(session, contract.source_label)
            instrument = session.get(InstrumentRegistryRecord, contract.instrument_id)
            if instrument is None:
                raise ValueError("instrument_id must exist in the local instrument registry")
            event_key = _text(contract.event_key, "event_key", maximum=128)
            duplicate = session.scalar(
                select(DividendEventRecord.event_id).where(
                    DividendEventRecord.source_id == source_id,
                    DividendEventRecord.event_key == event_key,
                )
            )
            if duplicate is not None:
                raise ValueError("a dividend event with this source and key already exists")

            event_id = str(uuid4())
            session.add(
                DividendEventRecord(
                    event_id=event_id,
                    event_key=event_key,
                    instrument_id=contract.instrument_id,
                    source_id=source_id,
                    dividend_type=contract.dividend_type.value,
                    event_status=contract.event_status.value,
                    amount_per_share=(
                        None
                        if contract.amount_per_share is None
                        else format(contract.amount_per_share, "f")
                    ),
                    currency=contract.currency,
                    ex_date=contract.ex_date.isoformat(),
                    cum_date=None if contract.cum_date is None else contract.cum_date.isoformat(),
                    record_date=(
                        None if contract.record_date is None else contract.record_date.isoformat()
                    ),
                    payment_date=(
                        None if contract.payment_date is None else contract.payment_date.isoformat()
                    ),
                    quality_status=contract.quality_status.value,
                    acquired_at_utc=contract.acquired_at.astimezone(UTC).isoformat(),
                    announced_at_utc=(
                        None
                        if contract.announced_at is None
                        else contract.announced_at.astimezone(UTC).isoformat()
                    ),
                    reporting_period_start=(
                        None
                        if contract.reporting_period_start is None
                        else contract.reporting_period_start.isoformat()
                    ),
                    reporting_period_end=(
                        None
                        if contract.reporting_period_end is None
                        else contract.reporting_period_end.isoformat()
                    ),
                    source_document_ref=contract.source_document_ref,
                    original_value=contract.original_value,
                    unit=contract.unit,
                    notes=contract.notes,
                    transformation_version=contract.transformation_version,
                    created_at_utc=created_at_utc,
                )
            )

        return DividendRecordResult(
            event_id=event_id,
            instrument_id=contract.instrument_id,
            source_id=source_id,
            source_label=contract.source_label,
            raw_quality=contract.quality_status.value,
            event_status=contract.event_status.value,
        )

    # -- Queries -----------------------------------------------------------

    def effective_quality(self, event_id: str) -> str:
        normalized_id = _text(event_id, "event_id", maximum=36)
        with self._sessions() as session:
            return self._effective_quality(session, normalized_id)

    def _effective_quality(self, session: Session, event_id: str) -> str:
        event = session.get(DividendEventRecord, event_id)
        if event is None:
            raise ValueError("dividend event must exist before it can be reviewed")
        latest = session.scalar(
            select(DividendReviewEventRecord.decision)
            .where(DividendReviewEventRecord.event_id == event_id)
            .order_by(
                DividendReviewEventRecord.reviewed_at_utc.desc(),
                DividendReviewEventRecord.review_id.desc(),
            )
            .limit(1)
        )
        return latest if latest is not None else event.quality_status

    def list_events(self, *, limit: int = 500) -> tuple[DividendEventCandidate, ...]:
        """Return recent events with raw and effective quality side by side."""

        if limit <= 0 or limit > 2_000:
            raise ValueError("limit must be between 1 and 2000")
        with self._sessions() as session:
            latest = _latest_decisions(session)
            rows = session.execute(
                select(DividendEventRecord, SourceRegistryRecord.display_name)
                .join(
                    SourceRegistryRecord,
                    SourceRegistryRecord.source_id == DividendEventRecord.source_id,
                )
                .order_by(
                    DividendEventRecord.ex_date.desc(),
                    DividendEventRecord.event_id.desc(),
                )
                .limit(limit)
            ).all()
        return tuple(
            DividendEventCandidate(
                event_id=record.event_id,
                event_key=record.event_key,
                instrument_id=record.instrument_id,
                source_id=record.source_id,
                source_label=source_label,
                dividend_type=record.dividend_type,
                event_status=record.event_status,
                amount_per_share=_decimal(record.amount_per_share, "amount_per_share"),
                currency=record.currency,
                ex_date=_parse_date(record.ex_date, "ex_date"),
                cum_date=_optional_date(record.cum_date, "cum_date"),
                record_date=_optional_date(record.record_date, "record_date"),
                payment_date=_optional_date(record.payment_date, "payment_date"),
                raw_quality=record.quality_status,
                effective_quality=latest.get(record.event_id, record.quality_status),
                acquired_at_utc=record.acquired_at_utc,
                unit=record.unit,
            )
            for record, source_label in rows
        )

    def review_history(
        self, event_id: str, *, limit: int = 100
    ) -> tuple[DividendReviewHistoryItem, ...]:
        normalized_id = _text(event_id, "event_id", maximum=36)
        if limit <= 0 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        with self._sessions() as session:
            records = session.scalars(
                select(DividendReviewEventRecord)
                .where(DividendReviewEventRecord.event_id == normalized_id)
                .order_by(
                    DividendReviewEventRecord.reviewed_at_utc.desc(),
                    DividendReviewEventRecord.review_id.desc(),
                )
                .limit(limit)
            ).all()
        return tuple(
            DividendReviewHistoryItem(
                review_id=record.review_id,
                event_id=record.event_id,
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

    def calendar(
        self,
        *,
        start: date,
        end: date,
        instrument_id: str | None = None,
    ) -> tuple[DividendCalendarEntry, ...]:
        """Return dated events in a window, with estimate/confirmation labels.

        Both ex-dates and payment dates are included so the same event may
        appear twice on different dates. Nothing here is a confirmed receipt.
        """

        if not isinstance(start, date) or not isinstance(end, date):
            raise ValueError("start and end must be calendar dates")
        if end < start:
            raise ValueError("end cannot precede start")

        entries: list[DividendCalendarEntry] = []
        for candidate in self.list_events(limit=2_000):
            if instrument_id is not None and candidate.instrument_id != instrument_id:
                continue
            confirmed = (
                candidate.effective_quality == DataQualityStatus.VERIFIED.value
                and candidate.event_status in OBSERVED_DIVIDEND_STATUSES
                and candidate.dividend_type in {item.value for item in CASH_DIVIDEND_TYPES}
            )
            is_estimate = candidate.event_status in {
                DividendEventStatus.ESTIMATED.value,
                DividendEventStatus.SIMULATED.value,
            }
            dated_events: tuple[tuple[date | None, Literal["EX_DATE", "PAYMENT_DATE"]], ...] = (
                (candidate.ex_date, "EX_DATE"),
                (candidate.payment_date, "PAYMENT_DATE"),
            )
            for event_date, kind in dated_events:
                if event_date is None or not start <= event_date <= end:
                    continue
                entries.append(
                    DividendCalendarEntry(
                        event_id=candidate.event_id,
                        instrument_id=candidate.instrument_id,
                        event_date=event_date,
                        date_kind=kind,
                        dividend_type=candidate.dividend_type,
                        event_status=candidate.event_status,
                        amount_per_share=candidate.amount_per_share,
                        currency=candidate.currency,
                        effective_quality=candidate.effective_quality,
                        source_label=candidate.source_label,
                        is_confirmed_cash=confirmed,
                        is_estimate=is_estimate,
                    )
                )
        ordered = sorted(
            entries,
            key=lambda item: (item.event_date, item.event_id, item.date_kind),
        )
        return tuple(ordered)

    def analytics(
        self,
        *,
        instrument_id: str,
        as_of: date,
        currency: str,
        price: Decimal | None = None,
        estimated_annual_dividend: Decimal | None = None,
        withholding_rate: Decimal | None = None,
        window_days: int = 365,
    ) -> DividendAnalyticsReport:
        """Compute labelled analytics from verified, observed cash events only."""

        if not isinstance(as_of, date):
            raise ValueError("as_of must be a calendar date")
        if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
            raise ValueError("currency must be a three-letter uppercase code")
        if price is not None and (not isinstance(price, Decimal) or not price.is_finite()):
            raise ValueError("price must be a finite decimal.Decimal")
        if window_days <= 0 or isinstance(window_days, bool):
            raise ValueError("window_days must be a positive integer")

        records: list[dividend_analytics.DividendRecord] = []
        annual: dict[int, Decimal] = {}
        verified_count = 0
        for candidate in self.list_events(limit=2_000):
            if candidate.instrument_id != instrument_id or candidate.currency != currency:
                continue
            if candidate.effective_quality != DataQualityStatus.VERIFIED.value:
                continue
            if candidate.event_status not in OBSERVED_DIVIDEND_STATUSES:
                continue
            if candidate.dividend_type not in {item.value for item in CASH_DIVIDEND_TYPES}:
                continue
            if candidate.amount_per_share is None:
                continue
            verified_count += 1
            records.append(
                dividend_analytics.DividendRecord(
                    event_id=candidate.event_id,
                    amount_per_share=candidate.amount_per_share,
                    ex_date=candidate.ex_date,
                    currency=candidate.currency,
                    dividend_type=dividend_analytics.DividendType(candidate.dividend_type),
                    quality=dividend_analytics.DividendQuality.VERIFIED,
                    source_id=candidate.source_id,
                )
            )
            year = candidate.ex_date.year
            annual[year] = annual.get(year, Decimal(0)) + candidate.amount_per_share

        trailing = dividend_analytics.trailing_dividend_per_share(
            records,
            as_of=as_of,
            currency=currency,
            window_days=window_days,
        )
        trailing_yield = (
            None
            if trailing is None or price is None
            else dividend_analytics.trailing_yield(
                records,
                as_of=as_of,
                currency=currency,
                price=price,
                window_days=window_days,
            )
        )
        forward_yield = (
            None
            if estimated_annual_dividend is None or price is None
            else dividend_analytics.forward_yield(estimated_annual_dividend, price)
        )
        net_trailing = (
            None
            if trailing is None
            else dividend_analytics.net_dividend_amount(trailing, withholding_rate)
        )
        return DividendAnalyticsReport(
            instrument_id=instrument_id,
            as_of=as_of,
            currency=currency,
            window_days=window_days,
            trailing_dividend_per_share=trailing,
            trailing_yield=trailing_yield,
            forward_yield=forward_yield,
            withholding_rate=withholding_rate,
            net_trailing_per_share=net_trailing,
            consistency=dividend_analytics.dividend_consistency(annual),
            annual_dividends=annual,
            verified_cash_event_count=verified_count,
        )

    # -- Evidence-backed review -------------------------------------------

    def review_event_from_file(
        self,
        event_id: str,
        *,
        decision: DividendReviewDecision,
        reviewer_label: str,
        evidence_file: Path,
        notes: str,
        reviewed_at: datetime | None = None,
    ) -> DividendReviewResult:
        """Archive selected evidence, hash it, and append a review decision."""

        if self._data_directory is None:
            raise RuntimeError("a persistent RFinance data directory is required for review")
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
        documents = data_root / "Documents"
        documents.mkdir(parents=True, exist_ok=True)
        if not documents.resolve().is_relative_to(data_root):
            raise ValueError("the Documents directory resolves outside RFinance data storage")
        evidence_dir = documents / "DividendReviewEvidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        resolved_dir = evidence_dir.resolve()
        if not resolved_dir.is_relative_to(data_root):
            raise ValueError("the dividend evidence archive resolves outside RFinance storage")

        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", source_path.name)[:120] or "evidence"
        destination_name = f"{uuid4()}_{safe_name}"
        destination = resolved_dir / destination_name
        temporary = resolved_dir / f".{destination_name}.part"

        digest = hashlib.sha256()
        copied = 0
        try:
            with source_path.open("rb") as source, temporary.open("xb") as target:
                while chunk := source.read(_COPY_CHUNK_BYTES):
                    copied += len(chunk)
                    if copied > self._max_evidence_bytes:
                        raise ValueError("evidence file grew beyond the configured size limit")
                    digest.update(chunk)
                    target.write(chunk)
                target.flush()
                os.fsync(target.fileno())
            temporary.replace(destination)
            return self.review_event(
                event_id,
                decision=decision,
                reviewer_label=reviewer_label,
                evidence_reference=destination.relative_to(data_root).as_posix(),
                evidence_sha256=digest.hexdigest(),
                notes=notes,
                reviewed_at=reviewed_at,
            )
        except Exception:
            temporary.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            raise

    def review_event(
        self,
        event_id: str,
        *,
        decision: DividendReviewDecision,
        reviewer_label: str,
        evidence_reference: str,
        evidence_sha256: str,
        notes: str,
        reviewed_at: datetime | None = None,
    ) -> DividendReviewResult:
        """Append a review after checking evidence and source-policy gates."""

        if not isinstance(decision, DividendReviewDecision):
            raise TypeError("decision must be an explicit DividendReviewDecision")
        normalized_id = _text(event_id, "event_id", maximum=36)
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
            event = session.get(DividendEventRecord, normalized_id)
            if event is None:
                raise ValueError("dividend event must exist before it can be reviewed")
            previous_quality = self._effective_quality(session, normalized_id)

            source = session.get(SourceRegistryRecord, event.source_id)
            if source is None:
                raise ValueError("dividend source is missing from the source registry")
            try:
                policy = SourcePolicyStatus(source.policy_status)
            except ValueError as error:
                raise ValueError("dividend source has an unknown policy status") from error

            if decision is DividendReviewDecision.VERIFIED:
                if previous_quality == DividendReviewDecision.VERIFIED.value:
                    raise ValueError("dividend event is already verified")
                if event.quality_status != DataQualityStatus.UNVERIFIED.value:
                    raise ValueError(
                        "only a raw UNVERIFIED dividend event can be promoted to VERIFIED"
                    )
                instrument = session.get(InstrumentRegistryRecord, event.instrument_id)
                if instrument is None or instrument.verification_status != "VERIFIED":
                    raise ValueError(
                        "instrument identity must be VERIFIED before a dividend can be verified"
                    )
                if policy in (SourcePolicyStatus.BLOCKED, SourcePolicyStatus.RESTRICTED):
                    raise ValueError("source policy does not permit dividend verification")
                if event.event_status in {
                    DividendEventStatus.ESTIMATED.value,
                    DividendEventStatus.SIMULATED.value,
                    DividendEventStatus.CANCELLED.value,
                }:
                    raise ValueError("an estimate, simulation or cancellation cannot be promoted")

            metadata = json.dumps(
                {
                    "event_key": event.event_key,
                    "instrument_id": event.instrument_id,
                    "source_id": event.source_id,
                    "dividend_type": event.dividend_type,
                    "event_status": event.event_status,
                    "amount_per_share": event.amount_per_share,
                    "currency": event.currency,
                    "ex_date": event.ex_date,
                    "payment_date": event.payment_date,
                },
                sort_keys=True,
            )
            session.add(
                DividendReviewEventRecord(
                    review_id=review_id,
                    event_id=normalized_id,
                    previous_quality=previous_quality,
                    decision=decision.value,
                    reviewed_at_utc=reviewed_at_utc,
                    reviewer_label=normalized_reviewer,
                    evidence_reference=normalized_reference,
                    evidence_sha256=normalized_digest,
                    notes=normalized_notes,
                    reviewed_metadata_json=metadata,
                )
            )

        return DividendReviewResult(
            event_id=normalized_id,
            previous_quality=previous_quality,
            decision=decision.value,
            review_id=review_id,
            reviewed_at_utc=reviewed_at_utc,
            evidence_reference=normalized_reference,
            evidence_sha256=normalized_digest,
        )
