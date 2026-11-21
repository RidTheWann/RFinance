from datetime import UTC, datetime
from decimal import Decimal

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from rfinance.domain.portfolio.ledger import (
    InsufficientCashError,
    InsufficientPositionError,
    LedgerEvent,
    LedgerEventType,
    LedgerValidationError,
    replay_ledger,
)

NOW = datetime(2026, 11, 21, 9, 0, tzinfo=UTC)
LOT_SIZES = {"BBCA": Decimal("100")}


def event(
    event_id: str,
    sequence: int,
    event_type: LedgerEventType,
    **kwargs: object,
) -> LedgerEvent:
    return LedgerEvent(
        event_id=event_id,
        sequence=sequence,
        occurred_at=NOW,
        event_type=event_type,
        **kwargs,
    )


def test_capital_buy_and_sell_reconstruct_cash_and_realized_profit() -> None:
    events = [
        event("capital", 1, LedgerEventType.CAPITAL_INJECTION, amount=Decimal("2000000")),
        event(
            "buy",
            2,
            LedgerEventType.BUY,
            instrument_id="BBCA",
            quantity=Decimal("100"),
            unit_price=Decimal("9000"),
            fees=Decimal("1000"),
        ),
        event(
            "sell",
            3,
            LedgerEventType.SELL,
            instrument_id="BBCA",
            quantity=Decimal("100"),
            unit_price=Decimal("9500"),
            fees=Decimal("1000"),
        ),
    ]

    result = replay_ledger(events, lot_sizes=LOT_SIZES)

    assert result.cash_balance == Decimal("2048000")
    assert result.positions == {}
    assert result.realized_profit_loss == Decimal("48000")
    assert result.total_fees == Decimal("2000")
    assert result.applied_events == 3


def test_weighted_average_cost_includes_buy_fees() -> None:
    events = [
        event("capital", 1, LedgerEventType.CAPITAL_INJECTION, amount=Decimal("5000000")),
        event(
            "buy-a",
            2,
            LedgerEventType.BUY,
            instrument_id="BBCA",
            quantity=Decimal("100"),
            unit_price=Decimal("10000"),
            fees=Decimal("1000"),
        ),
        event(
            "buy-b",
            3,
            LedgerEventType.BUY,
            instrument_id="BBCA",
            quantity=Decimal("100"),
            unit_price=Decimal("12000"),
            fees=Decimal("1000"),
        ),
    ]

    position = replay_ledger(events, lot_sizes=LOT_SIZES).positions["BBCA"]
    assert position.quantity == Decimal("200")
    assert position.cost_basis == Decimal("2202000")
    assert position.average_cost == Decimal("11010")


def test_sale_cannot_exceed_holding() -> None:
    events = [
        event("capital", 1, LedgerEventType.CAPITAL_INJECTION, amount=Decimal("1000000")),
        event(
            "buy",
            2,
            LedgerEventType.BUY,
            instrument_id="BBCA",
            quantity=Decimal("100"),
            unit_price=Decimal("9000"),
        ),
        event(
            "oversell",
            3,
            LedgerEventType.SELL,
            instrument_id="BBCA",
            quantity=Decimal("200"),
            unit_price=Decimal("9500"),
        ),
    ]
    with pytest.raises(InsufficientPositionError):
        replay_ledger(events, lot_sizes=LOT_SIZES)


def test_purchase_cannot_create_negative_cash() -> None:
    events = [
        event("capital", 1, LedgerEventType.CAPITAL_INJECTION, amount=Decimal("500000")),
        event(
            "overspend",
            2,
            LedgerEventType.BUY,
            instrument_id="BBCA",
            quantity=Decimal("100"),
            unit_price=Decimal("9000"),
        ),
    ]
    with pytest.raises(InsufficientCashError):
        replay_ledger(events, lot_sizes=LOT_SIZES)


def test_unknown_lot_size_and_non_multiple_quantity_are_rejected() -> None:
    capital = event("capital", 1, LedgerEventType.CAPITAL_INJECTION, amount=Decimal("1000000"))
    unknown = event(
        "buy",
        2,
        LedgerEventType.BUY,
        instrument_id="UNKNOWN",
        quantity=Decimal("100"),
        unit_price=Decimal("1000"),
    )
    non_multiple = event(
        "buy",
        2,
        LedgerEventType.BUY,
        instrument_id="BBCA",
        quantity=Decimal("150"),
        unit_price=Decimal("1000"),
    )
    with pytest.raises(LedgerValidationError, match="lot size is required"):
        replay_ledger([capital, unknown], lot_sizes=LOT_SIZES)
    with pytest.raises(LedgerValidationError, match="multiple of lot size"):
        replay_ledger([capital, non_multiple], lot_sizes=LOT_SIZES)


