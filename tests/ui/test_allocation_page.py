# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from decimal import Decimal

from rfinance.application.allocation_planning import AllocationPlanningService
from rfinance.application.portfolio_ledger import PortfolioLedgerService
from rfinance.application.portfolio_valuation import PortfolioValuationService
from rfinance.domain.portfolio.allocation import AllocationAction
from rfinance.storage.database import Database
from rfinance.storage.repositories.portfolio_ledger import LedgerRepository
from rfinance.ui.allocation_page import AllocationPage


def test_allocation_page_shows_unfilled_targets_off_ui_thread(qtbot, tmp_path) -> None:
    database = Database.open(tmp_path / "allocation-page.sqlite3")
    database.upgrade()
    try:
        ledger = PortfolioLedgerService(LedgerRepository(database.sessions), lot_sizes={})
        ledger.initialize_portfolio(Decimal("5000000"))
        service = AllocationPlanningService(PortfolioValuationService(database.sessions, ledger))
        page = AllocationPage(service)
        qtbot.addWidget(page)
        page.show()

        qtbot.waitUntil(
            lambda: (
                not page.is_busy
                and page.summary_label.text().startswith("Portfolio value: Rp5,000,000.00")
            ),
            timeout=30000,
        )

        assert page.table.rowCount() == 3
        assert [page.table.item(row, 5).text() for row in range(3)] == [
            AllocationAction.UNFILLED_TARGET.value
        ] * 3
        assert page.table.item(0, 2).text() == "Rp2,500,000.00"
        qtbot.wait(200)
        assert page.refresh_button.isEnabled()
    finally:
        database.close()
