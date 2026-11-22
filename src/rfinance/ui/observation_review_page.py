# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Desktop workflow for evidence-backed market-observation review."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
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

from rfinance.application.observation_review import (
    ObservationReviewDecision,
    ObservationReviewResult,
    ObservationReviewService,
)


class ObservationReviewWorker(QObject):
    """Archive evidence and append an observation decision outside the UI thread."""

    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        service: ObservationReviewService,
        observation_id: str,
        decision: ObservationReviewDecision,
        reviewer_label: str,
        evidence_file: Path,
        notes: str,
    ) -> None:
        super().__init__()
        self._service = service
        self._observation_id = observation_id
        self._decision = decision
        self._reviewer_label = reviewer_label
        self._evidence_file = evidence_file
        self._notes = notes

    @Slot()
    def run(self) -> None:
        try:
            result = self._service.review_observation_from_file(
                self._observation_id,
                decision=self._decision,
                reviewer_label=self._reviewer_label,
                evidence_file=self._evidence_file,
                notes=self._notes,
            )
        except Exception as error:
            self.failed.emit(str(error))
            return
        self.completed.emit(result)


class ObservationReviewPage(QWidget):
    """Evidence-first UI for reviewing imported prices without mutating raw rows."""

    def __init__(self, service: ObservationReviewService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._thread: QThread | None = None
        self._worker: ObservationReviewWorker | None = None
        self._build_ui()
        self.refresh_queue()

    @property
    def is_busy(self) -> bool:
        """Whether a review is active, including its pending Qt cleanup.

        ``_thread`` is cleared from the thread's ``finished`` handler, which is
        queued to the main event loop. Reporting busy via ``isRunning()`` alone
        would allow a second submit to be silently ignored in the gap between
        the thread stopping and that cleanup running.
        """

        return self._thread is not None

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(12)

        title = QLabel("Observation Review")
        title.setStyleSheet("font-size: 26px; font-weight: 600;")
        layout.addWidget(title)
        description = QLabel(
            "Inspect imported market prices and record an evidence-backed decision. "
            "A VERIFIED decision is an operator review, not a live-data guarantee; "
            "freshness, instrument identity, currency, and source policy remain separate gates."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        self.empty_label = QLabel(
            "No market observations are available. Import a user-supplied CSV from Overview first."
        )
        self.empty_label.setObjectName("observationReviewEmpty")
        layout.addWidget(self.empty_label)

        self.observation_table = QTableWidget(0, 7)
        self.observation_table.setObjectName("observationReviewQueue")
        self.observation_table.setHorizontalHeaderLabels(
            [
                "Observed (UTC)",
                "Instrument",
                "Close",
                "Currency",
                "Raw quality",
                "Effective quality",
                "Source ID",
            ]
        )
        self.observation_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.observation_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.observation_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.observation_table.setAlternatingRowColors(True)
        self.observation_table.setMaximumHeight(240)
        self.observation_table.horizontalHeader().setStretchLastSection(True)
        self.observation_table.itemSelectionChanged.connect(self._on_selection_changed)
        self.observation_table.hide()
        layout.addWidget(self.observation_table)

        form_title = QLabel("Evidence-backed decision")
        form_title.setStyleSheet("font-size: 17px; font-weight: 600;")
        layout.addWidget(form_title)
        form = QFormLayout()

        self.selected_observation_label = QLabel("Select an observation above")
        form.addRow("Selected observation", self.selected_observation_label)

        self.reviewer_input = QLineEdit()
        self.reviewer_input.setPlaceholderText("Operator / reviewer label")
        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("What was checked and why is this decision justified?")
        form.addRow("Reviewer", self.reviewer_input)
        form.addRow("Review notes", self.notes_input)

        evidence_row = QWidget()
        evidence_layout = QHBoxLayout(evidence_row)
        evidence_layout.setContentsMargins(0, 0, 0, 0)
        self.evidence_path_input = QLineEdit()
        self.evidence_path_input.setReadOnly(True)
        self.evidence_path_input.setPlaceholderText("Select a local source document")
        self.browse_evidence_button = QPushButton("Choose evidence file")
        self.browse_evidence_button.clicked.connect(self._select_evidence)
        evidence_layout.addWidget(self.evidence_path_input, 1)
        evidence_layout.addWidget(self.browse_evidence_button)
        form.addRow("Evidence file", evidence_row)
        layout.addLayout(form)

        actions = QHBoxLayout()
        self.verify_button = QPushButton("Record VERIFIED decision")
        self.verify_button.setObjectName("verifyObservationButton")
        self.verify_button.clicked.connect(lambda: self._submit(ObservationReviewDecision.VERIFIED))
        self.reject_button = QPushButton("Record REJECTED decision")
        self.reject_button.setObjectName("rejectObservationButton")
        self.reject_button.clicked.connect(lambda: self._submit(ObservationReviewDecision.REJECTED))
        actions.addWidget(self.verify_button)
        actions.addWidget(self.reject_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.status_label = QLabel(
            "Raw observations are immutable. Decisions are appended to the local audit ledger."
        )
        self.status_label.setObjectName("observationReviewStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        history_title = QLabel("Selected observation review history")
        history_title.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(history_title)
        self.history_table = QTableWidget(0, 5)
        self.history_table.setObjectName("observationReviewHistory")
        self.history_table.setHorizontalHeaderLabels(
            ["Reviewed (UTC)", "Previous quality", "Decision", "Reviewer", "Evidence"]
        )
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_table.setMaximumHeight(180)
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.hide()
        layout.addWidget(self.history_table)
        layout.addStretch(1)

    def _selected_observation_id(self) -> str | None:
        selected = self.observation_table.selectedItems()
        if not selected:
            return None
        value = selected[0].data(Qt.ItemDataRole.UserRole)
        return value if isinstance(value, str) else None

    def refresh_queue(self, *, select_observation_id: str | None = None) -> None:
        """Refresh raw/effective quality without changing observation records."""

        previous_selection = select_observation_id or self._selected_observation_id()
        candidates = self._service.list_candidates(limit=500)
        self.observation_table.setRowCount(len(candidates))
        has_candidates = bool(candidates)
        self.empty_label.setVisible(not has_candidates)
        self.observation_table.setVisible(has_candidates)

        selected_row: int | None = None
        for row_index, candidate in enumerate(candidates):
            values = (
                candidate.observed_at_utc.replace("T", " "),
                candidate.instrument_id,
                candidate.close,
                candidate.currency,
                candidate.raw_quality,
                candidate.effective_quality,
                candidate.source_id,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, candidate.observation_id)
                item.setToolTip(
                    f"Observation: {candidate.observation_id}\n"
                    f"Acquired (UTC): {candidate.acquired_at_utc}\n"
                    f"Source ID: {candidate.source_id}"
                )
                self.observation_table.setItem(row_index, column, item)
            if candidate.observation_id == previous_selection:
                selected_row = row_index

        self.observation_table.resizeColumnsToContents()
        if selected_row is not None:
            self.observation_table.selectRow(selected_row)
        elif candidates:
            self.observation_table.selectRow(0)
        else:
            self.selected_observation_label.setText("Select an observation above")
            self.history_table.setRowCount(0)
            self.history_table.hide()
        self.refresh_history()

    def _on_selection_changed(self) -> None:
        observation_id = self._selected_observation_id()
        self.selected_observation_label.setText(observation_id or "Select an observation above")
        self.refresh_history()

    def refresh_history(self) -> None:
        """Render append-only review history for the selected observation."""

        observation_id = self._selected_observation_id()
        history = () if observation_id is None else self._service.review_history(observation_id)
        self.history_table.setRowCount(len(history))
        self.history_table.setVisible(bool(history))
        for row_index, event in enumerate(history):
            values = (
                event.reviewed_at_utc.replace("T", " "),
                event.previous_quality,
                event.decision,
                event.reviewer_label,
                Path(event.evidence_reference).name,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(
                    f"Review: {event.review_id}\n"
                    f"Evidence: {event.evidence_reference}\n"
                    f"SHA-256: {event.evidence_sha256}\n"
                    f"Notes: {event.notes}"
                )
                self.history_table.setItem(row_index, column, item)
        self.history_table.resizeColumnsToContents()

    def _select_evidence(self) -> None:
        selected_file, _ = QFileDialog.getOpenFileName(
            self,
            "Select market-price evidence",
            str(Path.home()),
            "Evidence files (*.pdf *.png *.jpg *.jpeg *.txt *.csv *.xlsx *.docx);;All files (*)",
        )
        if selected_file:
            self.evidence_path_input.setText(selected_file)

    def _submit(self, decision: ObservationReviewDecision) -> None:
        if self._thread is not None:
            return
        observation_id = self._selected_observation_id()
        evidence_text = self.evidence_path_input.text().strip()
        reviewer_label = self.reviewer_input.text().strip()
        notes = self.notes_input.text().strip()
        if observation_id is None:
            self.status_label.setText("Select a market observation to review.")
            return
        if not evidence_text:
            self.status_label.setText("Choose a local evidence file first.")
            return
        if not reviewer_label or not notes:
            self.status_label.setText("Reviewer label and review notes are required.")
            return

        worker = ObservationReviewWorker(
            self._service,
            observation_id,
            decision,
            reviewer_label,
            Path(evidence_text),
            notes,
        )
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(self._on_completed)
        worker.failed.connect(self._on_failed)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.completed.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(lambda: self._on_thread_finished(thread))
        thread.finished.connect(thread.deleteLater)

        self._thread = thread
        self._worker = worker
        self.verify_button.setEnabled(False)
        self.reject_button.setEnabled(False)
        self.browse_evidence_button.setEnabled(False)
        self.status_label.setText("Archiving evidence and recording the review decision…")
        thread.start()

    def _on_completed(self, result: ObservationReviewResult) -> None:
        self.status_label.setText(
            f"Review recorded: {result.observation_id} is effectively {result.decision}. "
            f"Evidence archived at {result.evidence_reference}; "
            f"SHA-256 {result.evidence_sha256}. "
            "The original market-observation row remains unchanged."
        )
        self.evidence_path_input.clear()
        self.notes_input.clear()
        self.refresh_queue(select_observation_id=result.observation_id)

    def _on_failed(self, message: str) -> None:
        self.status_label.setText(f"Observation review failed: {message}")

    def _on_thread_finished(self, thread: QThread) -> None:
        if self._thread is thread:
            self._thread = None
            self._worker = None
        self.verify_button.setEnabled(True)
        self.reject_button.setEnabled(True)
        self.browse_evidence_button.setEnabled(True)
