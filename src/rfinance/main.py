# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Desktop application entry point."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QApplication, QMessageBox

from rfinance import __version__
from rfinance.bootstrap import create_application_context
from rfinance.ui.main_window import MainWindow

if TYPE_CHECKING:
    from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(argv) if argv is not None else sys.argv
    application = QApplication(arguments)
    application.setApplicationName("RFinance")
    application.setApplicationVersion(__version__)
    application.setOrganizationName("RidTheWann")

    try:
        context = create_application_context()
    except Exception as error:
        QMessageBox.critical(
            None,
            "RFinance startup failed",
            f"RFinance could not initialize its local database.\n\n{error}",
        )
        return 1

    window = MainWindow(
        context.paths,
        context.portfolio_ledger,
        context.market_csv_import,
        context.instrument_review,
        context.observation_review,
        context.portfolio_valuation,
        context.technical_analysis,
        context.dividend_events,
    )
    application.aboutToQuit.connect(context.close)
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
