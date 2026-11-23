# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Assemble and export a simulated portfolio report from local records."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from rfinance.reporting.pdf import PortfolioReportData, ReportLine, render_portfolio_report

if TYPE_CHECKING:
    from decimal import Decimal
    from pathlib import Path

    from rfinance.application.portfolio_ledger import PortfolioLedgerService
    from rfinance.application.portfolio_valuation import PortfolioValuationService
    from rfinance.application.recommendations import RecommendationService
    from rfinance.application.risk_monitoring import RiskMonitoringService


class PortfolioReportService:
    """Build explicit report content; no figure is computed in the UI layer."""

    def __init__(
        self,
        ledger: PortfolioLedgerService,
        valuation: PortfolioValuationService,
        *,
        risk_monitoring: RiskMonitoringService | None = None,
        recommendations: RecommendationService | None = None,
    ) -> None:
        self._ledger = ledger
        self._valuation = valuation
        self._risk_monitoring = risk_monitoring
        self._recommendations = recommendations

    @staticmethod
    def _idr(value: Decimal | None) -> str:
        return "—" if value is None else f"Rp{value:,.2f}"

    def build(self, *, as_of: datetime | None = None) -> PortfolioReportData:
        moment = datetime.now(UTC) if as_of is None else as_of
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        moment = moment.astimezone(UTC)

        snapshot = self._valuation.value(as_of=moment)
        valuation = snapshot.valuation
        replay = self._ledger.snapshot()
        risk_controls = (
            self._risk_monitoring.screening_controls()
            if self._risk_monitoring is not None
            else None
        )
        recent = self._recommendations.recent(limit=5) if self._recommendations is not None else ()

        metadata = (
            ReportLine("Record status", "SIMULATED — not brokerage performance"),
            ReportLine("Currency", valuation.currency),
            ReportLine("Valuation methodology", valuation.methodology_version),
            ReportLine("Price eligibility methodology", snapshot.eligibility_methodology),
            ReportLine("Observations considered", str(snapshot.observations_considered)),
            ReportLine("Observations rejected", str(snapshot.observations_rejected)),
        )
        portfolio = (
            ReportLine("Cash balance", self._idr(replay.cash_balance)),
            ReportLine("Eligible market value", self._idr(valuation.market_value)),
            ReportLine("Total simulated value", self._idr(valuation.total_value)),
            ReportLine("Unrealized P/L", self._idr(valuation.unrealized_profit_loss)),
            ReportLine("Realized P/L", self._idr(replay.realized_profit_loss)),
            ReportLine("Valuation complete", "yes" if valuation.is_complete else "no"),
            ReportLine("Recorded ledger events", str(replay.applied_events)),
        )
        positions = tuple(
            ReportLine(
                item.instrument_id,
                (
                    f"{item.quantity} @ {self._idr(item.price)} = {self._idr(item.market_value)}"
                    if item.market_value is not None and item.price is not None
                    else "not valued — excluded from market value"
                ),
            )
            for item in valuation.positions
        ) or (ReportLine("Positions", "none recorded"),)
        allocation = tuple(
            ReportLine(
                line.category.value,
                f"target {line.target:.0%}, current {line.weight:.2%}, "
                f"deviation {line.deviation:+.2%}",
            )
            for line in valuation.allocation
        )
        sections: list[tuple[str, tuple[ReportLine, ...]]] = [
            ("Report metadata", metadata),
            ("Simulated portfolio", portfolio),
            ("Positions", positions),
            ("Allocation", allocation),
        ]
        if risk_controls is not None:
            sections.append(
                (
                    "Risk controls",
                    (
                        ReportLine(
                            "Active review events", str(len(risk_controls.active_event_ids))
                        ),
                        ReportLine(
                            "New BUY_CANDIDATE promotion",
                            "suspended" if risk_controls.buy_candidates_suspended else "available",
                        ),
                        ReportLine(
                            "Allocation changes",
                            (
                                "suspended"
                                if risk_controls.allocation_changes_suspended
                                else "available"
                            ),
                        ),
                        ReportLine(
                            "Drawdown",
                            (
                                "—"
                                if risk_controls.drawdown is None
                                else f"{risk_controls.drawdown:.2%}"
                            ),
                        ),
                    ),
                )
            )
        if recent:
            sections.append(
                (
                    "Recent recommendations",
                    tuple(
                        ReportLine(
                            item.recommendation_id[:8],
                            f"{item.action} ({item.confidence_level:.2f}) — "
                            f"{', '.join(item.risk_flags) or 'no risk flags'}",
                        )
                        for item in recent
                    ),
                )
            )

        warnings = tuple(valuation.unvalued_instruments)
        return PortfolioReportData(
            title="RFinance Simulated Portfolio Report",
            generated_at_utc=moment.isoformat(),
            reporting_period=f"as of {valuation.as_of_utc}",
            currency=valuation.currency,
            sections=tuple(sections),
            warnings=warnings,
        )

    def export_pdf(self, path: Path, *, as_of: datetime | None = None) -> Path:
        """Render the assembled report to a user-chosen PDF path."""

        return render_portfolio_report(path, self.build(as_of=as_of))
