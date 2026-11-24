# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from rfinance.application.historical_price_series import HistoricalPriceSeriesService
from rfinance.application.instrument_metadata import InstrumentMetadataEvidenceService
from rfinance.domain.eligibility.metadata import AdjustmentStatus, SamplingFrequency
from rfinance.storage.database import Database
from rfinance.storage.models.instrument_registry import InstrumentRegistryRecord

if TYPE_CHECKING:
    from pathlib import Path

AS_OF = datetime(2026, 11, 24, 12, tzinfo=UTC)
SOURCE_ID = "src:user-import"


def seed(database: Database, *, status: str = "VERIFIED") -> None:
    with database.sessions.begin() as session:
        session.add(
            InstrumentRegistryRecord(
                instrument_id="IDX:BBCA",
                ticker="BBCA",
                exchange="IDX",
                instrument_type="EQUITY",
                company_name="Bank Central Asia",
                currency="IDR",
                sector="Financials",
                active=True,
                lot_size=100,
                minimum_investment=None,
                verification_status=status,
                created_at_utc=AS_OF.isoformat(),
                updated_at_utc=AS_OF.isoformat(),
            )
        )


def service(database: Database, data_directory: Path) -> InstrumentMetadataEvidenceService:
    return InstrumentMetadataEvidenceService(database.sessions, data_directory=data_directory)


def _evidence_file(tmp_path: Path, name: str = "series.txt") -> Path:
    path = tmp_path / name
    path.write_text("daily, split-adjusted\n", encoding="utf-8")
    return path


def test_verified_metadata_is_persisted_and_returned(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "metadata.sqlite3")
    database.upgrade()
    try:
        seed(database)
        decisions = service(database, tmp_path / "data")
        decision = decisions.record_from_file(
            "IDX:BBCA",
            source_id=SOURCE_ID,
            sampling_frequency=SamplingFrequency.DAILY,
            adjustment_status=AdjustmentStatus.ADJUSTED,
            decision="VERIFIED",
            reviewer_label="Operator",
            notes="Provider documentation states daily split-adjusted bars.",
            evidence_file=_evidence_file(tmp_path),
            decided_at=AS_OF,
        )

        assert decision.decision == "VERIFIED"
        latest = decisions.latest_verified("IDX:BBCA", SOURCE_ID)
        assert latest is not None
        assert latest.sampling_frequency is SamplingFrequency.DAILY
        assert latest.adjustment_status is AdjustmentStatus.ADJUSTED
        assert latest.methodology_version == "instrument-metadata-evidence-v1"
        assert decisions.latest_verified("IDX:BBCA", "src:other") is None
    finally:
        database.close()


def test_newer_rejection_suppresses_the_prior_verified_decision(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "metadata-reject.sqlite3")
    database.upgrade()
    try:
        seed(database)
        decisions = service(database, tmp_path / "data")
        for index, (decision_value, filename) in enumerate(
            (("VERIFIED", "doc-1.txt"), ("REJECTED", "doc-2.txt"))
        ):
            decisions.record_from_file(
                "IDX:BBCA",
                source_id=SOURCE_ID,
                sampling_frequency=SamplingFrequency.DAILY,
                adjustment_status=AdjustmentStatus.NONE_CONFIRMED,
                decision=decision_value,
                reviewer_label="Operator",
                notes=f"Round {index}",
                evidence_file=_evidence_file(tmp_path, filename),
                decided_at=datetime(2026, 11, 24 + index, 12, tzinfo=UTC),
            )

        assert decisions.latest_verified("IDX:BBCA", SOURCE_ID) is None
    finally:
        database.close()


def test_metadata_events_are_append_only(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "metadata-append.sqlite3")
    database.upgrade()
    try:
        seed(database)
        decisions = service(database, tmp_path / "data")
        decisions.record_from_file(
            "IDX:BBCA",
            source_id=SOURCE_ID,
            sampling_frequency=SamplingFrequency.WEEKLY,
            adjustment_status=AdjustmentStatus.UNKNOWN_AS_SUPPLIED,
            decision="VERIFIED",
            reviewer_label="Operator",
            notes="Weekly, unadjusted.",
            evidence_file=_evidence_file(tmp_path),
            decided_at=AS_OF,
        )

        with database.sessions.begin() as session:
            row = session.execute(
                text("SELECT event_id FROM instrument_metadata_events LIMIT 1")
            ).one()
            with pytest.raises(IntegrityError):
                session.execute(
                    text(f"DELETE FROM instrument_metadata_events WHERE event_id = '{row[0]}'")
                )
            with pytest.raises(IntegrityError):
                session.execute(
                    text(
                        f"UPDATE instrument_metadata_events SET decision = 'REJECTED' "
                        f"WHERE event_id = '{row[0]}'"
                    )
                )
    finally:
        database.close()


