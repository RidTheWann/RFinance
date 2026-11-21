"""Application composition root."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rfinance.application.market_csv_import import MarketCSVImportService
from rfinance.application.portfolio_ledger import PortfolioLedgerService
from rfinance.core.config import AppPaths
from rfinance.core.logging import configure_logging
from rfinance.storage.database import Database
from rfinance.storage.repositories.data_ingestion import DataIngestionRepository
from rfinance.storage.repositories.portfolio_ledger import LedgerRepository

if TYPE_CHECKING:
    import logging


@dataclass(slots=True)
class ApplicationContext:
    """Runtime dependencies owned by the desktop process."""

    paths: AppPaths
    database: Database
    portfolio_ledger: PortfolioLedgerService
    market_csv_import: MarketCSVImportService
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
        data_ingestion_repository = DataIngestionRepository(database.sessions)
        market_csv_import = MarketCSVImportService(
            data_ingestion_repository,
            data_directory=paths.root,
        )
    except Exception:
        database.close()
        logger.exception("Database initialization failed")
        raise
    logger.info("RFinance initialized using local data directory: %s", paths.root)
    return ApplicationContext(
        paths=paths,
        database=database,
        portfolio_ledger=portfolio_ledger,
        market_csv_import=market_csv_import,
        logger=logger,
    )
