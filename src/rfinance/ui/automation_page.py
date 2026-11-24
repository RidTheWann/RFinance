# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Desktop view for registered local jobs and their append-only run ledger."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from rfinance.application.automation import AutomationService


class AutomationWorker(QObject):
    """Run one registered job outside the Qt main thread."""

    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, service: AutomationService, job_id: str) -> None:
        super().__init__()
        self._service = service
        self._job_id = job_id

    @Slot()
    def run(self) -> None:
        try:
            result = self._service.run(self._job_id)
        except Exception as error:
            self.failed.emit(str(error))
            return
        self.completed.emit(result)


class AutomationPage(QWidget):
    """Manual job execution and inspection; no scheduler runs implicitly."""

    def __init__(self, service: AutomationService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._thread: QThread | None = None
        self._worker: AutomationWorker | None = None
        self._build_ui()
        self.refresh()

    @property
    def is_busy(self) -> bool:
        return self._thread is not None

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)
        title = QLabel("Automation Center")
        title.setObjectName("automationPageTitle")
        title.setStyleSheet("font-size: 26px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(
            QLabel(
                "Only code-registered local jobs can run here. Each attempt is recorded "
                "in an append-only ledger. No job runs automatically and no website or "
                "external command can be added at runtime."
            )
        )

        self.jobs_table = QTableWidget(0, 5)
        self.jobs_table.setObjectName("automationJobsTable")
        self.jobs_table.setHorizontalHeaderLabels(
            ["Job ID", "Name", "Enabled", "Max attempts", "Timeout (s)"]
        )
        self.jobs_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.jobs_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.jobs_table.setAlternatingRowColors(True)
        layout.addWidget(self.jobs_table)

        controls = QHBoxLayout()
        self.run_button = QPushButton("Run selected job")
        self.run_button.setObjectName("runAutomationJobButton")
        self.run_button.clicked.connect(self.run_selected)
        controls.addWidget(self.run_button)
        self.refresh_button = QPushButton("Refresh run history")
        self.refresh_button.setObjectName("refreshAutomationRunsButton")
        self.refresh_button.clicked.connect(self.refresh)
        controls.addWidget(self.refresh_button)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.status_label = QLabel("No job has been run in this session.")
        self.status_label.setObjectName("automationStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.runs_table = QTableWidget(0, 6)
        self.runs_table.setObjectName("automationRunsTable")
        self.runs_table.setHorizontalHeaderLabels(
            ["Job", "Status", "Attempt", "Started (UTC)", "Detail / error", "Methodology"]
        )
        self.runs_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.runs_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.runs_table.setAlternatingRowColors(True)
        self.runs_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.runs_table, 1)

    def refresh(self) -> None:
        definitions = self._service.definitions()
        self.jobs_table.setRowCount(len(definitions))
        for row, job in enumerate(definitions):
            values = (
                job.job_id,
                job.display_name,
                "yes" if job.enabled else "no",
                str(job.max_attempts),
                str(job.timeout_seconds),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(job.description)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, job.job_id)
                self.jobs_table.setItem(row, column, item)
        if definitions:
            self.jobs_table.selectRow(0)

        runs = self._service.recent_runs()
        self.runs_table.setRowCount(len(runs))
        for row, run in enumerate(runs):
            run_values = (
                run.job_id,
                run.status,
                str(run.attempt),
                run.started_at_utc.replace("T", " "),
                run.detail or run.error or "—",
                run.methodology_version,
            )
            for column, value in enumerate(run_values):
                self.runs_table.setItem(row, column, QTableWidgetItem(value))
        self.jobs_table.resizeColumnsToContents()
        self.runs_table.resizeColumnsToContents()

    def run_selected(self) -> None:
        if self._thread is not None:
            return
        # Read the identifier from column 0's user data, not whichever cell was
        # clicked: clicking Name/Enabled/Schedule must still target the right job.
        current_row = self.jobs_table.currentRow()
        if current_row < 0:
            self.status_label.setText("Select a registered job first.")
            return
        id_item = self.jobs_table.item(current_row, 0)
        job_id = "" if id_item is None else str(id_item.data(Qt.ItemDataRole.UserRole) or "")
        if not job_id:
            self.status_label.setText("Select a registered job first.")
            return
        thread = QThread(self)
        worker = AutomationWorker(self._service, job_id)
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
        self.run_button.setEnabled(False)
        self.status_label.setText(f"Running {job_id}…")
        thread.start()

    @Slot(object)
    def _completed(self, result: object) -> None:
        status = result.status if hasattr(result, "status") else "UNKNOWN"
        detail = getattr(result, "detail", None) or getattr(result, "error", None) or "—"
        self.status_label.setText(f"Run finished with status {status}. {detail}")
        self.run_button.setEnabled(True)
        self.refresh()

    @Slot(str)
    def _failed(self, message: str) -> None:
        self.status_label.setText(f"Job failed to start: {message}")
        self.run_button.setEnabled(True)

    def _thread_finished(self, thread: QThread) -> None:
        if self._thread is thread:
            self._thread = None
            self._worker = None
        self.run_button.setEnabled(True)
