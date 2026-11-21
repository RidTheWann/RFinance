# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Main desktop window and first functional portfolio setup workflow."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from rfinance.application.portfolio_ledger import (
    DEFAULT_SIMULATION_CAPITAL,
    PortfolioLedgerService,
)

if TYPE_CHECKING:
    from rfinance.core.config import AppPaths


class MainWindow(QMainWindow):
    """Navigable desktop shell connected to local application services."""

    def __init__(self, paths: AppPaths, portfolio_ledger: PortfolioLedgerService) -> None:
        super().__init__()
        self.paths = paths
        self.portfolio_ledger = portfolio_ledger
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
        title = QLabel("Overview")
        title.setObjectName("pageTitle")
        title.setStyleSheet("font-size: 26px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Local-first investment research workspace"))
        layout.addWidget(QLabel("Application storage: initialized"))
        layout.addWidget(QLabel("Market data: no provider configured"))
        layout.addWidget(QLabel("Portfolio figures are available in Portfolio Simulator"))
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
