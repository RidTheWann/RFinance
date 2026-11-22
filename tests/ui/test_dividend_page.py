# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import Qt

from rfinance.application.dividend_events import (
    DividendEventService,
    DividendReviewDecision,
)
from rfinance.data.contracts import DividendEventContract, DividendEventStatus, DividendType
from rfinance.storage.database import Database
from rfinance.storage.models.instrument_registry import InstrumentRegistryRecord
from rfinance.ui.dividend_page import DividendPage

NOW = datetime(2026, 11, 21, 10, 0, tzinfo=UTC)
DIGEST = "b" * 64


def seed(database: Database) -> DividendEventService:
    with database.sessions.begin() as session:
        session.add(
            InstrumentRegistryRecord(
                instrument_id="IDX:BBCA",
                verification_status="VERIFIED",
                created_at_utc=NOW.isoformat(),
                updated_at_utc=NOW.isoformat(),
            )
        )
    service = DividendEventService(database.sessions, data_directory=Path("unused"))
    recorded = service.record_event(
        DividendEventContract(
            event_key="cash-2026",
            instrument_id="IDX:BBCA",
            source_label="Annual report",
            dividend_type=DividendType.CASH,
            event_status=DividendEventStatus.CONFIRMED,
            amount_per_share=Decimal("150"),
            currency="IDR",
            ex_date=date(2026, 5, 20),
            payment_date=date(2026, 6, 5),
            acquired_at=NOW,
        ),
        recorded_at=NOW,
    )
    service.review_event(
        recorded.event_id,
        decision=DividendReviewDecision.VERIFIED,
        reviewer_label="Operator",
        evidence_reference="Documents/report.pdf",
        evidence_sha256=DIGEST,
        notes="Confirmed against the issuer report",
    )
    return service


def test_dividend_page_renders_persisted_events_calendar_and_analytics(qtbot, tmp_path) -> None:
    database = Database.open(tmp_path / "dividend-ui.sqlite3")
    database.upgrade()
    try:
        service = seed(database)
        page = DividendPage(service)
        qtbot.addWidget(page)
        page.show()

        assert page.events_table.rowCount() == 1
        assert page.events_table.item(0, 0).text() == "IDX:BBCA"
        assert page.events_table.item(0, 8).text() == "VERIFIED"
        assert page.events_table.item(0, 9).text() == "Annual report"
        assert page.history_table.rowCount() == 1

        page.calendar_start_input.setText("2026-01-01")
        page.calendar_end_input.setText("2026-12-31")
        page.refresh_calendar()
        assert page.calendar_table.rowCount() == 2
        interpretations = {
            page.calendar_table.item(row, 8).text() for row in range(page.calendar_table.rowCount())
        }
        assert interpretations == {"VERIFIED observed cash"}

        report = service.analytics(
            instrument_id="IDX:BBCA",
            as_of=date(2026, 11, 21),
            currency="IDR",
            price=Decimal("9500"),
        )
        page._render_analytics(report)
        assert "1.58% TRAILING (observed)" in page.analytics_result_label.text()
        assert "gross only (withholding unknown)" in page.analytics_result_label.text()
        assert "dividend-analytics-v1" in page.analytics_result_label.text()
    finally:
        database.close()


def test_dividend_page_posts_confirmed_receipt_and_shows_allocation(qtbot, tmp_path: Path) -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    from rfinance.application.dividend_events import DividendEventService, DividendReviewDecision
    from rfinance.application.dividend_receipts import DividendReceiptService
    from rfinance.application.portfolio_ledger import PortfolioLedgerService
    from rfinance.data.contracts import (
        DividendEventContract,
        DividendEventStatus,
        DividendType,
    )
    from rfinance.storage.models.instrument_registry import InstrumentRegistryRecord
    from rfinance.storage.repositories.portfolio_ledger import LedgerRepository
    from rfinance.ui.dividend_page import DividendPage

    database = Database.open(tmp_path / "receipt-ui.sqlite3")
    database.upgrade()
    moment = datetime(2026, 11, 22, 10, tzinfo=UTC)
    with database.sessions.begin() as session:
        session.add(
            InstrumentRegistryRecord(
                instrument_id="IDX:BBCA",
                verification_status="VERIFIED",
                created_at_utc=moment.isoformat(),
                updated_at_utc=moment.isoformat(),
            )
        )
    events_service = DividendEventService(database.sessions)
    recorded = events_service.record_event(
        DividendEventContract(
            event_key="cash-2026",
            instrument_id="IDX:BBCA",
            source_label="Annual report",
            dividend_type=DividendType.CASH,
            event_status=DividendEventStatus.CONFIRMED,
            amount_per_share=Decimal("500"),
            currency="IDR",
            ex_date=date(2026, 5, 20),
            acquired_at=moment,
        ),
        recorded_at=moment,
    )
    events_service.review_event(
        recorded.event_id,
        decision=DividendReviewDecision.VERIFIED,
        reviewer_label="Operator",
        evidence_reference="Documents/report.pdf",
        evidence_sha256="c" * 64,
        notes="Confirmed",
    )
    ledger = PortfolioLedgerService(LedgerRepository(database.sessions), lot_sizes={})
    ledger.initialize_portfolio(Decimal("5000000"))
    receipts = DividendReceiptService(
        database.sessions,
        dividend_events=events_service,
        portfolio_ledger=ledger,
    )

    try:
        page = DividendPage(events_service, receipts=receipts)
        qtbot.addWidget(page)
        page.show()
        page.events_table.selectRow(0)

        page.receipt_amount_input.setText("100000")
        qtbot.mouseClick(page.post_receipt_button, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(
            lambda: page.receipt_result_label.text().startswith("Receipt posted:"),
            timeout=30000,
        )

        assert "50,000" in page.receipt_result_label.text()
        assert "30,000" in page.receipt_result_label.text()
        assert "20,000" in page.receipt_result_label.text()
        assert ledger.snapshot().confirmed_dividend_income == Decimal("100000")
    finally:
        page.close()
        database.close()
