# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Deterministic risk review with append-only events and explicit reviews."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select

from rfinance.domain.recommendations.screening import RiskControlEvidence
from rfinance.domain.risk.controls import (
    FORMULA_VERSION,
    RiskAssessment,
    RiskFinding,
    RiskPolicy,
    RiskRule,
    RiskSeverity,
    RiskSnapshot,
    evaluate_risk,
)
from rfinance.storage.models.risk_event import (
    RiskEventRecord,
    RiskReviewRecord,
    ValuationHistoryRecord,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker

    from rfinance.analysis.portfolio.valuation import ValuationResult

_BUY_SUSPENDING = frozenset(
    {
        RiskRule.ELEVATED_DRAWDOWN,
        RiskRule.CRITICAL_DRAWDOWN,
        RiskRule.SINGLE_INSTRUMENT_CONCENTRATION,
        RiskRule.SECTOR_CONCENTRATION,
        RiskRule.PROHIBITED_ACTIVITY,
    }
)
_ALLOCATION_SUSPENDING = frozenset({RiskRule.CRITICAL_DRAWDOWN, RiskRule.PROHIBITED_ACTIVITY})
ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class RiskReviewSummary:
    """An operator's explicit resolution of one risk event."""

    review_id: str
    event_id: str
    reviewer_label: str
    notes: str
    evidence_reference: str
    reviewed_at_utc: str


@dataclass(frozen=True, slots=True)
class RiskEventSummary:
    """A persisted risk event with its optional resolution."""

    event_id: str
    rule: RiskRule
    severity: RiskSeverity
    triggered_at_utc: str
    observed_value: Decimal | None
    threshold: Decimal | None
    valuation_methodology: str
    explanation: str
    evidence_reference: str
    methodology_version: str
    review: RiskReviewSummary | None = None


@dataclass(frozen=True, slots=True)
class ValuationHistorySummary:
    """A stored valuation point used for the documented drawdown series."""

    valuation_id: str
    as_of_utc: str
    currency: str
    total_value: Decimal
    is_complete: bool
    methodology_version: str


class RiskMonitoringService:
    """Evaluate risk triggers, retain evidence, and record explicit reviews."""

    def __init__(
        self,
        sessions: sessionmaker[Session],
        *,
        policy: RiskPolicy | None = None,
    ) -> None:
        self._sessions = sessions
        self._policy = RiskPolicy() if policy is None else policy

    def evaluate(
        self,
        snapshot: RiskSnapshot,
        *,
        triggered_at: datetime | None = None,
    ) -> RiskAssessment:
        """Run the engine, append new events, and apply still-unresolved events."""

        moment = triggered_at or snapshot.as_of
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("triggered_at must be timezone-aware")
        moment_utc = moment.astimezone(UTC)
        assessment = evaluate_risk(snapshot, policy=self._policy)

        with self._sessions.begin() as session:
            for finding in assessment.findings:
                event_id = _event_id(finding, moment_utc, snapshot.valuation_methodology)
                if session.get(RiskEventRecord, event_id) is None:
                    session.add(
                        _event_record(finding, event_id, moment_utc, snapshot.valuation_methodology)
                    )
            active = _active_rules(session)

        unresolved = {event.rule for event in active}
        return replace(
            assessment,
            review_required=bool(active),
            buy_candidates_suspended=bool(unresolved & _BUY_SUSPENDING),
            allocation_changes_suspended=bool(unresolved & _ALLOCATION_SUSPENDING),
        )

    def evaluate_valuation(
        self,
        valuation: ValuationResult,
        *,
        as_of: datetime | None = None,
        prohibited_activities: tuple[str, ...] = (),
    ) -> RiskAssessment:
        """Record a valuation point and evaluate risk against the stored series."""

        if as_of is None:
            as_of = datetime.fromisoformat(valuation.as_of_utc)
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        moment_utc = as_of.astimezone(UTC)
        snapshot = self._build_snapshot(valuation, moment_utc, prohibited_activities)
        return self.evaluate(snapshot, triggered_at=moment_utc)

    def _build_snapshot(
        self,
        valuation: ValuationResult,
        moment_utc: datetime,
        prohibited_activities: tuple[str, ...],
    ) -> RiskSnapshot:
        valuation_id = hashlib.sha256(
            f"{moment_utc.isoformat()}|{valuation.currency}|{valuation.methodology_version}".encode()
        ).hexdigest()[:32]
        positions = [
            {
                "instrument_id": item.instrument_id,
                "market_value": (
                    None if item.market_value is None else format(item.market_value, "f")
                ),
            }
            for item in valuation.positions
        ]
        allocation = [
            {"category": line.category.value, "deviation": format(abs(line.deviation), "f")}
            for line in valuation.allocation
        ]

        with self._sessions.begin() as session:
            if session.get(ValuationHistoryRecord, valuation_id) is None:
                session.add(
                    ValuationHistoryRecord(
                        valuation_id=valuation_id,
                        as_of_utc=moment_utc.isoformat(),
                        currency=valuation.currency,
                        total_value=format(valuation.total_value, "f"),
                        is_complete=1 if valuation.is_complete else 0,
                        methodology_version=valuation.methodology_version,
                        positions_json=json.dumps(positions, sort_keys=True),
                        allocation_json=json.dumps(allocation, sort_keys=True),
                    )
                )
            rows = session.scalars(
                select(ValuationHistoryRecord).where(
                    ValuationHistoryRecord.currency == valuation.currency
                )
            ).all()
            latest_review = session.scalars(
                select(RiskReviewRecord).order_by(RiskReviewRecord.reviewed_at_utc.desc())
            ).first()

        complete = sorted(
            (row for row in rows if row.is_complete == 1),
            key=lambda row: row.as_of_utc,
        )
        current_row = complete[-1] if complete else None
        current = Decimal(current_row.total_value) if current_row is not None else None
        peak = max(Decimal(row.total_value) for row in complete) if complete else None

        instrument_weights: dict[str, Decimal] = {}
        allocation_deviations: dict[str, Decimal] = {}
        if current is not None and current > 0:
            for item in json.loads(current_row.positions_json) if current_row else []:
                if item["market_value"] is None:
                    continue
                value = Decimal(item["market_value"])
                if value > 0:
                    instrument_weights[item["instrument_id"]] = value / current
        if current_row is not None:
            for item in json.loads(current_row.allocation_json):
                allocation_deviations[item["category"]] = Decimal(item["deviation"])

        last_reviewed_at = (
            datetime.fromisoformat(latest_review.reviewed_at_utc)
            if latest_review is not None
            else None
        )
        return RiskSnapshot(
            as_of=moment_utc,
            peak_value=peak,
            current_value=current,
            valuation_methodology=valuation.methodology_version,
            valuation_is_complete=current_row is not None,
            instrument_weights=instrument_weights,
            sector_weights={},
            allocation_deviations=allocation_deviations,
            last_reviewed_at=last_reviewed_at,
            prohibited_activities=prohibited_activities,
        )

    def active_events(self) -> tuple[RiskEventSummary, ...]:
        """Return only risk events without an explicit recorded review."""

        return tuple(item for item in self.recent_events(limit=500) if item.review is None)

    def current_drawdown(self) -> Decimal | None:
        """Peak-to-current decline from complete stored valuations, or ``None``.

        Incomplete valuation points are excluded and an unknown drawdown is
        never reported as zero. The arithmetic matches ``risk-controls-v1``.
        """

        points = sorted(
            (item for item in self.recent_valuations(limit=500) if item.is_complete),
            key=lambda item: item.as_of_utc,
        )
        if not points:
            return None
        peak = max(item.total_value for item in points)
        current = points[-1].total_value
        if peak <= ZERO:
            return None
        return max(ZERO, (peak - current) / peak)

    def screening_controls(self) -> RiskControlEvidence:
        """Persisted risk state that constrains new BUY_CANDIDATE promotion.

        Only rules that suspend buy candidates block a recommendation. A
        recorded but non-blocking review is still reported as context, and a
        critical event downgrades the result to AVOID. Active event IDs are
        retained so the recommendation can cite the exact audit records.
        """

        active = self.active_events()
        return RiskControlEvidence(
            review_required=bool(active),
            buy_candidates_suspended=any(item.rule in _BUY_SUSPENDING for item in active),
            critical=any(
                item.severity is RiskSeverity.CRITICAL or item.rule in _ALLOCATION_SUSPENDING
                for item in active
            ),
            drawdown=self.current_drawdown(),
            active_event_ids=tuple(item.event_id for item in active),
        )

    def recent_events(self, *, limit: int = 50) -> tuple[RiskEventSummary, ...]:
        """Return recent risk events with their review status, newest first."""

        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        with self._sessions() as session:
            events = session.scalars(
                select(RiskEventRecord)
                .order_by(
                    RiskEventRecord.triggered_at_utc.desc(),
                    RiskEventRecord.event_id.desc(),
                )
                .limit(limit)
            ).all()
            reviews = {
                review.event_id: review
                for review in session.scalars(select(RiskReviewRecord)).all()
            }
        return tuple(
            RiskEventSummary(
                event_id=event.event_id,
                rule=RiskRule(event.rule),
                severity=RiskSeverity(event.severity),
                triggered_at_utc=event.triggered_at_utc,
                observed_value=(
                    None if event.observed_value is None else Decimal(event.observed_value)
                ),
                threshold=None if event.threshold is None else Decimal(event.threshold),
                valuation_methodology=event.valuation_methodology,
                explanation=event.explanation,
                evidence_reference=event.evidence_reference,
                methodology_version=event.methodology_version,
                review=(
                    None
                    if event.event_id not in reviews
                    else _review_summary(reviews[event.event_id])
                ),
            )
            for event in events
        )

    def recent_valuations(self, *, limit: int = 50) -> tuple[ValuationHistorySummary, ...]:
        """Return the recorded valuation series, newest first."""

        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        with self._sessions() as session:
            rows = session.scalars(
                select(ValuationHistoryRecord)
                .order_by(ValuationHistoryRecord.as_of_utc.desc())
                .limit(limit)
            ).all()
        return tuple(
            ValuationHistorySummary(
                valuation_id=row.valuation_id,
                as_of_utc=row.as_of_utc,
                currency=row.currency,
                total_value=Decimal(row.total_value),
                is_complete=row.is_complete == 1,
                methodology_version=row.methodology_version,
            )
            for row in rows
        )

    def record_review(
        self,
        event_id: str,
        *,
        reviewer_label: str,
        notes: str,
        evidence_reference: str,
        reviewed_at: datetime | None = None,
    ) -> RiskReviewSummary:
        """Append an explicit, auditable resolution for one risk event."""

        moment = datetime.now(UTC) if reviewed_at is None else reviewed_at
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("reviewed_at must be timezone-aware")
        for name, value in (
            ("reviewer_label", reviewer_label),
            ("notes", notes),
            ("evidence_reference", evidence_reference),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must not be empty")
        with self._sessions.begin() as session:
            if session.get(RiskEventRecord, event_id) is None:
                raise ValueError("Unknown risk event")
            existing = session.scalar(
                select(RiskReviewRecord).where(RiskReviewRecord.event_id == event_id)
            )
            if existing is not None:
                raise ValueError("This risk event has already been reviewed")
            record = RiskReviewRecord(
                review_id=str(uuid4()),
                event_id=event_id,
                reviewer_label=reviewer_label.strip(),
                notes=notes.strip(),
                evidence_reference=evidence_reference.strip(),
                reviewed_at_utc=moment.astimezone(UTC).isoformat(),
            )
            session.add(record)
        return _review_summary(record)


def _event_id(finding: RiskFinding, moment: datetime, methodology: str) -> str:
    raw = (
        f"{finding.rule.value}|{finding.severity.value}|"
        f"{moment.date().isoformat()}|{methodology}|{finding.evidence_reference}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _event_record(
    finding: RiskFinding,
    event_id: str,
    moment: datetime,
    valuation_methodology: str,
) -> RiskEventRecord:
    return RiskEventRecord(
        event_id=event_id,
        rule=finding.rule.value,
        severity=finding.severity.value,
        triggered_at_utc=moment.isoformat(),
        observed_value=(
            None if finding.observed_value is None else format(finding.observed_value, "f")
        ),
        threshold=None if finding.threshold is None else format(finding.threshold, "f"),
        valuation_methodology=valuation_methodology,
        explanation=finding.explanation,
        evidence_reference=finding.evidence_reference,
        methodology_version=FORMULA_VERSION,
    )


def _review_summary(record: RiskReviewRecord) -> RiskReviewSummary:
    return RiskReviewSummary(
        review_id=record.review_id,
        event_id=record.event_id,
        reviewer_label=record.reviewer_label,
        notes=record.notes,
        evidence_reference=record.evidence_reference,
        reviewed_at_utc=record.reviewed_at_utc,
    )


def _active_rules(session: Session) -> tuple[RiskEventSummary, ...]:
    events = session.scalars(select(RiskEventRecord)).all()
    reviews = {
        review.event_id: review for review in session.scalars(select(RiskReviewRecord)).all()
    }
    return tuple(
        RiskEventSummary(
            event_id=event.event_id,
            rule=RiskRule(event.rule),
            severity=RiskSeverity(event.severity),
            triggered_at_utc=event.triggered_at_utc,
            observed_value=None,
            threshold=None,
            valuation_methodology=event.valuation_methodology,
            explanation=event.explanation,
            evidence_reference=event.evidence_reference,
            methodology_version=event.methodology_version,
            review=(
                None if event.event_id not in reviews else _review_summary(reviews[event.event_id])
            ),
        )
        for event in events
        if event.event_id not in reviews
    )
