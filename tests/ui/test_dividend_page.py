from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

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
