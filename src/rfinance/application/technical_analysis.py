"""Application service composing historical provenance and Decimal indicators."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from rfinance.analysis.technical.indicators import (
    atr,
    bollinger_bands,
    drawdown_series,
    ema,
    macd,
    maximum_drawdown,
    momentum,
    rolling_volatility,
    rsi,
    sma,
)

if TYPE_CHECKING:
    from rfinance.application.historical_price_series import (
        HistoricalPriceSeriesService,
        HistoricalPriceSeriesSnapshot,
        HistoricalSeriesChoice,
    )


TECHNICAL_ANALYSIS_VERSION = "technical-analysis-report-v1"
INDICATOR_FORMULA_VERSION = "technical-decimal-v1"


@dataclass(frozen=True, slots=True)
class TechnicalIndicatorReading:
    """Latest aligned indicator value with explicit unit and parameters."""

    key: str
    label: str
    value: Decimal | None
    unit: str
    parameters: str


@dataclass(frozen=True, slots=True)
class TechnicalAnalysisReport:
    """Historical evidence and deterministic indicator summary."""

    series: HistoricalPriceSeriesSnapshot
    latest_close: Decimal | None
    indicators: tuple[TechnicalIndicatorReading, ...]
    formula_version: str = INDICATOR_FORMULA_VERSION
    methodology_version: str = TECHNICAL_ANALYSIS_VERSION


def _latest(values: tuple[Decimal | None, ...]) -> Decimal | None:
    """Return the value aligned with the latest bar, preserving warm-up None."""

    return values[-1] if values else None


class TechnicalAnalysisService:
    """Calculate indicators only from one explicitly selected historical source."""

    def __init__(self, series: HistoricalPriceSeriesService) -> None:
        self._series = series

    def available_series(self) -> tuple[HistoricalSeriesChoice, ...]:
        """Expose only instrument/source pairs with a verified active identity."""

        return self._series.available_series()

    def analyze(
        self,
        instrument_id: str,
        source_id: str,
        *,
        max_gap_days: int = 7,
    ) -> TechnicalAnalysisReport:
        """Build a point-in-time report; all periods are measured in observed bars."""

        history = self._series.load(
            instrument_id,
            source_id,
            max_gap_days=max_gap_days,
        )
        closes = history.closes
        highs = history.highs
        lows = history.lows

        simple_average = sma(closes, 20)
        exponential_average = ema(closes, 20)
        relative_strength_index = rsi(closes, 14)
        moving_average_convergence = macd(closes, 12, 26, 9)
        bands = bollinger_bands(closes, 20, Decimal("2"))
        average_true_range = atr(highs, lows, closes, 14)
        volatility = rolling_volatility(closes, 20)
        drawdowns = drawdown_series(closes)
        price_momentum = momentum(closes, 20)
        maximum_loss = maximum_drawdown(closes)

        price_unit = f"{history.currency} / unit"
        fraction_unit = "fraction (not annualized)"
        readings = (
            TechnicalIndicatorReading(
                "sma20", "Simple moving average (20)", _latest(simple_average),
                price_unit, "20 consecutive bars",
            ),
            TechnicalIndicatorReading(
                "ema20", "Exponential moving average (20)", _latest(exponential_average),
                price_unit, "20-bar SMA seed; alpha = 2/21",
            ),
            TechnicalIndicatorReading(
                "rsi14", "Relative strength index (14)", _latest(relative_strength_index),
                "index (0–100)", "14 close-to-close changes; Wilder smoothing",
            ),
            TechnicalIndicatorReading(
                "macd_line", "MACD line (12, 26)", _latest(moving_average_convergence.line),
                price_unit, "EMA(12) − EMA(26)",
            ),
            TechnicalIndicatorReading(
                "macd_signal", "MACD signal (9)", _latest(moving_average_convergence.signal),
                price_unit, "9-bar EMA of MACD line",
            ),
            TechnicalIndicatorReading(
                "macd_histogram", "MACD histogram", _latest(moving_average_convergence.histogram),
                price_unit, "MACD line − signal",
            ),
            TechnicalIndicatorReading(
                "bollinger_upper", "Bollinger upper (20, 2)", _latest(bands.upper),
                price_unit, "20-bar SMA + 2 × population standard deviation",
            ),
            TechnicalIndicatorReading(
                "bollinger_middle", "Bollinger middle (20)", _latest(bands.middle),
                price_unit, "20-bar SMA",
            ),
            TechnicalIndicatorReading(
                "bollinger_lower", "Bollinger lower (20, 2)", _latest(bands.lower),
                price_unit, "20-bar SMA − 2 × population standard deviation",
            ),
            TechnicalIndicatorReading(
                "atr14", "Average true range (14)", _latest(average_true_range),
                price_unit, "14-bar Wilder ATR; requires high/low/close",
            ),
            TechnicalIndicatorReading(
                "volatility20", "Rolling volatility (20)", _latest(volatility),
                fraction_unit, "Sample standard deviation of 20 simple returns",
            ),
            TechnicalIndicatorReading(
                "drawdown", "Current drawdown", _latest(drawdowns),
                fraction_unit, "Close versus running peak in supplied series",
            ),
            TechnicalIndicatorReading(
                "maximum_drawdown", "Maximum drawdown", maximum_loss,
                fraction_unit, "Largest peak-to-current decline in supplied series",
            ),
            TechnicalIndicatorReading(
                "momentum20", "Price momentum (20)", _latest(price_momentum),
                fraction_unit, "Current close / close 20 bars earlier − 1",
            ),
        )
        latest_close = history.points[-1].close if history.points else None
        return TechnicalAnalysisReport(
            series=history,
            latest_close=latest_close,
            indicators=readings,
        )
