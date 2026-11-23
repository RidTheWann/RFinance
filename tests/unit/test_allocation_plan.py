# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from rfinance.analysis.portfolio.valuation import (
    AllocationLine,
    ValuationCategory,
    ValuationResult,
)
from rfinance.domain.portfolio.allocation import (
    FORMULA_VERSION,
    AllocationAction,
    InvestableInstrument,
    build_allocation_plan,
)

AS_OF = datetime(2026, 11, 23, 12, tzinfo=UTC)
TOTAL = Decimal("5000000")
CAT = ValuationCategory


def valuation(
    *,
    total: Decimal = TOTAL,
    cash: Decimal = TOTAL,
    values: dict[ValuationCategory, Decimal] | None = None,
    targets: dict[ValuationCategory, Decimal] | None = None,
    complete: bool = True,
    unvalued: tuple[str, ...] = (),
) -> ValuationResult:
    applied_targets = targets or {
        CAT.EQUITY_INDEX: Decimal("0.5"),
        CAT.DIVIDEND_EQUITY: Decimal("0.2"),
        CAT.MONEY_MARKET: Decimal("0.3"),
        CAT.CASH: Decimal("0"),
        CAT.OTHER: Decimal("0"),
    }
    applied_values = values or {
        CAT.EQUITY_INDEX: Decimal("0"),
        CAT.DIVIDEND_EQUITY: Decimal("0"),
        CAT.MONEY_MARKET: Decimal("0"),
        CAT.CASH: cash,
        CAT.OTHER: Decimal("0"),
    }
    allocation = tuple(
        AllocationLine(
            category=category,
            value=applied_values[category],
            weight=(Decimal("0") if total <= 0 else applied_values[category] / total),
            target=applied_targets[category],
            deviation=(
                Decimal("0")
                if total <= 0
                else applied_values[category] / total - applied_targets[category]
            ),
        )
        for category in CAT
    )
    return ValuationResult(
        as_of_utc=AS_OF.isoformat(),
        currency="IDR",
        cash=cash,
        market_value=total - cash,
        total_value=total,
        realized_profit_loss=Decimal("0"),
        unrealized_profit_loss=Decimal("0"),
        positions=(),
        allocation=allocation,
        unvalued_instruments=unvalued,
        is_complete=complete,
    )


def test_cash_only_portfolio_shows_explicit_unfilled_targets() -> None:
    plan = build_allocation_plan(valuation())

    assert plan.methodology_version == FORMULA_VERSION
    assert plan.total_value == TOTAL
    assert [line.category for line in plan.lines] == [
        CAT.EQUITY_INDEX,
        CAT.DIVIDEND_EQUITY,
        CAT.MONEY_MARKET,
    ]
    assert [line.target_amount for line in plan.lines] == [
        Decimal("2500000"),
        Decimal("1000000"),
        Decimal("1500000"),
    ]
    assert {line.action for line in plan.lines} == {AllocationAction.UNFILLED_TARGET}
    assert all(line.instrument_id is None for line in plan.lines)
    assert all("No verified investable instrument" in line.reasons[0] for line in plan.lines)


def test_verified_instrument_and_price_produce_a_simulated_lot_quantity() -> None:
    instrument = InvestableInstrument(
        instrument_id="IDX:BBCA",
        category=CAT.EQUITY_INDEX,
        lot_size=Decimal("100"),
        evidence_reference="Documents/InstrumentReview/bbca-lot.pdf",
        price=Decimal("10000"),
    )

    plan = build_allocation_plan(valuation(), instruments=[instrument])
    line = plan.lines[0]

    assert line.action is AllocationAction.INVESTABLE
    assert line.instrument_id == "IDX:BBCA"
    assert line.quantity_lots == 2
    assert "bbca-lot.pdf" in line.reasons[0]
    assert plan.lines[1].action is AllocationAction.UNFILLED_TARGET


def test_instrument_without_eligible_price_remains_unfilled() -> None:
    instrument = InvestableInstrument(
        instrument_id="IDX:BBCA",
        category=CAT.EQUITY_INDEX,
        lot_size=Decimal("100"),
        evidence_reference="doc-1",
    )

    plan = build_allocation_plan(valuation(), instruments=[instrument])

    assert plan.lines[0].action is AllocationAction.UNFILLED_TARGET
    assert plan.lines[0].quantity_lots is None


