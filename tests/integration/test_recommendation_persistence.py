# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy

from rfinance.analysis.fundamental.metrics import (
    DEBT_TO_EQUITY,
    NET_MARGIN,
    PRICE_TO_EARNINGS,
    RETURN_ON_EQUITY,
    REVENUE_GROWTH,
    ComputedMetric,
    MetricStatus,
)
from rfinance.application.recommendations import RecommendationService
from rfinance.domain.recommendations.screening import (
    EvidenceItem,
    EvidenceKind,
    RecommendationAction,
    RiskFlag,
    ScreeningInput,
)
from rfinance.storage.database import Database
from rfinance.storage.models.recommendation import RecommendationRecord

AS_OF = datetime(2026, 11, 22, 10, tzinfo=UTC)


def make_candidate(**overrides: object) -> ScreeningInput:
    metrics = tuple(
        ComputedMetric(
            name=name,
            value=value,
            status=MetricStatus.OK,
            formula="test",
            inputs=(("input", "1"),),
        )
        for name, value in (
            (REVENUE_GROWTH, Decimal("0.20")),
            (NET_MARGIN, Decimal("0.15")),
            (RETURN_ON_EQUITY, Decimal("0.18")),
            (DEBT_TO_EQUITY, Decimal("0.40")),
            (PRICE_TO_EARNINGS, Decimal("12")),
        )
    )
    evidence = (
        EvidenceItem(
            evidence_id="fin-1",
            kind=EvidenceKind.FUNDAMENTAL_METRIC,
            reference="report.pdf",
            quality="VERIFIED",
            observed_at=AS_OF,
            summary="Audited report",
        ),
    )
    values: dict[str, object] = {
        "instrument_id": "IDX:BBCA",
        "as_of": AS_OF,
        "currency": "IDR",
        "metrics": metrics,
        "price_observation_age_days": 2,
        "price_quality": "VERIFIED",
        "price_evidence_id": "price-1",
        "dividend_evidence_ids": ("div-1",),
        "evidence": evidence,
    }
    values.update(overrides)
    return ScreeningInput(**values)  # type: ignore[arg-type]


def test_evaluate_persists_and_reconstructs_evidence_linked_result(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "recommendations.sqlite3")
    database.upgrade()
    service = RecommendationService(database.sessions)

    result = service.evaluate(make_candidate(), generated_at=AS_OF)

    assert result.action is RecommendationAction.BUY_CANDIDATE
    recent = service.recent()
    assert len(recent) == 1
    stored = recent[0]
    assert stored.action == "BUY_CANDIDATE"
    assert stored.instrument_id == "IDX:BBCA"
    assert stored.evidence_ids == ("fin-1", "price-1", "div-1")
    assert stored.risk_flags == ()
    assert stored.confidence_level == result.confidence_level
    assert stored.methodology_version == "screening-deterministic-v1"

    reconstructed = service.get(stored.recommendation_id)
    assert reconstructed is not None
    assert reconstructed.generated_at == AS_OF
    assert reconstructed.invalidation_conditions == result.invalidation_conditions
    assert reconstructed.fundamental_assessment == result.fundamental_assessment
    database.close()


def test_recommendation_rows_are_append_only(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "recommendations.sqlite3")
    database.upgrade()
    service = RecommendationService(database.sessions)
    service.evaluate(make_candidate(), generated_at=AS_OF)

    with database.sessions.begin() as session:
        record = session.scalar(sqlalchemy.select(RecommendationRecord))
        assert record is not None
        assert json.loads(record.evidence_ids_json) == ["fin-1", "price-1", "div-1"]

    with pytest.raises(sqlalchemy.exc.IntegrityError), database.sessions.begin() as session:
        record = session.scalar(sqlalchemy.select(RecommendationRecord))
        assert record is not None
        record.action = "AVOID"
    with pytest.raises(sqlalchemy.exc.IntegrityError), database.sessions.begin() as session:
        record = session.scalar(sqlalchemy.select(RecommendationRecord))
        assert record is not None
        session.delete(record)
    database.close()


def test_blocked_recommendation_persists_risk_flags(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "recommendations.sqlite3")
    database.upgrade()
    service = RecommendationService(database.sessions)

    result = service.evaluate(
        make_candidate(price_observation_age_days=30, portfolio_drawdown=Decimal("0.20")),
        generated_at=AS_OF,
    )

    assert result.action is RecommendationAction.AVOID
    assert RiskFlag.STALE_PRICE in result.risk_flags
    assert RiskFlag.CRITICAL_DRAWDOWN in result.risk_flags
    stored = service.recent()[0]
    assert set(stored.risk_flags) == {"STALE_PRICE", "CRITICAL_DRAWDOWN"}
    database.close()
