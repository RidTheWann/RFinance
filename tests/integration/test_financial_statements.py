# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Persistence and review tests for verified financial statement metrics."""

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa

from rfinance.application.financial_statements import (
    FinancialMetricContract,
    FinancialReviewDecision,
    FinancialStatementService,
)
from rfinance.data.contracts import DataQualityStatus, ReportingBasis
from rfinance.storage.database import Database
from rfinance.storage.models.instrument_registry import InstrumentRegistryRecord

AS_OF = datetime(2026, 11, 22, 12, tzinfo=UTC)


def seed_instrument(database: Database) -> None:
    with database.sessions.begin() as session:
        session.add(
            InstrumentRegistryRecord(
                instrument_id="IDX:BBCA",
                verification_status="VERIFIED",
                created_at_utc=AS_OF.isoformat(),
                updated_at_utc=AS_OF.isoformat(),
            )
        )


def metric(value: str = "1000", **overrides: object) -> FinancialMetricContract:
    values: dict[str, object] = {
        "instrument_id": "IDX:BBCA",
        "metric_name": "revenue",
        "value": Decimal(value),
        "unit": "IDR",
        "currency": "IDR",
        "period_start": date(2025, 1, 1),
        "period_end": date(2025, 12, 31),
        "reporting_basis": "ANNUAL",
        "source_label": "Issuer annual report",
        "acquired_at": AS_OF,
    }
    values.update(overrides)
    return FinancialMetricContract(**values)  # type: ignore[arg-type]


def test_record_metric_persists_provenance_as_unverified(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "financial.sqlite3")
    database.upgrade()
    seed_instrument(database)
    service = FinancialStatementService(database.sessions)

    result = service.record_metric(metric(), recorded_at=AS_OF)

    assert result.quality == "UNVERIFIED"
    assert result.source_id
    assert service.verified_inputs("IDX:BBCA") == {}
    for item in service.list_metrics():
        assert item.metric_name == "revenue"
        assert item.value == Decimal("1000")
        assert item.effective_quality == "UNVERIFIED"
        assert item.period_end == date(2025, 12, 31)
    database.close()


def test_review_promotes_with_evidence_and_rejects_estimate(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "financial-review.sqlite3")
    database.upgrade()
    seed_instrument(database)
    service = FinancialStatementService(database.sessions, data_directory=tmp_path / "data")
    first = service.record_metric(metric(), recorded_at=AS_OF)
    estimate = service.record_metric(
        metric(
            value="1200",
            metric_name="revenue_previous",
            quality_status=DataQualityStatus.ESTIMATED,
        ),
        recorded_at=AS_OF,
    )
    evidence = tmp_path / "annual-report.txt"
    evidence.write_text("Verified revenue figure", encoding="utf-8")

    service.review_metric_from_file(
        first.metric_id,
        decision=FinancialReviewDecision.VERIFIED,
        reviewer_label="Operator",
        evidence_file=evidence,
        notes="Matched the audited statement",
        reviewed_at=AS_OF,
    )
    with pytest.raises(ValueError, match="UNVERIFIED"):
        service.review_metric(
            estimate.metric_id,
            decision=FinancialReviewDecision.VERIFIED,
            reviewer_label="Operator",
            evidence_reference="Documents/report.pdf",
            evidence_sha256="a" * 64,
            notes="This is an estimate",
            reviewed_at=AS_OF,
        )

    inputs = service.verified_inputs("IDX:BBCA")
    assert inputs == {"revenue": Decimal("1000")}
    assert service.effective_quality(first.metric_id) == "VERIFIED"
    assert service.effective_quality(estimate.metric_id) == "ESTIMATED"
    database.close()


def test_verified_inputs_uses_latest_period_and_ignores_future(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "financial-periods.sqlite3")
    database.upgrade()
    seed_instrument(database)
    service = FinancialStatementService(database.sessions)
    older = service.record_metric(
        metric(value="900", period_end=date(2024, 12, 31), period_start=date(2024, 1, 1)),
        recorded_at=AS_OF,
    )
    newer = service.record_metric(metric(value="1000"), recorded_at=AS_OF)
    future = service.record_metric(
        metric(value="9999", period_end=date(2027, 12, 31), period_start=date(2027, 1, 1)),
        recorded_at=AS_OF,
    )
    for item in (older, newer, future):
        service.review_metric(
            item.metric_id,
            decision=FinancialReviewDecision.VERIFIED,
            reviewer_label="Operator",
            evidence_reference="Documents/report.pdf",
            evidence_sha256="a" * 64,
            notes="Checked",
            reviewed_at=AS_OF,
        )

    assert service.verified_inputs("IDX:BBCA", as_of=AS_OF) == {"revenue": Decimal("1000")}
    database.close()


def test_verified_inputs_separates_reporting_basis_and_prefers_requested(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "financial-basis.sqlite3")
    database.upgrade()
    seed_instrument(database)
    service = FinancialStatementService(database.sessions)
    annual = service.record_metric(metric(value="1000"), recorded_at=AS_OF)
    quarterly = service.record_metric(
        metric(
            value="300",
            period_start=date(2025, 10, 1),
            period_end=date(2025, 12, 31),
            reporting_basis="QUARTERLY",
        ),
        recorded_at=AS_OF,
    )
    for item in (annual, quarterly):
        service.review_metric(
            item.metric_id,
            decision=FinancialReviewDecision.VERIFIED,
            reviewer_label="Operator",
            evidence_reference="Documents/report.pdf",
            evidence_sha256="a" * 64,
            notes="Checked",
            reviewed_at=AS_OF,
        )

    # A newer quarter never replaces the annual figure: mixing bases would feed a
    # three-month revenue into a formula that assumes an annual denominator.
    assert service.verified_inputs("IDX:BBCA", as_of=AS_OF)["revenue"] == Decimal("1000")
    assert service.verified_inputs("IDX:BBCA", as_of=AS_OF, reporting_basis=ReportingBasis.ANNUAL)[
        "revenue"
    ] == Decimal("1000")
    assert service.verified_inputs(
        "IDX:BBCA", as_of=AS_OF, reporting_basis=ReportingBasis.QUARTERLY
    )["revenue"] == Decimal("300")
    assert (
        service.verified_inputs("IDX:BBCA", as_of=AS_OF, reporting_basis=ReportingBasis.TTM) == {}
    )
    database.close()


def test_financial_metric_tables_are_append_only(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "financial-append.sqlite3")
    database.upgrade()
    seed_instrument(database)
    service = FinancialStatementService(database.sessions)
    recorded = service.record_metric(metric(), recorded_at=AS_OF)

    with pytest.raises(sa.exc.IntegrityError), database.sessions.begin() as session:
        session.execute(sa.text("UPDATE financial_metrics SET value = '1'"))
    with pytest.raises(sa.exc.IntegrityError), database.sessions.begin() as session:
        session.execute(
            sa.text(
                "INSERT INTO financial_metrics "
                "(metric_id, instrument_id, source_id, metric_name, value, unit, currency, "
                "period_start, period_end, reporting_basis, quality_status, acquired_at_utc, "
                "transformation_version, created_at_utc) VALUES "
                "(:id, 'IDX:BBCA', :source, 'revenue', '1', 'IDR', 'IDR', '2025-01-01', "
                "'2025-12-31', 'ANNUAL', 'UNVERIFIED', '2026-11-22T12:00:00+00:00', 'v1', "
                "'2026-11-22T12:00:00+00:00')"
            ),
            {"id": recorded.metric_id, "source": recorded.source_id},
        )
    database.close()
