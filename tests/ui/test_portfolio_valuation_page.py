# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from datetime import UTC, datetime
from decimal import Decimal

from rfinance.application.portfolio_ledger import PortfolioLedgerService
from rfinance.application.portfolio_valuation import PortfolioValuationService
from rfinance.storage.database import Database
from rfinance.storage.repositories.portfolio_ledger import LedgerRepository
from rfinance.ui.portfolio_valuation_page import PortfolioValuationPage

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


def test_portfolio_valuation_page_refreshes_cash_only_ledger_off_ui_thread(
    qtbot,
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "portfolio-page.sqlite3")
    database.upgrade()
    try:
        ledger = PortfolioLedgerService(LedgerRepository(database.sessions), lot_sizes={})
        ledger.initialize_portfolio(Decimal("5000000"))
        page = PortfolioValuationPage(PortfolioValuationService(database.sessions, ledger))
        qtbot.addWidget(page)
        page.show()

        page.refresh()
        qtbot.waitUntil(
            lambda: (
                not page.is_busy and page.status_label.text().startswith("Cash-only simulation")
            ),
            timeout=30000,
        )

        assert not page.is_busy
        assert page.market_value_label.text() == "Eligible market value: Rp0.00"
        assert page.portfolio_value_label.text() == "Portfolio value: Rp5,000,000.00"
        assert page.positions_table.rowCount() == 0
        assert page.refresh_button.isEnabled()
    finally:
        database.close()
