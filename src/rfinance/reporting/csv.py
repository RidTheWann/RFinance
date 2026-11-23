# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Deterministic CSV rendering of the simulated portfolio ledger.

Formula version: ``ledger-csv-v1``. This module only formats explicit ledger
records supplied by the caller. It never fetches prices, invents instruments or
presents simulated activity as brokerage performance. Missing values are empty
CSV cells, never a fabricated zero.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from decimal import Decimal

    from rfinance.domain.portfolio.ledger import LedgerEvent

FORMULA_VERSION = "ledger-csv-v1"
RECORD_STATUS = "SIMULATED"

HEADER: tuple[str, ...] = (
    "sequence",
    "event_id",
    "occurred_at_utc",
    "event_type",
    "instrument_id",
    "quantity",
    "unit_price",
    "amount",
    "fees",
    "taxes",
    "currency",
    "source_reference",
    "record_status",
    "methodology_version",
    "generated_at_utc",
)


@dataclass(frozen=True, slots=True)
class LedgerCsvReport:
    """A rendered export plus the metadata needed to interpret it."""

    csv_text: str
    event_count: int
    generated_at_utc: str
    currency: str
    methodology_version: str = FORMULA_VERSION


_DANGEROUS_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _decimal_cell(value: Decimal | None) -> str:
    return "" if value is None else format(value, "f")


def _text_cell(value: str | None) -> str:
    """Neutralise spreadsheet formula prefixes in user-supplied text cells."""

    if value is None:
        return ""
    if value.startswith(_DANGEROUS_FORMULA_PREFIXES):
        return "'" + value
    return value


def render_ledger_report(
    events: Sequence[LedgerEvent],
    *,
    generated_at: datetime,
    currency: str,
) -> LedgerCsvReport:
    """Render ledger events as CSV after validating currency and sequence."""

    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")
    if len(currency) != 3 or not currency.isascii() or not currency.isupper():
        raise ValueError("currency must be a three-letter uppercase code")

    ordered = sorted(events, key=lambda event: event.sequence)
    sequences = [event.sequence for event in ordered]
    if len(set(sequences)) != len(sequences):
        raise ValueError("ledger event sequences must be unique")
    if any(event.currency != currency for event in ordered):
        raise ValueError("ledger contains an event in a different currency")

    moment = generated_at.astimezone(UTC).isoformat()
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(HEADER)
    for event in ordered:
        writer.writerow(
            (
                event.sequence,
                _text_cell(event.event_id),
                event.occurred_at.astimezone(UTC).isoformat(),
                event.event_type.value,
                _text_cell(event.instrument_id),
                _decimal_cell(event.quantity),
                _decimal_cell(event.unit_price),
                _decimal_cell(event.amount),
                _decimal_cell(event.fees),
                _decimal_cell(event.taxes),
                event.currency,
                _text_cell(event.source_reference),
                RECORD_STATUS,
                FORMULA_VERSION,
                moment,
            )
        )
    return LedgerCsvReport(
        csv_text=buffer.getvalue(),
        event_count=len(ordered),
        generated_at_utc=moment,
        currency=currency,
    )
