# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from rfinance.application.portfolio_ledger import PortfolioLedgerService
from rfinance.application.portfolio_reports import PortfolioReportService
from rfinance.application.portfolio_valuation import PortfolioValuationService
from rfinance.application.recommendations import RecommendationService
from rfinance.application.risk_monitoring import RiskMonitoringService
from rfinance.storage.database import Database
from rfinance.storage.repositories.portfolio_ledger import LedgerRepository

if TYPE_CHECKING:
    from pathlib import Path

AS_OF = datetime(2026, 11, 23, 12, tzinfo=UTC)


def test_report_is_assembled_from_local_records_and_rendered_as_pdf(tmp_path: Path, qapp) -> None:
    database = Database.open(tmp_path / "report.sqlite3")
    database.upgrade()
    try:
        ledger = PortfolioLedgerService(LedgerRepository(database.sessions), lot_sizes={})
        ledger.initialize_portfolio(Decimal("5000000"))
        valuation = PortfolioValuationService(database.sessions, ledger)
        service = PortfolioReportService(
            ledger,
            valuation,
            risk_monitoring=RiskMonitoringService(database.sessions),
            recommendations=RecommendationService(database.sessions),
        )

        report = service.build(as_of=AS_OF)
        text = report.as_text()

        assert "SIMULATED — not brokerage performance" in text
        assert "Rp5,000,000.00" in text
        assert "portfolio-valuation-v1" in text
        assert "Risk controls" in text
        assert report.generated_at_utc == AS_OF.isoformat()
        assert report.methodology_version == "portfolio-pdf-v1"

        target = service.export_pdf(tmp_path / "report.pdf", as_of=AS_OF)
        assert target.read_bytes()[:5] == b"%PDF-"
        assert target.stat().st_size > 1000
    finally:
        database.close()
