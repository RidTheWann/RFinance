from decimal import Decimal

from rfinance.analysis.fundamental.metrics import (
    debt_to_equity,
    margin_ratio,
    ratio,
    return_on_equity,
)


def test_margin_is_a_fraction() -> None:
    assert margin_ratio(Decimal("25"), Decimal("100")) == Decimal("0.25")


def test_negative_profit_is_preserved() -> None:
    assert margin_ratio(Decimal("-5"), Decimal("100")) == Decimal("-0.05")


def test_zero_or_negative_denominator_returns_none() -> None:
    assert ratio(Decimal("10"), Decimal("0")) is None
    assert return_on_equity(Decimal("10"), Decimal("-2")) is None


def test_debt_to_equity_rejects_negative_debt() -> None:
    assert debt_to_equity(Decimal("-1"), Decimal("10")) is None
    assert debt_to_equity(Decimal("20"), Decimal("10")) == Decimal("2")


def test_valid_zero_profit_is_not_missing_data() -> None:
    assert margin_ratio(Decimal("0"), Decimal("100")) == Decimal("0")
