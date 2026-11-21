# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from rfinance.application.market_csv_import import MarketCSVImportService
from rfinance.data.csv_market_import import CSVImportError, parse_market_observation_csv
from rfinance.storage.database import Database
from rfinance.storage.models.data_ingestion import (
    DataImportBatchRecord,
    DataImportIssueRecord,
    MarketObservationRecord,
    SourceRegistryRecord,
)
from rfinance.storage.repositories.data_ingestion import DataIngestionRepository

if TYPE_CHECKING:
    from pathlib import Path


ACQUIRED_AT = datetime(2026, 11, 21, 9, 0, tzinfo=UTC)

GOOD_ROW = "IDX:BBCA,2026-11-20T09:00:00+07:00,IDR,9000,9200,8900,9100,1000\n"


def write_csv(tmp_path: Path, content: str, name: str = "market.csv") -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8", newline="")
    return path


def test_parser_accepts_valid_row_and_records_invalid_and_duplicate_rows(tmp_path) -> None:
    path = write_csv(
        tmp_path,
        "instrument_id,observed_at,currency,open,high,low,close,volume\n"
        + GOOD_ROW
        + "IDX:BBRI,2026-11-20T09:00:00+07:00,IDR,4000,4100,3900,-1,2000\n"
        + GOOD_ROW,
    )

    result = parse_market_observation_csv(path, acquired_at=ACQUIRED_AT)

    assert result.row_count == 3
    assert len(result.accepted) == 1
    assert len(result.rejected) == 2
    assert result.accepted[0].row_number == 2
    assert result.accepted[0].observation.close == Decimal("9100")
    assert result.accepted[0].observation.quality_status.value == "UNVERIFIED"
    assert result.rejected[0].row_number == 3
    assert "greater than 0" in result.rejected[0].error_message
    assert result.rejected[1].row_number == 4
    assert "duplicate" in result.rejected[1].error_message


def test_parser_requires_timezone_and_canonical_columns(tmp_path) -> None:
    naive = write_csv(
        tmp_path,
        "instrument_id,observed_at,currency,close\nIDX:BBCA,2026-11-20T09:00:00,IDR,9100\n",
    )
    parsed = parse_market_observation_csv(naive, acquired_at=ACQUIRED_AT)
    assert len(parsed.accepted) == 0
    assert "timezone-aware" in parsed.rejected[0].error_message

    invalid_header = write_csv(
        tmp_path,
        "ticker,date,currency,close\nIDX:BBCA,2026-11-20,IDR,9100\n",
        "wrong-schema.csv",
    )
    with pytest.raises(CSVImportError, match="missing required columns"):
        parse_market_observation_csv(invalid_header, acquired_at=ACQUIRED_AT)


def test_market_csv_import_persists_source_provenance_and_unverified_rows(tmp_path) -> None:
    source_file = write_csv(
        tmp_path,
        "instrument_id,observed_at,currency,open,high,low,close,volume\n"
        + GOOD_ROW
        + "IDX:BBRI,2026-11-20T09:00:00+07:00,IDR,4000,4100,3900,-1,2000\n",
    )
    data_directory = tmp_path / "RFinanceData"
    database = Database.open(data_directory / "Database" / "test.sqlite3")
    database.upgrade()
    try:
        service = MarketCSVImportService(
            DataIngestionRepository(database.sessions),
            data_directory=data_directory,
        )

        result = service.import_market_csv(
            source_file,
            source_name="User-supplied IDX EOD CSV",
        )

        assert result.row_count == 2
        assert result.accepted_rows == 1
        assert result.rejected_rows == 1
        assert len(result.file_sha256) == 64
        assert result.file_sha256 == hashlib.sha256(source_file.read_bytes()).hexdigest()

        history = service.recent_imports()
        assert len(history) == 1
        assert history[0].batch_id == result.batch_id
        assert history[0].source_name == "User-supplied IDX EOD CSV"
        assert history[0].original_filename == source_file.name
        assert history[0].accepted_rows == 1
        assert history[0].rejected_rows == 1
        assert history[0].file_sha256 == result.file_sha256
        assert history[0].document_relative_path.startswith("Documents/MarketImports/")

        with database.sessions() as session:
            source = session.get(SourceRegistryRecord, result.source_id)
            batch = session.get(DataImportBatchRecord, result.batch_id)
            observation = session.scalar(select(MarketObservationRecord))
            issue = session.scalar(select(DataImportIssueRecord))

            assert source is not None
            assert source.access_method == "USER_IMPORT"
            assert source.policy_status == "UNREVIEWED"
            assert source.automated_access_allowed is False
            assert source.redistribution_allowed is False
            assert batch is not None
            assert batch.row_count == 2
            assert batch.accepted_rows == 1
            assert batch.rejected_rows == 1
            assert observation is not None
            assert observation.quality_status == "UNVERIFIED"
            assert observation.currency == "IDR"
            assert observation.close == "9100"
            assert observation.source_id == result.source_id
            assert observation.transformation_version == "csv-market-v1"
            assert json.loads(observation.original_row_json)["close"] == "9100"
            assert issue is not None
            assert issue.row_number == 3

            archived_file = data_directory / batch.document_relative_path
            assert archived_file.is_file()
            assert archived_file.read_bytes() == source_file.read_bytes()
    finally:
        database.close()


