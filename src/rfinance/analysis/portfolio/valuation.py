# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Deterministic portfolio valuation from an audited ledger and eligible prices.

Formula version: ``portfolio-valuation-v1``.

A position without an eligible price is reported as unvalued; it is never
silently valued at cost or at zero. Valuation is simulated and must not be
presented as brokerage performance.
"""

from __future__ import annotations

import decimal
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING

from rfinance.domain.eligibility.observation import ObservationCandidate, ObservationQuality

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from rfinance.domain.portfolio.ledger import LedgerReplayResult

FORMULA_VERSION = "portfolio-valuation-v1"

_ZERO = decimal.Decimal("0")
_ONE = decimal.Decimal("1")


class ValuationCategory(StrEnum):
    """Allocation buckets; instrument-to-bucket mapping is caller supplied."""

    EQUITY_INDEX = "EQUITY_INDEX"
    DIVIDEND_EQUITY = "DIVIDEND_EQUITY"
    MONEY_MARKET = "MONEY_MARKET"
    CASH = "CASH"
    OTHER = "OTHER"


DEFAULT_TARGETS: dict[ValuationCategory, decimal.Decimal] = {
    ValuationCategory.EQUITY_INDEX: decimal.Decimal("0.5"),
    ValuationCategory.DIVIDEND_EQUITY: decimal.Decimal("0.2"),
    ValuationCategory.MONEY_MARKET: decimal.Decimal("0.3"),
    ValuationCategory.CASH: _ZERO,
    ValuationCategory.OTHER: _ZERO,
}


@dataclass(frozen=True, slots=True)
class PriceQuote:
    """A price that has passed the observation eligibility gate."""

    instrument_id: str
    close: decimal.Decimal
    currency: str
    observed_at: datetime
    quality: ObservationQuality

    def __post_init__(self) -> None:
        _text(self.instrument_id, "instrument_id")
        _text(self.currency, "currency")
        if len(self.currency) != 3 or not self.currency.isascii() or not self.currency.isupper():
            raise ValueError("currency must be a three-letter uppercase code")
        if not isinstance(self.close, decimal.Decimal) or not self.close.is_finite():
            raise ValueError("close must be a finite decimal.Decimal")
        if self.close <= _ZERO:
            raise ValueError("close must be positive")
        if not isinstance(self.observed_at, datetime):
            raise ValueError("observed_at must be a datetime")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        if not isinstance(self.quality, ObservationQuality):
            raise ValueError("quality must be an ObservationQuality")


@dataclass(frozen=True, slots=True)
class PositionValuation:
    """Valuation of one ledger position; None means no eligible price."""

    instrument_id: str
    category: ValuationCategory
    quantity: decimal.Decimal
    cost_basis: decimal.Decimal
    average_cost: decimal.Decimal
    price: decimal.Decimal | None
    market_value: decimal.Decimal | None
    unrealized_profit_loss: decimal.Decimal | None

    @property
    def is_valued(self) -> bool:
        return self.price is not None


@dataclass(frozen=True, slots=True)
class AllocationLine:
    """Actual weight versus configured target for one category."""

    category: ValuationCategory
    value: decimal.Decimal
    weight: decimal.Decimal
    target: decimal.Decimal
    deviation: decimal.Decimal


@dataclass(frozen=True, slots=True)
class ValuationResult:
    """Portfolio valuation with explicit completeness and allocation diagnostics."""

    as_of_utc: str
    currency: str
    cash: decimal.Decimal
    market_value: decimal.Decimal
    total_value: decimal.Decimal
    realized_profit_loss: decimal.Decimal
    unrealized_profit_loss: decimal.Decimal
    positions: tuple[PositionValuation, ...]
    allocation: tuple[AllocationLine, ...]
    unvalued_instruments: tuple[str, ...]
    is_complete: bool
    is_simulated: bool = True
    methodology_version: str = FORMULA_VERSION


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _weights(targets: Mapping[ValuationCategory, decimal.Decimal]) -> None:
    if not targets:
        raise ValueError("target allocation cannot be empty")
    total = _ZERO
    for category, target in targets.items():
        if not isinstance(category, ValuationCategory):
            raise ValueError("target keys must be ValuationCategory values")
        if not isinstance(target, decimal.Decimal) or not target.is_finite():
            raise ValueError("target weights must be finite decimal.Decimal values")
        if target < _ZERO or target > _ONE:
            raise ValueError("target weights must be between zero and one")
        total += target
    if total != _ONE:
        raise ValueError("target weights must sum to one")


def _price_map(
    quotes: Sequence[PriceQuote],
    *,
    currency: str,
    as_of: datetime,
    max_age_days: int,
) -> dict[str, PriceQuote]:
    if isinstance(max_age_days, bool) or not isinstance(max_age_days, int) or max_age_days <= 0:
        raise ValueError("max_age_days must be a positive integer")
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")

    prices: dict[str, PriceQuote] = {}
    for quote in quotes:
        if quote.currency != currency:
            raise ValueError(f"quote currency {quote.currency} does not match {currency}")
        if quote.quality is not ObservationQuality.VERIFIED:
            raise ValueError("only VERIFIED prices can value a position")
        observed_at = quote.observed_at.astimezone(as_of.tzinfo)
        age = as_of - observed_at
        if age < timedelta(0) or age > timedelta(days=max_age_days):
            raise ValueError("price observation is outside the valuation freshness window")
        prices[quote.instrument_id] = quote
    return prices


def value_portfolio(
    snapshot: LedgerReplayResult,
    *,
    quotes: Sequence[PriceQuote],
    categories: Mapping[str, ValuationCategory],
    as_of: datetime,
    currency: str,
    target_allocation: Mapping[ValuationCategory, decimal.Decimal] | None = None,
    max_age_days: int = 7,
) -> ValuationResult:
    """Value ledger positions using only eligible prices in the base currency."""

    if snapshot.currency != currency:
        raise ValueError("snapshot currency does not match the requested currency")
    targets = DEFAULT_TARGETS if target_allocation is None else target_allocation
    _weights(targets)
    prices = _price_map(quotes, currency=currency, as_of=as_of, max_age_days=max_age_days)

    positions: list[PositionValuation] = []
    unvalued: list[str] = []
    market_value = _ZERO
    unrealized = _ZERO

    for instrument_id, position in snapshot.positions.items():
        category = categories.get(instrument_id, ValuationCategory.OTHER)
        quote = prices.get(instrument_id)
        if quote is None:
            unvalued.append(instrument_id)
            positions.append(
                PositionValuation(
                    instrument_id=instrument_id,
                    category=category,
                    quantity=position.quantity,
                    cost_basis=position.cost_basis,
                    average_cost=position.average_cost,
                    price=None,
                    market_value=None,
                    unrealized_profit_loss=None,
                )
            )
            continue
        current_value = position.quantity * quote.close
        gain = current_value - position.cost_basis
        market_value += current_value
        unrealized += gain
        positions.append(
            PositionValuation(
                instrument_id=instrument_id,
                category=category,
                quantity=position.quantity,
                cost_basis=position.cost_basis,
                average_cost=position.average_cost,
                price=quote.close,
                market_value=current_value,
                unrealized_profit_loss=gain,
            )
        )

    total_value = snapshot.cash_balance + market_value
    category_values: dict[ValuationCategory, decimal.Decimal] = {
        category: _ZERO for category in ValuationCategory
    }
    category_values[ValuationCategory.CASH] = snapshot.cash_balance
    for valuation in positions:
        if valuation.market_value is not None:
            category_values[valuation.category] += valuation.market_value

    allocation: list[AllocationLine] = []
    for category in ValuationCategory:
        value = category_values[category]
        weight = _ZERO if total_value <= _ZERO else value / total_value
        target = targets.get(category, _ZERO)
        allocation.append(
            AllocationLine(
                category=category,
                value=value,
                weight=weight,
                target=target,
                deviation=weight - target,
            )
        )

    return ValuationResult(
        as_of_utc=as_of.astimezone(UTC).isoformat(),
        currency=currency,
        cash=snapshot.cash_balance,
        market_value=market_value,
        total_value=total_value,
        realized_profit_loss=snapshot.realized_profit_loss,
        unrealized_profit_loss=unrealized,
        positions=tuple(positions),
        allocation=tuple(allocation),
        unvalued_instruments=tuple(sorted(unvalued)),
        is_complete=not unvalued,
    )


def quotes_from_eligible_candidates(
    candidates: Sequence[object],
) -> tuple[PriceQuote, ...]:
    """Map gated ``ObservationCandidate`` values into valuation quotes.

    The caller must have already run the full eligibility gate; this only
    transfers the validated price and provenance fields.
    """

    quotes: list[PriceQuote] = []
    for candidate in candidates:
        if not isinstance(candidate, ObservationCandidate):
            raise ValueError("candidates must contain ObservationCandidate instances")
        quotes.append(
            PriceQuote(
                instrument_id=candidate.instrument_id,
                close=candidate.close,
                currency=candidate.currency,
                observed_at=candidate.observed_at,
                quality=candidate.quality,
            )
        )
    return tuple(quotes)
