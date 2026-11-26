# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication

from rfinance.ui.theme import (
    DARK_THEME,
    LIGHT_THEME,
    apply_app_theme,
    build_stylesheet,
    get_monospace_font,
    get_theme_tokens,
)
from rfinance.ui.widgets.financial_components import KpiCard, StatusPill, TaskRunner, ToastBanner

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def test_theme_tokens_and_stylesheet_are_available(qtbot: QtBot) -> None:
    app = QApplication.instance()
    assert app is not None

    dark = apply_app_theme(app)
    assert dark == DARK_THEME
    assert "#0B0F17" in app.styleSheet()
    assert "QTableView" in app.styleSheet()
    assert get_theme_tokens("light") == LIGHT_THEME
    assert "#F8FAFC" in build_stylesheet(LIGHT_THEME)

    font = get_monospace_font(point_size=11, bold=True)
    assert font.pointSize() == 11
    assert font.bold()


def test_financial_widgets_expose_trend_and_provenance(qtbot: QtBot) -> None:
    card = KpiCard("Portfolio value", "Rp5,000,000")
    qtbot.addWidget(card)
    card.set_metric(
        "Rp5,250,000",
        delta_text="+5.0%",
        tone="positive",
        subtitle="As of 2026-11-26",
        provenance="Local ledger + verified market observations",
    )

    assert card.value_label.text() == "Rp5,250,000"
    assert card.delta_pill.text() == "+5.0%"
    assert card.delta_pill.property("pill") == "positive"
    assert card.subtitle_label.text() == "As of 2026-11-26"
    assert card.provenance_label.text() == "Local ledger + verified market observations"

    pill = StatusPill("BREACH", "negative")
    qtbot.addWidget(pill)
    assert pill.property("pill") == "negative"
    pill.set_state("REVIEW", "warning")
    assert pill.text() == "REVIEW"
    assert pill.property("pill") == "warning"


def test_toast_banner_can_be_persistent_or_timed(qtbot: QtBot) -> None:
    toast = ToastBanner()
    qtbot.addWidget(toast)

    toast.show_message("Import completed", tone="positive", label="DONE", timeout_ms=0)
    assert toast.isVisible()
    assert toast.badge.text() == "DONE"

    toast.show_message("A warning", tone="warning", label="REVIEW", timeout_ms=25)
    qtbot.waitUntil(lambda: not toast.isVisible(), timeout=1000)


def test_task_runner_delivers_callbacks_on_its_qt_thread(qtbot: QtBot) -> None:
    app = QApplication.instance()
    assert app is not None

    runner = TaskRunner()
    results: list[tuple[int, QThread | None]] = []
    finished: list[bool] = []
    worker_thread_ids: list[int] = []

    def operation() -> int:
        worker_thread_ids.append(threading.get_ident())
        return 42

    def on_success(value: object) -> None:
        results.append((int(value), QThread.currentThread()))

    runner.submit(operation, on_success=on_success, on_finished=lambda: finished.append(True))

    qtbot.waitUntil(lambda: bool(results) and bool(finished), timeout=3000)
    assert results[0][0] == 42
    assert results[0][1] == app.thread()
    assert worker_thread_ids
    assert runner.active_count == 0
