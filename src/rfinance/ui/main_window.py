# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Main desktop window with local portfolio and market-import workflows."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rfinance.application.instrument_review import (
    InstrumentReviewDecision,
    InstrumentReviewResult,
    InstrumentReviewService,
)
from rfinance.application.observation_review import ObservationReviewService
from rfinance.application.portfolio_ledger import (
    DEFAULT_SIMULATION_CAPITAL,
    PortfolioLedgerService,
)
from rfinance.data.contracts import InstrumentContract, InstrumentType
from rfinance.ui.observation_review_page import ObservationReviewPage

if TYPE_CHECKING:
    from PySide6.QtGui import QCloseEvent

    from rfinance.application.market_csv_import import MarketCSVImportService
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


class InstrumentReviewWorker(QObject):
    """Archive selected evidence and record a review outside the Qt UI thread."""

    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        service: InstrumentReviewService,
        instrument_id: str,
        decision: InstrumentReviewDecision,
        reviewer_label: str,
        evidence_file: Path,
        notes: str,
        verified_instrument: InstrumentContract | None,
    ) -> None:
        super().__init__()
        self._service = service
        self._instrument_id = instrument_id
        self._decision = decision
        self._reviewer_label = reviewer_label
        self._evidence_file = evidence_file
        self._notes = notes
        self._verified_instrument = verified_instrument

    @Slot()
    def run(self) -> None:
        try:
            result = self._service.review_instrument_from_file(
                self._instrument_id,
                decision=self._decision,
                reviewer_label=self._reviewer_label,
                evidence_file=self._evidence_file,
                notes=self._notes,
                verified_instrument=self._verified_instrument,
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
        instrument_review: InstrumentReviewService,
        observation_review: ObservationReviewService,
    ) -> None:
        super().__init__()
        self.paths = paths
        self.portfolio_ledger = portfolio_ledger
        self.market_csv_import = market_csv_import
        self.instrument_review = instrument_review
        self._import_thread: QThread | None = None
        self._import_worker: MarketCSVImportWorker | None = None
        self._review_thread: QThread | None = None
        self._review_worker: InstrumentReviewWorker | None = None
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
        self.navigation.addItems(
            ["Overview", "Portfolio", "Instrument Review", "Observation Review", "Settings"]
        )

        self.pages = QStackedWidget(root)
        self.pages.addWidget(self._overview_page())
        self.pages.addWidget(self._portfolio_page())
        self.pages.addWidget(self._instrument_review_page())
        self.observation_review_page = ObservationReviewPage(observation_review)
        self.pages.addWidget(self.observation_review_page)
        self.pages.addWidget(self._settings_page())

        layout.addWidget(self.navigation)
        layout.addWidget(self.pages, 1)
        self.setCentralWidget(root)

        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.navigation.setCurrentRow(0)
        self.refresh_portfolio()
        self.refresh_market_import_history()
        self.refresh_instrument_review_queue()
        self.observation_review_page.refresh_queue()

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

        history_title = QLabel("Recent import history")
        history_title.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(history_title)
        self.market_import_history_empty_label = QLabel(
            "No local market-data import batches have been recorded."
        )
        self.market_import_history_empty_label.setObjectName("marketImportHistoryEmpty")
        layout.addWidget(self.market_import_history_empty_label)

        self.market_import_history_table = QTableWidget(0, 6)
        self.market_import_history_table.setObjectName("marketImportHistoryTable")
        self.market_import_history_table.setHorizontalHeaderLabels(
            ["Imported (UTC)", "Source", "File", "Accepted", "Rejected", "Trust status"]
        )
        self.market_import_history_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.market_import_history_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.market_import_history_table.setAlternatingRowColors(True)
        self.market_import_history_table.setSortingEnabled(False)
        self.market_import_history_table.setMaximumHeight(230)
        self.market_import_history_table.horizontalHeader().setStretchLastSection(True)
        self.market_import_history_table.resizeColumnsToContents()
        self.market_import_history_table.hide()
        layout.addWidget(self.market_import_history_table)
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

    def _instrument_review_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(12)

        title = QLabel("Instrument Review")
        title.setStyleSheet("font-size: 26px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(
            QLabel(
                "Verify instrument identity and trading metadata against evidence you inspect. "
                "This does not verify imported prices, market-data source rights, or historical "
                "data completeness."
            )
        )

        queue_title = QLabel("Instrument master")
        queue_title.setStyleSheet("font-size: 17px; font-weight: 600;")
        layout.addWidget(queue_title)
        self.instrument_review_empty_label = QLabel(
            "No instruments are registered. Import a user-supplied market CSV to create "
            "UNVERIFIED placeholders, or add instruments through a future provider workflow."
        )
        layout.addWidget(self.instrument_review_empty_label)

        self.instrument_review_table = QTableWidget(0, 7)
        self.instrument_review_table.setObjectName("instrumentReviewQueue")
        self.instrument_review_table.setHorizontalHeaderLabels(
            ["Instrument ID", "Ticker", "Exchange", "Issuer", "Currency", "Type", "Status"]
        )
        self.instrument_review_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.instrument_review_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.instrument_review_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.instrument_review_table.setAlternatingRowColors(True)
        self.instrument_review_table.setMaximumHeight(220)
        self.instrument_review_table.horizontalHeader().setStretchLastSection(True)
        self.instrument_review_table.itemSelectionChanged.connect(
            self._on_instrument_review_selection_changed
        )
        self.instrument_review_table.hide()
        layout.addWidget(self.instrument_review_table)

        form_title = QLabel("Evidence-backed review")
        form_title.setStyleSheet("font-size: 17px; font-weight: 600;")
        layout.addWidget(form_title)
        form = QFormLayout()

        self.review_instrument_id_label = QLabel("Select an instrument above")
        form.addRow("Selected instrument", self.review_instrument_id_label)

        self.review_ticker_input = QLineEdit()
        self.review_exchange_input = QLineEdit("IDX")
        self.review_company_name_input = QLineEdit()
        self.review_currency_input = QLineEdit("IDR")
        self.review_type_combo = QComboBox()
        for instrument_type in InstrumentType:
            self.review_type_combo.addItem(instrument_type.value, instrument_type.value)
        self.review_sector_input = QLineEdit()
        self.review_lot_size_input = QLineEdit("100")
        self.review_minimum_investment_input = QLineEdit()
        self.review_active_checkbox = QCheckBox("Instrument is active")
        self.review_active_checkbox.setChecked(True)

        form.addRow("Ticker", self.review_ticker_input)
        form.addRow("Exchange", self.review_exchange_input)
        form.addRow("Company / issuer", self.review_company_name_input)
        form.addRow("Currency", self.review_currency_input)
        form.addRow("Instrument type", self.review_type_combo)
        form.addRow("Sector", self.review_sector_input)
        form.addRow("Lot size (shares)", self.review_lot_size_input)
        form.addRow("Minimum investment (IDR)", self.review_minimum_investment_input)
        form.addRow("Status", self.review_active_checkbox)

        self.review_reviewer_input = QLineEdit()
        self.review_reviewer_input.setPlaceholderText("Operator / reviewer label")
        self.review_notes_input = QLineEdit()
        self.review_notes_input.setPlaceholderText(
            "What was checked and which source details matched?"
        )
        form.addRow("Reviewer", self.review_reviewer_input)
        form.addRow("Review notes", self.review_notes_input)

        evidence_row = QWidget()
        evidence_layout = QHBoxLayout(evidence_row)
        evidence_layout.setContentsMargins(0, 0, 0, 0)
        self.review_evidence_path_input = QLineEdit()
        self.review_evidence_path_input.setReadOnly(True)
        self.review_evidence_path_input.setPlaceholderText("Select a local evidence document")
        self.review_evidence_browse_button = QPushButton("Choose evidence file")
        self.review_evidence_browse_button.clicked.connect(self._select_instrument_review_evidence)
        evidence_layout.addWidget(self.review_evidence_path_input, 1)
        evidence_layout.addWidget(self.review_evidence_browse_button)
        form.addRow("Evidence file", evidence_row)

        layout.addLayout(form)

        actions = QHBoxLayout()
        self.verify_instrument_button = QPushButton("Verify instrument identity")
        self.verify_instrument_button.setObjectName("verifyInstrumentButton")
        self.verify_instrument_button.clicked.connect(
            lambda: self._submit_instrument_review(InstrumentReviewDecision.VERIFIED)
        )
        self.reject_instrument_button = QPushButton("Reject instrument identity")
        self.reject_instrument_button.setObjectName("rejectInstrumentButton")
        self.reject_instrument_button.clicked.connect(
            lambda: self._submit_instrument_review(InstrumentReviewDecision.REJECTED)
        )
        actions.addWidget(self.verify_instrument_button)
        actions.addWidget(self.reject_instrument_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.instrument_review_status_label = QLabel(
            "A manual decision requires a selected instrument, evidence file, "
            "reviewer label, and notes."
        )
        self.instrument_review_status_label.setObjectName("instrumentReviewStatus")
        self.instrument_review_status_label.setWordWrap(True)
        layout.addWidget(self.instrument_review_status_label)

        history_title = QLabel("Selected instrument review history")
        history_title.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(history_title)
        self.instrument_review_history_table = QTableWidget(0, 5)
        self.instrument_review_history_table.setObjectName("instrumentReviewHistory")
        self.instrument_review_history_table.setHorizontalHeaderLabels(
            ["Reviewed (UTC)", "Previous", "Decision", "Reviewer", "Evidence"]
        )
        self.instrument_review_history_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.instrument_review_history_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.instrument_review_history_table.setMaximumHeight(180)
        self.instrument_review_history_table.horizontalHeader().setStretchLastSection(True)
        self.instrument_review_history_table.hide()
        layout.addWidget(self.instrument_review_history_table)
        layout.addStretch(1)
        return page

    def _selected_review_instrument_id(self) -> str | None:
        selected = self.instrument_review_table.selectedItems()
        if not selected:
            return None
        value = selected[0].data(Qt.ItemDataRole.UserRole)
        return value if isinstance(value, str) else None

    def refresh_instrument_review_queue(self, *, select_instrument_id: str | None = None) -> None:
        """Reload canonical instrument metadata and the selected record's audit history."""

        previous_selection = select_instrument_id or self._selected_review_instrument_id()
        instruments = self.instrument_review.list_instruments(limit=500)
        self.instrument_review_table.setRowCount(len(instruments))
        has_instruments = bool(instruments)
        self.instrument_review_empty_label.setVisible(not has_instruments)
        self.instrument_review_table.setVisible(has_instruments)

        selected_row: int | None = None
        for row_index, instrument in enumerate(instruments):
            values = (
                instrument.instrument_id,
                instrument.ticker or "—",
                instrument.exchange or "—",
                instrument.company_name or "—",
                instrument.currency or "—",
                instrument.instrument_type or "—",
                instrument.verification_status,
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, instrument.instrument_id)
                self.instrument_review_table.setItem(row_index, column, cell)
            if instrument.instrument_id == previous_selection:
                selected_row = row_index

        self.instrument_review_table.resizeColumnsToContents()
        if selected_row is not None:
            self.instrument_review_table.selectRow(selected_row)
        elif instruments:
            self.instrument_review_table.selectRow(0)
        else:
            self.review_instrument_id_label.setText("Select an instrument above")
            self.instrument_review_history_table.setRowCount(0)
            self.instrument_review_history_table.hide()

    def _on_instrument_review_selection_changed(self) -> None:
        instrument_id = self._selected_review_instrument_id()
        self.review_instrument_id_label.setText(instrument_id or "Select an instrument above")
        self.refresh_instrument_review_history()

    def refresh_instrument_review_history(self) -> None:
        instrument_id = self._selected_review_instrument_id()
        history = (
            () if instrument_id is None else self.instrument_review.review_history(instrument_id)
        )
        self.instrument_review_history_table.setRowCount(len(history))
        self.instrument_review_history_table.setVisible(bool(history))
        for row_index, event in enumerate(history):
            values = (
                event.reviewed_at_utc.replace("T", " "),
                event.previous_status,
                event.decision,
                event.reviewer_label,
                Path(event.evidence_reference).name,
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setToolTip(
                    f"Review: {event.review_id}\n"
                    f"Evidence: {event.evidence_reference}\n"
                    f"SHA-256: {event.evidence_sha256}\n"
                    f"Notes: {event.notes}"
                )
                self.instrument_review_history_table.setItem(row_index, column, cell)
        self.instrument_review_history_table.resizeColumnsToContents()

    def _select_instrument_review_evidence(self) -> None:
        selected_file, _ = QFileDialog.getOpenFileName(
            self,
            "Select instrument identity evidence",
            str(Path.home()),
            "Evidence files (*.pdf *.png *.jpg *.jpeg *.txt *.csv *.xlsx *.docx);;All files (*)",
        )
        if selected_file:
            self.review_evidence_path_input.setText(selected_file)

    def _submit_instrument_review(self, decision: InstrumentReviewDecision) -> None:
        if self._review_thread is not None:
            return
        instrument_id = self._selected_review_instrument_id()
        evidence_text = self.review_evidence_path_input.text().strip()
        reviewer_label = self.review_reviewer_input.text().strip()
        notes = self.review_notes_input.text().strip()
        if instrument_id is None:
            self.instrument_review_status_label.setText("Select an instrument to review.")
            return
        if not evidence_text:
            self.instrument_review_status_label.setText("Choose a local evidence file first.")
            return
        if not reviewer_label or not notes:
            self.instrument_review_status_label.setText(
                "Reviewer label and review notes are required."
            )
            return

        verified_instrument: InstrumentContract | None = None
        if decision is InstrumentReviewDecision.VERIFIED:
            try:
                lot_text = self.review_lot_size_input.text().strip()
                minimum_text = self.review_minimum_investment_input.text().strip()
                verified_instrument = InstrumentContract(
                    instrument_id=instrument_id,
                    ticker=self.review_ticker_input.text().strip(),
                    exchange=self.review_exchange_input.text().strip(),
                    instrument_type=InstrumentType(self.review_type_combo.currentData()),
                    company_name=self.review_company_name_input.text().strip(),
                    currency=self.review_currency_input.text().strip().upper(),
                    sector=self.review_sector_input.text().strip() or None,
                    active=self.review_active_checkbox.isChecked(),
                    lot_size=None if not lot_text else int(lot_text),
                    minimum_investment=None if not minimum_text else Decimal(minimum_text),
                )
            except (ValueError, TypeError, InvalidOperation) as error:
                self.instrument_review_status_label.setText(
                    f"Instrument metadata is invalid: {error}"
                )
                return

        worker = InstrumentReviewWorker(
            self.instrument_review,
            instrument_id,
            decision,
            reviewer_label,
            Path(evidence_text),
            notes,
            verified_instrument,
        )
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(self._on_instrument_review_completed)
        worker.failed.connect(self._on_instrument_review_failed)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.completed.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(lambda: self._on_review_thread_finished(thread))
        thread.finished.connect(thread.deleteLater)
        self._review_thread = thread
        self._review_worker = worker
        self.verify_instrument_button.setEnabled(False)
        self.reject_instrument_button.setEnabled(False)
        self.review_evidence_browse_button.setEnabled(False)
        self.instrument_review_status_label.setText("Archiving evidence and recording review…")
        thread.start()

    def _on_instrument_review_completed(self, result: InstrumentReviewResult) -> None:
        self.instrument_review_status_label.setText(
            f"{result.instrument_id}: {result.verification_status}. "
            f"Evidence archived at {result.evidence_reference}; SHA-256 {result.evidence_sha256}. "
            "Market observations remain unchanged and require separate quality review."
        )
        self.review_evidence_path_input.clear()
        self.review_notes_input.clear()
        self.refresh_instrument_review_queue(select_instrument_id=result.instrument_id)

    def _on_instrument_review_failed(self, message: str) -> None:
        self.instrument_review_status_label.setText(f"Instrument review failed: {message}")

    def _on_review_thread_finished(self, thread: QThread) -> None:
        if self._review_thread is thread:
            self._review_thread = None
            self._review_worker = None
        self.verify_instrument_button.setEnabled(True)
        self.reject_instrument_button.setEnabled(True)
        self.review_evidence_browse_button.setEnabled(True)

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
        self.refresh_market_import_history()
        self.refresh_instrument_review_queue()

    def _on_market_csv_import_failed(self, message: str) -> None:
        self.market_import_status_label.setText(f"CSV import failed: {message}")

    def _on_import_thread_finished(self, thread: QThread) -> None:
        if self._import_thread is thread:
            self._import_thread = None
            self._import_worker = None
        self.import_market_csv_button.setEnabled(True)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._import_thread is not None and self._import_thread.isRunning():
            self.market_import_status_label.setText(
                "A CSV import is still running. Wait for it to finish before closing RFinance."
            )
            event.ignore()
            return
        if self._review_thread is not None and self._review_thread.isRunning():
            self.instrument_review_status_label.setText(
                "An instrument review is still running. "
                "Wait for it to finish before closing RFinance."
            )
            event.ignore()
            return
        if self.observation_review_page.is_busy:
            self.observation_review_page.status_label.setText(
                "An observation review is still running. "
                "Wait for it to finish before closing RFinance."
            )
            event.ignore()
            return
        super().closeEvent(event)

    def refresh_market_import_history(self) -> None:
        """Render recent import batches without calculating or altering financial data."""

        batches = self.market_csv_import.recent_imports(limit=20)
        self.market_import_history_table.setRowCount(len(batches))
        has_batches = bool(batches)
        self.market_import_history_empty_label.setVisible(not has_batches)
        self.market_import_history_table.setVisible(has_batches)

        for row_index, batch in enumerate(batches):
            trust_status = "UNVERIFIED" if batch.accepted_rows else "No accepted rows"
            values = (
                batch.imported_at_utc.replace("T", " "),
                batch.source_name,
                batch.original_filename,
                str(batch.accepted_rows),
                str(batch.rejected_rows),
                trust_status,
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setToolTip(
                    f"Batch: {batch.batch_id}\n"
                    f"SHA-256: {batch.file_sha256}\n"
                    f"Archived file: {batch.document_relative_path}"
                )
                self.market_import_history_table.setItem(row_index, column, cell)

        self.market_import_history_table.resizeColumnsToContents()

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
