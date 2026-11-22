"""Desktop Dividend Center for recorded events, calendar and labelled analytics."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from rfinance.application.dividend_events import (
    DividendAnalyticsReport,
    DividendEventService,
    DividendRecordResult,
    DividendReviewDecision,
    DividendReviewResult,
)
from rfinance.data.contracts import DividendEventContract, DividendEventStatus, DividendType

if TYPE_CHECKING:
    from collections.abc import Callable

    from PySide6.QtGui import QCloseEvent


class DividendWorker(QObject):
    """Run one application-service operation outside the Qt main thread."""

    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, operation: Callable[[], object]) -> None:
        super().__init__()
        self._operation = operation

    @Slot()
    def run(self) -> None:
        try:
            result = self._operation()
        except Exception as error:
            self.failed.emit(str(error))
            return
        self.completed.emit(result)


class DividendPage(QWidget):
    """A connected view over persisted dividend events and the calculation layer."""

    def __init__(self, service: DividendEventService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._thread: QThread | None = None
        self._worker: DividendWorker | None = None
        self._build_ui()
        self.refresh_events()

    @property
    def is_busy(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        title = QLabel("Dividend Center")
        title.setObjectName("dividendPageTitle")
        title.setStyleSheet("font-size: 26px; font-weight: 600;")
        layout.addWidget(title)
        description = QLabel(
            "User-supplied dividend records remain UNVERIFIED until an evidence-backed review. "
            "Announced, estimated and simulated events are labelled and never treated as cash "
            "actually received."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        self.status_label = QLabel(
            "All figures below come from the local dividend ledger and deterministic analytics."
        )
        self.status_label.setObjectName("dividendStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        tabs = QTabWidget()
        tabs.addTab(self._events_tab(), "Events")
        tabs.addTab(self._calendar_tab(), "Calendar")
        tabs.addTab(self._analytics_tab(), "Analytics")
        tabs.addTab(self._review_tab(), "Evidence review")
        layout.addWidget(tabs, 1)

    def _events_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)

        form_title = QLabel("Record a user-supplied dividend document")
        form_title.setStyleSheet("font-size: 17px; font-weight: 600;")
        layout.addWidget(form_title)
        form = QFormLayout()

        self.event_instrument_input = QLineEdit("IDX:BBCA")
        self.event_source_input = QLineEdit()
        self.event_source_input.setPlaceholderText("Who published the document?")
        self.event_key_input = QLineEdit()
        self.event_key_input.setPlaceholderText("Stable identifier from the source")
        self.event_type_combo = QComboBox()
        for item in DividendType:
            self.event_type_combo.addItem(item.value, item.value)
        self.event_status_combo = QComboBox()
        for status_item in DividendEventStatus:
            self.event_status_combo.addItem(status_item.value, status_item.value)
        self.event_amount_input = QLineEdit()
        self.event_amount_input.setPlaceholderText("Gross amount per share; blank for stock rights")
        self.event_currency_input = QLineEdit("IDR")
        self.event_ex_date_input = QLineEdit(date.today().isoformat())
        self.event_payment_date_input = QLineEdit()
        self.event_payment_date_input.setPlaceholderText("YYYY-MM-DD (optional)")
        self.event_notes_input = QLineEdit()
        self.event_notes_input.setPlaceholderText("Short note about the source document")

        form.addRow("Instrument ID", self.event_instrument_input)
        form.addRow("Source label", self.event_source_input)
        form.addRow("Source event key", self.event_key_input)
        form.addRow("Dividend type", self.event_type_combo)
        form.addRow("Event status", self.event_status_combo)
        form.addRow("Gross per share", self.event_amount_input)
        form.addRow("Currency", self.event_currency_input)
        form.addRow("Ex-date", self.event_ex_date_input)
        form.addRow("Payment date", self.event_payment_date_input)
        form.addRow("Notes", self.event_notes_input)
        layout.addLayout(form)

        self.record_button = QPushButton("Record dividend event")
        self.record_button.setObjectName("recordDividendButton")
        self.record_button.clicked.connect(self._record_event)
        layout.addWidget(self.record_button)

        self.events_empty_label = QLabel("No dividend events have been recorded locally.")
        self.events_empty_label.setObjectName("dividendEventsEmpty")
        layout.addWidget(self.events_empty_label)

        self.events_table = QTableWidget(0, 10)
        self.events_table.setObjectName("dividendEventsTable")
        self.events_table.setHorizontalHeaderLabels(
            [
                "Instrument",
                "Type",
                "Status",
                "Gross/share",
                "Currency",
                "Ex-date",
                "Payment date",
                "Raw quality",
                "Effective quality",
                "Source",
            ]
        )
        self.events_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.events_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.events_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.events_table.setAlternatingRowColors(True)
        self.events_table.itemSelectionChanged.connect(self._on_event_selected)
        self.events_table.hide()
        layout.addWidget(self.events_table, 1)
        return page

    def _calendar_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)
        layout.addWidget(QLabel("Dated ex-dates and payment dates in a selected window."))
        note = QLabel(
            "An announced or estimated date is a planning item, not confirmed cash. "
            "Both a confirmed and an unconfirmed event can appear on the same date."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        controls = QHBoxLayout()
        self.calendar_start_input = QLineEdit(date.today().isoformat())
        self.calendar_end_input = QLineEdit(date(date.today().year + 1, 1, 1).isoformat())
        self.calendar_refresh_button = QPushButton("Refresh calendar")
        self.calendar_refresh_button.setObjectName("refreshDividendCalendarButton")
        self.calendar_refresh_button.clicked.connect(self.refresh_calendar)
        controls.addWidget(QLabel("From"))
        controls.addWidget(self.calendar_start_input)
        controls.addWidget(QLabel("To"))
        controls.addWidget(self.calendar_end_input)
        controls.addWidget(self.calendar_refresh_button)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.calendar_table = QTableWidget(0, 9)
        self.calendar_table.setObjectName("dividendCalendarTable")
        self.calendar_table.setHorizontalHeaderLabels(
            [
                "Date",
                "Date kind",
                "Instrument",
                "Type",
                "Gross/share",
                "Currency",
                "Status",
                "Quality",
                "Interpretation",
            ]
        )
        self.calendar_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.calendar_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.calendar_table.setAlternatingRowColors(True)
        self.calendar_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.calendar_table, 1)
        return page

    def _analytics_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)
        form_title = QLabel("Labelled dividend analytics")
        form_title.setStyleSheet("font-size: 17px; font-weight: 600;")
        layout.addWidget(form_title)

        form = QFormLayout()
        self.analytics_instrument_input = QLineEdit("IDX:BBCA")
        self.analytics_currency_input = QLineEdit("IDR")
        self.analytics_as_of_input = QLineEdit(date.today().isoformat())
        self.analytics_price_input = QLineEdit()
        self.analytics_price_input.setPlaceholderText("Optional verified price for yield")
        self.analytics_estimate_input = QLineEdit()
        self.analytics_estimate_input.setPlaceholderText("Optional estimated annual dividend")
        self.analytics_withholding_input = QLineEdit()
        self.analytics_withholding_input.setPlaceholderText("Optional rate, e.g. 0.10")
        self.analytics_window_input = QLineEdit("365")
        form.addRow("Instrument ID", self.analytics_instrument_input)
        form.addRow("Currency", self.analytics_currency_input)
        form.addRow("As-of date", self.analytics_as_of_input)
        form.addRow("Price", self.analytics_price_input)
        form.addRow("Estimated annual dividend", self.analytics_estimate_input)
        form.addRow("Withholding rate", self.analytics_withholding_input)
        form.addRow("Trailing window (days)", self.analytics_window_input)
        layout.addLayout(form)

        self.calculate_button = QPushButton("Calculate from verified events")
        self.calculate_button.setObjectName("calculateDividendAnalyticsButton")
        self.calculate_button.clicked.connect(self._calculate_analytics)
        layout.addWidget(self.calculate_button)

        self.analytics_result_label = QLabel(
            "No calculation has been run. Missing observations are never converted to zero."
        )
        self.analytics_result_label.setObjectName("dividendAnalyticsResult")
        self.analytics_result_label.setWordWrap(True)
        layout.addWidget(self.analytics_result_label)
        layout.addStretch(1)
        return page

    def _review_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)
        layout.addWidget(
            QLabel("Verify or reject a selected event using a document you inspected locally.")
        )

        form = QFormLayout()
        self.selected_event_label = QLabel("Select an event in the Events tab")
        self.reviewer_input = QLineEdit()
        self.reviewer_input.setPlaceholderText("Operator / reviewer label")
        self.review_notes_input = QLineEdit()
        self.review_notes_input.setPlaceholderText("What was checked in the source document?")
        evidence_row = QWidget()
        evidence_layout = QHBoxLayout(evidence_row)
        evidence_layout.setContentsMargins(0, 0, 0, 0)
        self.evidence_path_input = QLineEdit()
        self.evidence_path_input.setReadOnly(True)
        self.evidence_path_input.setPlaceholderText("Select a local evidence document")
        self.browse_evidence_button = QPushButton("Choose evidence file")
        self.browse_evidence_button.clicked.connect(self._select_evidence)
        evidence_layout.addWidget(self.evidence_path_input, 1)
        evidence_layout.addWidget(self.browse_evidence_button)
        form.addRow("Selected event", self.selected_event_label)
        form.addRow("Reviewer", self.reviewer_input)
        form.addRow("Review notes", self.review_notes_input)
        form.addRow("Evidence file", evidence_row)
        layout.addLayout(form)

        actions = QHBoxLayout()
        self.verify_button = QPushButton("Record VERIFIED decision")
        self.verify_button.setObjectName("verifyDividendButton")
        self.verify_button.clicked.connect(lambda: self._review(DividendReviewDecision.VERIFIED))
        self.reject_button = QPushButton("Record REJECTED decision")
        self.reject_button.setObjectName("rejectDividendButton")
        self.reject_button.clicked.connect(lambda: self._review(DividendReviewDecision.REJECTED))
        actions.addWidget(self.verify_button)
        actions.addWidget(self.reject_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.review_status_label = QLabel(
            "A raw event is immutable; decisions are appended to the local audit ledger."
        )
        self.review_status_label.setObjectName("dividendReviewStatus")
        self.review_status_label.setWordWrap(True)
        layout.addWidget(self.review_status_label)

        self.history_table = QTableWidget(0, 5)
        self.history_table.setObjectName("dividendReviewHistory")
        self.history_table.setHorizontalHeaderLabels(
            ["Reviewed (UTC)", "Previous", "Decision", "Reviewer", "Evidence"]
        )
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.history_table, 1)
        return page

    # -- Event table -------------------------------------------------------

    def _selected_event_id(self) -> str | None:
        selected = self.events_table.selectedItems()
        if not selected:
            return None
        value = selected[0].data(Qt.ItemDataRole.UserRole)
        return value if isinstance(value, str) else None

    def refresh_events(self, *, select_event_id: str | None = None) -> None:
        candidates = self._service.list_events(limit=500)
        previous = select_event_id or self._selected_event_id()
        self.events_table.setRowCount(len(candidates))
        self.events_empty_label.setVisible(not candidates)
        self.events_table.setVisible(bool(candidates))
        selected_row: int | None = None
        for row, candidate in enumerate(candidates):
            values = (
                candidate.instrument_id,
                candidate.dividend_type,
                candidate.event_status,
                "—"
                if candidate.amount_per_share is None
                else format(candidate.amount_per_share, "f"),
                candidate.currency,
                candidate.ex_date.isoformat(),
                "—" if candidate.payment_date is None else candidate.payment_date.isoformat(),
                candidate.raw_quality,
                candidate.effective_quality,
                candidate.source_label,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, candidate.event_id)
                item.setToolTip(
                    f"Event: {candidate.event_id}\n"
                    f"Source key: {candidate.event_key}\n"
                    f"Acquired (UTC): {candidate.acquired_at_utc}\n"
                    f"Unit: {candidate.unit}"
                )
                self.events_table.setItem(row, column, item)
            if candidate.event_id == previous:
                selected_row = row
        self.events_table.resizeColumnsToContents()
        if selected_row is not None:
            self.events_table.selectRow(selected_row)
        elif candidates:
            self.events_table.selectRow(0)
        else:
            self.selected_event_label.setText("Select an event in the Events tab")
            self.history_table.setRowCount(0)
        self.refresh_calendar()
        self._refresh_history()

    def _on_event_selected(self) -> None:
        event_id = self._selected_event_id()
        self.selected_event_label.setText(event_id or "Select an event in the Events tab")
        self._refresh_history()

    def _refresh_history(self) -> None:
        event_id = self._selected_event_id()
        history = () if event_id is None else self._service.review_history(event_id)
        self.history_table.setRowCount(len(history))
        for row, item in enumerate(history):
            values = (
                item.reviewed_at_utc.replace("T", " "),
                item.previous_quality,
                item.decision,
                item.reviewer_label,
                Path(item.evidence_reference).name,
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setToolTip(
                    f"Review: {item.review_id}\n"
                    f"Evidence: {item.evidence_reference}\n"
                    f"SHA-256: {item.evidence_sha256}\n"
                    f"Notes: {item.notes}"
                )
                self.history_table.setItem(row, column, cell)
        self.history_table.resizeColumnsToContents()

    # -- Calendar ----------------------------------------------------------

    def refresh_calendar(self) -> None:
        try:
            start = date.fromisoformat(self.calendar_start_input.text().strip())
            end = date.fromisoformat(self.calendar_end_input.text().strip())
        except ValueError:
            self.status_label.setText("Calendar dates must use YYYY-MM-DD format.")
            return
        if end < start:
            self.status_label.setText("Calendar end date cannot precede the start date.")
            return
        entries = self._service.calendar(start=start, end=end)
        self.calendar_table.setRowCount(len(entries))
        for row, item in enumerate(entries):
            if item.is_estimate:
                interpretation = "ESTIMATE - not confirmed cash"
            elif item.is_confirmed_cash:
                interpretation = "VERIFIED observed cash"
            else:
                interpretation = "UNVERIFIED - review required"
            values = (
                item.event_date.isoformat(),
                item.date_kind,
                item.instrument_id,
                item.dividend_type,
                "—" if item.amount_per_share is None else format(item.amount_per_share, "f"),
                item.currency,
                item.event_status,
                item.effective_quality,
                interpretation,
            )
            for column, value in enumerate(values):
                self.calendar_table.setItem(row, column, QTableWidgetItem(value))
        self.calendar_table.resizeColumnsToContents()

    # -- Operations --------------------------------------------------------

    def _start_worker(
        self,
        operation: Callable[[], object],
        *,
        on_success: Callable[[object], None],
    ) -> None:
        if self._thread is not None:
            self.status_label.setText("Another dividend operation is still running.")
            return
        thread = QThread(self)
        worker = DividendWorker(operation)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(on_success)
        worker.failed.connect(self._on_operation_failed)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.completed.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(lambda: self._on_thread_finished(thread))
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        self._worker = worker
        thread.start()

    def _on_thread_finished(self, thread: QThread) -> None:
        if self._thread is thread:
            self._thread = None
            self._worker = None

    def _on_operation_failed(self, message: str) -> None:
        self._enable_controls()
        self.status_label.setText(f"Dividend operation failed: {message}")

    def _enable_controls(self) -> None:
        self.record_button.setEnabled(True)
        self.calculate_button.setEnabled(True)
        self.verify_button.setEnabled(True)
        self.reject_button.setEnabled(True)
        self.browse_evidence_button.setEnabled(True)

    def _on_operation_completed(self, message: str) -> None:
        self._enable_controls()
        self.status_label.setText(message)
        self.refresh_events()

    def _record_event(self) -> None:
        self.record_button.setEnabled(False)
        try:
            amount_text = self.event_amount_input.text().strip()
            contract = DividendEventContract(
                event_key=self.event_key_input.text().strip(),
                instrument_id=self.event_instrument_input.text().strip(),
                source_label=self.event_source_input.text().strip(),
                dividend_type=DividendType(self.event_type_combo.currentData()),
                event_status=DividendEventStatus(self.event_status_combo.currentData()),
                amount_per_share=None if not amount_text else Decimal(amount_text),
                currency=self.event_currency_input.text().strip().upper(),
                ex_date=date.fromisoformat(self.event_ex_date_input.text().strip()),
                payment_date=(
                    date.fromisoformat(self.event_payment_date_input.text().strip())
                    if self.event_payment_date_input.text().strip()
                    else None
                ),
                notes=self.event_notes_input.text().strip() or None,
                acquired_at=datetime.now(UTC),
            )
        except (ValueError, TypeError, InvalidOperation) as error:
            self.record_button.setEnabled(True)
            self.status_label.setText(f"Dividend event was not recorded: {error}")
            return

        def operation() -> object:
            return self._service.record_event(contract)

        def on_success(result: object) -> None:
            assert isinstance(result, DividendRecordResult)
            self.event_key_input.clear()
            self.event_notes_input.clear()
            self._on_operation_completed(
                f"Recorded dividend event {result.event_id} with raw quality "
                f"{result.raw_quality}. An evidence-backed review is required before analytics."
            )

        self._start_worker(operation, on_success=on_success)

    def _calculate_analytics(self) -> None:
        try:
            instrument_id = self.analytics_instrument_input.text().strip()
            currency = self.analytics_currency_input.text().strip().upper()
            as_of = date.fromisoformat(self.analytics_as_of_input.text().strip())
            price_text = self.analytics_price_input.text().strip()
            estimate_text = self.analytics_estimate_input.text().strip()
            withholding_text = self.analytics_withholding_input.text().strip()
            price = Decimal(price_text) if price_text else None
            estimate = Decimal(estimate_text) if estimate_text else None
            withholding = Decimal(withholding_text) if withholding_text else None
            window = int(self.analytics_window_input.text().strip())
        except (ValueError, TypeError, InvalidOperation) as error:
            self.status_label.setText(f"Analytics inputs are invalid: {error}")
            return

        def operation() -> object:
            return self._service.analytics(
                instrument_id=instrument_id,
                as_of=as_of,
                currency=currency,
                price=price,
                estimated_annual_dividend=estimate,
                withholding_rate=withholding,
                window_days=window,
            )

        def on_success(result: object) -> None:
            assert isinstance(result, DividendAnalyticsReport)
            self._render_analytics(result)

        self.calculate_button.setEnabled(False)
        self._start_worker(operation, on_success=on_success)

    def _render_analytics(self, report: DividendAnalyticsReport) -> None:
        self.calculate_button.setEnabled(True)
        trailing = report.trailing_dividend_per_share
        trailing_text = (
            "unavailable (no verified observation)" if trailing is None else format(trailing, "f")
        )
        yield_text = (
            "unavailable (no verified price)"
            if report.trailing_yield is None
            else (f"{report.trailing_yield.value * 100:.2f}% TRAILING (observed)")
        )
        forward_text = (
            "not requested"
            if report.forward_yield is None
            else (f"{report.forward_yield.value * 100:.2f}% FORWARD (estimate)")
        )
        net_text = (
            "gross only (withholding unknown)"
            if report.net_trailing_per_share is None
            else (format(report.net_trailing_per_share, "f"))
        )
        self.analytics_result_label.setText(
            f"{report.instrument_id} as of {report.as_of.isoformat()} ({report.currency}): "
            f"trailing gross DPS {trailing_text}; trailing yield {yield_text}; "
            f"forward yield {forward_text}; net trailing per share {net_text}. "
            f"Verified cash events: {report.verified_cash_event_count}. "
            f"Consecutive paid years: {report.consistency.consecutive_years} "
            f"of {report.consistency.years_observed} observed years. "
            f"Methodology: {report.methodology_version}."
        )

    def _select_evidence(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Select dividend evidence",
            str(Path.home()),
            "Evidence files (*.pdf *.png *.jpg *.jpeg *.txt *.csv *.xlsx *.docx);;All files (*)",
        )
        if selected:
            self.evidence_path_input.setText(selected)

    def _review(self, decision: DividendReviewDecision) -> None:
        event_id = self._selected_event_id()
        evidence = self.evidence_path_input.text().strip()
        reviewer = self.reviewer_input.text().strip()
        notes = self.review_notes_input.text().strip()
        if event_id is None:
            self.review_status_label.setText("Select a dividend event to review.")
            return
        if not evidence:
            self.review_status_label.setText("Choose a local evidence file first.")
            return
        if not reviewer or not notes:
            self.review_status_label.setText("Reviewer label and review notes are required.")
            return

        def operation() -> DividendReviewResult:
            return self._service.review_event_from_file(
                event_id,
                decision=decision,
                reviewer_label=reviewer,
                evidence_file=Path(evidence),
                notes=notes,
            )

        def on_success(result: object) -> None:
            assert isinstance(result, DividendReviewResult)
            self.review_status_label.setText(
                f"Review recorded: {result.event_id} is effectively {result.decision}. "
                f"Evidence SHA-256 {result.evidence_sha256}. The raw event is unchanged."
            )
            self.evidence_path_input.clear()
            self.review_notes_input.clear()
            self.refresh_events(select_event_id=result.event_id)

        self.verify_button.setEnabled(False)
        self.reject_button.setEnabled(False)
        self.browse_evidence_button.setEnabled(False)
        self._start_worker(operation, on_success=on_success)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.is_busy:
            self.status_label.setText(
                "A dividend operation is still running. Wait for it to finish before closing."
            )
            event.ignore()
            return
        super().closeEvent(event)
