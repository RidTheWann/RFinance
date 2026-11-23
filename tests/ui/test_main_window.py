# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QInputDialog
from sqlalchemy import func, select

from rfinance.application.allocation_planning import AllocationPlanningService
from rfinance.application.dividend_events import DividendEventService
from rfinance.application.dividend_receipts import DividendReceiptService
from rfinance.application.historical_price_series import HistoricalPriceSeriesService
from rfinance.application.instrument_review import InstrumentReviewService
from rfinance.application.ledger_reporting import LedgerReportService
from rfinance.application.market_csv_import import MarketCSVImportService
from rfinance.application.observation_review import ObservationReviewService
from rfinance.application.portfolio_ledger import PortfolioLedgerService
from rfinance.application.portfolio_trading import (
    PortfolioTradingService,
    VerifiedLotSizeService,
)
from rfinance.application.portfolio_valuation import PortfolioValuationService
from rfinance.application.recommendations import RecommendationService
from rfinance.application.risk_monitoring import RiskMonitoringService
from rfinance.application.screening_evaluation import ScreeningEvaluationService
from rfinance.application.technical_analysis import TechnicalAnalysisService
from rfinance.core.config import AppPaths
from rfinance.storage.database import Database
from rfinance.storage.models.data_ingestion import MarketObservationRecord
from rfinance.storage.repositories.data_ingestion import DataIngestionRepository
from rfinance.storage.repositories.portfolio_ledger import LedgerRepository
from rfinance.ui.main_window import MainWindow


def create_window(database: Database, tmp_path) -> MainWindow:
    data_directory = tmp_path / "rfinance-data"
    portfolio_service = PortfolioLedgerService(
        LedgerRepository(database.sessions),
        lot_sizes={},
    )
    import_service = MarketCSVImportService(
        DataIngestionRepository(database.sessions),
        data_directory=data_directory,
    )
    instrument_review_service = InstrumentReviewService(
        database.sessions,
        data_directory=data_directory,
    )
    dividend_events = DividendEventService(database.sessions, data_directory=data_directory)
    receipt_service = DividendReceiptService(
        database.sessions,
        dividend_events=dividend_events,
        portfolio_ledger=portfolio_service,
    )
    recommendation_service = RecommendationService(database.sessions)
    evaluation_service = ScreeningEvaluationService(
        database.sessions,
        dividend_events=dividend_events,
        observation_review=ObservationReviewService(database.sessions),
        recommendations=recommendation_service,
    )
    observation_review_service = ObservationReviewService(
        database.sessions,
        data_directory=data_directory,
    )
    verified_lots = VerifiedLotSizeService(database.sessions)
    trading_service = PortfolioTradingService(
        LedgerRepository(database.sessions), lot_sizes=verified_lots
    )
    portfolio_valuation_service = PortfolioValuationService(
        database.sessions,
        portfolio_service,
    )
    return MainWindow(
        AppPaths.resolve(data_directory),
        portfolio_service,
        import_service,
        instrument_review_service,
        observation_review_service,
        trading_service,
        verified_lots,
        portfolio_valuation_service,
        TechnicalAnalysisService(HistoricalPriceSeriesService(database.sessions)),
        dividend_events,
        receipt_service,
        recommendation_service,
        evaluation_service,
        RiskMonitoringService(database.sessions),
        LedgerReportService(portfolio_service),
        AllocationPlanningService(portfolio_valuation_service),
    )


def test_main_window_navigation_and_initial_portfolio_setup(qtbot, tmp_path) -> None:
    database = Database.open(tmp_path / "rfinance.sqlite3")
    database.upgrade()
    try:
        window = create_window(database, tmp_path)
        qtbot.addWidget(window)
        window.show()
        window.navigation.setCurrentRow(1)

        assert window.windowTitle() == "RFinance"
        assert window.navigation.count() == 9
        assert [window.navigation.item(row).text() for row in range(9)] == [
            "Overview",
            "Portfolio",
            "Research Center",
            "Instrument Review",
            "Observation Review",
            "Technical Analysis",
            "Dividend Center",
            "Risk Management",
            "Settings",
        ]
        assert window.pages.count() == 9
        assert window.dividend_page is not None
        assert window.research_page is not None
        assert window.risk_page is not None
        assert window.allocation_page is not None
        assert window.initial_capital_input.text() == "5000000"
        assert not window._portfolio_empty_panel.isHidden()
        assert window._portfolio_dashboard.isHidden()

        assert window.pages.currentIndex() == 1
        window.initial_capital_input.setText("1250000")
        qtbot.mouseClick(window.initialize_portfolio_button, Qt.MouseButton.LeftButton)
        assert window.portfolio_valuation_page is not None
        qtbot.waitUntil(
            lambda: (
                window.portfolio_valuation_page is not None
                and window.portfolio_valuation_page.status_label.text().startswith(
                    "Cash-only simulation"
                )
            ),
            timeout=30000,
        )

        assert window.portfolio_ledger.snapshot().cash_balance == Decimal("1250000")
        assert len(window.portfolio_ledger.events()) == 1
        assert window.portfolio_ledger.events()[0].event_type.value == "CAPITAL_INJECTION"
        assert not window._portfolio_dashboard.isHidden()
        assert window._portfolio_empty_panel.isHidden()
        assert window.portfolio_cash_label.text() == "Cash balance: Rp1,250,000.00"
    finally:
        database.close()


