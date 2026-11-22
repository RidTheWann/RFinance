# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Application composition root."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rfinance.application.dividend_events import DividendEventService
from rfinance.application.dividend_receipts import DividendReceiptService
from rfinance.application.financial_statements import FinancialStatementService
from rfinance.application.historical_price_series import HistoricalPriceSeriesService
from rfinance.application.instrument_review import InstrumentReviewService
from rfinance.application.market_csv_import import MarketCSVImportService
from rfinance.application.observation_review import ObservationReviewService
from rfinance.application.portfolio_ledger import PortfolioLedgerService
from rfinance.application.portfolio_trading import (
    PortfolioTradingService,
    VerifiedLotSizeService,
)
from rfinance.application.portfolio_valuation import PortfolioValuationService
from rfinance.application.recommendations import RecommendationService
from rfinance.application.screening_evaluation import ScreeningEvaluationService
from rfinance.application.technical_analysis import TechnicalAnalysisService
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
    portfolio_trading: PortfolioTradingService
    verified_lot_sizes: VerifiedLotSizeService
    market_csv_import: MarketCSVImportService
    instrument_review: InstrumentReviewService
    observation_review: ObservationReviewService
    dividend_events: DividendEventService
    dividend_receipts: DividendReceiptService
    financial_statements: FinancialStatementService
    recommendations: RecommendationService
    screening_evaluation: ScreeningEvaluationService
    portfolio_valuation: PortfolioValuationService
    technical_analysis: TechnicalAnalysisService
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
        verified_lot_sizes = VerifiedLotSizeService(database.sessions)
        portfolio_trading = PortfolioTradingService(ledger_repository, lot_sizes=verified_lot_sizes)
        portfolio_valuation = PortfolioValuationService(database.sessions, portfolio_ledger)
        technical_analysis = TechnicalAnalysisService(
            HistoricalPriceSeriesService(database.sessions)
        )
        data_ingestion_repository = DataIngestionRepository(database.sessions)
        market_csv_import = MarketCSVImportService(
            data_ingestion_repository,
            data_directory=paths.root,
        )
        instrument_review = InstrumentReviewService(
            database.sessions,
            data_directory=paths.root,
        )
        observation_review = ObservationReviewService(
            database.sessions,
            data_directory=paths.root,
        )
        dividend_events = DividendEventService(
            database.sessions,
            data_directory=paths.root,
        )
        dividend_receipts = DividendReceiptService(
            database.sessions,
            dividend_events=dividend_events,
            portfolio_ledger=portfolio_ledger,
        )
        financial_statements = FinancialStatementService(
            database.sessions, data_directory=paths.root
        )
        recommendations = RecommendationService(database.sessions)
        screening_evaluation = ScreeningEvaluationService(
            database.sessions,
            dividend_events=dividend_events,
            observation_review=observation_review,
            recommendations=recommendations,
            financial_statements=financial_statements,
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
        portfolio_trading=portfolio_trading,
        verified_lot_sizes=verified_lot_sizes,
        market_csv_import=market_csv_import,
        instrument_review=instrument_review,
        observation_review=observation_review,
        dividend_events=dividend_events,
        dividend_receipts=dividend_receipts,
        financial_statements=financial_statements,
        recommendations=recommendations,
        screening_evaluation=screening_evaluation,
        portfolio_valuation=portfolio_valuation,
        technical_analysis=technical_analysis,
        logger=logger,
    )
