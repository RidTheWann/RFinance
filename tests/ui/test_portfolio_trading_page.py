# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import Qt

from rfinance.application.portfolio_ledger import PortfolioLedgerService
from rfinance.storage.database import Database
from rfinance.storage.repositories.portfolio_ledger import LedgerRepository
from rfinance.ui.portfolio_trading_page import PortfolioTradingPage


def test_trading_page_records_buy_from_verified_lot(qtbot, tmp_path: Path, monkeypatch) -> None:
    from rfinance.application.portfolio_trading import (
        PortfolioTradingService,
        VerifiedLotSizeService,
    )
    from rfinance.storage.models.instrument_registry import (
        InstrumentRegistryRecord,
        InstrumentReviewEventRecord,
    )

    database = Database.open(tmp_path / "trade-ui.sqlite3")
    database.upgrade()
    from datetime import UTC, datetime

    moment = datetime(2026, 11, 22, 12, tzinfo=UTC)
    with database.sessions.begin() as session:
        session.add(
            InstrumentRegistryRecord(
                instrument_id="IDX:BBCA",
                verification_status="VERIFIED",
                lot_size=100,
                active=True,
                currency="IDR",
                created_at_utc=moment.isoformat(),
                updated_at_utc=moment.isoformat(),
                last_reviewed_at_utc=moment.isoformat(),
                last_review_id="r1",
            )
        )
        session.add(
            InstrumentReviewEventRecord(
                review_id="r1",
                instrument_id="IDX:BBCA",
                previous_status="UNVERIFIED",
                decision="VERIFIED",
                reviewed_at_utc=moment.isoformat(),
                reviewer_label="Operator",
                evidence_reference="Documents/lot.pdf",
                evidence_sha256="a" * 64,
                notes="Verified lot rule",
            )
        )

    repository = LedgerRepository(database.sessions)
    ledger = PortfolioLedgerService(repository, lot_sizes={})
    ledger.initialize_portfolio(Decimal("5000000"))
    lots = VerifiedLotSizeService(database.sessions)
    service = PortfolioTradingService(repository, lot_sizes=lots)

    page = PortfolioTradingPage(service, ledger, lots)
    monkeypatch.setattr(
        page,
        "_start_worker",
        lambda operation, on_success: on_success(operation()),
    )
    qtbot.addWidget(page)
    page.show()

    page.instrument_input.setText("IDX:BBCA")
    page.quantity_input.setText("100")
    page.price_input.setText("9500")
    qtbot.mouseClick(page.submit_button, Qt.MouseButton.LeftButton)

    assert "BUY" in page.status_label.text()
    assert "4,050,000" in page.status_label.text()
    check_ledger = PortfolioLedgerService(repository, lot_sizes=lots.lot_sizes())
    assert check_ledger.snapshot().positions["IDX:BBCA"].quantity == Decimal("100")
