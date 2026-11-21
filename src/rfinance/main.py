"""Desktop application entry point."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication, QMessageBox

from rfinance import __version__
from rfinance.bootstrap import create_application_context
from rfinance.ui.main_window import MainWindow


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

    window = MainWindow(context.paths)
    application.aboutToQuit.connect(context.close)
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
