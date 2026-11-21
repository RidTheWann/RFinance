# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Main desktop window with local portfolio and market-import workflows."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from rfinance.application.market_csv_import import MarketCSVImportService
from rfinance.application.portfolio_ledger import (
    DEFAULT_SIMULATION_CAPITAL,
    PortfolioLedgerService,
)

if TYPE_CHECKING:
    from rfinance.core.config import AppPaths
    from rfinance.storage.repositories.data_ingestion import DataImportSummary


class MarketCSVImportWorker(QObject):
    """Execute CSV parsing and persistence outside the Qt main thread."""

    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        service: MarketCSVImportService,
        selected_file: Path,
        source_name: str,
    ) -> None:
        super().__init__()
        self._service = service
        self._selected_file = selected_file
        self._source_name = source_name

    @Slot()
    def run(self) -> None:
        try:
            result = self._service.import_market_csv(
                self._selected_file,
                source_name=self._source_name,
            )
        except Exception as error:
            self.failed.emit(str(error))
            return
        self.completed.emit(result)


class MainWindow(QMainWindow):
    """Navigable desktop shell connected to local application services."""

    def __init__(
        self,
        paths: AppPaths,
        portfolio_ledger: PortfolioLedgerService,
        market_csv_import: MarketCSVImportService,
    ) -> None:
        super().__init__()
        self.paths = paths
        self.portfolio_ledger = portfolio_ledger
        self.market_csv_import = market_csv_import
        self._import_thread: QThread | None = None
        self._import_worker: MarketCSVImportWorker | None = None
        self.setWindowTitle("RFinance")
        self.resize(1280, 800)
        self.setMinimumSize(900, 600)

        root = QWidget(self)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.navigation = QListWidget(root)
        self.navigation.setObjectName("mainNavigation")
        self.navigation.setFixedWidth(210)
        self.navigation.addItems(["Overview", "Portfolio", "Settings"])

        self.pages = QStackedWidget(root)
        self.pages.addWidget(self._overview_page())
        self.pages.addWidget(self._portfolio_page())
        self.pages.addWidget(self._settings_page())

        layout.addWidget(self.navigation)
        layout.addWidget(self.pages, 1)
        self.setCentralWidget(root)

        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.navigation.setCurrentRow(0)
        self.refresh_portfolio()

    def _overview_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(14)
        title = QLabel("Overview")
        title.setObjectName("pageTitle")
        title.setStyleSheet("font-size: 26px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Local-first investment research workspace"))
        layout.addWidget(QLabel("Application storage: initialized"))
        layout.addWidget(QLabel("Automated market-data providers: none configured"))
        layout.addWidget(QLabel("Portfolio figures are available in Portfolio Simulator"))

        import_title = QLabel("Local market-data import")
        import_title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(import_title)
        layout.addWidget(
            QLabel(
                "Import a CSV file you obtained lawfully. Imported observations remain "
                "UNVERIFIED until separately reviewed; this workflow does not fetch data "
                "from IDX, OJK, KSEI, or any remote provider."
            )
        )
        self.import_market_csv_button = QPushButton("Import market CSV")
        self.import_market_csv_button.setObjectName("importMarketCSVButton")
        self.import_market_csv_button.clicked.connect(self._select_market_csv)
        layout.addWidget(self.import_market_csv_button)

        self.market_import_status_label = QLabel("No user-supplied market data imported.")
        self.market_import_status_label.setObjectName("marketImportStatus")
        self.market_import_status_label.setWordWrap(True)
        layout.addWidget(self.market_import_status_label)
        layout.addStretch(1)
        return page

    def _portfolio_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        title = QLabel("Portfolio Simulator")
        title.setObjectName("portfolioTitle")
        title.setStyleSheet("font-size: 26px; font-weight: 600;")
        layout.addWidget(title)

        self._portfolio_empty_panel = QWidget(page)
        empty_layout = QVBoxLayout(self._portfolio_empty_panel)
        empty_layout.setContentsMargins(0, 8, 0, 8)
        empty_title = QLabel("Initialize your simulated portfolio")
        empty_title.setStyleSheet("font-size: 18px; font-weight: 600;")
        empty_layout.addWidget(empty_title)
        empty_layout.addWidget(
            QLabel(
                "Choose the opening cash balance. The Rp5,000,000 value is only a default "
                "suggestion: no money, asset, or monthly contribution is recorded until "
                "you explicitly initialize this local simulation."
            )
        )

        form = QFormLayout()
        self.initial_capital_input = QLineEdit(format(DEFAULT_SIMULATION_CAPITAL, "f"))
        self.initial_capital_input.setObjectName("initialCapitalInput")
        self.initial_capital_input.setPlaceholderText("Amount in IDR, e.g. 5000000")
        form.addRow("Opening capital (IDR)", self.initial_capital_input)
        empty_layout.addLayout(form)

        self.initialize_portfolio_button = QPushButton("Initialize simulated portfolio")
        self.initialize_portfolio_button.setObjectName("initializePortfolioButton")
        self.initialize_portfolio_button.clicked.connect(self._initialize_portfolio)
        empty_layout.addWidget(self.initialize_portfolio_button)
        layout.addWidget(self._portfolio_empty_panel)

        self._portfolio_dashboard = QWidget(page)
        dashboard_layout = QVBoxLayout(self._portfolio_dashboard)
        dashboard_layout.setContentsMargins(0, 8, 0, 8)
        dashboard_title = QLabel("Simulated portfolio")
        dashboard_title.setStyleSheet("font-size: 18px; font-weight: 600;")
        dashboard_layout.addWidget(dashboard_title)

        self.portfolio_cash_label = QLabel()
        self.portfolio_positions_label = QLabel()
        self.portfolio_events_label = QLabel()
        dashboard_layout.addWidget(self.portfolio_cash_label)
        dashboard_layout.addWidget(self.portfolio_positions_label)
        dashboard_layout.addWidget(self.portfolio_events_label)
        dashboard_layout.addWidget(
            QLabel(
                "Market value and unrealized P/L are unavailable until verified market "
                "observations are configured. The current balance is reconstructed from "
                "the local event ledger."
            )
        )
        dashboard_layout.addWidget(
            QLabel(
                "Allocation targets only — not executed holdings: "
                "equity index 50% · dividend equities 20% · money market 30%. "
                "Unfilled targets remain uninvested."
            )
        )
        layout.addWidget(self._portfolio_dashboard)

        self.portfolio_status_label = QLabel()
        self.portfolio_status_label.setObjectName("portfolioStatus")
        self.portfolio_status_label.setWordWrap(True)
        layout.addWidget(self.portfolio_status_label)
        layout.addStretch(1)
        return page

    def _settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 28, 32, 28)
        title = QLabel("Settings")
        title.setStyleSheet("font-size: 26px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(QLabel(f"Persistent data directory: {self.paths.root}"))
        layout.addWidget(QLabel(f"SQLite database: {self.paths.database_file}"))
        open_folder = QPushButton("Open data directory")
        open_folder.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.paths.root)))
        )
        layout.addWidget(open_folder)
        layout.addStretch(1)
        return page

    def _select_market_csv(self) -> None:
        if self._import_thread is not None:
            return

        selected_file, _ = QFileDialog.getOpenFileName(
            self,
            "Select market-observation CSV",
            str(Path.home()),
            "CSV files (*.csv)",
        )
        if not selected_file:
            return

        default_source = f"Local CSV: {Path(selected_file).stem}"
        source_name, accepted = QInputDialog.getText(
            self,
            "Import source details",
            "Source label (who published or supplied this file):",
            text=default_source,
        )
        if not accepted:
            return
        if not source_name.strip():
            self.market_import_status_label.setText(
                "Import cancelled: source label cannot be blank."
            )
            return

        thread = QThread(self)
        worker = MarketCSVImportWorker(
            self.market_csv_import,
            Path(selected_file),
            source_name,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(self._on_market_csv_imported)
        worker.failed.connect(self._on_market_csv_import_failed)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.completed.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(lambda: self._on_import_thread_finished(thread))
        thread.finished.connect(thread.deleteLater)

        self._import_thread = thread
        self._import_worker = worker
        self.import_market_csv_button.setEnabled(False)
        self.market_import_status_label.setText("Importing and validating the selected CSV…")
        thread.start()

    def _on_market_csv_imported(self, result: DataImportSummary) -> None:
        self.market_import_status_label.setText(
            f"Import complete: {result.accepted_rows:,} observations accepted, "
            f"{result.rejected_rows:,} rows rejected. All accepted observations are "
            f"UNVERIFIED. Batch: {result.batch_id}"
        )

    def _on_market_csv_import_failed(self, message: str) -> None:
        self.market_import_status_label.setText(f"CSV import failed: {message}")

    def _on_import_thread_finished(self, thread: QThread) -> None:
        if self._import_thread is thread:
            self._import_thread = None
            self._import_worker = None
        self.import_market_csv_button.setEnabled(True)

    @staticmethod
    def _format_idr(amount: Decimal) -> str:
        return f"Rp{amount:,.2f}"

    def refresh_portfolio(self) -> None:
        """Refresh presentation from the ledger service; no accounting in the UI."""

        events = self.portfolio_ledger.events()
        initialized = bool(events)
        self._portfolio_empty_panel.setVisible(not initialized)
        self._portfolio_dashboard.setVisible(initialized)
        if not initialized:
            return

        snapshot = self.portfolio_ledger.snapshot()
        self.portfolio_cash_label.setText(
            f"Cash balance: {self._format_idr(snapshot.cash_balance)}"
        )
        self.portfolio_positions_label.setText(f"Open positions: {len(snapshot.positions)}")
        self.portfolio_events_label.setText(f"Recorded ledger events: {snapshot.applied_events}")

    def _initialize_portfolio(self) -> None:
        try:
            opening_capital = Decimal(self.initial_capital_input.text().strip())
            self.portfolio_ledger.initialize_portfolio(opening_capital)
        except (InvalidOperation, ValueError) as error:
            self.portfolio_status_label.setText(f"Portfolio was not initialized: {error}")
            return
        except Exception as error:
            self.portfolio_status_label.setText(
                f"Could not save the portfolio to local storage: {error}"
            )
            return

        self.portfolio_status_label.setText(
            "Simulated portfolio initialized. The opening capital is recorded locally."
        )
        self.refresh_portfolio()
