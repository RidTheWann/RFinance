from datetime import UTC, datetime

from rfinance.application.historical_price_series import HistoricalPriceSeriesService
from rfinance.application.technical_analysis import TechnicalAnalysisService
from rfinance.storage.database import Database
from rfinance.storage.models.data_ingestion import (
    DataImportBatchRecord,
    MarketObservationRecord,
    SourceRegistryRecord,
)
from rfinance.storage.models.instrument_registry import InstrumentRegistryRecord
from rfinance.ui.technical_analysis_page import TechnicalAnalysisPage


def test_technical_analysis_page_loads_local_catalog_and_calculates_off_ui_thread(
    qtbot,
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "technical-page.sqlite3")
    database.upgrade()
    observed_at = datetime.now(UTC)
    acquired_at = datetime.now(UTC)
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
                created_at_utc=acquired_at.isoformat(),
                updated_at_utc=acquired_at.isoformat(),
            )
        )
        session.add(
            SourceRegistryRecord(
                source_id="source-user",
                display_name="User supplied prices",
                access_method="USER_IMPORT",
                policy_status="UNREVIEWED",
                description="User-provided price history",
                terms_url=None,
                reviewed_at_utc=None,
                automated_access_allowed=False,
                redistribution_allowed=False,
                created_at_utc=acquired_at.isoformat(),
            )
        )
        session.flush()
        session.add(
            DataImportBatchRecord(
                batch_id="batch-tech",
                source_id="source-user",
                original_filename="history.csv",
                file_sha256="d" * 64,
                document_relative_path="Documents/MarketImports/history.csv",
                imported_at_utc=acquired_at.isoformat(),
                row_count=1,
                accepted_rows=1,
                rejected_rows=0,
            )
        )
        session.flush()
        session.add(
            MarketObservationRecord(
                observation_id="tech-price",
                batch_id="batch-tech",
                source_id="source-user",
                instrument_id="IDX:BBCA",
                observed_at_utc=observed_at.isoformat(),
                acquired_at_utc=acquired_at.isoformat(),
                open="10000",
                high="10100",
                low="9900",
                close="10000",
                volume="100000",
                currency="IDR",
                quality_status="VERIFIED",
                original_row_json="{}",
                transformation_version="test-v1",
            )
        )

    try:
        service = TechnicalAnalysisService(HistoricalPriceSeriesService(database.sessions))
        page = TechnicalAnalysisPage(service)
        qtbot.addWidget(page)
        page.show()

        page.refresh_catalog()
        qtbot.waitUntil(
            lambda: (
                not page.is_busy
                and page.status_label.text().startswith("Loaded 1 verified instrument")
            ),
            timeout=10000,
        )
        assert page.instrument_combo.count() == 1
        assert page.source_combo.count() == 1

        page.analyze()
        qtbot.waitUntil(
            lambda: (
                not page.is_busy
                and page.status_label.text().startswith("1 verified historical bar")
            ),
            timeout=10000,
        )

        assert page.summary_label.text().startswith("BBCA — Bank Central Asia")
        assert "UNKNOWN_AS_SUPPLIED" in page.status_label.text()
        assert page.indicator_table.rowCount() == 14
        assert page.indicator_table.item(0, 1).text().startswith("—")
        assert page.indicator_table.item(0, 1).toolTip().find("technical-decimal-v1") >= 0
    finally:
        database.close()
