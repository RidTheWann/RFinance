# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from PySide6.QtWidgets import QFileDialog

from rfinance.application.allocation_planning import AllocationPlanningService
from rfinance.application.instrument_category import InstrumentCategoryService
from rfinance.application.portfolio_ledger import PortfolioLedgerService
from rfinance.application.portfolio_valuation import PortfolioValuationService
from rfinance.domain.portfolio.allocation import AllocationAction
from rfinance.storage.database import Database
from rfinance.storage.models.instrument_registry import InstrumentRegistryRecord
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


def test_category_evidence_form_records_verified_decision(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    database = Database.open(tmp_path / "category-page.sqlite3")
    database.upgrade()
    evidence = tmp_path / "lot-rule.pdf"
    evidence.write_bytes(b"%PDF-1.4 test evidence")
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (str(evidence), "All files (*)"),
    )
    moment = datetime(2026, 11, 23, 12, tzinfo=UTC)
    with database.sessions.begin() as session:
        session.add(
            InstrumentRegistryRecord(
                instrument_id="IDX:BBCA",
                ticker="BBCA",
                exchange="IDX",
                instrument_type="EQUITY",
                company_name="Bank Central Asia",
                currency="IDR",
                sector="Financials",
                active=True,
                lot_size=100,
                minimum_investment=None,
                verification_status="VERIFIED",
                created_at_utc=moment.isoformat(),
                updated_at_utc=moment.isoformat(),
            )
        )
    try:
        ledger = PortfolioLedgerService(LedgerRepository(database.sessions), lot_sizes={})
        ledger.initialize_portfolio(Decimal("5000000"))
        categories = InstrumentCategoryService(database.sessions, data_directory=tmp_path / "data")
        planning = AllocationPlanningService(
            PortfolioValuationService(database.sessions, ledger),
            instrument_categories=categories,
        )
        page = AllocationPage(planning, category_service=categories)
        qtbot.addWidget(page)
        page.show()
        panel = page.category_panel
        assert panel is not None

        panel.instrument_input.setText("IDX:BBCA")
        panel.reviewer_input.setText("Operator")
        panel.notes_input.setText("Checked exchange lot rule")
        panel._choose_evidence()
        panel._record("VERIFIED")
        qtbot.waitUntil(
            lambda: not panel.is_busy and "Recorded decision" in panel.status_label.text(),
            timeout=30000,
        )
        qtbot.wait(200)

        assert panel.table.rowCount() == 1
        assert panel.table.item(0, 3).text() == "VERIFIED"
    finally:
        database.close()
