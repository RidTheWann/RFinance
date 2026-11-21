"""Deterministic technical indicators using Decimal arithmetic.

All functions preserve input alignment. Values are None during warm-up or
where the explicitly documented input window is incomplete.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal


ZERO = Decimal("0")
ONE = Decimal("1")
TWO = Decimal("2")
HUNDRED = Decimal("100")

DecimalValue = Decimal | None
PriceSeries = Sequence[DecimalValue]


def _period(value: int, *, minimum: int = 1) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"period must be an integer greater than or equal to {minimum}")


def _series(values: PriceSeries, *, positive: bool = False) -> tuple[DecimalValue, ...]:
    normalized = tuple(values)
    for index, value in enumerate(normalized):
        if value is None:
            continue
        if not isinstance(value, Decimal) or not value.is_finite():
            raise ValueError(f"series value at index {index} must be a finite Decimal or None")
        if positive and value <= ZERO:
            raise ValueError(f"price at index {index} must be greater than zero")
    return normalized


def sma(values: PriceSeries, period: int) -> tuple[DecimalValue, ...]:
    """Simple moving average over period consecutive non-missing values."""

    _period(period)
    data = _series(values)
    result: list[DecimalValue] = []
    window: list[DecimalValue] = []

    for value in data:
        window.append(value)
        if len(window) > period:
            window.pop(0)
        if len(window) == period and all(item is not None for item in window):
            numeric_window = [item for item in window if item is not None]
            result.append(sum(numeric_window, start=ZERO) / Decimal(period))
        else:
            result.append(None)
    return tuple(result)


def ema(values: PriceSeries, period: int) -> tuple[DecimalValue, ...]:
    """Exponential moving average seeded by an SMA of period consecutive values.

    After a missing value, EMA state is reset and reseeded from the next full
    period of consecutive observations. Alpha = 2 / (period + 1).
    """

    _period(period)
    data = _series(values)
    alpha = TWO / Decimal(period + 1)
    one_minus_alpha = ONE - alpha
    seed: list[Decimal] = []
    current: Decimal | None = None
    result: list[DecimalValue] = []

    for value in data:
        if value is None:
            seed.clear()
            current = None
            result.append(None)
            continue

        if current is None:
            seed.append(value)
            if len(seed) == period:
                current = sum(seed, start=ZERO) / Decimal(period)
                seed.clear()
                result.append(current)
            else:
                result.append(None)
            continue

        current = alpha * value + one_minus_alpha * current
        result.append(current)

    return tuple(result)


def rsi(prices: PriceSeries, period: int = 14) -> tuple[DecimalValue, ...]:
    """Wilder RSI from close-to-close changes, expressed on a 0..100 scale.

    The first value appears after period price changes. Missing prices reset
    the previous close and Wilder averages; a fresh period is required to seed.
    A fully flat seed returns 50, positive gain with zero loss returns 100,
    and zero gain with positive loss returns 0.
    """

    _period(period)
    data = _series(prices, positive=True)
    result: list[DecimalValue] = []
    gains: list[Decimal] = []
    losses: list[Decimal] = []
    average_gain: Decimal | None = None
    average_loss: Decimal | None = None
    previous: Decimal | None = None

    def rsi_value(gain: Decimal, loss: Decimal) -> Decimal:
        if gain == ZERO and loss == ZERO:
            return Decimal("50")
        if loss == ZERO:
            return HUNDRED
        if gain == ZERO:
            return ZERO
        relative_strength = gain / loss
        return HUNDRED - (HUNDRED / (ONE + relative_strength))

    for price in data:
        if price is None:
            previous = None
            gains.clear()
            losses.clear()
            average_gain = None
            average_loss = None
            result.append(None)
            continue

        if previous is None:
            previous = price
            result.append(None)
            continue

        change = price - previous
        previous = price
        gain = max(change, ZERO)
        loss = max(-change, ZERO)

        if average_gain is None or average_loss is None:
            gains.append(gain)
            losses.append(loss)
            if len(gains) < period:
                result.append(None)
                continue
            average_gain = sum(gains, start=ZERO) / Decimal(period)
            average_loss = sum(losses, start=ZERO) / Decimal(period)
            gains.clear()
            losses.clear()
        else:
            divisor = Decimal(period)
            average_gain = (
                average_gain * Decimal(period - 1) + gain
            ) / divisor
            average_loss = (
                average_loss * Decimal(period - 1) + loss
            ) / divisor

        result.append(rsi_value(average_gain, average_loss))

    return tuple(result)


@dataclass(frozen=True, slots=True)
class MACDResult:
    line: tuple[DecimalValue, ...]
    signal: tuple[DecimalValue, ...]
    histogram: tuple[DecimalValue, ...]


def macd(
    prices: PriceSeries,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> MACDResult:
    """MACD line = fast EMA - slow EMA; signal = EMA of MACD line."""

    _period(fast_period)
    _period(slow_period)
    _period(signal_period)
    if fast_period >= slow_period:
        raise ValueError("fast_period must be smaller than slow_period")

    fast = ema(prices, fast_period)
    slow = ema(prices, slow_period)
    line: list[DecimalValue] = [
        fast_value - slow_value
        if fast_value is not None and slow_value is not None
        else None
        for fast_value, slow_value in zip(fast, slow, strict=True)
    ]
    signal = ema(line, signal_period)
    histogram = tuple(
        line_value - signal_value
        if line_value is not None and signal_value is not None
        else None
        for line_value, signal_value in zip(line, signal, strict=True)
    )
    return MACDResult(tuple(line), signal, histogram)


@dataclass(frozen=True, slots=True)
class BollingerBands:
    upper: tuple[DecimalValue, ...]
    middle: tuple[DecimalValue, ...]
    lower: tuple[DecimalValue, ...]


def bollinger_bands(
    prices: PriceSeries,
    period: int = 20,
    standard_deviations: Decimal = TWO,
) -> BollingerBands:
    """Population-standard-deviation Bollinger bands around a simple average."""

    _period(period)
    if not isinstance(standard_deviations, Decimal) or not standard_deviations.is_finite():
        raise ValueError("standard_deviations must be a finite Decimal")
    if standard_deviations < ZERO:
        raise ValueError("standard_deviations cannot be negative")

    data = _series(prices)
    middle = sma(data, period)
    upper: list[DecimalValue] = []
    lower: list[DecimalValue] = []

    for index, average in enumerate(middle):
        start = index - period + 1
        window = data[start : index + 1] if start >= 0 else ()
        if average is None or len(window) != period or any(value is None for value in window):
            upper.append(None)
            lower.append(None)
            continue

        values = [value for value in window if value is not None]
        variance = sum(
            ((value - average) ** 2 for value in values),
            start=ZERO,
        ) / Decimal(period)
        deviation = variance.sqrt()
        width = standard_deviations * deviation
        upper.append(average + width)
        lower.append(average - width)

    return BollingerBands(tuple(upper), middle, tuple(lower))


def true_range(
    highs: PriceSeries,
    lows: PriceSeries,
    closes: PriceSeries,
) -> tuple[DecimalValue, ...]:
    """True range; first valid bar uses high-low because no prior close exists."""

    high_values = _series(highs, positive=True)
    low_values = _series(lows, positive=True)
    close_values = _series(closes, positive=True)
    if not (len(high_values) == len(low_values) == len(close_values)):
        raise ValueError("high, low, and close series must have equal lengths")

    result: list[DecimalValue] = []
    previous_close: Decimal | None = None
    for index, (high, low, close) in enumerate(
        zip(high_values, low_values, close_values, strict=True)
    ):
        if high is None or low is None or close is None:
            previous_close = close
            result.append(None)
            continue
        if high < low:
            raise ValueError(f"high cannot be lower than low at index {index}")

        if previous_close is None:
            range_value = high - low
        else:
            range_value = max(
                high - low,
                abs(high - previous_close),
                abs(low - previous_close),
            )
        result.append(range_value)
        previous_close = close

    return tuple(result)


def atr(
    highs: PriceSeries,
    lows: PriceSeries,
    closes: PriceSeries,
    period: int = 14,
) -> tuple[DecimalValue, ...]:
    """Wilder average true range; first ATR follows period valid true ranges."""

    _period(period)
    ranges = true_range(highs, lows, closes)
    result: list[DecimalValue] = []
    seed: list[Decimal] = []
    current: Decimal | None = None

    for value in ranges:
        if value is None:
            seed.clear()
            current = None
            result.append(None)
            continue

        if current is None:
            seed.append(value)
            if len(seed) < period:
                result.append(None)
                continue
            current = sum(seed, start=ZERO) / Decimal(period)
            seed.clear()
        else:
            current = (
                current * Decimal(period - 1) + value
            ) / Decimal(period)
        result.append(current)

    return tuple(result)


def rolling_volatility(
    prices: PriceSeries,
    period: int = 20,
) -> tuple[DecimalValue, ...]:
    """Sample standard deviation of period consecutive simple returns.

    This function does not annualize volatility. The first value requires
    period + 1 consecutive positive prices; missing values reset the window.
    """

    _period(period, minimum=2)
    data = _series(prices, positive=True)
    returns: list[DecimalValue] = []
    previous: Decimal | None = None

    for price in data:
        if price is None or previous is None:
            returns.append(None)
            previous = price
            continue
        returns.append(price / previous - ONE)
        previous = price

    result: list[DecimalValue] = []
    window: list[DecimalValue] = []
    for value in returns:
        window.append(value)
        if len(window) > period:
            window.pop(0)
        if len(window) != period or any(item is None for item in window):
            result.append(None)
            continue
        numeric = [item for item in window if item is not None]
        mean = sum(numeric, start=ZERO) / Decimal(period)
        variance = sum(
            ((item - mean) ** 2 for item in numeric),
            start=ZERO,
        ) / Decimal(period - 1)
        result.append(variance.sqrt())

    return tuple(result)


def drawdown_series(prices: PriceSeries) -> tuple[DecimalValue, ...]:
    """Peak-to-current drawdown as a fraction; missing points retain the prior peak."""

    data = _series(prices, positive=True)
    peak: Decimal | None = None
    result: list[DecimalValue] = []

    for price in data:
        if price is None:
            result.append(None)
            continue
        peak = price if peak is None else max(peak, price)
        result.append(price / peak - ONE)

    return tuple(result)


def maximum_drawdown(prices: PriceSeries) -> Decimal | None:
    """Return the most negative observed peak-to-current drawdown fraction."""

    drawdowns = [value for value in drawdown_series(prices) if value is not None]
    return min(drawdowns) if drawdowns else None


def momentum(prices: PriceSeries, lookback: int) -> tuple[DecimalValue, ...]:
    """Price momentum as a fraction, requiring a complete lookback window."""

    _period(lookback)
    data = _series(prices, positive=True)
    result: list[DecimalValue] = []

    for index, current in enumerate(data):
        start = index - lookback
        window = data[start : index + 1] if start >= 0 else ()
        if (
            current is None
            or len(window) != lookback + 1
            or any(value is None for value in window)
        ):
            result.append(None)
            continue
        base = window[0]
        assert base is not None
        result.append(current / base - ONE)

    return tuple(result)


def relative_strength(
    prices: PriceSeries,
    benchmark: PriceSeries,
    lookback: int,
) -> tuple[DecimalValue, ...]:
    """Relative total-return ratio against a benchmark over the same lookback.

    Output = (asset return factor / benchmark return factor) - 1.
    The same number of consecutive non-missing observations is required in both
    series. This is not a percentile rank or an annualized return.
    """

    _period(lookback)
    data = _series(prices, positive=True)
    benchmark_values = _series(benchmark, positive=True)
    if len(data) != len(benchmark_values):
        raise ValueError("price and benchmark series must have equal lengths")

    result: list[DecimalValue] = []
    for index, (current, benchmark_current) in enumerate(
        zip(data, benchmark_values, strict=True)
    ):
        start = index - lookback
        asset_window = data[start : index + 1] if start >= 0 else ()
        benchmark_window = (
            benchmark_values[start : index + 1] if start >= 0 else ()
        )
        if (
            current is None
            or benchmark_current is None
            or len(asset_window) != lookback + 1
            or any(value is None for value in asset_window)
            or any(value is None for value in benchmark_window)
        ):
            result.append(None)
            continue

        asset_base = asset_window[0]
        benchmark_base = benchmark_window[0]
        assert asset_base is not None and benchmark_base is not None
        asset_factor = current / asset_base
        benchmark_factor = benchmark_current / benchmark_base
        result.append(asset_factor / benchmark_factor - ONE)

    return tuple(result)
