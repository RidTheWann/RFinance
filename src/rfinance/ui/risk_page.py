# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Desktop view for deterministic risk review and explicit event resolution."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from decimal import Decimal

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rfinance.domain.risk.controls import RiskAssessment, RiskRule
from rfinance.ui.formatting import MISSING, format_decimal, format_percent

if TYPE_CHECKING:
    from collections.abc import Callable

    from rfinance.application.portfolio_valuation import PortfolioValuationService
    from rfinance.application.risk_monitoring import RiskMonitoringService


class RiskEvaluationWorker(QObject):
    """Run valuation plus risk evaluation outside the Qt main thread."""

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


class RiskPage(QWidget):
    """Risk status and auditable event review; no financial formulas in the UI."""

    def __init__(
        self,
        risk: RiskMonitoringService,
        *,
        valuation: PortfolioValuationService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._risk = risk
        self._valuation = valuation
        self._thread: QThread | None = None
        self._worker: RiskEvaluationWorker | None = None
        self._drawdown: str | None = None
        self._build_ui()
        self.refresh()

    @property
    def is_busy(self) -> bool:
        """Whether evaluation is active, including pending Qt cleanup."""

        return self._thread is not None

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(12)

        title = QLabel("Risk Management")
        title.setObjectName("riskTitle")
        title.setStyleSheet("font-size: 26px; font-weight: 600;")
        layout.addWidget(title)
        description = QLabel(
            "Review triggers are deterministic and use the recorded portfolio valuation "
            "series. Thresholds are review prompts, not loss limits. Drawdown is unknown "
            "when valuation is incomplete; simulated figures are never brokerage results."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        self.level_label = QLabel("NORMAL")
        self.level_label.setObjectName("riskLevel")
        self.level_label.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(self.level_label)
        self.drawdown_label = QLabel("Drawdown: not available")
        self.drawdown_label.setObjectName("riskDrawdown")
        layout.addWidget(self.drawdown_label)

        actions = QHBoxLayout()
        self.evaluate_button = QPushButton("Evaluate current portfolio")
        self.evaluate_button.setObjectName("evaluateRiskButton")
        self.evaluate_button.setEnabled(self._valuation is not None)
        self.evaluate_button.clicked.connect(self.evaluate)
        self.refresh_button = QPushButton("Refresh events")
        self.refresh_button.setObjectName("refreshRiskButton")
        self.refresh_button.clicked.connect(self.refresh)
        actions.addWidget(self.evaluate_button)
        actions.addWidget(self.refresh_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.events_table = QTableWidget(0, 6)
        self.events_table.setObjectName("riskEventsTable")
        self.events_table.setHorizontalHeaderLabels(
            ["Triggered (UTC)", "Rule", "Severity", "Observed", "Threshold", "Reviewed"]
        )
        self.events_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.events_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.events_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.events_table.setAlternatingRowColors(True)
        self.events_table.setMaximumHeight(220)
        self.events_table.horizontalHeader().setStretchLastSection(True)
        self.events_table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.events_table)

        form_title = QLabel("Explicit review of a selected event")
        form_title.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(form_title)
        form = QFormLayout()
        self.selected_event_label = QLabel("Select an event above")
        self.selected_event_label.setObjectName("riskSelectedEvent")
        form.addRow("Selected event", self.selected_event_label)
        self.reviewer_input = QLineEdit()
        self.reviewer_input.setObjectName("riskReviewerInput")
        self.notes_input = QLineEdit()
        self.notes_input.setObjectName("riskNotesInput")
        self.evidence_input = QLineEdit()
        self.evidence_input.setObjectName("riskEvidenceInput")
        form.addRow("Reviewer", self.reviewer_input)
        form.addRow("Review notes", self.notes_input)
        form.addRow("Evidence reference", self.evidence_input)
        layout.addLayout(form)

        self.review_button = QPushButton("Record review")
        self.review_button.setObjectName("recordRiskReviewButton")
        self.review_button.setEnabled(False)
        self.review_button.clicked.connect(self.record_review)
        layout.addWidget(self.review_button)

        self.status_label = QLabel("No risk evaluation has been run in this session.")
        self.status_label.setObjectName("riskStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        layout.addStretch(1)

    def refresh(self) -> None:
        """Render unresolved events from local storage."""

        events = self._risk.active_events()
        self.events_table.setRowCount(len(events))
        for row_index, event in enumerate(events):
            values = (
                event.triggered_at_utc.replace("T", " "),
                event.rule.value,
                event.severity.value,
                self._render_metric(event.rule, event.observed_value),
                self._render_metric(event.rule, event.threshold),
                "Reviewed" if event.review is not None else "Pending",
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, event.event_id)
                self.events_table.setItem(row_index, column, cell)
        self.events_table.resizeColumnsToContents()

        rules = {event.rule for event in events}
        if RiskRule.CRITICAL_DRAWDOWN in rules or RiskRule.PROHIBITED_ACTIVITY in rules:
            self.level_label.setText("CRITICAL — ALLOCATION CHANGES SUSPENDED")
        elif rules:
            self.level_label.setText("REVIEW REQUIRED — NEW BUY CANDIDATES SUSPENDED")
        else:
            self.level_label.setText("NORMAL")
        self.drawdown_label.setText(
            "Drawdown: not available" if self._drawdown is None else f"Drawdown: {self._drawdown}"
        )
        if not events:
            self.selected_event_label.setText("Select an event above")
            self.review_button.setEnabled(False)
        self._on_selection_changed()

    def _selected_event_id(self) -> str | None:
        selected = self.events_table.selectedItems()
        if not selected:
            return None
        value = selected[0].data(Qt.ItemDataRole.UserRole)
        return value if isinstance(value, str) else None

    @staticmethod
    def _render_metric(rule: RiskRule, value: Decimal | None) -> str:
        """Render a risk metric in the unit its rule measures."""

        if value is None:
            return MISSING
        ratio_rules = {
            RiskRule.CRITICAL_DRAWDOWN,
            RiskRule.ELEVATED_DRAWDOWN,
            RiskRule.SINGLE_INSTRUMENT_CONCENTRATION,
            RiskRule.SECTOR_CONCENTRATION,
            RiskRule.ALLOCATION_DEVIATION,
        }
        return format_percent(value) if rule in ratio_rules else format_decimal(value)

    def _on_selection_changed(self) -> None:
        event_id = self._selected_event_id()
        self.selected_event_label.setText(event_id or "Select an event above")
        # Clear the draft fields so a note written for one event cannot be
        # submitted against a different event after re-selection.
        self.reviewer_input.clear()
        self.notes_input.clear()
        self.evidence_input.clear()
        self.review_button.setEnabled(event_id is not None and not self.is_busy)

    def evaluate(self) -> None:
        """Record a valuation point and evaluate risk on a worker thread."""

        if self.is_busy:
            return
        if self._valuation is None:
            self.status_label.setText("Portfolio valuation is unavailable in this context.")
            return

        def operation() -> object:
            snapshot = self._valuation.value()  # type: ignore[union-attr]
            return self._risk.evaluate_valuation(snapshot.valuation)

        thread = QThread(self)
        worker = RiskEvaluationWorker(operation)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(self._evaluation_completed)
        worker.failed.connect(self._evaluation_failed)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.completed.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(lambda: self._thread_finished(thread))
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        self._worker = worker
        self.review_button.setEnabled(False)
        self.evaluate_button.setEnabled(False)
        self.status_label.setText("Valuing the ledger and evaluating risk triggers…")
        thread.start()

    def _evaluation_completed(self, result: object) -> None:
        if not isinstance(result, RiskAssessment):
            self.status_label.setText("Risk evaluation returned an unexpected result.")
            return
        self._drawdown = (
            "not available"
            if result.drawdown is None
            else f"{format_percent(result.drawdown)} of peak"
        )
        self.status_label.setText(
            "Risk evaluation complete. Unresolved events require an explicit review."
        )
        self.refresh()

    def _evaluation_failed(self, message: str) -> None:
        self.status_label.setText(f"Risk evaluation failed: {message}")

    def _thread_finished(self, thread: QThread) -> None:
        if self._thread is thread:
            self._thread = None
            self._worker = None
        self.evaluate_button.setEnabled(self._valuation is not None)
        self._on_selection_changed()

    def record_review(self) -> None:
        """Append an explicit review for the selected event."""

        event_id = self._selected_event_id()
        reviewer = self.reviewer_input.text().strip()
        notes = self.notes_input.text().strip()
        evidence = self.evidence_input.text().strip()
        if event_id is None:
            self.status_label.setText("Select a risk event first.")
            return
        if not reviewer or not notes or not evidence:
            self.status_label.setText(
                "Reviewer, review notes and an evidence reference are all required."
            )
            return
        try:
            self._risk.record_review(
                event_id,
                reviewer_label=reviewer,
                notes=notes,
                evidence_reference=evidence,
            )
        except ValueError as error:
            self.status_label.setText(f"Review was not recorded: {error}")
            return
        self.reviewer_input.clear()
        self.notes_input.clear()
        self.evidence_input.clear()
        self.status_label.setText("Review recorded. The resolved event is no longer active.")
        self.refresh()