def test_export_ledger_csv_writes_simulated_records(qtbot, tmp_path, monkeypatch) -> None:
    database = Database.open(tmp_path / "export-ledger.sqlite3")
    database.upgrade()
    target = tmp_path / "ledger.csv"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(target), "CSV files (*.csv)"),
    )
    try:
        window = create_window(database, tmp_path)
        qtbot.addWidget(window)
        window.show()
        window.navigation.setCurrentRow(1)
        window.initial_capital_input.setText("5000000")
        qtbot.mouseClick(window.initialize_portfolio_button, Qt.MouseButton.LeftButton)

        qtbot.mouseClick(window.export_ledger_button, Qt.MouseButton.LeftButton)

        text = target.read_text(encoding="utf-8")
        assert "event_type" in text
        assert "CAPITAL_INJECTION" in text
        assert "SIMULATED" in text
        assert "ledger-csv-v1" in text
        assert "Exported 1 simulated ledger event(s)" in window.portfolio_status_label.text()
    finally:
        database.close()


def test_invalid_initial_capital_does_not_create_ledger_event(qtbot, tmp_path) -> None:
    database = Database.open(tmp_path / "invalid-capital.sqlite3")
    database.upgrade()
    try:
        window = create_window(database, tmp_path)
        qtbot.addWidget(window)
        window.show()
        window.navigation.setCurrentRow(1)
        window.initial_capital_input.setText("not-a-number")

        qtbot.mouseClick(window.initialize_portfolio_button, Qt.MouseButton.LeftButton)

        assert window.portfolio_ledger.events() == ()
        assert "not initialized" in window.portfolio_status_label.text()
        assert not window._portfolio_empty_panel.isHidden()
    finally:
        database.close()


def test_market_csv_import_is_started_off_ui_thread_and_reported(
    qtbot, tmp_path, monkeypatch
) -> None:
    database = Database.open(tmp_path / "market-import.sqlite3")
    database.upgrade()
    csv_file = tmp_path / "market.csv"
    csv_file.write_text(
        "instrument_id,observed_at,currency,close\nIDX:BBCA,2026-11-20T09:00:00+07:00,IDR,9100\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (str(csv_file), "CSV files (*.csv)"),
    )
    monkeypatch.setattr(
        QInputDialog,
        "getText",
        lambda *_args, **_kwargs: ("User-supplied BBCA file", True),
    )
    try:
        window = create_window(database, tmp_path)
        qtbot.addWidget(window)
        window.show()

        qtbot.mouseClick(window.import_market_csv_button, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(
            lambda: (
                window._import_thread is None
                and window.market_import_status_label.text().startswith("Import complete")
            ),
            timeout=30000,
        )

        assert "1 observations accepted, 0 rows rejected" in (
            window.market_import_status_label.text()
        )
        assert "UNVERIFIED" in window.market_import_status_label.text()
        assert window.market_import_history_table.rowCount() == 1
        assert window.market_import_history_table.item(0, 1).text() == "User-supplied BBCA file"
        assert window.market_import_history_table.item(0, 5).text() == "UNVERIFIED"
        assert "SHA-256:" in window.market_import_history_table.item(0, 2).toolTip()
        assert window.instrument_review_table.rowCount() == 1
        assert window.instrument_review_table.item(0, 0).text() == "IDX:BBCA"
        assert window.instrument_review_table.item(0, 6).text() == "UNVERIFIED"
        assert not window.instrument_review_empty_label.isVisible()
        assert window.observation_review_page.observation_table.rowCount() == 1
        assert window.observation_review_page.observation_table.item(0, 1).text() == "IDX:BBCA"
        assert window.observation_review_page.observation_table.item(0, 4).text() == "UNVERIFIED"
        assert window.observation_review_page.observation_table.item(0, 5).text() == "UNVERIFIED"
        with database.sessions() as session:
            observation = session.scalar(select(MarketObservationRecord))
            assert observation is not None
            assert observation.quality_status == "UNVERIFIED"
            assert session.scalar(select(func.count()).select_from(MarketObservationRecord)) == 1
    finally:
        database.close()
