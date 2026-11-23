# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from decimal import Decimal

from rfinance.application.ledger_reporting import LedgerReportService
from rfinance.application.portfolio_ledger import PortfolioLedgerService
from rfinance.domain.portfolio.ledger import LedgerEvent, LedgerEventType
from rfinance.storage.database import Database
from rfinance.storage.repositories.portfolio_ledger import LedgerRepository

NOW = datetime(2026, 11, 23, 12, tzinfo=UTC)


def test_ledger_export_reconciles_with_replayed_events(tmp_path) -> None:
    database = Database.open(tmp_path / "ledger-report.sqlite3")
    database.upgrade()
    try:
        ledger = PortfolioLedgerService(LedgerRepository(database.sessions), lot_sizes={})
        ledger.initialize_portfolio(Decimal("5000000"))
        ledger.append(
            LedgerEvent(
                event_id="withdrawal-1",
                sequence=2,
                occurred_at=NOW,
                event_type=LedgerEventType.CASH_WITHDRAWAL,
                amount=Decimal("250000"),
            )
        )

        report = LedgerReportService(ledger).ledger_csv(generated_at=NOW)
        parsed = list(csv.DictReader(io.StringIO(report.csv_text)))

        assert report.event_count == 2
        assert [row["event_type"] for row in parsed] == [
            "CAPITAL_INJECTION",
            "CASH_WITHDRAWAL",
        ]
        assert parsed[0]["amount"] == "5000000"
        assert parsed[1]["amount"] == "250000"
        assert all(row["record_status"] == "SIMULATED" for row in parsed)
        assert ledger.snapshot().cash_balance == Decimal("4750000")
    finally:
        database.close()
