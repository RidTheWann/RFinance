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
from rfinance.ui.theme import apply_app_theme

if TYPE_CHECKING:
    from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(argv) if argv is not None else sys.argv
    if "--smoke-test" in arguments[1:]:
        try:
            context = create_application_context()
            try:
                with context.database.engine.connect() as connection:
                    revision = connection.exec_driver_sql(
                        "SELECT version_num FROM alembic_version"
                    ).scalar_one_or_none()
                if not isinstance(revision, str) or not revision:
                    raise RuntimeError("database migration revision was not recorded")
                context.logger.info("Frozen application smoke test passed at schema %s", revision)
            finally:
                context.close()
        except Exception as error:  # noqa: BLE001 - smoke-test failures must produce a nonzero exit.
            sys.stderr.write(f"RFinance packaging smoke test failed: {error}\\n")
            return 1
        return 0

    application = QApplication(arguments)
    application.setApplicationName("RFinance")
    application.setApplicationVersion(__version__)
    application.setOrganizationName("RidTheWann")
    apply_app_theme(application, mode="dark")

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
        context.portfolio_trading,
        context.verified_lot_sizes,
        context.portfolio_valuation,
        context.technical_analysis,
        context.dividend_events,
        context.dividend_receipts,
        context.recommendations,
        context.screening_evaluation,
        context.risk_monitoring,
        context.ledger_reports,
        context.allocation_planning,
        context.backups,
        context.automation,
        context.portfolio_reports,
        context.instrument_categories,
        context.ai_settings,
        context.ai_research,
    )
    application.aboutToQuit.connect(context.close)
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
