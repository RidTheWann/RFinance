# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Desktop controls for verified local backup and non-destructive restore."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rfinance.security.backup import BackupVerification, RestoreResult

if TYPE_CHECKING:
    from collections.abc import Callable

    from rfinance.security.backup import BackupService


class BackupWorker(QObject):
    """Run one backup or restore operation outside the Qt main thread."""

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


class BackupPage(QWidget):
    """Backup creation, verification and restore into a new folder."""

    def __init__(self, service: BackupService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._thread: QThread | None = None
        self._worker: BackupWorker | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(8)

        title = QLabel("Backup and restore")
        title.setStyleSheet("font-size: 17px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(
            QLabel(
                "Backups use SQLite's online backup API and carry a SHA-256 manifest. "
                "Restore writes a verified copy to a new folder; existing databases are "
                "never overwritten."
            )
        )
        buttons = QHBoxLayout()
        self.create_button = QPushButton("Create verified backup")
        self.create_button.setObjectName("createBackupButton")
        self.create_button.clicked.connect(self.create_backup)
        buttons.addWidget(self.create_button)
        self.restore_button = QPushButton("Restore backup to folder…")
        self.restore_button.setObjectName("restoreBackupButton")
        self.restore_button.clicked.connect(self.restore_backup)
        buttons.addWidget(self.restore_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.status_label = QLabel("No backup operation has been run in this session.")
        self.status_label.setObjectName("backupStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    @property
    def is_busy(self) -> bool:
        return self._thread is not None

    def create_backup(self) -> None:
        self._start(self._service.create_backup)

    def restore_backup(
        self,
        backup_path: str | None = None,
        target_dir: str | None = None,
    ) -> None:
        """Restore a chosen backup; paths may be injected by tests or file dialogs."""

        if not backup_path:
            backup_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select verified backup",
                str(self._service.backups_dir),
                "SQLite backup (*.sqlite3)",
            )
            if not backup_path:
                return
        if not target_dir:
            target_dir = QFileDialog.getExistingDirectory(self, "Select empty restore folder")
            if not target_dir:
                return
        source = Path(backup_path)
        destination = Path(target_dir)

        def operation() -> object:
            return self._service.restore_to(source, destination)

        self._start(operation)

    def _start(self, operation: Callable[[], object]) -> None:
        if self._thread is not None:
            return
        thread = QThread(self)
        worker = BackupWorker(operation)
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
        self.create_button.setEnabled(False)
        self.restore_button.setEnabled(False)
        self.status_label.setText("Working on the local backup…")
        thread.start()

    @Slot(object)
    def _completed(self, result: object) -> None:
        if isinstance(result, (BackupVerification, RestoreResult)):
            self.status_label.setText(
                f"Completed: {result.path}\n"
                f"SHA-256: {result.sha256}\n"
                f"Schema: {result.alembic_version} · "
                f"Ledger events: {result.ledger_event_count} · "
                f"Integrity: {result.integrity_check}"
            )
        else:
            self.status_label.setText(str(result))
        self.create_button.setEnabled(True)
        self.restore_button.setEnabled(True)

    @Slot(str)
    def _failed(self, message: str) -> None:
        self.status_label.setText(f"Backup operation failed: {message}")
        self.create_button.setEnabled(True)
        self.restore_button.setEnabled(True)

    def _thread_finished(self, thread: QThread) -> None:
        if self._thread is thread:
            self._thread = None
            self._worker = None
        self.create_button.setEnabled(True)
        self.restore_button.setEnabled(True)
