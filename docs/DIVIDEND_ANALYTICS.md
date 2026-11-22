# Dividend Analytics

Formula version: `dividend-analytics-v1`.

This document specifies the deterministic dividend calculation layer in
`src/rfinance/analysis/dividend/analytics.py`. The module is a pure calculation
layer: it does not fetch data, infer sampling frequency, adjust prices for
corporate actions, certify source entitlement, or read the portfolio ledger.
All monetary and per-share values are `Decimal`.

## Evidence model

Each `DividendRecord` carries an `event_id`, gross `amount_per_share`, `ex_date`,
`currency`, `dividend_type`, `quality`, and `source_id`. `DividendQuality` values
mirror `DataQualityStatus`; the application layer maps persisted contracts into
this dependency-free enum.

Only `CASH`, `INTERIM`, `FINAL`, and `SPECIAL` types are treated as cash
dividends. `STOCK` and `RIGHTS` are corporate actions and are excluded from cash
totals to prevent double counting. Records whose currency does not match the
requested currency are ignored rather than converted.

By default only `VERIFIED` records are eligible. Callers may widen eligibility
explicitly, and the resulting label reflects the selected basis. Duplicate
`event_id` values are collapsed; conflicting records sharing an `event_id` raise
an error instead of silently overwriting history.

## Formula reference

All ratios are fractions (0.05 = 5%). Presentation formatting is a separate
concern. A `None` result means the input is missing or the denominator is
unusable; it is never coerced to zero.

| Metric | Definition | Numerator | Denominator | Units | Missing / invalid behavior |
|---|---|---|---|---|---|
| Trailing dividend per share | Sum of eligible cash `amount_per_share` within the window | eligible per-share amounts | n/a | currency per share | `None` if no eligible event exists |
| Net dividend amount | `gross x (1 - withholding_rate)` | gross per-share amount | n/a | currency per share | `None` if tax treatment unknown; rate outside `[0, 1]` is rejected |
| Dividend yield | `dividend_per_share / price` | dividend per share | positive price | fraction | `None` when price <= 0 |
| Payout ratio | `dividend_per_share / earnings_per_share` | dividend per share | positive earnings per share | fraction | `None` when earnings <= 0 |
| Earnings coverage | `earnings_per_share / dividend_per_share` | earnings per share | positive dividend per share | multiple | `None` when dividend <= 0 |
| Free-cash-flow coverage | `free_cash_flow_per_share / dividend_per_share` | free cash flow per share | positive dividend per share | multiple | `None` when dividend <= 0; negative FCF is preserved |
| Dividend growth | `current / previous - 1` | current per-share amount | positive previous amount | fraction | `None` when previous <= 0 |
| Dividend CAGR | `(ending / beginning) ^ (1 / years) - 1` | ending per-share amount | positive beginning per share and positive years | fraction per year | `None` when beginning <= 0 or years <= 0 |
| Consecutive distribution years | Count of contiguous years with a positive dividend ending at the latest observed year | n/a | n/a | years | `0` when no observation exists; gaps stop the count |
| Consistency | Observed years, paid years, consecutive years, adjacent-year reductions | n/a | n/a | counts | Missing years are not invented; reductions require adjacent calendar years |

The trailing window is anchored at `as_of`, inclusive at `as_of` and exclusive
at its lower bound. `window_days=None` means no lower bound. The caller supplies
`as_of` as a calendar `date`; timezone-aware `datetime` values are rejected so
that observation timing cannot be silently reinterpreted.

## Trailing versus forward

`trailing_yield` returns a `LabeledYield` with `basis="TRAILING"` and
`is_estimate=False`, computed only from eligible observed cash dividends.
`forward_yield` returns `basis="FORWARD"` and `is_estimate=True` because its
input is an explicitly estimated annual dividend. The two values must not be
presented as interchangeable, and a forward estimate is never treated as a
confirmed cash receipt.

## Gross, net, and tax

`net_dividend_amount` returns a value only when a withholding rate is supplied.
When the applicable tax treatment is unknown, callers must display the gross
value and an explicitly labelled estimated net value; the module returns `None`
for the net amount rather than assuming a rate.

`project_dividend_cash` simulates annual cash for whole shares and always sets
`is_simulated=True`. It never represents money actually received.

## Confirmed receipt allocation

`allocate_confirmed_dividend` splits a **confirmed** net receipt using the
configured reinvestment / money-market / withdrawal weights. Weights must each
lie in `[0, 1]` and sum to one. The withdrawal leg is computed as the residual
so the three parts always reconcile exactly to the confirmed net amount. This
function is not for simulated dividends.

## Limitations

- No price resampling, sampling-frequency inference, or corporate-action price
  adjustment is performed here.
- Credentials, provider entitlement, and licensing are outside this layer.
- No conclusion about future prices or dividend payments is implied.
- Data-quality and freshness gates for recommendations are a separate concern;
  this module exposes eligibility selection but does not decide recommendation
  status.
