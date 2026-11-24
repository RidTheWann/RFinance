# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from rfinance.storage.database import Database


def _alembic_config(database: Database) -> Config:
    config = Config()
    config.set_main_option(
        "script_location",
        str(Path(__file__).resolve().parents[2] / "src" / "rfinance" / "storage" / "migrations"),
    )
    config.set_main_option(
        "sqlalchemy.url",
        database.engine.url.render_as_string(hide_password=False).replace("%", "%%"),
    )
    return config


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


def test_upgrade_from_an_older_revision_preserves_recorded_events(tmp_path: Path) -> None:
    """Data written at an older Alembic revision survives a head upgrade.

    This is the acceptance evidence for the Windows in-place upgrade path: an
    existing local database must gain new tables without losing recorded ledger
    events.
    """

    database_file = tmp_path / "upgrade.sqlite3"
    database = Database.open(database_file)
    database.upgrade()
    with database.engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO portfolio_ledger_events "
                "(event_id, sequence, occurred_at_utc, event_type, currency, amount) "
                "VALUES ('event-1', 1, '2026-01-01T00:00:00+00:00', "
                "'CAPITAL_INJECTION', 'IDR', '5000000')"
            )
        )
    database.close()

    # Rewind to an early schema so the upgrade has real work to do.
    stale = Database.open(database_file)
    config = _alembic_config(stale)
    command.downgrade(config, "0002_portfolio_ledger")
    stale.close()

    upgraded = Database.open(database_file)
    try:
        upgraded.upgrade()
        with upgraded.engine.connect() as connection:
            version = connection.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            ).scalar_one()
            preserved = connection.execute(
                text("SELECT amount FROM portfolio_ledger_events WHERE event_id = 'event-1'")
            ).scalar_one()
            tables = set(inspect(upgraded.engine).get_table_names())
    finally:
        upgraded.close()

    assert version == "0013_instrument_metadata_evidence"
    assert preserved == "5000000"
    assert {"instrument_metadata_events", "portfolio_valuation_history"} <= tables
