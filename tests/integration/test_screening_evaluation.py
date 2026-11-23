# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Integration tests for guided screening evidence assembly."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from rfinance.application.dividend_events import DividendEventService, DividendReviewDecision
from rfinance.application.observation_review import ObservationReviewService
from rfinance.application.recommendations import RecommendationService
from rfinance.application.risk_monitoring import RiskMonitoringService
from rfinance.application.screening_evaluation import ScreeningEvaluationService
from rfinance.data.contracts import (
    DividendEventContract,
    DividendEventStatus,
    DividendType,
)
from rfinance.domain.recommendations.screening import RecommendationAction, RiskFlag
from rfinance.domain.risk.controls import RiskSnapshot
from rfinance.storage.database import Database
from rfinance.storage.models.data_ingestion import (
    DataImportBatchRecord,
    MarketObservationRecord,
    SourceRegistryRecord,
)
from rfinance.storage.models.instrument_registry import InstrumentRegistryRecord

AS_OF = datetime(2026, 11, 22, 12, tzinfo=UTC)
HEALTHY = {
    "revenue": Decimal("1000"),
    "revenue_previous": Decimal("800"),
    "net_income": Decimal("150"),
    "gross_profit": Decimal("400"),
    "operating_income": Decimal("200"),
    "average_equity": Decimal("750"),
    "earnings_per_share": Decimal("5"),
    "effective_tax_rate": Decimal("0.2"),
    "total_debt": Decimal("300"),
    "total_equity": Decimal("750"),
    "cash_and_equivalents": Decimal("100"),
    "price": Decimal("50"),
}


def seed(
    database: Database,
    *,
    instrument_status: str = "VERIFIED",
    policy: str = "APPROVED",
    observed_days_ago: int = 2,
) -> None:
    moment = AS_OF.isoformat()
    with database.sessions.begin() as session:
        session.add(
            SourceRegistryRecord(
                source_id="src-1",
                display_name="Official issuer feed",
                access_method="OFFICIAL_DOWNLOAD",
                policy_status=policy,
                description=None,
                terms_url="https://example.test/terms",
                reviewed_at_utc=moment,
                automated_access_allowed=False,
                redistribution_allowed=False,
                created_at_utc=moment,
            )
        )
        session.flush()
        session.add(
            InstrumentRegistryRecord(
                instrument_id="IDX:BBCA",
                verification_status=instrument_status,
                created_at_utc=moment,
                updated_at_utc=moment,
            )
        )
        session.flush()
        session.add(
            DataImportBatchRecord(
                batch_id="batch-1",
                source_id="src-1",
                original_filename="prices.csv",
                file_sha256="b" * 64,
                document_relative_path="Documents/MarketImports/prices.csv",
                imported_at_utc=moment,
                row_count=1,
                accepted_rows=1,
                rejected_rows=0,
            )
        )
        session.flush()
        observed = AS_OF - timedelta(days=observed_days_ago)
        session.add(
            MarketObservationRecord(
                observation_id="obs-1",
                batch_id="batch-1",
                source_id="src-1",
                instrument_id="IDX:BBCA",
                observed_at_utc=observed.isoformat(),
                acquired_at_utc=observed.isoformat(),
                open=None,
                high=None,
                low=None,
                close="9500",
                volume=None,
                currency="IDR",
                quality_status="VERIFIED",
                original_row_json="{}",
                transformation_version="market-csv-v1",
            )
        )


def service_for(database: Database) -> ScreeningEvaluationService:
    dividends = DividendEventService(database.sessions)
    observations = ObservationReviewService(database.sessions)
    recommendations = RecommendationService(database.sessions)
    return ScreeningEvaluationService(
        database.sessions,
        dividend_events=dividends,
        observation_review=observations,
        recommendations=recommendations,
    )


def test_healthy_candidate_produces_buy_candidate_with_evidence(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "screen.sqlite3")
    database.upgrade()
    seed(database)
    dividends = DividendEventService(database.sessions)
    recorded = dividends.record_event(
        DividendEventContract(
            event_key="cash-1",
            instrument_id="IDX:BBCA",
            source_label="Issuer report",
            dividend_type=DividendType.CASH,
            event_status=DividendEventStatus.CONFIRMED,
            amount_per_share=Decimal("100"),
            currency="IDR",
            ex_date=date(2026, 5, 20),
            acquired_at=AS_OF,
        ),
        recorded_at=AS_OF,
    )
    dividends.review_event(
        recorded.event_id,
        decision=DividendReviewDecision.VERIFIED,
        reviewer_label="Operator",
        evidence_reference="Documents/report.pdf",
        evidence_sha256="a" * 64,
        notes="Checked issuer report",
    )

    result = service_for(database).evaluate("IDX:BBCA", fundamentals=HEALTHY, as_of=AS_OF)

    assert result.action is RecommendationAction.BUY_CANDIDATE
    assert result.risk_flags == ()
    assert "price:obs-1" in result.evidence_ids
    assert f"dividend:{recorded.event_id}" in result.evidence_ids
    assert "metric:RETURN_ON_EQUITY" in result.evidence_ids
    assert "dividend-analytics-v1" not in result.explanation
    database.close()