def test_duplicate_simulated_dividend_is_blocked() -> None:
    events = [
        event("capital", 1, LedgerEventType.CAPITAL_INJECTION, amount=Decimal("2000000")),
        event(
            "buy",
            2,
            LedgerEventType.BUY,
            instrument_id="BBCA",
            quantity=Decimal("100"),
            unit_price=Decimal("9000"),
        ),
        event(
            "dividend-a",
            3,
            LedgerEventType.SIMULATED_DIVIDEND,
            instrument_id="BBCA",
            amount=Decimal("50000"),
            source_reference="BBCA-2026-EX1",
        ),
        event(
            "dividend-b",
            4,
            LedgerEventType.SIMULATED_DIVIDEND,
            instrument_id="BBCA",
            amount=Decimal("50000"),
            source_reference="BBCA-2026-EX1",
        ),
    ]
    with pytest.raises(LedgerValidationError, match="duplicate simulated dividend"):
        replay_ledger(events, lot_sizes=LOT_SIZES)


def test_dividend_requires_a_held_position_and_withdrawal_cash() -> None:
    with pytest.raises(InsufficientPositionError):
        replay_ledger(
            [
                event(
                    "dividend",
                    1,
                    LedgerEventType.SIMULATED_DIVIDEND,
                    instrument_id="BBCA",
                    amount=Decimal("50000"),
                    source_reference="event-1",
                )
            ],
            lot_sizes=LOT_SIZES,
        )

    with pytest.raises(InsufficientCashError):
        replay_ledger(
            [event("withdrawal", 1, LedgerEventType.CASH_WITHDRAWAL, amount=Decimal("1"))],
            lot_sizes=LOT_SIZES,
        )


@given(
    capital=st.integers(min_value=100_000, max_value=100_000_000),
    lots=st.integers(min_value=1, max_value=10),
    price=st.integers(min_value=100, max_value=100_000),
)
@settings(max_examples=50, deadline=None)
def test_buy_then_sell_at_same_price_reconciles(capital: int, lots: int, price: int) -> None:
    quantity = Decimal(lots * 100)
    gross = quantity * Decimal(price)
    assume(gross <= Decimal(capital))

    events = [
        event("capital", 1, LedgerEventType.CAPITAL_INJECTION, amount=Decimal(capital)),
        event(
            "buy",
            2,
            LedgerEventType.BUY,
            instrument_id="BBCA",
            quantity=quantity,
            unit_price=Decimal(price),
        ),
        event(
            "sell",
            3,
            LedgerEventType.SELL,
            instrument_id="BBCA",
            quantity=quantity,
            unit_price=Decimal(price),
        ),
    ]
    result = replay_ledger(events, lot_sizes=LOT_SIZES)

    assert result.cash_balance == Decimal(capital)
    assert result.realized_profit_loss == Decimal("0")
    assert result.positions == {}


def test_ledger_requires_increasing_unique_events_and_single_currency() -> None:
    capital = event("capital", 1, LedgerEventType.CAPITAL_INJECTION, amount=Decimal("1000"))
    duplicate = event("capital", 2, LedgerEventType.CAPITAL_INJECTION, amount=Decimal("1000"))
    with pytest.raises(LedgerValidationError, match="duplicate event_id"):
        replay_ledger([capital, duplicate], lot_sizes=LOT_SIZES)

    out_of_order = event("withdrawal", 1, LedgerEventType.CASH_WITHDRAWAL, amount=Decimal("1"))
    with pytest.raises(LedgerValidationError, match="increasing sequence"):
        replay_ledger([capital, out_of_order], lot_sizes=LOT_SIZES)

    wrong_currency = event(
        "capital-usd",
        2,
        LedgerEventType.CAPITAL_INJECTION,
        currency="USD",
        amount=Decimal("1"),
    )
    with pytest.raises(LedgerValidationError, match="currency mismatch"):
        replay_ledger([capital, wrong_currency], lot_sizes=LOT_SIZES)