def test_unverified_instrument_cannot_receive_metadata_evidence(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "metadata-instrument.sqlite3")
    database.upgrade()
    try:
        seed(database, status="UNVERIFIED")
        decisions = service(database, tmp_path / "data")
        with pytest.raises(ValueError):
            decisions.record_from_file(
                "IDX:BBCA",
                source_id=SOURCE_ID,
                sampling_frequency=SamplingFrequency.DAILY,
                adjustment_status=AdjustmentStatus.ADJUSTED,
                decision="VERIFIED",
                reviewer_label="Operator",
                notes="Attempt on an unverified instrument.",
                evidence_file=_evidence_file(tmp_path),
                decided_at=AS_OF,
            )
    finally:
        database.close()


def test_historical_series_defaults_to_unknown_without_evidence(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "series-default.sqlite3")
    database.upgrade()
    try:
        _seed_series(database)
        result = HistoricalPriceSeriesService(database.sessions).load(
            "IDX:BBCA", SOURCE_ID, as_of=AS_OF
        )
        assert result.adjustment_status == "UNKNOWN_AS_SUPPLIED"
        assert result.sampling_frequency is SamplingFrequency.UNKNOWN_AS_SUPPLIED
    finally:
        database.close()


def test_verified_evidence_drives_the_reported_metadata(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "series-evidence.sqlite3")
    database.upgrade()
    try:
        _seed_series(database)
        decisions = service(database, tmp_path / "data")
        decisions.record_from_file(
            "IDX:BBCA",
            source_id=SOURCE_ID,
            sampling_frequency=SamplingFrequency.DAILY,
            adjustment_status=AdjustmentStatus.ADJUSTED,
            decision="VERIFIED",
            reviewer_label="Operator",
            notes="Documented daily split-adjusted series.",
            evidence_file=_evidence_file(tmp_path),
            decided_at=datetime(2026, 11, 25, 12, tzinfo=UTC),
        )

        result = HistoricalPriceSeriesService(
            database.sessions,
            metadata_service=decisions,
        ).load("IDX:BBCA", SOURCE_ID, as_of=AS_OF)
        assert result.adjustment_status == "ADJUSTED"
        assert result.sampling_frequency is SamplingFrequency.DAILY
    finally:
        database.close()


def _seed_series(database: Database) -> None:
    from rfinance.storage.models.data_ingestion import (
        DataImportBatchRecord,
        MarketObservationRecord,
        SourceRegistryRecord,
    )

    with database.sessions.begin() as session:
        session.add(
            InstrumentRegistryRecord(
                instrument_id="IDX:BBCA",
                ticker="BBCA",
                exchange="IDX",
                instrument_type="EQUITY",
                company_name="Bank Central Asia",
                currency="IDR",
                sector="Financials",
                active=True,
                lot_size=100,
                minimum_investment=None,
                verification_status="VERIFIED",
                created_at_utc=NOW.isoformat(),
                updated_at_utc=NOW.isoformat(),
            )
        )
        session.flush()
        session.add(
            SourceRegistryRecord(
                source_id=SOURCE_ID,
                display_name="User data 1",
                access_method="USER_IMPORT",
                policy_status="UNREVIEWED",
                description="User-supplied historical observations",
                terms_url=None,
                reviewed_at_utc=None,
                automated_access_allowed=False,
                redistribution_allowed=False,
                created_at_utc=NOW.isoformat(),
            )
        )
        session.flush()
        session.add(
            DataImportBatchRecord(
                batch_id=f"batch-{SOURCE_ID}",
                source_id=SOURCE_ID,
                original_filename=f"{SOURCE_ID}.csv",
                file_sha256="a" * 64,
                document_relative_path=f"Documents/MarketImports/{SOURCE_ID}.csv",
                imported_at_utc=NOW.isoformat(),
                row_count=1,
                accepted_rows=1,
                rejected_rows=0,
            )
        )
        session.add(
            MarketObservationRecord(
                observation_id="bbca-bar",
                batch_id=f"batch-{SOURCE_ID}",
                source_id=SOURCE_ID,
                instrument_id="IDX:BBCA",
                observed_at_utc=BAR_TIME.isoformat(),
                acquired_at_utc=NOW.isoformat(),
                open="9000",
                high="9100",
                low="8900",
                close="9000",
                volume="100000",
                currency="IDR",
                quality_status="VERIFIED",
                original_row_json="{}",
                transformation_version="fixture-market-v1",
            )
        )


NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
BAR_TIME = datetime(2010, 1, 4, 9, 0, tzinfo=UTC)
