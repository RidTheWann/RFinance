# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Deterministic dividend analytics using Decimal arithmetic.

Formula version: ``dividend-analytics-v1``.

This module is a pure calculation layer. It does not fetch data, infer sampling
frequency, apply corporate actions to prices, or certify source entitlement.
Missing, estimated and simulated values are never silently converted into
verified cash amounts.
"""

from __future__ import annotations

import decimal
import re
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

FORMULA_VERSION = "dividend-analytics-v1"

ZERO = decimal.Decimal("0")
ONE = decimal.Decimal("1")

_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")


class DividendType(StrEnum):
    """Dividend classifications relevant to cash and non-cash events."""

    CASH = "CASH"
    INTERIM = "INTERIM"
    FINAL = "FINAL"
    SPECIAL = "SPECIAL"
    STOCK = "STOCK"
    RIGHTS = "RIGHTS"


CASH_DIVIDEND_TYPES = frozenset(
    {
        DividendType.CASH,
        DividendType.INTERIM,
        DividendType.FINAL,
        DividendType.SPECIAL,
    }
)


class DividendQuality(StrEnum):
    """Qualities accepted by the calculation layer.

    Values intentionally mirror ``DataQualityStatus`` so the application layer
    can map persisted contracts into this dependency-free enum.
    """

    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    ESTIMATED = "ESTIMATED"
    STALE = "STALE"
    INCOMPLETE = "INCOMPLETE"
    REJECTED = "REJECTED"
    SIMULATED = "SIMULATED"


VERIFIED_QUALITIES = frozenset({DividendQuality.VERIFIED})


@dataclass(frozen=True, slots=True)
class DividendRecord:
    """A single gross, per-share dividend observation with provenance."""

    event_id: str
    amount_per_share: decimal.Decimal
    ex_date: date
    currency: str
    dividend_type: DividendType
    quality: DividendQuality
    source_id: str

    def __post_init__(self) -> None:
        _non_negative(self.amount_per_share, "amount_per_share")
        _calendar_date(self.ex_date, "ex_date")
        _text(self.event_id, "event_id")
        _text(self.source_id, "source_id")
        _currency(self.currency, "currency")
        if not isinstance(self.dividend_type, DividendType):
            raise ValueError("dividend_type must be a DividendType")
        if not isinstance(self.quality, DividendQuality):
            raise ValueError("quality must be a DividendQuality")


@dataclass(frozen=True, slots=True)
class LabeledYield:
    """A yield whose trailing/forward basis and estimate status are explicit."""

    value: decimal.Decimal
    basis: Literal["TRAILING", "FORWARD"]
    is_estimate: bool
    methodology_version: str = FORMULA_VERSION


@dataclass(frozen=True, slots=True)
class DividendConsistency:
    """Distribution history summarized without treating missing years as zero."""

    years_observed: int
    years_paid: int
    consecutive_years: int
    year_over_year_reductions: int


@dataclass(frozen=True, slots=True)
class DividendProjection:
    """A clearly labelled simulated dividend cash flow."""

    quantity: decimal.Decimal
    annual_dividend_per_share_gross: decimal.Decimal
    withholding_rate: decimal.Decimal | None
    gross_cash: decimal.Decimal
    net_cash: decimal.Decimal | None
    is_simulated: bool = True
    methodology_version: str = FORMULA_VERSION


@dataclass(frozen=True, slots=True)
class DividendDistribution:
    """Allocation of a confirmed net dividend receipt.

    Simulated dividends must not be passed to this allocation.
    """

    net_amount: decimal.Decimal
    reinvestment: decimal.Decimal
    money_market: decimal.Decimal
    withdrawal: decimal.Decimal


def _finite(value: object, name: str) -> decimal.Decimal:
    if not isinstance(value, decimal.Decimal):
        raise ValueError(f"{name} must be a decimal.Decimal")
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")
    return value


def _non_negative(value: object, name: str) -> decimal.Decimal:
    result = _finite(value, name)
    if result < ZERO:
        raise ValueError(f"{name} cannot be negative")
    return result


def _rate(value: object, name: str) -> decimal.Decimal:
    result = _finite(value, name)
    if result < ZERO or result > ONE:
        raise ValueError(f"{name} must be between zero and one")
    return result


def _calendar_date(value: object, name: str) -> date:
    if type(value) is not date:
        raise ValueError(f"{name} must be a calendar date")
    return value


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _currency(value: object, name: str) -> str:
    result = _text(value, name)
    if _CURRENCY_PATTERN.fullmatch(result) is None:
        raise ValueError(f"{name} must be a three-letter uppercase currency code")
    return result


def _window(window_days: int | None) -> int | None:
    if window_days is None:
        return None
    if isinstance(window_days, bool) or not isinstance(window_days, int) or window_days <= 0:
        raise ValueError("window_days must be a positive integer or None")
    return window_days


def select_cash_dividends(
    records: Sequence[DividendRecord],
    *,
    as_of: date,
    currency: str,
    eligible_qualities: frozenset[DividendQuality] = VERIFIED_QUALITIES,
    window_days: int | None = None,
) -> tuple[DividendRecord, ...]:
    """Select eligible cash dividends up to ``as_of`` in one currency.

    Identical event identifiers are collapsed. Conflicting records that share
    an event identifier are rejected rather than silently overwritten. Results
    are ordered by ex-date and event identifier for deterministic replay.
    """

    cutoff = _calendar_date(as_of, "as_of")
    expected_currency = _currency(currency, "currency")
    days = _window(window_days)
    earliest = cutoff - timedelta(days=days) if days is not None else None

    by_event: dict[str, DividendRecord] = {}
    for record in records:
        if not isinstance(record, DividendRecord):
            raise ValueError("records must contain DividendRecord instances")
        if record.currency != expected_currency:
            continue
        if record.dividend_type not in CASH_DIVIDEND_TYPES:
            continue
        if record.quality not in eligible_qualities:
            continue
        if record.ex_date > cutoff or (earliest is not None and record.ex_date <= earliest):
            continue
        previous = by_event.get(record.event_id)
        if previous is not None and previous != record:
            raise ValueError(f"conflicting records for event {record.event_id!r}")
        by_event[record.event_id] = record

    return tuple(sorted(by_event.values(), key=lambda item: (item.ex_date, item.event_id)))


def trailing_dividend_per_share(
    records: Sequence[DividendRecord],
    *,
    as_of: date,
    currency: str,
    window_days: int | None = 365,
    eligible_qualities: frozenset[DividendQuality] = VERIFIED_QUALITIES,
) -> decimal.Decimal | None:
    """Gross cash dividend per share over the trailing window.

    ``None`` means no eligible observation exists; it is not a zero dividend.
    """

    selected = select_cash_dividends(
        records,
        as_of=as_of,
        currency=currency,
        eligible_qualities=eligible_qualities,
        window_days=window_days,
    )
    if not selected:
        return None
    return sum((record.amount_per_share for record in selected), start=ZERO)


def net_dividend_amount(
    gross_per_share: decimal.Decimal,
    withholding_rate: decimal.Decimal | None,
) -> decimal.Decimal | None:
    """Net per-share amount when the tax treatment is known.

    An unknown withholding rate returns ``None`` so callers show gross only.
    """

    gross = _non_negative(gross_per_share, "gross_per_share")
    if withholding_rate is None:
        return None
    return gross * (ONE - _rate(withholding_rate, "withholding_rate"))


def dividend_yield(
    dividend_per_share: decimal.Decimal,
    price: decimal.Decimal,
) -> decimal.Decimal | None:
    """Dividend per share divided by a positive price, returned as a fraction."""

    distribution = _non_negative(dividend_per_share, "dividend_per_share")
    valid_price = _finite(price, "price")
    if valid_price <= ZERO:
        return None
    return distribution / valid_price


def trailing_yield(
    records: Sequence[DividendRecord],
    *,
    as_of: date,
    currency: str,
    price: decimal.Decimal,
    window_days: int | None = 365,
    eligible_qualities: frozenset[DividendQuality] = VERIFIED_QUALITIES,
) -> LabeledYield | None:
    """Historical yield computed only from eligible observed dividends."""

    observed = trailing_dividend_per_share(
        records,
        as_of=as_of,
        currency=currency,
        window_days=window_days,
        eligible_qualities=eligible_qualities,
    )
    if observed is None:
        return None
    value = dividend_yield(observed, price)
    assert value is not None
    return LabeledYield(value=value, basis="TRAILING", is_estimate=False)


def forward_yield(
    estimated_annual_dividend: decimal.Decimal,
    price: decimal.Decimal,
) -> LabeledYield:
    """Yield based on an explicitly estimated forward annual dividend."""

    estimate = _non_negative(estimated_annual_dividend, "estimated_annual_dividend")
    value = dividend_yield(estimate, price)
    assert value is not None
    return LabeledYield(value=value, basis="FORWARD", is_estimate=True)


def payout_ratio(
    dividend_per_share: decimal.Decimal,
    earnings_per_share: decimal.Decimal,
) -> decimal.Decimal | None:
    """Dividend / earnings. Non-positive earnings are not interpretable."""

    distribution = _non_negative(dividend_per_share, "dividend_per_share")
    earnings = _finite(earnings_per_share, "earnings_per_share")
    if earnings <= ZERO:
        return None
    return distribution / earnings


def earnings_coverage(
    earnings_per_share: decimal.Decimal,
    dividend_per_share: decimal.Decimal,
) -> decimal.Decimal | None:
    """Earnings / dividend. A zero dividend has no finite coverage multiple."""

    earnings = _finite(earnings_per_share, "earnings_per_share")
    distribution = _finite(dividend_per_share, "dividend_per_share")
    if distribution <= ZERO:
        return None
    return earnings / distribution


def free_cash_flow_coverage(
    free_cash_flow_per_share: decimal.Decimal,
    dividend_per_share: decimal.Decimal,
) -> decimal.Decimal | None:
    """Free cash flow / dividend. Negative free cash flow is preserved."""

    cash_flow = _finite(free_cash_flow_per_share, "free_cash_flow_per_share")
    distribution = _finite(dividend_per_share, "dividend_per_share")
    if distribution <= ZERO:
        return None
    return cash_flow / distribution


def dividend_growth(
    current_per_share: decimal.Decimal,
    previous_per_share: decimal.Decimal,
) -> decimal.Decimal | None:
    """Period-over-period growth fraction; the prior dividend must be positive."""

    current = _non_negative(current_per_share, "current_per_share")
    previous = _finite(previous_per_share, "previous_per_share")
    if previous <= ZERO:
        return None
    return current / previous - ONE


def dividend_cagr(
    beginning_per_share: decimal.Decimal,
    ending_per_share: decimal.Decimal,
    years: int | decimal.Decimal,
) -> decimal.Decimal | None:
    """Compound annual growth fraction over a positive number of years."""

    beginning = _finite(beginning_per_share, "beginning_per_share")
    ending = _non_negative(ending_per_share, "ending_per_share")
    if isinstance(years, bool) or not isinstance(years, (int, decimal.Decimal)):
        raise ValueError("years must be an int or decimal.Decimal")
    periods = decimal.Decimal(years)
    if beginning <= ZERO or not periods.is_finite() or periods <= ZERO:
        return None
    return (ending / beginning) ** (ONE / periods) - ONE


def consecutive_distribution_years(annual: Mapping[int, decimal.Decimal]) -> int:
    """Count consecutive years with a positive dividend, ending at the last year."""

    if not annual:
        return 0
    for year, value in annual.items():
        if isinstance(year, bool) or not isinstance(year, int):
            raise ValueError("annual keys must be integer years")
        _non_negative(value, f"annual[{year}]")
    latest = max(annual)
    count = 0
    year = latest
    while year in annual and annual[year] > ZERO:
        count += 1
        year -= 1
    return count


def dividend_consistency(annual: Mapping[int, decimal.Decimal]) -> DividendConsistency:
    """Summarize distribution history without inventing missing years."""

    if not annual:
        return DividendConsistency(0, 0, 0, 0)
    for year, value in annual.items():
        if isinstance(year, bool) or not isinstance(year, int):
            raise ValueError("annual keys must be integer years")
        _non_negative(value, f"annual[{year}]")

    years = sorted(annual)
    paid = sum(1 for value in annual.values() if value > ZERO)
    reductions = 0
    for previous_year, current_year in zip(years, years[1:], strict=False):
        previous = annual[previous_year]
        if (
            previous > ZERO
            and current_year == previous_year + 1
            and annual[current_year] < previous
        ):
            reductions += 1
    return DividendConsistency(
        years_observed=len(years),
        years_paid=paid,
        consecutive_years=consecutive_distribution_years(annual),
        year_over_year_reductions=reductions,
    )


def project_dividend_cash(
    quantity: decimal.Decimal | int,
    annual_dividend_per_share_gross: decimal.Decimal,
    withholding_rate: decimal.Decimal | None,
) -> DividendProjection:
    """Simulate annual gross and net dividend cash for whole shares."""

    if isinstance(quantity, bool) or not isinstance(quantity, (int, decimal.Decimal)):
        raise ValueError("quantity must be an int or decimal.Decimal")
    shares = decimal.Decimal(quantity)
    if not shares.is_finite() or shares < ZERO or shares != shares.to_integral_value():
        raise ValueError("quantity must be a non-negative whole number of shares")
    distribution = _non_negative(annual_dividend_per_share_gross, "annual_dividend_per_share_gross")
    gross_cash = shares * distribution
    net_cash = (
        None if withholding_rate is None else net_dividend_amount(gross_cash, withholding_rate)
    )
    return DividendProjection(
        quantity=shares,
        annual_dividend_per_share_gross=distribution,
        withholding_rate=(
            None if withholding_rate is None else _rate(withholding_rate, "withholding_rate")
        ),
        gross_cash=gross_cash,
        net_cash=net_cash,
    )


def allocate_confirmed_dividend(
    net_amount: decimal.Decimal,
    *,
    reinvest: decimal.Decimal,
    money_market: decimal.Decimal,
    withdrawal: decimal.Decimal,
) -> DividendDistribution:
    """Split a confirmed net receipt by configured weights.

    The withdrawal leg is the residual so the three parts always reconcile
    exactly to the confirmed amount.
    """

    confirmed = _non_negative(net_amount, "net_amount")
    reinvest_weight = _rate(reinvest, "reinvest")
    money_market_weight = _rate(money_market, "money_market")
    withdrawal_weight = _rate(withdrawal, "withdrawal")
    if reinvest_weight + money_market_weight + withdrawal_weight != ONE:
        raise ValueError("reinvest, money_market and withdrawal weights must sum to one")

    reinvestment = confirmed * reinvest_weight
    money_market_amount = confirmed * money_market_weight
    withdrawal_amount = confirmed - reinvestment - money_market_amount
    return DividendDistribution(
        net_amount=confirmed,
        reinvestment=reinvestment,
        money_market=money_market_amount,
        withdrawal=withdrawal_amount,
    )
