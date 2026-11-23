# Allocation Planning

Formula version: `allocation-plan-v1`. The planner is a deterministic, pure
policy layer in `src/rfinance/domain/portfolio/allocation.py`. It derives a gap
report from an explicit `ValuationResult`; it does not fetch data, create
investment products or execute orders.

## Inputs

- `ValuationResult` from `portfolio-valuation-v1`, including category weights,
  targets, cash and an explicit completeness flag.
- `InvestableInstrument` values that must carry a non-empty evidence reference,
  a positive lot size and an optional eligible price. They are supplied by the
  application layer from verified evidence; none are inferred by the planner.
- `allocation_changes_suspended` from persisted risk-control state.
- A configurable absolute-relative tolerance, default 5% of total portfolio
  value.

## Rules

For each category with a positive target:

```
target_amount = total_value * target
difference    = target_amount - current_category_value
```

- `|difference| <= tolerance * total_value` → `AT_TARGET`.
- `difference < 0` → `REDUCE_REQUIRED`. An overweight category is only flagged;
  no automatic sale is planned.
- `difference > 0`:
  - no evidence-backed investable instrument → `UNFILLED_TARGET`;
  - verified instrument but no eligible price → `UNFILLED_TARGET`, because a
    lot quantity cannot be computed;
  - gap smaller than one verified lot → `UNFILLED_TARGET`;
  - otherwise → `INVESTABLE`, with a floor-rounded lot quantity derived from
    `difference / (lot_size * price)`.
- If allocation changes are suspended by an active risk event, an otherwise
  investable line becomes `BLOCKED` and its lot quantity is cleared. Every line
  still records the reason and the suspension warning.

An incomplete valuation, unvalued instruments and zero recorded capital produce
explicit warnings rather than silently treating missing values as zero exposure.
Unknown instruments are categorised as `OTHER` by `portfolio-valuation-v1`, so
they cannot be presented as dividend equities or an index fund.

## Interpretation

`INVESTABLE` means "a verified lot rule and eligible price exist for a
simulated target", not "buy now". `UNFILLED_TARGET` is the required state when
no suitable instrument has been verified. No plan entry is a brokerage order,
tax record or guarantee of execution. The desktop view renders the plan on a
Qt worker thread and exposes every line's reasons as tooltips.
