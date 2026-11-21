# Portfolio Valuation

Formula version: `portfolio-valuation-v1`.

Implemented in `src/rfinance/analysis/portfolio/valuation.py`, this is a pure
Decimal calculation layer over the immutable ledger replay. It does not fetch
prices, submit orders, or present simulated results as brokerage performance.

## Inputs

- `LedgerReplayResult` from `replay_ledger`: cash, positions, cost bases, and
  realized P/L reconstructed from recorded events.
- `PriceQuote` values: instrument id, positive finite close, currency,
  timezone-aware observation time, and `ObservationQuality`.
- A caller-supplied instrument-to-`ValuationCategory` mapping; unknown
  instruments fall into `OTHER`.
- `as_of`, `currency`, and optional target weights.

Quotes should come from `quotes_from_eligible_candidates`, using candidates that
already passed `eligibility-observation-v1`. The valuation re-checks the
essential safety invariants: the quality must be `VERIFIED`, the currency must
match, and the observation must be no older than `max_age_days` (default 7) and
not in the future. A quote failing any check is rejected rather than ignored.

## Formulas

| Metric | Definition | Missing-data behavior |
|---|---|---|
| Market value (position) | `quantity x price` | `None` when no eligible price exists |
| Unrealized P/L (position) | `market_value - cost_basis` | `None` when no eligible price exists |
| Market value (portfolio) | Sum of valued positions only | Unvalued positions contribute nothing and are listed explicitly |
| Total value | `cash + market_value` | Partial total when `is_complete` is false |
| Unrealized P/L (portfolio) | Sum of valued-position unrealized P/L | Excludes unvalued positions |
| Allocation weight | `category_value / total_value` | Zero when total value is not positive |
| Deviation | `weight - target` | Targets absent from the mapping default to zero |

Target weights must be finite values in `[0, 1]` and sum to one. The default
baseline is 50% equity index, 20% individual dividend equities, 30% money
market, with zero target for cash and other.

## Completeness rule

A position without an eligible price is *unvalued*, never valued at cost or at
zero. `is_complete` and `unvalued_instruments` make this visible so the UI can
show an unfilled or partially valued state rather than a fabricated total.
Realized P/L is carried from the ledger unchanged and is not mixed into
unrealized P/L.

## Limitations

- No currency conversion is attempted; all inputs must already be in the
  requested currency.
- No brokerage truth, corporate-action price adjustment, or live market data is
  implied.
- Allocation execution and rebalancing are not performed by this module.
