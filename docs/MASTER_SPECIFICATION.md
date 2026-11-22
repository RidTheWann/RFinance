# RFinance Master Specification

## Product

RFinance is a local-first Windows 11 x64 desktop platform for investment research, intelligence, and simulated portfolio management, initially focused on Indonesian publicly listed instruments and IDR.

## Non-negotiable behavior

- No application account or mandatory login.
- Core storage and calculation remain local; offline mode must use clearly timestamped cached observations.
- No broker passwords, brokerage login, live trading, payment initiation, or real-money orders.
- Deterministic calculations are authoritative; local AI is optional and subordinate.
- Every acquired observation has source provenance, time, currency, units, and quality state.
- Historical, derived, forecast, AI-interpreted, and simulated values remain distinguishable.
- No fake market data, fictional tickers, invented products, or unsupported portfolio positions.

## Initial configuration defaults

| Setting | Initial value |
|---|---|
| Simulation capital | Rp5,000,000 |
| Risk profile | Moderate |
| Monthly contribution | None |
| Strategy preference | Growth + sustainable dividends |
| Market | Indonesia |
| Currency | IDR |

Initial target weights are 50% equity-index exposure, 20% individual dividend equities, and 30% money-market exposure. These are targets, not orders or verified available instruments. Unfilled targets stay visible; funds must not be allocated to fabricated products.

Confirmed net dividend receipt distribution defaults: 50% reinvestment, 30% money-market allocation, 20% withdrawal. Announced and estimated dividends are not actual receipts.

## Release scope boundary

A product release must have independently verified calculations, ledger reconciliation, permitted and traceable data sources, reliable local persistence, backup/restore, offline behavior, and a tested Windows installer. Opening a window alone is not a release milestone.
