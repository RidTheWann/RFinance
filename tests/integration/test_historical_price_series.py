# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from rfinance.application.historical_price_series import HistoricalPriceSeriesService
from rfinance.application.technical_analysis import TechnicalAnalysisService
from rfinance.storage.database import Database
from rfinance.storage.models.data_ingestion import (
    DataImportBatchRecord,
    MarketObservationRecord,
    SourceRegistryRecord,
)
from rfinance.storage.models.instrument_registry import InstrumentRegistryRecord
from rfinance.storage.models.observation_review import ObservationReviewEventRecord

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


def seed_registry(
    database: Database,
    *,
    source_ids: tuple[str, ...] = ("source-main",),
    source_policy: str = "UNREVIEWED",
    instrument_status: str = "VERIFIED",
    active: bool = True,
    currency: str = "IDR",
) -> None:
    with database.sessions.begin() as session:
        session.add(
            InstrumentRegistryRecord(
                instrument_id="IDX:BBCA",
                ticker="BBCA",
                exchange="IDX",
                instrument_type="EQUITY",
                company_name="Bank Central Asia",
                currency=currency,
                sector="Financials",
                active=active,
                lot_size=100,
                minimum_investment=None,
                verification_status=instrument_status,
                created_at_utc=NOW.isoformat(),
                updated_at_utc=NOW.isoformat(),
            )
        )
        session.flush()
        for index, source_id in enumerate(source_ids):
            session.add(
                SourceRegistryRecord(
                    source_id=source_id,
                    display_name=f"User data {index + 1}",
                    access_method="USER_IMPORT",
                    policy_status=source_policy,
                    description="User-supplied historical test observations",
                    terms_url=None,
                    reviewed_at_utc=None,
                    automated_access_allowed=False,
                    redistribution_allowed=False,
                    created_at_utc=NOW.isoformat(),
                )
            )
        session.flush()
        for index, source_id in enumerate(source_ids):
            session.add(
                DataImportBatchRecord(
                    batch_id=f"batch-{source_id}",
                    source_id=source_id,
                    original_filename=f"{source_id}.csv",
                    file_sha256=chr(97 + index) * 64,
                    document_relative_path=f"Documents/MarketImports/{source_id}.csv",
                    imported_at_utc=NOW.isoformat(),
                    row_count=1,
                    accepted_rows=1,
                    rejected_rows=0,
                )
            )


def add_bars(
    database: Database,
    *,
    source_id: str = "source-main",
    observations: tuple[tuple[str, datetime, Decimal, str, str], ...],
    currency: str = "IDR",
) -> None:
    with database.sessions.begin() as session:
        for observation_id, observed_at, close, quality, batch_id in observations:
            session.add(
                MarketObservationRecord(
                    observation_id=observation_id,
                    batch_id=batch_id,
                    source_id=source_id,
                    instrument_id="IDX:BBCA",
                    observed_at_utc=observed_at.isoformat(),
                    acquired_at_utc=NOW.isoformat(),
                    open=str(close),
                    high=str(close + Decimal("100")),
                    low=str(max(Decimal("1"), close - Decimal("100"))),
                    close=str(close),
                    volume="100000",
                    currency=currency,
                    quality_status=quality,
                    original_row_json="{}",
                    transformation_version="fixture-market-v1",
                )
            )


def verify_observation(database: Database, observation_id: str, review_id: str) -> None:
    with database.sessions.begin() as session:
        session.add(
            ObservationReviewEventRecord(
                review_id=review_id,
                observation_id=observation_id,
                instrument_id="IDX:BBCA",
                source_id="source-main",
                previous_quality="UNVERIFIED",
                decision="VERIFIED",
                reviewed_at_utc=NOW.isoformat(),
                reviewer_label="Test reviewer",
                evidence_reference="Documents/ReviewEvidence/price.pdf",
                evidence_sha256="a" * 64,
                notes="Checked against the user-selected source document.",
                reviewed_metadata_json=None,
            )
        )


