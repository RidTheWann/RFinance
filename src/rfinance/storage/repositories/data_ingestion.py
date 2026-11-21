"""SQLite persistence for source registry, file imports, and market observations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select, tuple_

from rfinance.data.contracts import DataQualityStatus
from rfinance.data.csv_market_import import (
    ParsedMarketCSVRow,
    RejectedMarketCSVRow,
    serialize_original_row,
)
from rfinance.storage.models.data_ingestion import (
    DataImportBatchRecord,
    DataImportIssueRecord,
    MarketObservationRecord,
    SourceRegistryRecord,
)
from rfinance.storage.models.instrument_registry import InstrumentRegistryRecord

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from sqlalchemy.orm import Session, sessionmaker


@dataclass(frozen=True, slots=True)
class DataImportSummary:
    batch_id: str
    source_id: str
    file_sha256: str
    row_count: int
    accepted_rows: int
    rejected_rows: int


@dataclass(frozen=True, slots=True)
class DataImportHistoryItem:
    batch_id: str
    source_name: str
    original_filename: str
    imported_at_utc: str
    row_count: int
    accepted_rows: int
    rejected_rows: int
    file_sha256: str
    document_relative_path: str


class DataIngestionRepository:
    """Writes one CSV import as an atomic source/batch/observation transaction."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def recent_imports(self, limit: int = 20) -> tuple[DataImportHistoryItem, ...]:
        """Return recent import batches with their source labels for UI provenance."""

        if limit <= 0 or limit > 100:
            raise ValueError("limit must be between 1 and 100")

        with self._sessions() as session:
            rows = session.execute(
                select(DataImportBatchRecord, SourceRegistryRecord.display_name)
                .join(
                    SourceRegistryRecord,
                    SourceRegistryRecord.source_id == DataImportBatchRecord.source_id,
                )
                .order_by(
                    DataImportBatchRecord.imported_at_utc.desc(),
                    DataImportBatchRecord.batch_id.desc(),
                )
                .limit(limit)
            ).all()

        return tuple(
            DataImportHistoryItem(
                batch_id=batch.batch_id,
                source_name=source_name,
                original_filename=batch.original_filename,
                imported_at_utc=batch.imported_at_utc,
                row_count=batch.row_count,
                accepted_rows=batch.accepted_rows,
                rejected_rows=batch.rejected_rows,
                file_sha256=batch.file_sha256,
                document_relative_path=batch.document_relative_path,
            )
            for batch, source_name in rows
        )

    def persist_market_csv_import(
        self,
        *,
        batch_id: str,
        source_name: str,
        original_filename: str,
        file_sha256: str,
        document_relative_path: str,
        imported_at: datetime,
        accepted_rows: Sequence[ParsedMarketCSVRow],
        rejected_rows: Sequence[RejectedMarketCSVRow],
    ) -> DataImportSummary:
        """Persist source metadata, a batch, accepted observations and row issues."""

        imported_at_utc = imported_at.astimezone(UTC).isoformat()
        row_count = len(accepted_rows) + len(rejected_rows)

        with self._sessions.begin() as session:
            source = session.scalar(
                select(SourceRegistryRecord).where(
                    SourceRegistryRecord.display_name == source_name,
                    SourceRegistryRecord.access_method == "USER_IMPORT",
                )
            )
            if source is None:
                source = SourceRegistryRecord(
                    source_id=str(uuid4()),
                    display_name=source_name,
                    access_method="USER_IMPORT",
                    policy_status="UNREVIEWED",
                    description="User-supplied local CSV; not an automated data feed.",
                    terms_url=None,
                    reviewed_at_utc=None,
                    automated_access_allowed=False,
                    redistribution_allowed=False,
                    created_at_utc=imported_at_utc,
                )
                session.add(source)
                session.flush()

            candidate_keys = [
                (
                    row.observation.instrument_id,
                    row.observation.observed_at.astimezone(UTC).isoformat(),
                )
                for row in accepted_rows
            ]
            existing_keys: set[tuple[str, str]] = set()
            for offset in range(0, len(candidate_keys), 400):
                key_chunk = candidate_keys[offset : offset + 400]
                if not key_chunk:
                    continue
                existing = session.execute(
                    select(
                        MarketObservationRecord.instrument_id,
                        MarketObservationRecord.observed_at_utc,
                    ).where(
                        MarketObservationRecord.source_id == source.source_id,
                        tuple_(
                            MarketObservationRecord.instrument_id,
                            MarketObservationRecord.observed_at_utc,
                        ).in_(key_chunk),
                    )
                ).all()
                existing_keys.update(
                    (instrument_id, observed_at) for instrument_id, observed_at in existing
                )

            accepted_count = 0
            rejected_records: list[RejectedMarketCSVRow] = list(rejected_rows)
            observation_records: list[MarketObservationRecord] = []

            for row in accepted_rows:
                observation = row.observation
                observed_at_utc = observation.observed_at.astimezone(UTC).isoformat()
                key = (observation.instrument_id, observed_at_utc)
                if key in existing_keys:
                    rejected_records.append(
                        RejectedMarketCSVRow(
                            row_number=row.row_number,
                            original_row=row.original_row,
                            error_message=(
                                "duplicate observation already exists for this source, "
                                "instrument, and timestamp"
                            ),
                        )
                    )
                    continue
                existing_keys.add(key)
                if session.get(InstrumentRegistryRecord, observation.instrument_id) is None:
                    session.add(
                        InstrumentRegistryRecord(
                            instrument_id=observation.instrument_id,
                            verification_status="UNVERIFIED",
                            created_at_utc=imported_at_utc,
                            updated_at_utc=imported_at_utc,
                        )
                    )
                observation_records.append(
                    MarketObservationRecord(
                        observation_id=str(uuid4()),
                        batch_id=batch_id,
                        source_id=source.source_id,
                        instrument_id=observation.instrument_id,
                        observed_at_utc=observed_at_utc,
                        acquired_at_utc=observation.acquired_at.astimezone(UTC).isoformat(),
                        open=None if observation.open is None else format(observation.open, "f"),
                        high=None if observation.high is None else format(observation.high, "f"),
                        low=None if observation.low is None else format(observation.low, "f"),
                        close=format(observation.close, "f"),
                        volume=(
                            None if observation.volume is None else format(observation.volume, "f")
                        ),
                        currency=observation.currency,
                        quality_status=DataQualityStatus.UNVERIFIED.value,
                        original_row_json=serialize_original_row(row.original_row),
                        transformation_version="csv-market-v1",
                    )
                )
                accepted_count += 1

            batch = DataImportBatchRecord(
                batch_id=batch_id,
                source_id=source.source_id,
                original_filename=original_filename,
                file_sha256=file_sha256,
                document_relative_path=document_relative_path,
                imported_at_utc=imported_at_utc,
                row_count=row_count,
                accepted_rows=accepted_count,
                rejected_rows=len(rejected_records),
            )
            session.add(batch)
            # Persist the batch and any new UNVERIFIED instrument placeholders
            # before observations reference them through database foreign keys.
            session.flush()
            session.add_all(observation_records)
            session.add_all(
                DataImportIssueRecord(
                    issue_id=str(uuid4()),
                    batch_id=batch_id,
                    row_number=row.row_number,
                    error_message=row.error_message,
                    original_row_json=serialize_original_row(row.original_row),
                )
                for row in rejected_records
            )

            source_id = source.source_id

        return DataImportSummary(
            batch_id=batch_id,
            source_id=source_id,
            file_sha256=file_sha256,
            row_count=row_count,
            accepted_rows=accepted_count,
            rejected_rows=len(rejected_records),
        )
