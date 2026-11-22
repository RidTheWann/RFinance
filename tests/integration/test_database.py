# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from pathlib import Path

from sqlalchemy import inspect

from rfinance.storage.database import Database


def test_database_upgrade_creates_initial_schema(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "db" / "test.sqlite3")
    try:
        database.upgrade()
        tables = set(inspect(database.engine).get_table_names())
        assert "application_settings" in tables
        assert "portfolio_ledger_events" in tables
        assert "alembic_version" in tables
    finally:
        database.close()


def test_database_can_be_reopened_after_migration(tmp_path: Path) -> None:
    database_file = tmp_path / "reopen.sqlite3"
    first = Database.open(database_file)
    first.upgrade()
    first.close()

    second = Database.open(database_file)
    try:
        schema = inspect(second.engine)
        assert schema.has_table("application_settings")
        assert schema.has_table("portfolio_ledger_events")
    finally:
        second.close()
