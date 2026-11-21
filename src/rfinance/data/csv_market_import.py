# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Strict parser for user-supplied market-observation CSV files."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from typing import TYPE_CHECKING

from rfinance.data.contracts import DataQualityStatus, MarketObservationContract

if TYPE_CHECKING:
    from collections.abc import Mapping


REQUIRED_COLUMNS = frozenset({"instrument_id", "observed_at", "currency", "close"})
OPTIONAL_COLUMNS = frozenset({"open", "high", "low", "volume"})
ALLOWED_COLUMNS = REQUIRED_COLUMNS | OPTIONAL_COLUMNS
MAX_IMPORT_ROWS = 500_000


class CSVImportError(ValueError):
    """The CSV file has an unsupported schema or cannot be decoded."""


@dataclass(frozen=True, slots=True)
class ParsedMarketCSVRow:
    row_number: int
    original_row: Mapping[str, str | None]
    observation: MarketObservationContract


@dataclass(frozen=True, slots=True)
class RejectedMarketCSVRow:
    row_number: int
    original_row: Mapping[str, str | None]
    error_message: str


@dataclass(frozen=True, slots=True)
class MarketCSVParseResult:
    accepted: tuple[ParsedMarketCSVRow, ...]
    rejected: tuple[RejectedMarketCSVRow, ...]

    @property
    def row_count(self) -> int:
        return len(self.accepted) + len(self.rejected)


def _decimal_value(
    row: Mapping[str, str | None],
    column: str,
    *,
    required: bool = False,
) -> Decimal | None:
    raw_value = row.get(column)
    if raw_value is None or not raw_value.strip():
        if required:
            raise ValueError(f"{column} is required")
        return None
    try:
        value = Decimal(raw_value.strip())
    except InvalidOperation as error:
        raise ValueError(f"{column} must be a plain decimal number") from error
    if not value.is_finite():
        raise ValueError(f"{column} must be finite")
    return value


def _observation_from_row(
    row: Mapping[str, str | None],
    *,
    acquired_at: datetime,
) -> MarketObservationContract:
    instrument_id = row.get("instrument_id")
    if instrument_id is None or not instrument_id.strip():
        raise ValueError("instrument_id is required")

    observed_at_raw = row.get("observed_at")
    if observed_at_raw is None or not observed_at_raw.strip():
        raise ValueError("observed_at is required and must include a timezone")
    try:
        observed_at = datetime.fromisoformat(
            observed_at_raw.strip().replace("Z", "+00:00")
        )
    except ValueError as error:
        raise ValueError("observed_at must be an ISO-8601 timestamp with timezone") from error

    currency = row.get("currency")
    if currency is None or not currency.strip():
        raise ValueError("currency is required")

    return MarketObservationContract.model_validate(
        {
            "instrument_id": instrument_id.strip(),
            "observed_at": observed_at,
            "acquired_at": acquired_at,
            "open": _decimal_value(row, "open"),
            "high": _decimal_value(row, "high"),
            "low": _decimal_value(row, "low"),
            "close": _decimal_value(row, "close", required=True),
            "volume": _decimal_value(row, "volume"),
            "currency": currency.strip(),
            "source_id": "pending-user-import",
            "quality_status": DataQualityStatus.UNVERIFIED,
        }
    )


def parse_market_observation_csv(
    path: Path,
    *,
    acquired_at: datetime,
    max_rows: int = MAX_IMPORT_ROWS,
) -> MarketCSVParseResult:
    """Parse a canonical CSV schema; row-level defects are retained as rejections."""

    if acquired_at.tzinfo is None or acquired_at.utcoffset() is None:
        raise ValueError("acquired_at must be timezone-aware")
    if max_rows <= 0:
        raise ValueError("max_rows must be positive")

    accepted: list[ParsedMarketCSVRow] = []
    rejected: list[RejectedMarketCSVRow] = []
    seen_keys: set[tuple[str, str]] = set()

    try:
        handle = path.open("r", encoding="utf-8-sig", newline="")
    except OSError as error:
        raise CSVImportError(f"could not open the selected CSV file: {error}") from error

    try:
        with handle:
            reader = csv.DictReader(handle, strict=True)
            if reader.fieldnames is None:
                raise CSVImportError("CSV header row is missing")

            fieldnames = [name.strip() for name in reader.fieldnames]
            if any(not name for name in fieldnames):
                raise CSVImportError("CSV headers cannot be blank")
            if len(set(fieldnames)) != len(fieldnames):
                raise CSVImportError("CSV contains duplicate column names")

            missing = REQUIRED_COLUMNS - set(fieldnames)
            unknown = set(fieldnames) - ALLOWED_COLUMNS
            if missing:
                raise CSVImportError(
                    "CSV is missing required columns: " + ", ".join(sorted(missing))
                )
            if unknown:
                raise CSVImportError(
                    "CSV contains unsupported columns: " + ", ".join(sorted(unknown))
                )
            reader.fieldnames = fieldnames

            for row in reader:
                row_number = reader.line_num
                if row_number - 1 > max_rows:
                    raise CSVImportError(
                        f"CSV exceeds the maximum of {max_rows:,} data rows"
                    )

                original_row = {
                    key: value for key, value in row.items() if isinstance(key, str)
                }
                extras = row.get(None)
                try:
                    if extras:
                        raise ValueError("row contains more values than the CSV header")
                    observation = _observation_from_row(
                        original_row,
                        acquired_at=acquired_at,
                    )
                    key = (
                        observation.instrument_id,
                        observation.observed_at.isoformat(),
                    )
                    if key in seen_keys:
                        raise ValueError(
                            "duplicate instrument_id and observed_at within this CSV"
                        )
                    seen_keys.add(key)
                    accepted.append(
                        ParsedMarketCSVRow(
                            row_number=row_number,
                            original_row=original_row,
                            observation=observation,
                        )
                    )
                except (ValueError, TypeError) as error:
                    rejected.append(
                        RejectedMarketCSVRow(
                            row_number=row_number,
                            original_row=original_row,
                            error_message=str(error),
                        )
                    )
    except csv.Error as error:
        raise CSVImportError(f"CSV syntax error near line {reader.line_num}: {error}") from error
    except UnicodeDecodeError as error:
        raise CSVImportError("CSV must be encoded as UTF-8 or UTF-8 with BOM") from error

    return MarketCSVParseResult(
        accepted=tuple(accepted),
        rejected=tuple(rejected),
    )


def serialize_original_row(row: Mapping[str, str | None]) -> str:
    """Serialize raw source cells without converting missing values to zero."""

    return json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
