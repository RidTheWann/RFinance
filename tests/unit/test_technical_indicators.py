from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from rfinance.analysis.technical.indicators import (
    atr,
    bollinger_bands,
    drawdown_series,
    ema,
    macd,
    maximum_drawdown,
    momentum,
    relative_strength,
    rolling_volatility,
    rsi,
    sma,
    true_range,
)

D = Decimal


def test_sma_and_ema_seed_with_simple_average_and_realign_after_missing_values() -> None:
    values = [D("1"), D("2"), D("3"), D("4")]
    expected = (None, D("1.5"), D("2.5"), D("3.5"))

    assert sma(values, period=2) == expected
    assert ema(values, period=2) == expected

    with_gap = [D("1"), D("2"), None, D("4"), D("6")]
    assert sma(with_gap, period=2) == (None, D("1.5"), None, None, D("5"))
    assert ema(with_gap, period=2) == (None, D("1.5"), None, None, D("5"))


def test_rsi_uses_wilder_smoothing_and_explicit_flat_market_convention() -> None:
    rising = rsi([D("1"), D("2"), D("3")], period=2)
    falling = rsi([D("3"), D("2"), D("1")], period=2)
    flat = rsi([D("5"), D("5"), D("5")], period=2)

    assert rising == (None, None, D("100"))
    assert falling == (None, None, D("0"))
    assert flat == (None, None, D("50"))

    mixed = rsi([D("1"), D("2"), D("3"), D("2")], period=2)
    assert mixed[2] == D("100")
    assert mixed[3] == D("50")


def test_macd_line_signal_and_histogram_keep_series_alignment() -> None:
    result = macd(
        [D("1"), D("2"), D("3"), D("4"), D("5"), D("6")],
        fast_period=2,
        slow_period=3,
        signal_period=2,
    )

    tolerance = D("1e-26")
    assert len(result.line) == 6
    assert result.line[:2] == (None, None)
    assert all(value is not None and abs(value - D("0.5")) <= tolerance for value in result.line[2:])
    assert result.signal[:3] == (None, None, None)
    assert all(
        value is not None and abs(value - D("0.5")) <= tolerance
        for value in result.signal[3:]
    )
    assert all(
        value is not None and abs(value) <= tolerance
        for value in result.histogram[3:]
    )


def test_bollinger_bands_use_population_standard_deviation() -> None:
    bands = bollinger_bands(
        [D("1"), D("3"), D("5")],
        period=2,
        standard_deviations=D("2"),
    )

    assert bands.middle == (None, D("2"), D("4"))
    assert bands.upper == (None, D("4"), D("6"))
    assert bands.lower == (None, D("0"), D("2"))


def test_true_range_and_atr_use_high_low_and_previous_close() -> None:
    highs = [D("11"), D("12"), D("13")]
    lows = [D("9"), D("10"), D("11")]
    closes = [D("10"), D("11"), D("12")]

    assert true_range(highs, lows, closes) == (D("2"), D("2"), D("2"))
    assert atr(highs, lows, closes, period=2) == (None, D("2"), D("2"))


def test_atr_resets_seed_after_incomplete_bar() -> None:
    highs = [D("10"), None, D("13"), D("14")]
    lows = [D("8"), None, D("11"), D("12")]
    closes = [D("9"), None, D("12"), D("13")]

    assert true_range(highs, lows, closes) == (D("2"), None, D("2"), D("2"))
    assert atr(highs, lows, closes, period=2) == (None, None, None, D("2"))


def test_rolling_volatility_is_sample_standard_deviation_and_not_annualized() -> None:
    prices = [D("100"), D("110"), D("99"), D("108.9")]
    volatility = rolling_volatility(prices, period=2)
    expected = D("0.02").sqrt()

    assert volatility[0:2] == (None, None)
    assert volatility[2] == expected
    assert volatility[3] == expected


def test_drawdown_series_and_maximum_drawdown_use_running_peak() -> None:
    prices = [D("100"), D("120"), D("90"), D("96")]
    assert drawdown_series(prices) == (
        D("0"),
        D("0"),
        D("-0.25"),
        D("-0.2"),
    )
    assert maximum_drawdown(prices) == D("-0.25")
    assert maximum_drawdown([None, None]) is None


def test_momentum_requires_complete_lookback_and_returns_a_fraction() -> None:
    prices = [D("100"), D("110"), D("121"), None, D("150"), D("165")]
    assert momentum(prices, lookback=2) == (
        None,
        None,
        D("0.21"),
        None,
        None,
        None,
    )


def test_relative_strength_compares_asset_and_benchmark_return_factors() -> None:
    prices = [D("100"), D("110"), D("121")]
    benchmark = [D("100"), D("105"), D("110.25")]

    result = relative_strength(prices, benchmark, lookback=2)
    assert result[0:2] == (None, None)
    assert result[2] == (D("1.21") / D("1.1025")) - D("1")
    assert relative_strength(prices, prices, lookback=2)[2] == D("0")


def test_missing_values_reset_rolling_windows_but_drawdown_retains_peak() -> None:
    values = [D("100"), D("110"), None, D("99"), D("105")]
    assert sma(values, period=2) == (None, D("105"), None, None, D("102"))
    assert drawdown_series(values) == (
        D("0"),
        D("0"),
        None,
        D("-0.1"),
        D("-0.0454545454545454545454545455"),
    )


@pytest.mark.parametrize(
    ("function", "args"),
    [
        (sma, ([D("1")], 0)),
        (ema, ([D("1")], True)),
        (rsi, ([D("1")], -1)),
        (rolling_volatility, ([D("1"), D("2")], 1)),
        (momentum, ([D("1")], 0)),
    ],
)
def test_indicators_reject_invalid_periods(function, args) -> None:
    with pytest.raises(ValueError):
        function(*args)


def test_indicators_reject_non_decimal_and_non_positive_price_inputs() -> None:
    with pytest.raises(ValueError, match="finite Decimal"):
        sma([1.0, D("2")], period=2)  # type: ignore[list-item]
    with pytest.raises(ValueError, match="greater than zero"):
        rsi([D("10"), D("0")], period=1)
    with pytest.raises(ValueError, match="equal lengths"):
        true_range([D("2")], [], [D("1")])


@given(
    constant=st.integers(min_value=1, max_value=1_000_000),
    period=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=50, deadline=None)
def test_sma_and_ema_of_constant_series_equal_the_constant(
    constant: int,
    period: int,
) -> None:
    value = D(constant)
    values = [value] * (period + 5)

    simple = sma(values, period)
    exponential = ema(values, period)

    assert all(item == value for item in simple[period - 1 :])
    assert all(item == value for item in exponential[period - 1 :])
