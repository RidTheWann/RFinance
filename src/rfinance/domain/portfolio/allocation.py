# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Deterministic allocation gap planning.

Formula version: ``allocation-plan-v1``. This is a pure policy layer: it reads
an explicit ``ValuationResult`` and explicit, evidence-backed investable
instruments. It never fetches data, executes trades, assumes a product exists,
or converts an unfilled target into a fabricated holding. Positive gaps remain
``UNFILLED_TARGET`` unless an operator-supplied verified instrument and an
eligible price are available, and an over-weight category is only flagged for
review because no automatic sale is planned.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from rfinance.analysis.portfolio.valuation import ValuationCategory

if TYPE_CHECKING:
    from collections.abc import Sequence

    from rfinance.analysis.portfolio.valuation import ValuationResult

FORMULA_VERSION = "allocation-plan-v1"
ZERO = Decimal("0")
ONE = Decimal("1")


class AllocationAction(StrEnum):
    AT_TARGET = "AT_TARGET"
    UNFILLED_TARGET = "UNFILLED_TARGET"
    INVESTABLE = "INVESTABLE"
    REDUCE_REQUIRED = "REDUCE_REQUIRED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class InvestableInstrument:
    """An instrument whose tradability and category came from explicit evidence."""

    instrument_id: str
    category: ValuationCategory
    lot_size: Decimal
    evidence_reference: str
    price: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.instrument_id.strip():
            raise ValueError("instrument_id must not be empty")
        if not isinstance(self.category, ValuationCategory):
            raise ValueError("category must be a ValuationCategory")
        if not isinstance(self.lot_size, Decimal) or not self.lot_size.is_finite():
            raise ValueError("lot_size must be a finite Decimal")
        if self.lot_size <= ZERO:
            raise ValueError("lot_size must be positive")
        if not self.evidence_reference.strip():
            raise ValueError("evidence_reference is required")
        if self.price is not None and (
            not isinstance(self.price, Decimal) or not self.price.is_finite() or self.price <= ZERO
        ):
            raise ValueError("price must be a positive finite Decimal when supplied")


@dataclass(frozen=True, slots=True)
class AllocationLinePlan:
    """Target, current value and the deterministic action for one category."""

    category: ValuationCategory
    target: Decimal
    target_amount: Decimal
    current_value: Decimal
    difference: Decimal
    action: AllocationAction
    instrument_id: str | None = None
    quantity_lots: int | None = None
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AllocationPlan:
    """An auditable snapshot; nothing here is an executed or simulated order."""

    as_of_utc: str
    currency: str
    total_value: Decimal
    cash: Decimal
    lines: tuple[AllocationLinePlan, ...]
    warnings: tuple[str, ...] = ()
    methodology_version: str = FORMULA_VERSION
    allocation_changes_suspended: bool = False


def _validate_instruments(instruments: Sequence[InvestableInstrument]) -> None:
    seen: set[tuple[str, ValuationCategory]] = set()
    for item in instruments:
        key = (item.instrument_id, item.category)
        if key in seen:
            raise ValueError("duplicate investable instrument for a category")
        seen.add(key)


def build_allocation_plan(
    valuation: ValuationResult,
    *,
    tolerance: Decimal = Decimal("0.05"),
    instruments: Sequence[InvestableInstrument] = (),
    allocation_changes_suspended: bool = False,
) -> AllocationPlan:
    """Derive target gaps from one valuation without inventing holdings."""

    if not isinstance(tolerance, Decimal) or not tolerance.is_finite():
        raise ValueError("tolerance must be a finite Decimal")
    if not ZERO <= tolerance <= ONE:
        raise ValueError("tolerance must be between zero and one")
    if valuation.currency != "IDR":
        raise ValueError("allocation planning currently supports IDR only")
    if valuation.total_value < ZERO:
        raise ValueError("total portfolio value cannot be negative")
    _validate_instruments(instruments)

    by_category = {line.category: line for line in valuation.allocation}
    tolerance_amount = abs(tolerance * valuation.total_value)
    lines: list[AllocationLinePlan] = []

    for category in ValuationCategory:
        allocation = by_category.get(category)
        if allocation is None or allocation.target <= ZERO:
            continue
        target_amount = valuation.total_value * allocation.target
        difference = target_amount - allocation.value
        reasons: list[str] = []
        instrument_id: str | None = None
        quantity_lots: int | None = None

        if abs(difference) <= tolerance_amount:
            action = AllocationAction.AT_TARGET
            reasons.append(
                f"Current value is within the {tolerance} total-value tolerance of the target."
            )
        elif difference < ZERO:
            action = AllocationAction.REDUCE_REQUIRED
            reasons.append(
                "Current value exceeds the target; no automatic sale is planned. "
                "Review the position explicitly."
            )
        else:
            candidates = sorted(
                (item for item in instruments if item.category == category),
                key=lambda item: item.instrument_id,
            )
            if not candidates:
                action = AllocationAction.UNFILLED_TARGET
                reasons.append(
                    "No verified investable instrument with category evidence is available; "
                    "the target remains unfilled."
                )
            else:
                candidate = candidates[0]
                instrument_id = candidate.instrument_id
                if candidate.price is None:
                    action = AllocationAction.UNFILLED_TARGET
                    reasons.append(
                        f"Verified instrument {candidate.instrument_id} has no eligible price; "
                        "a lot quantity cannot be computed."
                    )
                else:
                    gross_per_lot = candidate.lot_size * candidate.price
                    lots = int((difference / gross_per_lot).to_integral_value(rounding=ROUND_FLOOR))
                    if lots <= 0:
                        action = AllocationAction.UNFILLED_TARGET
                        reasons.append(
                            f"The gap is smaller than one verified lot of "
                            f"{candidate.instrument_id}."
                        )
                    else:
                        action = AllocationAction.INVESTABLE
                        quantity_lots = lots
                        reasons.append(
                            f"Verified lot rule from {candidate.evidence_reference}; "
                            "eligible price and lot size permit a simulated quantity only."
                        )
            if allocation_changes_suspended:
                reasons.append(
                    "An active risk event suspends simulated allocation changes; "
                    "no change may be executed pending review."
                )
                if action is AllocationAction.INVESTABLE:
                    action = AllocationAction.BLOCKED
                    quantity_lots = None

        lines.append(
            AllocationLinePlan(
                category=category,
                target=allocation.target,
                target_amount=target_amount,
                current_value=allocation.value,
                difference=difference,
                action=action,
                instrument_id=instrument_id,
                quantity_lots=quantity_lots,
                reasons=tuple(reasons),
            )
        )

    warnings: list[str] = []
    if valuation.total_value == ZERO:
        warnings.append("No capital is recorded yet; all target amounts are zero and unfilled.")
    if not valuation.is_complete:
        warnings.append(
            "Valuation is incomplete; gaps use only valued positions and may understate exposure."
        )
    if valuation.unvalued_instruments:
        warnings.append("Unvalued instruments: " + ", ".join(valuation.unvalued_instruments) + ".")
    if allocation_changes_suspended:
        warnings.append("Simulated allocation changes are suspended by an active risk event.")

    return AllocationPlan(
        as_of_utc=valuation.as_of_utc,
        currency=valuation.currency,
        total_value=valuation.total_value,
        cash=valuation.cash,
        lines=tuple(lines),
        warnings=tuple(warnings),
        allocation_changes_suspended=allocation_changes_suspended,
    )
