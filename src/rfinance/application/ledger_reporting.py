# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Application service for exporting the simulated ledger."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from rfinance.reporting.csv import render_ledger_report

if TYPE_CHECKING:
    from rfinance.application.portfolio_ledger import PortfolioLedgerService
    from rfinance.reporting.csv import LedgerCsvReport


class LedgerReportService:
    """Render a user-controlled export from the authoritative ledger."""

    def __init__(self, ledger: PortfolioLedgerService) -> None:
        self._ledger = ledger

    def ledger_csv(self, *, generated_at: datetime | None = None) -> LedgerCsvReport:
        """Export every recorded event exactly as replayed for the ledger."""

        moment = datetime.now(UTC) if generated_at is None else generated_at
        return render_ledger_report(
            self._ledger.events(),
            generated_at=moment,
            currency=self._ledger.base_currency,
        )
