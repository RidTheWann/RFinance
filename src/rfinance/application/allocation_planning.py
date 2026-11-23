# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Application service assembling an allocation plan from local evidence."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from rfinance.domain.portfolio.allocation import build_allocation_plan

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from rfinance.application.instrument_category import InstrumentCategoryService
    from rfinance.application.portfolio_valuation import PortfolioValuationService
    from rfinance.application.risk_monitoring import RiskMonitoringService
    from rfinance.domain.portfolio.allocation import (
        AllocationPlan,
        InvestableInstrument,
    )


class AllocationPlanningService:
    """Combine the persisted valuation with persisted risk-control state."""

    def __init__(
        self,
        valuation: PortfolioValuationService,
        *,
        risk_monitoring: RiskMonitoringService | None = None,
        instrument_categories: InstrumentCategoryService | None = None,
        tolerance: Decimal = Decimal("0.05"),
    ) -> None:
        self._valuation = valuation
        self._risk_monitoring = risk_monitoring
        self._instrument_categories = instrument_categories
        self._tolerance = tolerance

    def plan(
        self,
        *,
        instruments: Sequence[InvestableInstrument] = (),
        as_of: datetime | None = None,
    ) -> AllocationPlan:
        """Derive target gaps; ``instruments`` must carry verified evidence."""

        snapshot = self._valuation.value(as_of=as_of)
        if not instruments and self._instrument_categories is not None:
            instruments = self._instrument_categories.verified_investables()
        suspended = False
        if self._risk_monitoring is not None:
            suspended = self._risk_monitoring.screening_controls().allocation_changes_suspended
        return build_allocation_plan(
            snapshot.valuation,
            tolerance=self._tolerance,
            instruments=instruments,
            allocation_changes_suspended=suspended,
        )
