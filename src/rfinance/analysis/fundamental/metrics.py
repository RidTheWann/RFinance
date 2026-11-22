# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Deterministic, Decimal-based fundamental metric primitives.

Formula version: ``fundamental-metrics-v1``.

Every metric records its formula, inputs and status so a reported figure can be
reproduced from the values that produced it. Missing values remain ``None``
and are never coerced to zero. Ratios are returned as fractions, not
percentages, unless the metric name explicitly says otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

FORMULA_VERSION = "fundamental-metrics-v1"
ZERO = Decimal("0")
ONE = Decimal("1")
# Canonical metric identifiers used by screening and reporting.
REVENUE_GROWTH = "REVENUE_GROWTH"
EPS_GROWTH = "EPS_GROWTH"
GROSS_MARGIN = "GROSS_MARGIN"
OPERATING_MARGIN = "OPERATING_MARGIN"
NET_MARGIN = "NET_MARGIN"
RETURN_ON_EQUITY = "RETURN_ON_EQUITY"
RETURN_ON_ASSETS = "RETURN_ON_ASSETS"
RETURN_ON_INVESTED_CAPITAL = "RETURN_ON_INVESTED_CAPITAL"
DEBT_TO_EQUITY = "DEBT_TO_EQUITY"
INTEREST_COVERAGE = "INTEREST_COVERAGE"
OPERATING_CASH_FLOW = "OPERATING_CASH_FLOW"
FREE_CASH_FLOW = "FREE_CASH_FLOW"
EARNINGS_QUALITY = "EARNINGS_QUALITY"
CASH_FLOW_QUALITY = "CASH_FLOW_QUALITY"
PRICE_TO_EARNINGS = "PRICE_TO_EARNINGS"
PRICE_TO_BOOK = "PRICE_TO_BOOK"
EV_TO_EBITDA = "EV_TO_EBITDA"

# Financial institutions do not share industrial leverage/cash-flow semantics.
_FINANCIAL_EXCLUSIONS = frozenset(
    {
        DEBT_TO_EQUITY,
        INTEREST_COVERAGE,
        FREE_CASH_FLOW,
        EARNINGS_QUALITY,
        CASH_FLOW_QUALITY,
        RETURN_ON_INVESTED_CAPITAL,
        EV_TO_EBITDA,
    }
)


class MetricStatus(StrEnum):
    OK = "OK"
    MISSING_INPUT = "MISSING_INPUT"
    UNUSABLE_DENOMINATOR = "UNUSABLE_DENOMINATOR"
    NEGATIVE_INPUT = "NEGATIVE_INPUT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class ComputedMetric:
    """A reproducible metric result with its inputs and interpretation status."""

    name: str
    value: Decimal | None
    status: MetricStatus
    formula: str
    formula_version: str = FORMULA_VERSION
    inputs: tuple[tuple[str, str], ...] = ()
    note: str = ""


