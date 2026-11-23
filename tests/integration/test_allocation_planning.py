# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from rfinance.analysis.portfolio.valuation import ValuationCategory
from rfinance.application.allocation_planning import AllocationPlanningService
from rfinance.application.portfolio_ledger import PortfolioLedgerService
from rfinance.application.portfolio_valuation import PortfolioValuationService
from rfinance.application.risk_monitoring import RiskMonitoringService
from rfinance.domain.portfolio.allocation import AllocationAction, InvestableInstrument
from rfinance.domain.risk.controls import RiskSnapshot
from rfinance.storage.database import Database
from rfinance.storage.repositories.portfolio_ledger import LedgerRepository

AS_OF = datetime(2026, 11, 23, 12, tzinfo=UTC)


def services(database: Database) -> tuple[AllocationPlanningService, RiskMonitoringService]:
    ledger = PortfolioLedgerService(LedgerRepository(database.sessions), lot_sizes={})
    ledger.initialize_portfolio(Decimal("5000000"))
    valuation = PortfolioValuationService(database.sessions, ledger)
    risk = RiskMonitoringService(database.sessions)
    return AllocationPlanningService(valuation, risk_monitoring=risk), risk


def test_plan_derives_targets_from_persisted_cash_ledger(tmp_path) -> None:
    database = Database.open(tmp_path / "allocation.sqlite3")
    database.upgrade()
    try:
        planning, _ = services(database)
        plan = planning.plan(as_of=AS_OF)

        assert plan.total_value == Decimal("5000000")
        assert plan.cash == Decimal("5000000")
        assert [line.target_amount for line in plan.lines] == [
            Decimal("2500000"),
            Decimal("1000000"),
            Decimal("1500000"),
        ]
        assert {line.action for line in plan.lines} == {AllocationAction.UNFILLED_TARGET}
    finally:
        database.close()


def test_prohibited_activity_event_blocks_allocated_purchase(tmp_path) -> None:
    database = Database.open(tmp_path / "allocation-risk.sqlite3")
    database.upgrade()
    try:
        planning, risk = services(database)
        risk.evaluate(
            RiskSnapshot(
                as_of=AS_OF,
                peak_value=None,
                current_value=None,
                valuation_methodology="portfolio-valuation-v1",
                valuation_is_complete=False,
                instrument_weights={},
                sector_weights={},
                allocation_deviations={},
                last_reviewed_at=None,
                prohibited_activities=("LEVERAGE",),
            ),
            triggered_at=AS_OF,
        )
        instrument = InvestableInstrument(
            instrument_id="IDX:BBCA",
            category=ValuationCategory.EQUITY_INDEX,
            lot_size=Decimal("100"),
            evidence_reference="doc-1",
            price=Decimal("10000"),
        )

        plan = planning.plan(instruments=[instrument], as_of=AS_OF)

        assert plan.allocation_changes_suspended is True
        assert plan.lines[0].action is AllocationAction.BLOCKED
        assert plan.lines[0].quantity_lots is None
    finally:
        database.close()
