# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Main desktop window and first functional navigation shell."""

from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from rfinance.core.config import AppPaths


class MainWindow(QMainWindow):
    """Navigable desktop shell with truthful implementation states."""

    def __init__(self, paths: AppPaths) -> None:
        super().__init__()
        self.paths = paths
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
        layout.addWidget(QLabel("Portfolio: not initialized"))
        layout.addStretch(1)
        return page

    def _portfolio_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 28, 32, 28)
        title = QLabel("Portfolio Simulator")
        title.setStyleSheet("font-size: 26px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(
            QLabel(
                "No simulated portfolio has been initialized. "
                "The default Rp5,000,000 capital and target allocation are configurable "
                "first-run defaults; no assets or transactions are assumed."
            )
        )
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
