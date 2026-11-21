"""SQLite engine, session factory, and Alembic migration entry point."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from rfinance.storage.models import Base


@dataclass(slots=True)
class Database:
    """Owns a local SQLite engine and its session factory."""

    engine: Engine
    sessions: sessionmaker[Session]

    @classmethod
    def open(cls, database_file: Path) -> Database:
        if str(database_file) == ":memory:":
            engine = create_engine(
                "sqlite+pysqlite:///:memory:",
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        else:
            database_file.parent.mkdir(parents=True, exist_ok=True)
            url = URL.create("sqlite+pysqlite", database=str(database_file.resolve()))
            engine = create_engine(
                url,
                connect_args={"check_same_thread": False, "timeout": 5},
            )

        @event.listens_for(engine, "connect")
        def set_sqlite_pragmas(dbapi_connection: object, _connection_record: object) -> None:
            cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=FULL")
            cursor.close()

        return cls(engine=engine, sessions=sessionmaker(bind=engine, expire_on_commit=False))

    def upgrade(self) -> None:
        """Apply repository migrations to the configured database."""

        migration_directory = Path(__file__).with_name("migrations")
        config = Config()
        config.set_main_option("script_location", str(migration_directory))
        config.set_main_option(
            "sqlalchemy.url",
            self.engine.url.render_as_string(hide_password=False).replace("%", "%%"),
        )
        command.upgrade(config, "head")

    def close(self) -> None:
        self.engine.dispose()
