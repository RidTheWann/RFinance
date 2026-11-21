# Technical Analysis Methodology

- Formula version: technical-decimal-v1
- Implementation: src/rfinance/analysis/technical/indicators.py
- Arithmetic: Python Decimal; no binary floating-point conversion is performed.
- Look-ahead: every output at index i uses observations at or before i only.
- Missing observations: represented as None, never silently replaced by zero.
- Alignment: every indicator returns a series with the same length and index alignment as its input (MACD returns three aligned series).

## Input contract

Price inputs must be finite positive Decimal values or None. High, low, and close series must have equal lengths. High must not be lower than low for any bar where both are present. Generic moving-average inputs may include finite Decimal values of any sign, including zero.

No automatic date resampling, split adjustment, dividend adjustment, or frequency inference is performed. The caller must supply one consistently sampled, correctly adjusted series and document its currency, unit, source, and adjustment policy.

## Warm-up and missing-data rules

- A rolling indicator returns None until it has the required number of consecutive valid observations.
- A missing value resets SMA/EMA and other consecutive-window calculations; the indicator becomes available again after a complete valid warm-up window.
- EMA is seeded using an SMA of the first complete valid period, then uses its recursive formula.
- RSI and ATR use Wilder smoothing, seeded by the arithmetic mean of the first complete period.
- MACD signal EMA is calculated over valid MACD line observations. Its own signal-period warm-up begins when the MACD line first becomes available.
- Drawdown emits None at missing prices but retains the last observed peak across the gap; the next valid price is compared with that prior peak.

## Indicators

### SMA

Simple moving average:

`SMA_t(n) = (1/n) \sum_{i=0}^{n-1} P_{t-i}`

Requires n consecutive non-missing values. The output remains in the price/quantity unit of the input.

### EMA

Exponential moving average:

`EMA_t = alpha * X_t + (1-alpha) * EMA_(t-1)`

`alpha = 2 / (n+1)`

Initial EMA is the SMA of the first n consecutive values. Missing data resets the EMA and requires a new seed window.

### RSI (Wilder)

For each close-to-close change, positive gains and absolute negative losses are calculated. Initial average gain/loss use arithmetic means of n changes. Later observations use Wilder smoothing:

`AvgGain_t = ((n-1)*AvgGain_(t-1) + Gain_t) / n`

`AvgLoss_t = ((n-1)*AvgLoss_(t-1) + Loss_t) / n`

`RSI = 100 - 100/(1 + AvgGain/AvgLoss)`

The first output requires n price changes. Conventions: both averages zero -> 50; loss zero with positive gain -> 100; gain zero with positive loss -> 0. Output scale is 0..100, not a probability.

### MACD

- MACD line = EMA(fast) - EMA(slow).
- Signal line = EMA(MACD line, signal period).
- Histogram = MACD line - signal line.

Fast period must be shorter than slow period. Defaults: 12, 26, and 9. Each component retains its own warm-up.

### Bollinger Bands

- Middle = SMA(n).
- Standard deviation = population standard deviation across the same n-value window.
- Upper/lower = middle +/- k * standard deviation.
- Default k = 2.

All outputs use the input price unit. Population rather than sample standard deviation is intentional for this indicator.

### True Range and ATR

For bars with a previous close:

`TR = max(High-Low, abs(High-PreviousClose), abs(Low-PreviousClose))`

For the first valid bar, where previous close is unavailable, TR = High-Low. ATR is Wilder's average of n consecutive valid true-range values. A missing high, low, or close breaks the ATR seed/smoothing sequence; after the gap, a new ATR warm-up is required.

ATR is a price-unit measure, not a percentage.

### Rolling volatility

Simple return:

`r_t = P_t/P_(t-1) - 1`

Volatility is the sample standard deviation of n consecutive simple returns (denominator n-1). It is not annualized. The first output requires n+1 consecutive positive prices. Missing observations reset the rolling return window.

### Drawdown and maximum drawdown

Running peak is the maximum valid price observed so far. Drawdown:

`DD_t = P_t/RunningPeak_t - 1`

Drawdowns are fractions at or below zero. Maximum drawdown is the minimum valid drawdown in the supplied series. Missing prices produce None but do not erase the previous peak.

### Price momentum

`Momentum_t(n) = P_t/P_(t-n) - 1`

Output is a fraction, not a percent. The entire n+1 price window must be consecutive and valid.

### Relative strength versus benchmark

`RS_t(n) = (P_t/P_(t-n)) / (B_t/B_(t-n)) - 1`

P is the instrument price; B is the benchmark value. This measures relative return over the same lookback, not percentile ranking and not an annualized return. Both series must have equal length and complete valid lookback windows.

## Important limitations

- Indicators summarize historical observations and do not predict future returns.
- A numeric output does not certify source quality. UNVERIFIED, STALE, INCOMPLETE, ESTIMATED, REJECTED, or SIMULATED inputs retain their quality state outside this pure calculation module.
- The module does not infer trading sessions, fill missing candles, resample intervals, or apply corporate actions.
- No indicator should be used in a BUY_CANDIDATE recommendation until data freshness, quality, instrument identity, and methodology eligibility checks are implemented.
