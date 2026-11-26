# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Reusable financial UI primitives and a GUI-thread-safe background task runner."""

from __future__ import annotations

import logging
import traceback
from typing import TYPE_CHECKING, Any, Literal

from rfinance.ui.qt_compat import (
    QObject,
    QRunnable,
    Qt,
    QThreadPool,
    QTimer,
    QtWidgets,
    Signal,
    Slot,
)
from rfinance.ui.theme import get_monospace_font

if TYPE_CHECKING:
    from collections.abc import Callable


_LOGGER = logging.getLogger(__name__)
PillTone = Literal["positive", "negative", "warning", "neutral"]


def _repolish(widget: QtWidgets.QWidget) -> None:
    """Re-evaluate dynamic QSS properties after a state change."""

    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)
    widget.update()


class StatusPill(QtWidgets.QLabel):
    """Compact semantic status badge for screening, risk and ingestion states."""

    def __init__(
        self,
        text: str = "",
        tone: PillTone = "neutral",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_state(text, tone)

    def set_state(self, text: str, tone: PillTone = "neutral") -> None:
        """Update the displayed state and its semantic color."""

        self.setText(text)
        self.setProperty("pill", tone)
        _repolish(self)


class KpiCard(QtWidgets.QFrame):
    """Metric card with monospaced value, trend badge and explicit provenance."""

    def __init__(
        self,
        title: str,
        initial_value: str = "—",
        subtitle: str = "",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("card", True)
        self.setMinimumWidth(190)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(7)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(8)

        self.title_label = QtWidgets.QLabel(title, self)
        self.title_label.setProperty("kpiTitle", True)
        header.addWidget(self.title_label)
        header.addStretch(1)

        self.delta_pill = StatusPill(parent=self)
        self.delta_pill.hide()
        header.addWidget(self.delta_pill)
        root.addLayout(header)

        self.value_label = QtWidgets.QLabel(initial_value, self)
        self.value_label.setProperty("kpiValue", True)
        self.value_label.setFont(get_monospace_font(point_size=16, bold=True))
        root.addWidget(self.value_label)

        self.subtitle_label = QtWidgets.QLabel(subtitle, self)
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setVisible(bool(subtitle))
        root.addWidget(self.subtitle_label)

        self.provenance_label = QtWidgets.QLabel("", self)
        self.provenance_label.setProperty("kpiProvenance", True)
        self.provenance_label.setWordWrap(True)
        self.provenance_label.hide()
        root.addWidget(self.provenance_label)

    def set_metric(
        self,
        value: str,
        delta_text: str | None = None,
        tone: PillTone = "neutral",
        subtitle: str | None = None,
        provenance: str | None = None,
    ) -> None:
        """Set the figure, optional trend, context and source description."""

        self.value_label.setText(value)
        if delta_text:
            self.delta_pill.set_state(delta_text, tone)
            self.delta_pill.show()
        else:
            self.delta_pill.hide()

        if subtitle is not None:
            self.subtitle_label.setText(subtitle)
            self.subtitle_label.setVisible(bool(subtitle))

        if provenance is not None:
            self.provenance_label.setText(provenance)
            self.provenance_label.setVisible(bool(provenance))


class ToastBanner(QtWidgets.QFrame):
    """Non-modal notification banner for completed UI operations."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("card", True)
        self.setObjectName("toastBanner")
        self.hide()

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        self.badge = StatusPill("INFO", "neutral", self)
        layout.addWidget(self.badge)

        self.message_label = QtWidgets.QLabel("", self)
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label, stretch=1)

        self.close_button = QtWidgets.QPushButton("Close", self)
        self.close_button.setFixedHeight(26)
        self.close_button.clicked.connect(self.hide)
        layout.addWidget(self.close_button)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(
        self,
        message: str,
        tone: PillTone = "neutral",
        label: str = "INFO",
        timeout_ms: int = 4500,
    ) -> None:
        """Show a message; use a non-positive timeout to keep it visible."""

        self._timer.stop()
        self.badge.set_state(label, tone)
        self.message_label.setText(message)
        self.show()
        if timeout_ms > 0:
            self._timer.start(timeout_ms)


class WorkerSignals(QObject):
    """Signals emitted by a background runnable."""

    started = Signal()
    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()


class AsyncWorker(QRunnable):
    """Execute one blocking callable without occupying the Qt GUI thread."""

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.setAutoDelete(False)

    @Slot()
    def run(self) -> None:
        self.signals.started.emit()
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as exc:  # noqa: BLE001 - report failures to the caller.
            detail = f"{exc}\n{traceback.format_exc(limit=3)}"
            self.signals.failed.emit(detail)
        else:
            self.signals.succeeded.emit(result)
        finally:
            self.signals.finished.emit()


class TaskRunner(QObject):
    """Retain active runnables and deliver all callbacks on the runner's Qt thread."""

    _success_dispatch = Signal(object, object)
    _error_dispatch = Signal(object, str)
    _finished_dispatch = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._active: set[AsyncWorker] = set()
        self._on_success: dict[AsyncWorker, Callable[[Any], None] | None] = {}
        self._on_error: dict[AsyncWorker, Callable[[str], None] | None] = {}
        self._on_finished: dict[AsyncWorker, Callable[[], None] | None] = {}

        self._success_dispatch.connect(self._deliver_success)
        self._error_dispatch.connect(self._deliver_error)
        self._finished_dispatch.connect(self._deliver_finished)

    @property
    def active_count(self) -> int:
        """Number of workers retained until their completion is delivered."""

        return len(self._active)

    def submit(
        self,
        fn: Callable[..., Any],
        *args: Any,
        on_success: Callable[[Any], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        on_finished: Callable[[], None] | None = None,
        **kwargs: Any,
    ) -> AsyncWorker:
        """Schedule a callable and dispatch its callbacks on the GUI thread."""

        worker = AsyncWorker(fn, *args, **kwargs)
        self._active.add(worker)
        self._on_success[worker] = on_success
        self._on_error[worker] = on_error
        self._on_finished[worker] = on_finished

        worker.signals.succeeded.connect(
            lambda result, task=worker: self._success_dispatch.emit(task, result)
        )
        worker.signals.failed.connect(
            lambda error, task=worker: self._error_dispatch.emit(task, error)
        )
        worker.signals.finished.connect(
            lambda task=worker: self._finished_dispatch.emit(task)
        )
        self._pool.start(worker)
        return worker

    @Slot(object, object)
    def _deliver_success(self, worker: AsyncWorker, result: Any) -> None:
        callback = self._on_success.get(worker)
        if callback is not None:
            try:
                callback(result)
            except Exception:  # noqa: BLE001 - callback errors must not escape a Qt slot.
                _LOGGER.exception("Background task success callback failed")

    @Slot(object, str)
    def _deliver_error(self, worker: AsyncWorker, error: str) -> None:
        callback = self._on_error.get(worker)
        if callback is not None:
            try:
                callback(error)
            except Exception:  # noqa: BLE001 - callback errors must not escape a Qt slot.
                _LOGGER.exception("Background task error callback failed")

    @Slot(object)
    def _deliver_finished(self, worker: AsyncWorker) -> None:
        self._active.discard(worker)
        callback = self._on_finished.pop(worker, None)
        self._on_success.pop(worker, None)
        self._on_error.pop(worker, None)
        if callback is not None:
            try:
                callback()
            except Exception:  # noqa: BLE001 - callback errors must not escape a Qt slot.
                _LOGGER.exception("Background task finished callback failed")

    def wait_for_done(self, timeout_ms: int = -1) -> bool:
        """Wait for queued work; intended for controlled shutdown and tests."""

        return self._pool.waitForDone(timeout_ms)


__all__ = [
    "AsyncWorker",
    "KpiCard",
    "PillTone",
    "StatusPill",
    "TaskRunner",
    "ToastBanner",
]