def test_history_uses_reviewed_prices_and_does_not_apply_current_staleness(tmp_path) -> None:
    database = Database.open(tmp_path / "historical.sqlite3")
    database.upgrade()
    try:
        seed_registry(database)
        observed = datetime(2010, 1, 4, 9, 0, tzinfo=UTC)
        add_bars(
            database,
            observations=(
                ("old-bbca", observed, Decimal("9000"), "UNVERIFIED", "batch-source-main"),
            ),
        )
        verify_observation(database, "old-bbca", "review-old")

        result = HistoricalPriceSeriesService(database.sessions).load(
            "IDX:BBCA",
            "source-main",
            as_of=NOW,
        )

        assert len(result.points) == 1
        assert result.points[0].close == Decimal("9000")
        assert result.points[0].observed_at == observed
        assert result.points[0].acquired_at == NOW
        assert result.rejected_count == 0
        assert result.adjustment_status == "UNKNOWN_AS_SUPPLIED"
    finally:
        database.close()


def test_history_does_not_mix_sources_and_breaks_indicator_windows_on_large_gaps(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "single-source.sqlite3")
    database.upgrade()
    try:
        seed_registry(database, source_ids=("source-main", "source-other"))
        day_one = datetime(2010, 1, 4, 9, 0, tzinfo=UTC)
        day_two = day_one + timedelta(days=1)
        day_late = day_one + timedelta(days=15)
        add_bars(
            database,
            observations=(
                ("bar-two", day_two, Decimal("110"), "VERIFIED", "batch-source-main"),
                ("bar-one", day_one, Decimal("100"), "VERIFIED", "batch-source-main"),
            ),
        )
        with database.sessions.begin() as session:
            session.add(
                MarketObservationRecord(
                    observation_id="bar-other-source",
                    batch_id="batch-source-other",
                    source_id="source-other",
                    instrument_id="IDX:BBCA",
                    observed_at_utc=day_late.isoformat(),
                    acquired_at_utc=NOW.isoformat(),
                    open="200",
                    high="300",
                    low="100",
                    close="200",
                    volume="1000",
                    currency="IDR",
                    quality_status="VERIFIED",
                    original_row_json="{}",
                    transformation_version="fixture-market-v1",
                )
            )
            session.add(
                MarketObservationRecord(
                    observation_id="bar-gap",
                    batch_id="batch-source-main",
                    source_id="source-main",
                    instrument_id="IDX:BBCA",
                    observed_at_utc=day_late.isoformat(),
                    acquired_at_utc=NOW.isoformat(),
                    open="120",
                    high="220",
                    low="20",
                    close="120",
                    volume="1000",
                    currency="IDR",
                    quality_status="VERIFIED",
                    original_row_json="{}",
                    transformation_version="fixture-market-v1",
                )
            )

        result = HistoricalPriceSeriesService(database.sessions).load(
            "IDX:BBCA",
            "source-main",
            as_of=NOW,
            max_gap_days=7,
        )

        assert [point.close for point in result.points] == [
            Decimal("100"),
            Decimal("110"),
            Decimal("120"),
        ]
        assert result.closes == (Decimal("100"), Decimal("110"), None, Decimal("120"))
        assert len(result.gaps) == 1
        assert result.gaps[0].elapsed_days == 14
        assert all(point.observation_id != "bar-other-source" for point in result.points)
    finally:
        database.close()


def test_unverified_and_future_bars_are_rejected_with_diagnostics(tmp_path) -> None:
    database = Database.open(tmp_path / "rejected-history.sqlite3")
    database.upgrade()
    try:
        seed_registry(database)
        old = NOW - timedelta(days=10)
        future = NOW + timedelta(days=1)
        add_bars(
            database,
            observations=(
                ("unverified", old, Decimal("100"), "UNVERIFIED", "batch-source-main"),
                ("future", future, Decimal("101"), "VERIFIED", "batch-source-main"),
            ),
        )

        result = HistoricalPriceSeriesService(database.sessions).load(
            "IDX:BBCA",
            "source-main",
            as_of=NOW,
        )

        assert result.points == ()
        diagnostics = dict(result.rejected_reasons)
        assert diagnostics["OBSERVATION_UNVERIFIED"] == 1
        assert diagnostics["FUTURE_OBSERVATION"] == 1
    finally:
        database.close()


