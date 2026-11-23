# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import Qt

from rfinance.application.portfolio_ledger import PortfolioLedgerService
from rfinance.security.backup import BackupService
from rfinance.storage.database import Database
from rfinance.storage.repositories.portfolio_ledger import LedgerRepository
from rfinance.ui.backup_page import BackupPage


def test_backup_page_creates_and_restores_off_ui_thread(qtbot, tmp_path: Path) -> None:
    database = Database.open(tmp_path / "data" / "rfinance.sqlite3")
    database.upgrade()
    try:
        ledger = PortfolioLedgerService(LedgerRepository(database.sessions), lot_sizes={})
        ledger.initialize_portfolio(Decimal("5000000"))
        service = BackupService(
            Path(str(database.engine.url.database)), tmp_path / "data" / "Backups"
        )
        page = BackupPage(service)
        qtbot.addWidget(page)
        page.show()

        qtbot.mouseClick(page.create_button, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(
            lambda: not page.is_busy and "SHA-256" in page.status_label.text(),
            timeout=30000,
        )
        qtbot.wait(200)
        assert "Ledger events: 1" in page.status_label.text()

        backups = sorted(service.backups_dir.glob("*.sqlite3"))
        assert len(backups) == 1
        page.restore_backup(str(backups[0]), str(tmp_path / "restored"))
        qtbot.waitUntil(
            lambda: not page.is_busy and str(tmp_path / "restored") in page.status_label.text(),
            timeout=30000,
        )
        qtbot.wait(200)
        assert (tmp_path / "restored" / "rfinance.sqlite3").is_file()
        assert page.create_button.isEnabled()
    finally:
        database.close()