def test_gap_smaller_than_one_lot_is_not_rounded_up() -> None:
    small_total = Decimal("200000")
    instrument = InvestableInstrument(
        instrument_id="IDX:BBCA",
        category=CAT.EQUITY_INDEX,
        lot_size=Decimal("100"),
        evidence_reference="doc-1",
        price=Decimal("10000"),
    )
    plan = build_allocation_plan(
        valuation(total=small_total, cash=small_total), instruments=[instrument]
    )

    assert plan.lines[0].action is AllocationAction.UNFILLED_TARGET
    assert "smaller than one verified lot" in plan.lines[0].reasons[0]


def test_overweight_category_requires_review_without_automatic_sale() -> None:
    values = {
        CAT.EQUITY_INDEX: Decimal("4000000"),
        CAT.DIVIDEND_EQUITY: Decimal("0"),
        CAT.MONEY_MARKET: Decimal("0"),
        CAT.CASH: Decimal("1000000"),
        CAT.OTHER: Decimal("0"),
    }
    plan = build_allocation_plan(valuation(values=values, cash=Decimal("1000000")))

    assert plan.lines[0].action is AllocationAction.REDUCE_REQUIRED
    assert plan.lines[0].difference == Decimal("-1500000")
    assert "no automatic sale" in plan.lines[0].reasons[0]


def test_active_suspension_blocks_investable_action() -> None:
    instrument = InvestableInstrument(
        instrument_id="IDX:BBCA",
        category=CAT.EQUITY_INDEX,
        lot_size=Decimal("100"),
        evidence_reference="doc-1",
        price=Decimal("10000"),
    )
    plan = build_allocation_plan(
        valuation(),
        instruments=[instrument],
        allocation_changes_suspended=True,
    )

    assert plan.lines[0].action is AllocationAction.BLOCKED
    assert plan.lines[0].quantity_lots is None
    assert plan.allocation_changes_suspended is True
    assert any("suspended" in warning for warning in plan.warnings)


def test_within_tolerance_is_at_target() -> None:
    values = {
        CAT.EQUITY_INDEX: Decimal("2500000"),
        CAT.DIVIDEND_EQUITY: Decimal("1000000"),
        CAT.MONEY_MARKET: Decimal("1500000"),
        CAT.CASH: Decimal("0"),
        CAT.OTHER: Decimal("0"),
    }
    plan = build_allocation_plan(valuation(values=values, cash=Decimal("0")))

    assert {line.action for line in plan.lines} == {AllocationAction.AT_TARGET}


def test_incomplete_valuation_is_reported_as_a_warning() -> None:
    plan = build_allocation_plan(valuation(complete=False, unvalued=("IDX:BBCA",)))

    assert plan.lines[0].action is AllocationAction.UNFILLED_TARGET
    assert any("incomplete" in warning for warning in plan.warnings)
    assert any("IDX:BBCA" in warning for warning in plan.warnings)


def test_invalid_inputs_are_rejected() -> None:
    with pytest.raises(ValueError, match="tolerance"):
        build_allocation_plan(valuation(), tolerance=Decimal("1.1"))
    non_idr = valuation()
    object.__setattr__(non_idr, "currency", "USD")
    with pytest.raises(ValueError, match="IDR"):
        build_allocation_plan(non_idr)
    with pytest.raises(ValueError, match="lot_size"):
        InvestableInstrument("IDX:X", CAT.EQUITY_INDEX, Decimal("0"), "doc")
    with pytest.raises(ValueError, match="evidence_reference"):
        InvestableInstrument("IDX:X", CAT.EQUITY_INDEX, Decimal("100"), "  ")


def test_duplicate_investable_instrument_is_rejected() -> None:
    item = InvestableInstrument("IDX:X", CAT.EQUITY_INDEX, Decimal("100"), "doc")
    with pytest.raises(ValueError, match="duplicate"):
        build_allocation_plan(valuation(), instruments=[item, item])
