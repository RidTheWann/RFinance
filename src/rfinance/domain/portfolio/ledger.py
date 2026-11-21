# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Immutable event-ledger replay for a local simulated portfolio.

The ledger is intentionally independent of Qt, SQLAlchemy, and provider adapters.
Only explicitly recorded events change cash or holdings; no monthly capital,
estimated income, or external position is ever added implicitly.
"""

from __future__ import annotations

import re
from collections.abc import Mapping as MappingABC
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


_ZERO = Decimal("0")
_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")


class LedgerEventType(StrEnum):
    CAPITAL_INJECTION = "CAPITAL_INJECTION"
    BUY = "BUY"
    SELL = "SELL"
    CASH_WITHDRAWAL = "CASH_WITHDRAWAL"
    SIMULATED_DIVIDEND = "SIMULATED_DIVIDEND"


class LedgerValidationError(ValueError):
    """An event or ledger sequence violates an accounting invariant."""


class InsufficientCashError(LedgerValidationError):
    """An event would make the portfolio cash balance negative."""


class InsufficientPositionError(LedgerValidationError):
    """A sale or dividend references a position that is not held."""


def _decimal(name: str, value: Decimal) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise LedgerValidationError(f"{name} must be a finite Decimal")


@dataclass(frozen=True, slots=True)
class LedgerEvent:
    """A single immutable, auditable portfolio event.

    BUY/SELL gross value is quantity * unit_price. Buy fees/taxes increase cost
    basis; sell fees/taxes reduce proceeds. SIMULATED_DIVIDEND amount is the
    explicit net cash amount to simulate as received, never a forecast.
    """

    event_id: str
    sequence: int
    occurred_at: datetime
    event_type: LedgerEventType
    currency: str = "IDR"
    amount: Decimal | None = None
    instrument_id: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    fees: Decimal = _ZERO
    taxes: Decimal = _ZERO
    source_reference: str | None = None

    def __post_init__(self) -> None:
        if not self.event_id.strip():
            raise LedgerValidationError("event_id must not be empty")
        if self.sequence <= 0:
            raise LedgerValidationError("sequence must be a positive integer")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise LedgerValidationError("occurred_at must be timezone-aware")
        if not _CURRENCY_PATTERN.fullmatch(self.currency):
            raise LedgerValidationError("currency must be a three-letter uppercase code")

        _decimal("fees", self.fees)
        _decimal("taxes", self.taxes)
        if self.fees < _ZERO or self.taxes < _ZERO:
            raise LedgerValidationError("fees and taxes cannot be negative")

        if self.event_type in {
            LedgerEventType.CAPITAL_INJECTION,
            LedgerEventType.CASH_WITHDRAWAL,
        }:
            self._validate_cash_event()
        elif self.event_type in {LedgerEventType.BUY, LedgerEventType.SELL}:
            self._validate_trade_event()
        elif self.event_type is LedgerEventType.SIMULATED_DIVIDEND:
            self._validate_dividend_event()
        else:
            raise LedgerValidationError(f"unsupported event type: {self.event_type}")

    def _validate_cash_event(self) -> None:
        if self.amount is None:
            raise LedgerValidationError("cash event requires amount")
        _decimal("amount", self.amount)
        if self.amount <= _ZERO:
            raise LedgerValidationError("cash event amount must be positive")
        if any(
            value is not None
            for value in (self.instrument_id, self.quantity, self.unit_price, self.source_reference)
        ):
            raise LedgerValidationError("cash event cannot contain instrument or trade fields")
        if self.fees != _ZERO or self.taxes != _ZERO:
            raise LedgerValidationError("cash event fees and taxes must be zero")

    def _validate_trade_event(self) -> None:
        if not self.instrument_id or not self.instrument_id.strip():
            raise LedgerValidationError("trade event requires instrument_id")
        if self.amount is not None or self.source_reference is not None:
            raise LedgerValidationError("trade event cannot contain cash amount or source reference")
        if self.quantity is None or self.unit_price is None:
            raise LedgerValidationError("trade event requires quantity and unit_price")
        _decimal("quantity", self.quantity)
        _decimal("unit_price", self.unit_price)
        if self.quantity <= _ZERO or self.unit_price <= _ZERO:
            raise LedgerValidationError("quantity and unit_price must be positive")
        if self.event_type is LedgerEventType.SELL and (
            self.quantity * self.unit_price < self.fees + self.taxes
        ):
            raise LedgerValidationError("sell fees and taxes cannot exceed gross proceeds")

    def _validate_dividend_event(self) -> None:
        if not self.instrument_id or not self.instrument_id.strip():
            raise LedgerValidationError("simulated dividend requires instrument_id")
        if self.amount is None:
            raise LedgerValidationError("simulated dividend requires net cash amount")
        _decimal("amount", self.amount)
        if self.amount <= _ZERO:
            raise LedgerValidationError("simulated dividend amount must be positive")
        if not self.source_reference or not self.source_reference.strip():
            raise LedgerValidationError("simulated dividend requires a unique source_reference")
        if self.quantity is not None or self.unit_price is not None:
            raise LedgerValidationError("simulated dividend cannot contain trade fields")
        if self.fees != _ZERO or self.taxes != _ZERO:
            raise LedgerValidationError(
                "simulated dividend amount must already represent its explicit net cash amount"
            )


@dataclass(frozen=True, slots=True)
class PositionSnapshot:
    """Position state reconstructed from all preceding ledger events."""

    instrument_id: str
    quantity: Decimal
    cost_basis: Decimal

    @property
    def average_cost(self) -> Decimal:
        if self.quantity == _ZERO:
            return _ZERO
        return self.cost_basis / self.quantity


@dataclass(frozen=True, slots=True)
class LedgerReplayResult:
    """Immutable result of replaying a complete portfolio ledger."""

    currency: str
    cash_balance: Decimal
    positions: MappingABC[str, PositionSnapshot]
    realized_profit_loss: Decimal
    simulated_dividends: Decimal
    total_fees: Decimal
    total_taxes: Decimal
    applied_events: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "positions", MappingProxyType(dict(self.positions)))


def replay_ledger(
    events: list[LedgerEvent] | tuple[LedgerEvent, ...],
    *,
    lot_sizes: MappingABC[str, Decimal],
    base_currency: str = "IDR",
) -> LedgerReplayResult:
    """Rebuild cash and positions in sequence order, enforcing accounting rules.

    Equity and other tradable units must have a known lot size. Unknown lot sizes
    block BUY/SELL rather than silently assuming a trading convention.
    """

    if not _CURRENCY_PATTERN.fullmatch(base_currency):
        raise LedgerValidationError("base_currency must be a three-letter uppercase code")

    cash = _ZERO
    realized = _ZERO
    dividends = _ZERO
    fees_total = _ZERO
    taxes_total = _ZERO
    last_sequence = 0
    seen_event_ids: set[str] = set()
    seen_dividend_refs: set[tuple[str, str]] = set()
    quantities: dict[str, Decimal] = {}
    cost_bases: dict[str, Decimal] = {}

    for event in events:
        if event.sequence <= last_sequence:
            raise LedgerValidationError("ledger events must have strictly increasing sequence")
        last_sequence = event.sequence
        if event.event_id in seen_event_ids:
            raise LedgerValidationError(f"duplicate event_id: {event.event_id}")
        seen_event_ids.add(event.event_id)

        if event.currency != base_currency:
            raise LedgerValidationError(
                f"currency mismatch: expected {base_currency}, got {event.currency}"
            )

        if event.event_type is LedgerEventType.CAPITAL_INJECTION:
            assert event.amount is not None
            cash += event.amount
            continue

        if event.event_type is LedgerEventType.CASH_WITHDRAWAL:
            assert event.amount is not None
            if event.amount > cash:
                raise InsufficientCashError("withdrawal would create a negative cash balance")
            cash -= event.amount
            continue

        instrument = event.instrument_id
        assert instrument is not None

        if event.event_type in {LedgerEventType.BUY, LedgerEventType.SELL}:
            lot_size = lot_sizes.get(instrument)
            if lot_size is None:
                raise LedgerValidationError(f"verified lot size is required for {instrument}")
            _decimal(f"lot size for {instrument}", lot_size)
            if lot_size <= _ZERO:
                raise LedgerValidationError(f"lot size for {instrument} must be positive")

            assert event.quantity is not None
            assert event.unit_price is not None
            if event.quantity % lot_size != _ZERO:
                raise LedgerValidationError(
                    f"quantity for {instrument} must be a multiple of lot size {lot_size}"
                )

            gross = event.quantity * event.unit_price
            if event.event_type is LedgerEventType.BUY:
                debit = gross + event.fees + event.taxes
                if debit > cash:
                    raise InsufficientCashError("purchase would create a negative cash balance")
                cash -= debit
                quantities[instrument] = quantities.get(instrument, _ZERO) + event.quantity
                cost_bases[instrument] = (
                    cost_bases.get(instrument, _ZERO) + gross + event.fees + event.taxes
                )
            else:
                held_quantity = quantities.get(instrument, _ZERO)
                if event.quantity > held_quantity:
                    raise InsufficientPositionError(
                        f"cannot sell {event.quantity} units of {instrument}; "
                        f"only {held_quantity} are held"
                    )
                current_cost = cost_bases[instrument]
                average_cost = current_cost / held_quantity
                removed_cost = (
                    current_cost
                    if event.quantity == held_quantity
                    else average_cost * event.quantity
                )
                net_proceeds = gross - event.fees - event.taxes
                cash += net_proceeds
                realized += net_proceeds - removed_cost
                remaining_quantity = held_quantity - event.quantity
                quantities[instrument] = remaining_quantity
                cost_bases[instrument] = (
                    _ZERO if remaining_quantity == _ZERO else current_cost - removed_cost
                )

            fees_total += event.fees
            taxes_total += event.taxes
            continue

        if event.event_type is LedgerEventType.SIMULATED_DIVIDEND:
            assert event.amount is not None
            assert event.source_reference is not None
            if quantities.get(instrument, _ZERO) <= _ZERO:
                raise InsufficientPositionError(
                    f"simulated dividend requires a held position in {instrument}"
                )
            dividend_key = (instrument, event.source_reference)
            if dividend_key in seen_dividend_refs:
                raise LedgerValidationError(
                    f"duplicate simulated dividend receipt: {instrument}/{event.source_reference}"
                )
            seen_dividend_refs.add(dividend_key)
            cash += event.amount
            dividends += event.amount
            continue

        raise LedgerValidationError(f"unsupported event type: {event.event_type}")

    positions = {
        instrument: PositionSnapshot(
            instrument_id=instrument,
            quantity=quantity,
            cost_basis=cost_bases[instrument],
        )
        for instrument, quantity in quantities.items()
        if quantity > _ZERO
    }
    return LedgerReplayResult(
        currency=base_currency,
        cash_balance=cash,
        positions=positions,
        realized_profit_loss=realized,
        simulated_dividends=dividends,
        total_fees=fees_total,
        total_taxes=taxes_total,
        applied_events=len(events),
    )
