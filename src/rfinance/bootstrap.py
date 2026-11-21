# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Application composition root."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rfinance.core.config import AppPaths
from rfinance.core.logging import configure_logging
from rfinance.storage.database import Database

if TYPE_CHECKING:
    import logging


@dataclass(slots=True)
class ApplicationContext:
    """Runtime dependencies owned by the desktop process."""

    paths: AppPaths
    database: Database
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
    except Exception:
        database.close()
        logger.exception("Database initialization failed")
        raise
    logger.info("RFinance initialized using local data directory: %s", paths.root)
    return ApplicationContext(paths=paths, database=database, logger=logger)
