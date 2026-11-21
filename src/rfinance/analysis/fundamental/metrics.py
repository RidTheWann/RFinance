"""Deterministic, Decimal-based fundamental metric primitives."""

from __future__ import annotations

from decimal import Decimal


def ratio(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    """Return numerator / denominator; None means the denominator is unusable."""

    if denominator <= 0:
        return None
    return numerator / denominator


def margin_ratio(profit: Decimal, revenue: Decimal) -> Decimal | None:
    """Return a margin as a fraction, not a percentage; revenue must be positive."""

    return ratio(profit, revenue)


def return_on_equity(net_income: Decimal, average_equity: Decimal) -> Decimal | None:
    """Return ROE as a fraction; non-positive average equity is not meaningful here."""

    return ratio(net_income, average_equity)


def debt_to_equity(total_debt: Decimal, total_equity: Decimal) -> Decimal | None:
    """Return debt/equity; negative debt or non-positive equity is rejected."""

    if total_debt < 0:
        return None
    return ratio(total_debt, total_equity)