def test_blocked_source_cannot_feed_historical_indicators(tmp_path) -> None:
    database = Database.open(tmp_path / "blocked-history.sqlite3")
    database.upgrade()
    try:
        seed_registry(database, source_policy="BLOCKED")
        add_bars(
            database,
            observations=(
                (
                    "blocked",
                    NOW - timedelta(days=1),
                    Decimal("100"),
                    "VERIFIED",
                    "batch-source-main",
                ),
            ),
        )

        result = HistoricalPriceSeriesService(database.sessions).load(
            "IDX:BBCA",
            "source-main",
            as_of=NOW,
        )

        assert result.points == ()
        assert dict(result.rejected_reasons)["SOURCE_BLOCKED"] == 1
        assert HistoricalPriceSeriesService(database.sessions).available_series() == ()
    finally:
        database.close()


def test_catalog_excludes_inactive_or_unverified_instruments(tmp_path) -> None:
    database = Database.open(tmp_path / "catalog.sqlite3")
    database.upgrade()
    try:
        seed_registry(database, instrument_status="UNVERIFIED")
        add_bars(
            database,
            observations=(
                (
                    "placeholder",
                    NOW - timedelta(days=1),
                    Decimal("100"),
                    "VERIFIED",
                    "batch-source-main",
                ),
            ),
        )

        assert HistoricalPriceSeriesService(database.sessions).available_series() == ()
    finally:
        database.close()


def test_technical_service_returns_only_values_aligned_to_latest_bar(tmp_path) -> None:
    database = Database.open(tmp_path / "technical-report.sqlite3")
    database.upgrade()
    try:
        seed_registry(database)
        bars = tuple(
            (
                f"bar-{index:02d}",
                datetime(2026, 10, 1, 9, 0, tzinfo=UTC) + timedelta(days=index),
                Decimal("10000") + Decimal(index * 100),
                "VERIFIED",
                "batch-source-main",
            )
            for index in range(40)
        )
        add_bars(database, observations=bars)

        report = TechnicalAnalysisService(HistoricalPriceSeriesService(database.sessions)).analyze(
            "IDX:BBCA", "source-main"
        )

        values = {item.key: item for item in report.indicators}
        assert report.latest_close == Decimal("13900")
        assert len(report.series.points) == 40
        assert values["sma20"].value == Decimal("12950")
        assert values["rsi14"].value == Decimal("100")
        assert values["maximum_drawdown"].value == Decimal("0")
        assert values["momentum20"].value is not None
        assert values["atr14"].value == Decimal("200")
        assert report.formula_version == "technical-decimal-v1"
    finally:
        database.close()


def test_date_filters_are_applied_before_quality_diagnostics(tmp_path) -> None:
    database = Database.open(tmp_path / "date-filter.sqlite3")
    database.upgrade()
    try:
        seed_registry(database)
        older = NOW - timedelta(days=30)
        newer = NOW - timedelta(days=2)
        add_bars(
            database,
            observations=(
                ("old-unverified", older, Decimal("100"), "UNVERIFIED", "batch-source-main"),
                ("in-range", newer, Decimal("110"), "VERIFIED", "batch-source-main"),
            ),
        )

        result = HistoricalPriceSeriesService(database.sessions).load(
            "IDX:BBCA",
            "source-main",
            as_of=NOW,
            start_at=NOW - timedelta(days=5),
        )

        assert [point.observation_id for point in result.points] == ["in-range"]
        assert result.rejected_count == 0
    finally:
        database.close()
