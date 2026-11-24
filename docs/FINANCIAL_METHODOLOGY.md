# Financial Methodology

## General rules

- Monetary and share-level calculations use Decimal; floating point is reserved for explicitly non-accounting statistical work.
- Every metric must declare its unit, currency, period, source inputs, formula version, and missing-data behavior.
- Never replace missing observations with zero.
- A zero or negative denominator is invalid for metrics whose denominator represents revenue, equity, assets, or capital base; return an unavailable result with a reason rather than infinity.
- Reported metrics, derived metrics, analyst estimates, forward estimates, AI interpretations, and simulations must be separately labelled.
- Financial statements must be period-aligned and use a declared reporting basis (annual, quarterly, trailing twelve months, etc.).

`verified_inputs` never blends reporting bases for one metric. With an explicit `reporting_basis`, only that basis is eligible and the newest period within it wins. Without one, the most complete available basis wins (`ANNUAL`, then `TTM`, then `QUARTERLY`) before period recency is compared, so a newer quarter cannot replace an annual figure and feed a three-month denominator into an annual formula. Callers of the persisted-fundamentals path must still declare the basis their formula version expects; `ScreeningEvaluationService.evaluate` rejects persisted fundamentals when `reporting_basis` is omitted.

## Fundamental metrics (`fundamental-metrics-v1`)

`src/rfinance/analysis/fundamental/metrics.py` provides both low-level pure
functions and a `compute_fundamental_metrics(inputs, is_financial=False)`
orchestrator. Each returned `ComputedMetric` carries its name, value, status,
formula string, canonical formula version, the exact inputs used (serialized,
with `MISSING` for absent values), and a note. This makes every derived figure
reproducible and keeps reported values, derived values, forecasts and
simulations distinct.

| Metric | Formula | Required inputs | Unusable condition |
|---|---|---|---|
| `REVENUE_GROWTH` | current revenue / prior revenue - 1 | both revenues | prior revenue <= 0 |
| `EPS_GROWTH` | current EPS / prior EPS - 1 | both EPS values | prior EPS <= 0 |
| `GROSS_MARGIN` | gross profit / revenue | gross profit, revenue | revenue <= 0 |
| `OPERATING_MARGIN` | operating income / revenue | operating income, revenue | revenue <= 0 |
| `NET_MARGIN` | net income / revenue | net income, revenue | revenue <= 0 |
| `RETURN_ON_EQUITY` | net income / average equity | net income, average equity | average equity <= 0 |
| `RETURN_ON_ASSETS` | net income / average total assets | net income, average assets | average assets <= 0 |
| `RETURN_ON_INVESTED_CAPITAL` | EBIT x (1 - tax rate) / (debt + equity - cash) | EBIT, tax rate, debt, equity, cash | tax rate outside [0,1], negative capital components, capital base <= 0 |
| `DEBT_TO_EQUITY` | total debt / total equity | debt, equity | negative debt or equity <= 0 |
| `INTEREST_COVERAGE` | EBIT / interest expense | EBIT, interest expense | interest expense <= 0 |
| `OPERATING_CASH_FLOW` | reported value, reporting currency | operating cash flow | missing |
| `FREE_CASH_FLOW` | operating cash flow - capital expenditure | OCF, capex | negative capex |
| `EARNINGS_QUALITY` | operating cash flow / net income | net income, OCF | net income <= 0 |
| `CASH_FLOW_QUALITY` | free cash flow / operating cash flow | OCF, FCF | OCF <= 0 |
| `PRICE_TO_EARNINGS` | price / EPS | price, EPS | EPS <= 0 |
| `PRICE_TO_BOOK` | price / book value per share | price, BVPS | BVPS <= 0 |
| `EV_TO_EBITDA` | enterprise value / EBITDA | EV, EBITDA | negative EV or EBITDA <= 0 |

All ratios are fractions, not percentages. A loss-making company has no P/E;
no zero or missing denominator is converted into a score. `MetricStatus`
distinguishes `OK`, `MISSING_INPUT`, `UNUSABLE_DENOMINATOR`, `NEGATIVE_INPUT`
and `NOT_APPLICABLE`.

### Financial-sector exception

Banks and other financial institutions do not share industrial leverage and
cash-flow semantics. When `is_financial=True`, the orchestrator returns
`DEBT_TO_EQUITY`, `INTEREST_COVERAGE`, `RETURN_ON_INVESTED_CAPITAL`,
`FREE_CASH_FLOW`, `EARNINGS_QUALITY`, `CASH_FLOW_QUALITY` and `EV_TO_EBITDA` with
status `NOT_APPLICABLE` and a null value. ROE, ROA, margins and per-share
valuation multiples remain available where their inputs are valid. The caller
must supply the industry classification from verified instrument metadata; it
is never inferred from a ticker or sector name.

## Dividend analytics (`dividend-analytics-v1`)

The deterministic dividend layer is specified in `docs/DIVIDEND_ANALYTICS.md`.
It provides trailing dividend per share, trailing and explicitly labelled
forward yield, net amount under a known withholding rate, payout ratio,
earnings and free-cash-flow coverage, growth, CAGR, distribution consistency,
simulated cash projection, and allocation of confirmed net receipts. All values
are Decimal. Missing or unusable denominators return `None`, never zero. A
forward estimate, a simulated cash flow, and a confirmed receipt are distinct
states and are labelled accordingly.

## Portfolio valuation (`portfolio-valuation-v1`)

Portfolio valuation is specified in `docs/PORTFOLIO_VALUATION.md`. It values
ledger positions only from eligible, verified, currency-matching, fresh prices.
A position without such a price is unvalued and reported explicitly; it is
never valued at cost or zero. Market value plus cash gives total value, and
allocation deviations compare actual weights with configurable targets. Results
are labelled as simulated.

## Planned metric conventions

Before release, document and test period alignment, treatment of negative earnings/equity, leases, minority interests, preferred equity, financial-sector exceptions, corporate actions, split adjustments, and restatements for every supported formula. Do not publish EV/EBITDA, yield, payout, coverage, or valuation outputs until their required inputs and conventions are defined.
