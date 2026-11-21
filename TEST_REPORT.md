# Test Report

Last updated: 2026-11-21

## Latest fully verified application-code checkpoint

Application-code commit `b37a15ef78afe4885c4282384923e27c5b0b5bd6` completed successfully on Windows and Ubuntu using Python 3.12. [Push CI run 44909356690](https://github.com/RidTheWann/RFinance/actions/runs/44909356690) and [PR CI run 44909361649](https://github.com/RidTheWann/RFinance/actions/runs/44909361649).

| Check | Windows | Ubuntu |
|---|---:|---:|
| Dependency installation | Passed | Passed |
| Ruff lint | Passed | Passed |
| Ruff format check | Passed; 94 files already formatted | Passed; 94 files already formatted |
| Mypy | Passed; 53 source files | Passed; 53 source files |
| pytest | **141 passed** | **141 passed** |

The verified commit includes the PySide6 shell, local portfolio ledger, CSV provenance pipeline, instrument identity review, append-only observation review, eligibility gates, Decimal technical and dividend calculations, and the persisted-observation PortfolioValuationService plus background desktop valuation page. All 141 tests pass on both operating systems.

## Historical developer checkpoint

A prior Termux/Python 3.14 session reported Ruff lint/format passing, Mypy passing for new dividend modules, and 127 non-UI pytest tests passing. PySide6 was unavailable in that environment, so this historical checkpoint did not validate UI behavior. It is superseded by the current Windows and Ubuntu Python 3.12 CI run above.

## Current verified implementation slice

The persisted-observation valuation service joins ledger positions to stored prices, current instrument/source policy, and append-only review decisions. It applies the observation eligibility policy before valuation and rejects conflicting latest prices instead of choosing a provider arbitrarily. The desktop refresh runs in a worker thread and exposes price provenance, freshness, unvalued positions and explicit partial-total semantics. The integration and Qt coverage is included in the 141-test Windows/Ubuntu checkpoint above.

## Coverage

### Application and persistence

- Local application path resolution and directory creation.
- SQLite schema migrations, database reopen, and application startup.
- Portfolio ledger reconciliation, weighted-average cost, fees/taxes, lot-size evidence, cash/position limits, duplicate dividend prevention, sequence and event ID integrity.
- Property-based buy/sell replay reconciliation.
- Exact Decimal persistence through SQLite close/reopen.
- Atomic rejection of invalid ledger events and append-only database triggers.
- Explicit one-time simulation initialization and invalid-capital rejection.

### Data provenance and instrument identity

- CSV schema/timezone/numeric validation, row-level rejection, duplicate handling, archive SHA-256, source provenance, unverified quality state, user-import policy constraints, and file-size/type limits.
- Import archive path containment, source and batch persistence, row diagnostics, and import-history metadata.
- New instrument placeholders remain UNVERIFIED and are inserted before market observations that reference them.
- Multiple observations for one newly discovered instrument create one placeholder per batch.
- Manual instrument review requires an explicit VERIFIED/REJECTED decision, complete identity metadata for VERIFIED, matching instrument ID, reviewer label, evidence reference, SHA-256 digest, and notes.
- Review decisions are stored with the previous state and metadata snapshot in append-only audit events.
- UI asynchronous import and recent import history display, including batch/source/hash tooltip information.

### Financial calculations

- Decimal margin, ROE, and debt/equity edge behavior.
- SMA/EMA seed and missing-value behavior, RSI/Wilder smoothing conventions, MACD alignment, Bollinger population standard deviation, True Range/ATR, rolling sample volatility, drawdown/maximum drawdown, price momentum, and benchmark-relative strength.
- Property-based constant-series checks and rejection of invalid periods and non-Decimal/non-positive price values.
- Dividend eligibility selection (cash types only, currency and quality gating, duplicate collapse, conflict rejection, deterministic ordering, window bounds), trailing/gross/net amounts, labelled trailing versus forward yield, payout/coverage ratios, growth/CAGR, consistency with gaps and reductions, simulated cash projection, and exact confirmed-receipt allocation reconciliation.
- Property-based checks that net amounts never exceed gross, trailing sums never decrease as the window grows, allocation parts always sum to the confirmed net amount, and selection never includes non-cash or unverified records.
- Observation eligibility gates: instrument identity/status/activity/currency, observation quality, look-ahead, staleness, acquisition lag, close validity, source policy, UTC normalization, and combined diagnostics. Property-based checks that unverified, stale and future observations are never eligible.
- Observation review: promotion gates (raw status, verified instrument, source policy), evidence/digest validation, append-only audit events, immutable raw rows, effective-quality derivation, review history, eligibility candidate mapping, file archiving, and append-only trigger enforcement.
- Portfolio valuation: market value and unrealized P/L per position, unvalued-position handling without cost fallback, portfolio reconciliation, allocation versus targets, rejection of unverified/stale/future/wrong-currency quotes, and property-based reconciliation invariants.
- Persisted-observation valuation integration tests: effective quality from append-only price-review events, verified instrument state, source-policy gates, freshness, provenance selection, source-conflict rejection, cash-only behavior, and base-currency enforcement.
- Desktop valuation test: background refresh and cash-only rendering; main-window integration is covered separately.

## Known boundaries

- Instrument identity review and market-observation review are separate evidence-backed desktop workflows with file hashing and append-only audit history. Verifying an instrument does not promote its prices to VERIFIED.
- Price review does not certify provider licensing, corporate-action adjustment, or freshness. Those remain independent gates.
- No IDX scraper or automated market-data provider is enabled.
- The technical-analysis module is a pure Decimal calculation layer and does not fetch, resample, or adjust data.
- The dividend module is likewise a pure calculation layer; dividend event persistence, calendar, and desktop UI are not connected.
- Screening, evidence-linked recommendations, extended financial statements, portfolio trade UI, Ollama, automation, reporting, backup/restore, and production packaging remain incomplete.

## Remaining validation work

- Connecting the implemented eligibility gate to deterministic screening and evidence-linked recommendations.
- Connecting technical indicators to persisted, evidence-qualified and consistently sampled historical series; do not infer adjustment policy or frequency.
- Dividend event persistence, calendar, and end-to-end UI connection.
- Dependency lockfile and reproducible locked installation.
- Migration downgrade/upgrade and corruption recovery.
- Backup/restore, offline operation, security/dependency audit, and clean Windows environment installation.
- Full portfolio workflows and production packaging acceptance.
