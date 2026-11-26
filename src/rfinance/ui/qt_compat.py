# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Small Qt binding compatibility surface for the presentation layer.

PySide6 remains the supported runtime dependency. The fallback keeps reusable
widgets portable to PyQt6-based integration environments without importing
binding-specific signal names throughout the UI package.
"""

from __future__ import annotations

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import (
        QObject,
        QRunnable,
        QThreadPool,
        QTimer,
        Qt,
        Signal,
        Slot,
    )
except ImportError:  # pragma: no cover - PySide6 is the supported application binding.
    from PyQt6 import QtCore, QtGui, QtWidgets  # type: ignore[no-redef]
    from PyQt6.QtCore import (  # type: ignore[no-redef]
        QObject,
        QRunnable,
        QThreadPool,
        QTimer,
        Qt,
        pyqtSignal as Signal,
        pyqtSlot as Slot,
    )

__all__ = [
    "QtCore",
    "QtGui",
    "QtWidgets",
    "QObject",
    "QRunnable",
    "Qt",
    "QThreadPool",
    "QTimer",
    "Signal",
    "Slot",
]
