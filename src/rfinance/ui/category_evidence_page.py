# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Desktop form for evidence-backed instrument category decisions."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QThread, Signal, Slot
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
    QVBoxLayout,
    QWidget,
)

from rfinance.analysis.portfolio.valuation import ValuationCategory

if TYPE_CHECKING:
    from collections.abc import Callable

    from rfinance.application.instrument_category import InstrumentCategoryService


class CategoryEvidenceWorker(QObject):
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


class CategoryEvidencePanel(QWidget):
    """Record and inspect the latest category decision per instrument."""

    def __init__(
        self,
        service: InstrumentCategoryService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._evidence_path: Path | None = None
        self._thread: QThread | None = None
        self._worker: CategoryEvidenceWorker | None = None
        self._build_ui()
        self.refresh()

    @property
    def is_busy(self) -> bool:
        return self._thread is not None

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(8)
        title = QLabel("Instrument category evidence")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(
            QLabel(
                "Category and lot size are recorded only with an inspected evidence file. "
                "A verified instrument identity is required; this does not verify a price."
            )
        )

        form = QFormLayout()
        self.instrument_input = QLineEdit()
        self.instrument_input.setObjectName("categoryEvidenceInstrument")
        self.category_combo = QComboBox()
        self.category_combo.addItems(
            [
                item.value
                for item in ValuationCategory
                if item.value in {"EQUITY_INDEX", "DIVIDEND_EQUITY", "MONEY_MARKET"}
            ]
        )
        self.lot_input = QLineEdit("100")
        self.reviewer_input = QLineEdit()
        self.notes_input = QLineEdit()
        form.addRow("Instrument ID", self.instrument_input)
        form.addRow("Category", self.category_combo)
        form.addRow("Lot size", self.lot_input)
        form.addRow("Reviewer", self.reviewer_input)
        form.addRow("Notes", self.notes_input)
        layout.addLayout(form)

        evidence_row = QHBoxLayout()
        self.evidence_button = QPushButton("Choose evidence file…")
        self.evidence_button.setObjectName("chooseCategoryEvidenceButton")
        self.evidence_button.clicked.connect(self._choose_evidence)
        evidence_row.addWidget(self.evidence_button)
        self.evidence_label = QLabel("No evidence file selected.")
        self.evidence_label.setWordWrap(True)
        evidence_row.addWidget(self.evidence_label)
        evidence_row.addStretch(1)
        layout.addLayout(evidence_row)

        actions = QHBoxLayout()
        self.verify_button = QPushButton("Record VERIFIED")
        self.verify_button.setObjectName("recordVerifiedCategoryButton")
        self.verify_button.clicked.connect(lambda: self._record("VERIFIED"))
        actions.addWidget(self.verify_button)
        self.reject_button = QPushButton("Record REJECTED")
        self.reject_button.setObjectName("recordRejectedCategoryButton")
        self.reject_button.clicked.connect(lambda: self._record("REJECTED"))
        actions.addWidget(self.reject_button)
        self.refresh_button = QPushButton("Refresh decisions")
        self.refresh_button.setObjectName("refreshCategoryEvidenceButton")
        self.refresh_button.clicked.connect(self.refresh)
        actions.addWidget(self.refresh_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.status_label = QLabel("No category decision has been recorded in this session.")
        self.status_label.setObjectName("categoryEvidenceStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.table = QTableWidget(0, 6)
        self.table.setObjectName("categoryEvidenceTable")
        self.table.setHorizontalHeaderLabels(
            ["Instrument", "Category", "Lot", "Decision", "Evidence", "Reviewer"]
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

    def _choose_evidence(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self, "Select category evidence", str(Path.home()), "All files (*)"
        )
        if selected:
            self._evidence_path = Path(selected)
            self.evidence_label.setText(self._evidence_path.name)

    def refresh(self) -> None:
        decisions = self._service.latest_decisions()
        self.table.setRowCount(len(decisions))
        for row, decision in enumerate(decisions):
            values = (
                decision.instrument_id,
                decision.category.value,
                format(decision.lot_size, "f"),
                decision.decision,
                decision.evidence_reference,
                decision.reviewer_label,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(f"{decision.notes}\nSHA-256: {decision.evidence_sha256}")
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()

    def _record(self, decision: str) -> None:
        if self._thread is not None:
            return
        try:
            lot_size = Decimal(self.lot_input.text().strip())
        except (InvalidOperation, ValueError):
            self.status_label.setText("Lot size must be a valid Decimal value.")
            return
        if self._evidence_path is None:
            self.status_label.setText("Choose an evidence file before recording a decision.")
            return
        instrument_id = self.instrument_input.text().strip()
        category = ValuationCategory(self.category_combo.currentText())
        reviewer = self.reviewer_input.text().strip()
        notes = self.notes_input.text().strip()
        evidence_path = self._evidence_path
        service = self._service

        def operation() -> object:
            return service.record_from_file(
                instrument_id,
                category=category,
                lot_size=lot_size,
                decision=decision,
                reviewer_label=reviewer,
                notes=notes,
                evidence_file=evidence_path,
            )

        thread = QThread(self)
        worker = CategoryEvidenceWorker(operation)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(self._completed)
        worker.failed.connect(self._failed)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.completed.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(lambda: self._thread_finished(thread))
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        self._worker = worker
        self.verify_button.setEnabled(False)
        self.reject_button.setEnabled(False)
        self.status_label.setText(f"Recording {decision} category evidence…")
        thread.start()

    @Slot(object)
    def _completed(self, result: object) -> None:
        self.status_label.setText(f"Recorded decision for {getattr(result, 'instrument_id', '')}.")
        self.refresh()

    @Slot(str)
    def _failed(self, message: str) -> None:
        self.status_label.setText(f"Category evidence failed: {message}")

    def _thread_finished(self, thread: QThread) -> None:
        if self._thread is thread:
            self._thread = None
            self._worker = None
        self.verify_button.setEnabled(True)
        self.reject_button.setEnabled(True)