def test_active_risk_event_blocks_buy_candidate_until_reviewed(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "screen-risk.sqlite3")
    database.upgrade()
    seed(database)
    risk = RiskMonitoringService(database.sessions)
    risk.evaluate(
        RiskSnapshot(
            as_of=AS_OF,
            peak_value=Decimal("1000000"),
            current_value=Decimal("900000"),
            valuation_methodology="portfolio-valuation-v1",
            valuation_is_complete=True,
            instrument_weights={},
            sector_weights={},
            allocation_deviations={},
            last_reviewed_at=None,
        ),
        triggered_at=AS_OF,
    )
    event_id = risk.active_events()[0].event_id
    service = ScreeningEvaluationService(
        database.sessions,
        dividend_events=DividendEventService(database.sessions),
        observation_review=ObservationReviewService(database.sessions),
        recommendations=RecommendationService(database.sessions),
        risk_monitoring=risk,
    )

    blocked = service.evaluate("IDX:BBCA", fundamentals=HEALTHY, as_of=AS_OF)
    assert blocked.action is RecommendationAction.WATCH
    assert RiskFlag.RISK_REVIEW_REQUIRED in blocked.risk_flags
    assert f"risk:{event_id}" in blocked.evidence_ids

    risk.record_review(
        event_id,
        reviewer_label="Portfolio operator",
        notes="Reviewed the elevated drawdown and allocation.",
        evidence_reference="Documents/RiskReview/2026-11.md",
        reviewed_at=AS_OF,
    )
    released = service.evaluate("IDX:BBCA", fundamentals=HEALTHY, as_of=AS_OF)

    assert released.action is RecommendationAction.BUY_CANDIDATE
    assert RiskFlag.RISK_REVIEW_REQUIRED not in released.risk_flags
    assert f"risk:{event_id}" not in released.evidence_ids
    database.close()


def test_unverified_instrument_blocks_buy_candidate(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "screen-unverified.sqlite3")
    database.upgrade()
    seed(database, instrument_status="UNVERIFIED")

    result = service_for(database).evaluate("IDX:BBCA", fundamentals=HEALTHY, as_of=AS_OF)

    assert result.action is RecommendationAction.WATCH
    assert RiskFlag.UNVERIFIED_PRICE in result.risk_flags
    database.close()


def test_stale_price_blocks_buy_candidate(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "screen-stale.sqlite3")
    database.upgrade()
    seed(database, observed_days_ago=30)

    result = service_for(database).evaluate("IDX:BBCA", fundamentals=HEALTHY, as_of=AS_OF)

    assert result.action is RecommendationAction.WATCH
    assert RiskFlag.STALE_PRICE in result.risk_flags
    database.close()


def test_missing_fundamentals_are_not_converted_to_zero(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "screen-missing.sqlite3")
    database.upgrade()
    seed(database)

    result = service_for(database).evaluate("IDX:BBCA", fundamentals={}, as_of=AS_OF)

    assert result.action is RecommendationAction.INSUFFICIENT_DATA
    assert result.confidence_level == Decimal("0")
    database.close()


def test_unknown_instrument_is_rejected(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "screen-unknown.sqlite3")
    database.upgrade()
    seed(database)
    with pytest.raises(ValueError, match="instrument"):
        service_for(database).evaluate("IDX:UNKNOWN", fundamentals=HEALTHY, as_of=AS_OF)
    database.close()


def test_persisted_verified_metrics_drive_screening(tmp_path: Path) -> None:
    from datetime import date

    from rfinance.application.financial_statements import (
        FinancialMetricContract,
        FinancialReviewDecision,
        FinancialStatementService,
    )
    from rfinance.data.contracts import DataQualityStatus

    database = Database.open(tmp_path / "screen-filings.sqlite3")
    database.upgrade()
    seed(database)
    filings = FinancialStatementService(database.sessions, data_directory=tmp_path / "data")
    for name, value in {
        "revenue": Decimal("1000"),
        "revenue_previous": Decimal("800"),
        "net_income": Decimal("150"),
        "average_equity": Decimal("750"),
        "total_debt": Decimal("300"),
        "total_equity": Decimal("750"),
        "earnings_per_share": Decimal("5"),
        "price": Decimal("50"),
    }.items():
        recorded = filings.record_metric(
            FinancialMetricContract(
                instrument_id="IDX:BBCA",
                metric_name=name,
                value=value,
                unit="IDR",
                currency="IDR",
                period_start=date(2025, 1, 1),
                period_end=date(2025, 12, 31),
                reporting_basis="ANNUAL",
                source_label="Audited annual report",
                acquired_at=AS_OF,
                quality_status=DataQualityStatus.UNVERIFIED,
            ),
            recorded_at=AS_OF,
        )
        filings.review_metric(
            recorded.metric_id,
            decision=FinancialReviewDecision.VERIFIED,
            reviewer_label="Operator",
            evidence_reference="Documents/annual-report.pdf",
            evidence_sha256="b" * 64,
            notes="Matched the audited filing",
            reviewed_at=AS_OF,
        )

    dividends = DividendEventService(database.sessions)
    observations = ObservationReviewService(database.sessions)
    recommendations = RecommendationService(database.sessions)
    service = ScreeningEvaluationService(
        database.sessions,
        dividend_events=dividends,
        observation_review=observations,
        recommendations=recommendations,
        financial_statements=filings,
    )

    result = service.evaluate(
        "IDX:BBCA",
        fundamentals={},
        as_of=AS_OF,
        use_persisted_fundamentals=True,
    )

    assert result.action is RecommendationAction.BUY_CANDIDATE
    assert "metric:RETURN_ON_EQUITY" in result.evidence_ids
    database.close()