def test_reimport_does_not_duplicate_observations_and_reconciles_issues(tmp_path) -> None:
    source_file = write_csv(
        tmp_path,
        "instrument_id,observed_at,currency,close\nIDX:BBCA,2026-11-20T09:00:00+07:00,IDR,9100\n",
    )
    database = Database.open(tmp_path / "database.sqlite3")
    database.upgrade()
    try:
        service = MarketCSVImportService(
            DataIngestionRepository(database.sessions),
            data_directory=tmp_path / "RFinanceData",
        )
        first = service.import_market_csv(source_file, source_name="My CSV source")
        second = service.import_market_csv(source_file, source_name="My CSV source")

        assert first.accepted_rows == 1
        assert second.accepted_rows == 0
        assert second.rejected_rows == 1
        with database.sessions() as session:
            assert session.scalar(select(func.count()).select_from(SourceRegistryRecord)) == 1
            assert session.scalar(select(func.count()).select_from(MarketObservationRecord)) == 1
            assert session.scalar(select(func.count()).select_from(DataImportBatchRecord)) == 2
            assert session.scalar(select(func.count()).select_from(DataImportIssueRecord)) == 1
            assert session.scalar(select(DataImportIssueRecord.error_message)).startswith(
                "duplicate observation"
            )
    finally:
        database.close()


def test_user_import_source_cannot_enable_automation_or_redistribution(tmp_path) -> None:
    database = Database.open(tmp_path / "policy.sqlite3")
    database.upgrade()
    try:
        with (
            pytest.raises(IntegrityError),
            database.sessions.begin() as session,
        ):
            session.add(
                SourceRegistryRecord(
                    source_id="invalid-user-source",
                    display_name="Invalid source",
                    access_method="USER_IMPORT",
                    policy_status="APPROVED",
                    automated_access_allowed=True,
                    redistribution_allowed=False,
                    created_at_utc=ACQUIRED_AT.isoformat(),
                )
            )
    finally:
        database.close()


def test_service_rejects_wrong_extension_and_oversized_file(tmp_path) -> None:
    database = Database.open(tmp_path / "limits.sqlite3")
    database.upgrade()
    try:
        service = MarketCSVImportService(
            DataIngestionRepository(database.sessions),
            data_directory=tmp_path / "RFinanceData",
            max_file_bytes=8,
        )
        wrong_extension = write_csv(tmp_path, "x", "market.txt")
        with pytest.raises(CSVImportError, match=".csv"):
            service.import_market_csv(wrong_extension, source_name="Local source")

        oversized = write_csv(tmp_path, "123456789", "large.csv")
        with pytest.raises(CSVImportError, match="limit"):
            service.import_market_csv(oversized, source_name="Local source")
    finally:
        database.close()
