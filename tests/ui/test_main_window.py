# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from rfinance.core.config import AppPaths
from rfinance.ui.main_window import MainWindow


def test_main_window_navigation(qtbot, tmp_path) -> None:
    paths = AppPaths.resolve(tmp_path / "rfinance")
    window = MainWindow(paths)
    qtbot.addWidget(window)

    assert window.windowTitle() == "RFinance"
    assert window.navigation.count() == 3
    window.navigation.setCurrentRow(1)
    assert window.pages.currentIndex() == 1
