from decimal import Decimal

from PySide6.QtCore import Qt

from rfinance.application.portfolio_ledger import PortfolioLedgerService
from rfinance.core.config import AppPaths
from rfinance.storage.database import Database
from rfinance.storage.repositories.portfolio_ledger import LedgerRepository
from rfinance.ui.main_window import MainWindow


def test_main_window_navigation_and_initial_portfolio_setup(qtbot, tmp_path) -> None:
    database = Database.open(tmp_path / "rfinance.sqlite3")
    database.upgrade()
    try:
        service = PortfolioLedgerService(
            LedgerRepository(database.sessions),
            lot_sizes={},
        )
        paths = AppPaths.resolve(tmp_path / "rfinance-data")
        window = MainWindow(paths, service)
        qtbot.addWidget(window)

        assert window.windowTitle() == "RFinance"
        assert window.navigation.count() == 3
        assert window.initial_capital_input.text() == "5000000"
        assert window._portfolio_empty_panel.isVisible()
        assert not window._portfolio_dashboard.isVisible()

        window.navigation.setCurrentRow(1)
        assert window.pages.currentIndex() == 1
        window.initial_capital_input.setText("1250000")
        qtbot.mouseClick(window.initialize_portfolio_button, Qt.MouseButton.LeftButton)

        assert service.snapshot().cash_balance == Decimal("1250000")
        assert len(service.events()) == 1
        assert service.events()[0].event_type.value == "CAPITAL_INJECTION"
        assert window._portfolio_dashboard.isVisible()
        assert not window._portfolio_empty_panel.isVisible()
        assert window.portfolio_cash_label.text() == "Cash balance: Rp1,250,000.00"
    finally:
        database.close()


def test_invalid_initial_capital_does_not_create_ledger_event(qtbot, tmp_path) -> None:
    database = Database.open(tmp_path / "invalid-capital.sqlite3")
    database.upgrade()
    try:
        service = PortfolioLedgerService(
            LedgerRepository(database.sessions),
            lot_sizes={},
        )
        window = MainWindow(AppPaths.resolve(tmp_path / "rfinance-data"), service)
        qtbot.addWidget(window)
        window.initial_capital_input.setText("not-a-number")

        qtbot.mouseClick(window.initialize_portfolio_button, Qt.MouseButton.LeftButton)

        assert service.events() == ()
        assert "not initialized" in window.portfolio_status_label.text()
        assert window._portfolio_empty_panel.isVisible()
    finally:
        database.close()
