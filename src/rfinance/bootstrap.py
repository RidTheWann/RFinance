"""Application composition root."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rfinance.application.portfolio_ledger import PortfolioLedgerService
from rfinance.core.config import AppPaths
from rfinance.core.logging import configure_logging
from rfinance.storage.database import Database
from rfinance.storage.repositories.portfolio_ledger import LedgerRepository

if TYPE_CHECKING:
    import logging


@dataclass(slots=True)
class ApplicationContext:
    """Runtime dependencies owned by the desktop process."""

    paths: AppPaths
    database: Database
    portfolio_ledger: PortfolioLedgerService
    logger: logging.Logger

    def close(self) -> None:
        self.database.close()


def create_application_context(data_directory: str | None = None) -> ApplicationContext:
    paths = AppPaths.resolve(data_directory)
    paths.ensure_directories()
    logger = configure_logging(paths.logs_dir)
    database = Database.open(paths.database_file)
    try:
        database.upgrade()
        ledger_repository = LedgerRepository(database.sessions)
        portfolio_ledger = PortfolioLedgerService(ledger_repository, lot_sizes={})
    except Exception:
        database.close()
        logger.exception("Database initialization failed")
        raise
    logger.info("RFinance initialized using local data directory: %s", paths.root)
    return ApplicationContext(
        paths=paths,
        database=database,
        portfolio_ledger=portfolio_ledger,
        logger=logger,
    )