def _finite(name: str, value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be a decimal.Decimal or None")
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")
    return value


def ratio(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    """Return numerator / denominator; None means the denominator is unusable."""

    return None if denominator <= ZERO else numerator / denominator


def margin_ratio(profit: Decimal, revenue: Decimal) -> Decimal | None:
    """Return a margin as a fraction, not a percentage; revenue must be positive."""

    return ratio(profit, revenue)


def return_on_equity(net_income: Decimal, average_equity: Decimal) -> Decimal | None:
    """Return ROE as a fraction; non-positive average equity is not meaningful here."""

    return ratio(net_income, average_equity)


def return_on_assets(net_income: Decimal, average_total_assets: Decimal) -> Decimal | None:
    """Return ROA as a fraction using average total assets as the denominator."""

    return ratio(net_income, average_total_assets)


def return_on_invested_capital(
    ebit: Decimal,
    tax_rate: Decimal,
    total_debt: Decimal,
    total_equity: Decimal,
    cash_and_equivalents: Decimal,
) -> Decimal | None:
    """Return NOPAT / invested capital.

    NOPAT = EBIT * (1 - tax_rate). Invested capital = total debt + total equity
    - cash and equivalents. A non-positive capital base is not interpretable.
    """

    if not ZERO <= tax_rate <= ONE:
        return None
    if total_debt < ZERO or total_equity < ZERO or cash_and_equivalents < ZERO:
        return None
    nopat = ebit * (ONE - tax_rate)
    capital = total_debt + total_equity - cash_and_equivalents
    return ratio(nopat, capital)


def debt_to_equity(total_debt: Decimal, total_equity: Decimal) -> Decimal | None:
    """Return debt/equity; negative debt or non-positive equity is rejected."""

    if total_debt < ZERO:
        return None
    return ratio(total_debt, total_equity)


def interest_coverage(ebit: Decimal, interest_expense: Decimal) -> Decimal | None:
    """Return EBIT / interest expense; a non-positive interest expense is unusable."""

    return ratio(ebit, interest_expense)


def free_cash_flow(operating_cash_flow: Decimal, capital_expenditure: Decimal) -> Decimal | None:
    """Return operating cash flow less capital expenditure in reporting currency."""

    if capital_expenditure < ZERO:
        return None
    return operating_cash_flow - capital_expenditure


def earnings_quality(net_income: Decimal, operating_cash_flow: Decimal) -> Decimal | None:
    """Return operating cash flow / net income (cash conversion of earnings)."""

    return ratio(operating_cash_flow, net_income)


def cash_flow_quality(
    operating_cash_flow: Decimal, free_cash_flow_value: Decimal
) -> Decimal | None:
    """Return FCF / OCF; non-positive OCF makes the ratio unusable."""

    return ratio(free_cash_flow_value, operating_cash_flow)


def price_to_earnings(price: Decimal, earnings_per_share: Decimal) -> Decimal | None:
    """Return price / EPS; a non-positive EPS has no meaningful P/E."""

    return ratio(price, earnings_per_share)


def price_to_book(price: Decimal, book_value_per_share: Decimal) -> Decimal | None:
    """Return price / book value per share; a non-positive book value is unusable."""

    return ratio(price, book_value_per_share)


def ev_to_ebitda(enterprise_value: Decimal, ebitda: Decimal) -> Decimal | None:
    """Return EV / EBITDA; a non-positive EBITDA is unusable."""

    if enterprise_value < ZERO:
        return None
    return ratio(enterprise_value, ebitda)


def growth_rate(current: Decimal, previous: Decimal) -> Decimal | None:
    """Return current/previous - 1; the prior value must be positive."""

    return None if previous <= ZERO else current / previous - ONE


def _inputs_record(**values: Decimal | None) -> tuple[tuple[str, str], ...]:
    """Build an ordered, string-serialized input record for reproducibility."""

    return tuple(
        (name, "MISSING" if value is None else format(value, "f")) for name, value in values.items()
    )


def _result(
    name: str,
    value: Decimal | None,
    formula: str,
    inputs: tuple[tuple[str, str], ...],
    *,
    missing: tuple[str, ...] = (),
    unusable_denominator: bool = False,
    note: str = "",
    is_financial: bool = False,
) -> ComputedMetric:
    if is_financial and name in _FINANCIAL_EXCLUSIONS:
        return ComputedMetric(
            name=name,
            value=None,
            status=MetricStatus.NOT_APPLICABLE,
            formula=formula,
            inputs=inputs,
            note="Not applicable to banks and other financial institutions.",
        )
    if missing:
        status = MetricStatus.MISSING_INPUT
        resolved_note = f"Missing inputs: {', '.join(missing)}."
    elif unusable_denominator or value is None:
        status = MetricStatus.UNUSABLE_DENOMINATOR
        resolved_note = note or "The denominator or required sign condition is unusable."
    else:
        status = MetricStatus.OK
        resolved_note = note
    return ComputedMetric(
        name=name,
        value=value,
        status=status,
        formula=formula,
        inputs=inputs,
        note=resolved_note,
    )


def compute_fundamental_metrics(
    inputs: Mapping[str, Decimal | None],
    *,
    is_financial: bool = False,
) -> tuple[ComputedMetric, ...]:
    """Compute all supported metrics from one named input mapping.

    The caller supplies reported or derived values explicitly; this function
    never fetches data, infers a prior period, or substitutes zero. When
    ``is_financial`` is true, leverage, cash-flow coverage and EV metrics are
    returned with ``NOT_APPLICABLE`` status instead of industrial-company
    values.
    """

    def get(name: str) -> Decimal | None:
        return _finite(name, inputs.get(name))

    values = {
        "revenue": get("revenue"),
        "revenue_previous": get("revenue_previous"),
        "earnings_per_share": get("earnings_per_share"),
        "earnings_per_share_previous": get("earnings_per_share_previous"),
        "gross_profit": get("gross_profit"),
        "operating_income": get("operating_income"),
        "net_income": get("net_income"),
        "average_equity": get("average_equity"),
        "average_total_assets": get("average_total_assets"),
        "effective_tax_rate": get("effective_tax_rate"),
        "total_debt": get("total_debt"),
        "total_equity": get("total_equity"),
        "cash_and_equivalents": get("cash_and_equivalents"),
        "interest_expense": get("interest_expense"),
        "operating_cash_flow": get("operating_cash_flow"),
        "capital_expenditure": get("capital_expenditure"),
        "price": get("price"),
        "book_value_per_share": get("book_value_per_share"),
        "enterprise_value": get("enterprise_value"),
        "ebitda": get("ebitda"),
    }
    number = values.get

    fcf_value: Decimal | None = None
    ocf = number("operating_cash_flow")
    capex = number("capital_expenditure")
    if ocf is not None and capex is not None:
        fcf_value = free_cash_flow(ocf, capex)

    results: list[ComputedMetric] = []

    def add(
        name: str,
        formula: str,
        function: Callable[..., Decimal | None],
        **named_inputs: Decimal | None,
    ) -> None:
        record = _inputs_record(**named_inputs)
        missing = tuple(key for key, value in named_inputs.items() if value is None)
        if missing:
            results.append(
                _result(
                    name,
                    None,
                    formula,
                    record,
                    missing=missing,
                    is_financial=is_financial,
                )
            )
            return
        value = function(*named_inputs.values())
        results.append(
            _result(
                name,
                value,
                formula,
                record,
                unusable_denominator=value is None,
                is_financial=is_financial,
            )
        )

    add(
        REVENUE_GROWTH,
        "current_revenue/prior_revenue - 1",
        growth_rate,
        current_revenue=number("revenue"),
        prior_revenue=number("revenue_previous"),
    )
    add(
        EPS_GROWTH,
        "current_eps/prior_eps - 1",
        growth_rate,
        current_eps=number("earnings_per_share"),
        prior_eps=number("earnings_per_share_previous"),
    )
    add(
        GROSS_MARGIN,
        "gross_profit/revenue",
        margin_ratio,
        gross_profit=number("gross_profit"),
        revenue=number("revenue"),
    )
    add(
        OPERATING_MARGIN,
        "operating_income/revenue",
        margin_ratio,
        operating_income=number("operating_income"),
        revenue=number("revenue"),
    )
    add(
        NET_MARGIN,
        "net_income/revenue",
        margin_ratio,
        net_income=number("net_income"),
        revenue=number("revenue"),
    )
    add(
        RETURN_ON_EQUITY,
        "net_income/average_equity",
        return_on_equity,
        net_income=number("net_income"),
        average_equity=number("average_equity"),
    )
    add(
        RETURN_ON_ASSETS,
        "net_income/average_total_assets",
        return_on_assets,
        net_income=number("net_income"),
        average_total_assets=number("average_total_assets"),
    )
    add(
        RETURN_ON_INVESTED_CAPITAL,
        "(EBIT*(1-tax_rate))/(total_debt+total_equity-cash)",
        return_on_invested_capital,
        ebit=number("operating_income"),
        effective_tax_rate=number("effective_tax_rate"),
        total_debt=number("total_debt"),
        total_equity=number("total_equity"),
        cash_and_equivalents=number("cash_and_equivalents"),
    )
    add(
        DEBT_TO_EQUITY,
        "total_debt/total_equity",
        debt_to_equity,
        total_debt=number("total_debt"),
        total_equity=number("total_equity"),
    )
    add(
        INTEREST_COVERAGE,
        "EBIT/interest_expense",
        interest_coverage,
        ebit=number("operating_income"),
        interest_expense=number("interest_expense"),
    )
    add(
        OPERATING_CASH_FLOW,
        "reported operating cash flow (reporting currency)",
        lambda amount: amount,
        operating_cash_flow=ocf,
    )
    add(
        FREE_CASH_FLOW,
        "operating_cash_flow - capital_expenditure",
        free_cash_flow,
        operating_cash_flow=ocf,
        capital_expenditure=capex,
    )
    add(
        EARNINGS_QUALITY,
        "operating_cash_flow/net_income",
        earnings_quality,
        net_income=number("net_income"),
        operating_cash_flow=ocf,
    )
    add(
        CASH_FLOW_QUALITY,
        "free_cash_flow/operating_cash_flow",
        cash_flow_quality,
        operating_cash_flow=ocf,
        free_cash_flow=fcf_value,
    )
    add(
        PRICE_TO_EARNINGS,
        "price/earnings_per_share",
        price_to_earnings,
        price=number("price"),
        earnings_per_share=number("earnings_per_share"),
    )
    add(
        PRICE_TO_BOOK,
        "price/book_value_per_share",
        price_to_book,
        price=number("price"),
        book_value_per_share=number("book_value_per_share"),
    )
    add(
        EV_TO_EBITDA,
        "enterprise_value/EBITDA",
        ev_to_ebitda,
        enterprise_value=number("enterprise_value"),
        ebitda=number("ebitda"),
    )
    return tuple(results)


def metric_by_name(metrics: tuple[ComputedMetric, ...], name: str) -> ComputedMetric | None:
    """Return one computed metric or ``None`` when it was not produced."""

    return next((metric for metric in metrics if metric.name == name), None)
