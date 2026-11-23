# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from rfinance.domain.portfolio.ledger import LedgerEvent, LedgerEventType
from rfinance.reporting.csv import FORMULA_VERSION, HEADER, RECORD_STATUS, render_ledger_report

GENERATED = datetime(2026, 11, 23, 12, tzinfo=UTC)
OCCURRED = datetime(2026, 11, 20, 9, tzinfo=UTC)


def make_event(sequence: int, **overrides: object) -> LedgerEvent:
    values: dict[str, object] = {
        "event_id": f"event-{sequence}",
        "sequence": sequence,
        "occurred_at": OCCURRED,
        "event_type": LedgerEventType.CAPITAL_INJECTION,
        "amount": Decimal("5000000"),
    }
    values.update(overrides)
    return LedgerEvent(**values)  # type: ignore[arg-type]


def rows(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text)))


def test_report_has_documented_header_and_simulation_label() -> None:
    report = render_ledger_report([make_event(1)], generated_at=GENERATED, currency="IDR")

    parsed = rows(report.csv_text)
    assert tuple(parsed[0]) == HEADER
    assert report.event_count == 1
    assert report.currency == "IDR"
    assert report.methodology_version == FORMULA_VERSION
    assert parsed[1][parsed[0].index("record_status")] == RECORD_STATUS
    assert parsed[1][parsed[0].index("methodology_version")] == FORMULA_VERSION
    assert parsed[1][parsed[0].index("generated_at_utc")] == GENERATED.isoformat()
    assert parsed[1][parsed[0].index("amount")] == "5000000"


def test_missing_optional_values_are_empty_not_zero() -> None:
    cash_event = make_event(1)
    trade_event = make_event(
        2,
        event_type=LedgerEventType.BUY,
        amount=None,
        instrument_id="IDX:BBCA",
        quantity=Decimal("10"),
        unit_price=Decimal("9500"),
    )
    report = render_ledger_report([cash_event, trade_event], generated_at=GENERATED, currency="IDR")

    parsed = rows(report.csv_text)
    header = parsed[0]
    assert parsed[1][header.index("quantity")] == ""
    assert parsed[1][header.index("instrument_id")] == ""
    assert parsed[2][header.index("amount")] == ""
    assert parsed[2][header.index("quantity")] == "10"
    assert parsed[1][header.index("fees")] == "0"


def test_csv_escaping_preserves_source_reference() -> None:
    reference = 'Issuer "Q3", report.pdf'
    event = make_event(
        1,
        event_type=LedgerEventType.SIMULATED_DIVIDEND,
        amount=Decimal("100000"),
        instrument_id="IDX:BBCA",
        source_reference=reference,
    )
    report = render_ledger_report([event], generated_at=GENERATED, currency="IDR")

    parsed = rows(report.csv_text)
    assert parsed[1][parsed[0].index("source_reference")] == reference


def test_events_are_ordered_by_sequence() -> None:
    first = make_event(1)
    second = make_event(2, event_type=LedgerEventType.CASH_WITHDRAWAL, amount=Decimal("1000"))
    report = render_ledger_report([second, first], generated_at=GENERATED, currency="IDR")

    parsed = rows(report.csv_text)
    assert [row[0] for row in parsed[1:]] == ["1", "2"]


def test_mismatched_currency_is_rejected() -> None:
    event = make_event(1, currency="USD")
    with pytest.raises(ValueError, match="currency"):
        render_ledger_report([event], generated_at=GENERATED, currency="IDR")


def test_duplicate_sequences_are_rejected() -> None:
    with pytest.raises(ValueError, match="unique"):
        render_ledger_report([make_event(1), make_event(1)], generated_at=GENERATED, currency="IDR")


def test_naive_generation_time_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        render_ledger_report(
            [make_event(1)], generated_at=datetime(2026, 11, 23, 12), currency="IDR"
        )
