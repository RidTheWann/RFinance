# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Risk-event persistence and review workflow integration tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from rfinance.analysis.portfolio.valuation import ValuationResult
from rfinance.application.risk_monitoring import RiskMonitoringService
from rfinance.domain.risk.controls import RiskRule, RiskSeverity, RiskSnapshot
from rfinance.storage.database import Database

if TYPE_CHECKING:
    from pathlib import Path

_TRIGGERED = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)


def _snapshot(**overrides: object) -> RiskSnapshot:
    values: dict[str, object] = {
        "as_of": _TRIGGERED,
        "peak_value": Decimal("1000000"),
        "current_value": Decimal("900000"),
        "valuation_methodology": "portfolio-valuation-v1",
        "valuation_is_complete": True,
        "instrument_weights": {},
        "sector_weights": {},
        "allocation_deviations": {},
        "last_reviewed_at": None,
    }
    values.update(overrides)
    return RiskSnapshot(**values)  # type: ignore[arg-type]


def _valuation(total: Decimal, as_of: datetime, *, complete: bool = True) -> ValuationResult:
    return ValuationResult(
        as_of_utc=as_of.isoformat(),
        currency="IDR",
        cash=total,
        market_value=Decimal("0"),
        total_value=total,
        realized_profit_loss=Decimal("0"),
        unrealized_profit_loss=Decimal("0"),
        positions=(),
        allocation=(),
        unvalued_instruments=(),
        is_complete=complete,
    )


@pytest.fixture()
def risk_database(tmp_path: Path) -> Database:
    database = Database.open(tmp_path / "db" / "risk.sqlite3")
    database.upgrade()
    yield database
    database.close()


@pytest.fixture()
def service(risk_database: Database) -> RiskMonitoringService:
    return RiskMonitoringService(risk_database.sessions)


def test_evaluate_persists_a_finding_and_reports_active_suspension(
    service: RiskMonitoringService,
) -> None:
    assessment = service.evaluate(_snapshot(), triggered_at=_TRIGGERED)

    assert assessment.buy_candidates_suspended is True
    events = service.active_events()
    assert len(events) == 1
    assert events[0].rule is RiskRule.ELEVATED_DRAWDOWN
    assert events[0].severity is RiskSeverity.WARNING
    assert events[0].observed_value == Decimal("0.10")
    assert events[0].review is None
    assert events[0].methodology_version == "risk-controls-v1"


def test_review_resolves_an_event_and_lifts_suspension(service: RiskMonitoringService) -> None:
    service.evaluate(_snapshot(), triggered_at=_TRIGGERED)
    event_id = service.active_events()[0].event_id

    review = service.record_review(
        event_id,
        reviewer_label="Portfolio operator",
        notes="Reviewed allocation and confirmed the drawdown trigger.",
        evidence_reference="Documents/RiskReview/2026-11.md",
        reviewed_at=_TRIGGERED,
    )
    assert review.event_id == event_id

    assert service.active_events() == ()
    reassessment = service.evaluate(_snapshot(), triggered_at=_TRIGGERED)
    assert reassessment.buy_candidates_suspended is False
    assert service.active_events() == ()


def test_duplicate_review_is_rejected(service: RiskMonitoringService) -> None:
    service.evaluate(_snapshot(), triggered_at=_TRIGGERED)
    event_id = service.active_events()[0].event_id
    service.record_review(
        event_id,
        reviewer_label="Operator",
        notes="First review",
        evidence_reference="doc-1",
        reviewed_at=_TRIGGERED,
    )

    with pytest.raises(ValueError, match="already been reviewed"):
        service.record_review(
            event_id,
            reviewer_label="Operator",
            notes="Second review",
            evidence_reference="doc-2",
            reviewed_at=_TRIGGERED,
        )


def test_review_requires_reviewer_notes_and_evidence(service: RiskMonitoringService) -> None:
    service.evaluate(_snapshot(), triggered_at=_TRIGGERED)
    event_id = service.active_events()[0].event_id

    with pytest.raises(ValueError, match="notes"):
        service.record_review(
            event_id,
            reviewer_label="Operator",
            notes="",
            evidence_reference="doc-1",
            reviewed_at=_TRIGGERED,
        )


def test_valuation_history_derives_peak_and_current_drawdown(
    service: RiskMonitoringService,
) -> None:
    earlier = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
    later = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)

    service.evaluate_valuation(_valuation(Decimal("1000000"), earlier), as_of=earlier)
    assessment = service.evaluate_valuation(_valuation(Decimal("900000"), later), as_of=later)

    assert assessment.drawdown == Decimal("0.10")
    events = service.active_events()
    assert [event.rule for event in events] == [RiskRule.ELEVATED_DRAWDOWN]
    assert events[0].valuation_methodology == "portfolio-valuation-v1"


def test_valuation_history_is_idempotent_for_the_same_as_of(
    service: RiskMonitoringService,
) -> None:
    moment = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
    valuation = _valuation(Decimal("900000"), moment)

    first = service.evaluate_valuation(valuation, as_of=moment)
    second = service.evaluate_valuation(valuation, as_of=moment)

    assert first.drawdown == second.drawdown
    assert first.drawdown == Decimal("0")
    assert service.recent_events() == ()
    assert len(service.recent_valuations()) == 1


def test_incomplete_valuation_does_not_enter_the_peak_series(
    service: RiskMonitoringService,
) -> None:
    earlier = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
    later = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)

    service.evaluate_valuation(
        _valuation(Decimal("9999999"), earlier, complete=False), as_of=earlier
    )
    assessment = service.evaluate_valuation(_valuation(Decimal("900000"), later), as_of=later)

    assert assessment.drawdown == Decimal("0")
    assert not any(
        event.rule in (RiskRule.ELEVATED_DRAWDOWN, RiskRule.CRITICAL_DRAWDOWN)
        for event in service.active_events()
    )


def test_risk_event_tables_are_append_only(risk_database: Database) -> None:
    service = RiskMonitoringService(risk_database.sessions)
    service.evaluate(_snapshot(), triggered_at=_TRIGGERED)
    event_id = service.active_events()[0].event_id
    service.record_review(
        event_id,
        reviewer_label="Operator",
        notes="Reviewed",
        evidence_reference="doc-1",
        reviewed_at=_TRIGGERED,
    )

    with risk_database.sessions.begin() as session, pytest.raises(IntegrityError):
        session.execute(text("UPDATE risk_events SET severity = 'INFO'"))
    with risk_database.sessions.begin() as session, pytest.raises(IntegrityError):
        session.execute(text("DELETE FROM risk_reviews"))
