"""Application service for safe, provenance-preserving local market CSV imports."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import os
from pathlib import Path
import re
import shutil
from uuid import uuid4

from rfinance.data.csv_market_import import CSVImportError, parse_market_observation_csv
from rfinance.storage.repositories.data_ingestion import (
    DataImportSummary,
    DataIngestionRepository,
)


MAX_MARKET_CSV_BYTES = 50 * 1024 * 1024


class MarketCSVImportService:
    """Imports only an explicitly selected local CSV; never fetches remote sources."""

    def __init__(
        self,
        repository: DataIngestionRepository,
        *,
        data_directory: Path,
        max_file_bytes: int = MAX_MARKET_CSV_BYTES,
    ) -> None:
        if max_file_bytes <= 0:
            raise ValueError("max_file_bytes must be positive")
        self._repository = repository
        self._data_directory = data_directory.resolve()
        self._documents_directory = self._data_directory / "Documents"
        self._max_file_bytes = max_file_bytes

    def import_market_csv(
        self,
        selected_file: Path,
        *,
        source_name: str,
    ) -> DataImportSummary:
        """Copy, hash, parse, validate and atomically persist a user-selected CSV."""

        normalized_source_name = source_name.strip()
        if not normalized_source_name:
            raise ValueError("source_name must not be blank")
        if len(normalized_source_name) > 256:
            raise ValueError("source_name must not exceed 256 characters")

        source_path = selected_file.expanduser().resolve(strict=True)
        if not source_path.is_file():
            raise CSVImportError("the selected path is not a regular file")
        if source_path.suffix.lower() != ".csv":
            raise CSVImportError("only .csv files are supported by this import workflow")
        if source_path.stat().st_size > self._max_file_bytes:
            raise CSVImportError(
                f"CSV file exceeds the {self._max_file_bytes // (1024 * 1024)} MiB limit"
            )

        batch_id = str(uuid4())
        safe_filename = re.sub(r"[^A-Za-z0-9._-]+", "_", source_path.name)[:120]
        if not safe_filename:
            safe_filename = "market-data.csv"

        import_directory = self._documents_directory / "MarketImports"
        import_directory.mkdir(parents=True, exist_ok=True)
        destination_name = f"{batch_id}_{safe_filename}"
        destination_path = import_directory / destination_name
        temporary_path = import_directory / f".{destination_name}.part"

        digest = hashlib.sha256()
        copied_bytes = 0
        try:
            with source_path.open("rb") as source, temporary_path.open("xb") as target:
                while chunk := source.read(1024 * 1024):
                    copied_bytes += len(chunk)
                    if copied_bytes > self._max_file_bytes:
                        raise CSVImportError("CSV grew beyond the configured size limit")
                    digest.update(chunk)
                    target.write(chunk)
                target.flush()
                os.fsync(target.fileno())

            acquired_at = datetime.now(UTC)
            parsed = parse_market_observation_csv(temporary_path, acquired_at=acquired_at)
            temporary_path.replace(destination_path)
            relative_path = destination_path.relative_to(self._data_directory).as_posix()

            return self._repository.persist_market_csv_import(
                batch_id=batch_id,
                source_name=normalized_source_name,
                original_filename=source_path.name[:512],
                file_sha256=digest.hexdigest(),
                document_relative_path=relative_path,
                imported_at=acquired_at,
                accepted_rows=parsed.accepted,
                rejected_rows=parsed.rejected,
            )
        except Exception:
            temporary_path.unlink(missing_ok=True)
            destination_path.unlink(missing_ok=True)
            raise
