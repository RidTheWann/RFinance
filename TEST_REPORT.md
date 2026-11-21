# Test Report

Last updated: 2026-11-21

## Latest fully verified application-code checkpoint

Application-code commit `e5cff0a979bf75a8c8a8b3b949123a491896e0d6` completed successfully on Windows and Ubuntu using Python 3.12.

| Check | Windows | Ubuntu |
|---|---:|---:|
| Dependency installation | Passed | Passed |
| Ruff lint | Passed | Passed |
| Ruff format check | Passed; 71 files formatted | Passed; 71 files formatted |
| Mypy | Passed | Passed |
| pytest | 65 passed | 65 passed |

The checkpoint includes the desktop foundation, portfolio ledger, local CSV provenance pipeline, instrument master and manual-review application service, append-only review audit, instrument foreign-key linkage, and Decimal technical indicators. All tests pass on both operating systems.

## Local checkpoint (current session)

| Check | Local result |
|---|---|
| Ruff 0.17.6 lint (`src`, `tests`) | Passed |
| Ruff 0.17.6 format check (`src`, `tests`) | Passed |
| Mypy (new dividend module) | Passed |
| pytest (non-UI) | 106 passed |

UI tests were not run locally because PySide6 is unavailable on this Termux/Android runtime. Python 3.12 CI has not yet run for post-`e5cff0a` commits.

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

## Known boundaries

- Instrument identity review is implemented as an application service and database audit workflow; a dedicated desktop review UI and evidence-file acquisition/hash-computation flow are not yet wired.
- Instrument verification does not promote market observations to VERIFIED. Price/source quality, freshness, corporate-action adjustment, and provider entitlement remain separate gates.
- No IDX scraper or automated market-data provider is enabled.
- The technical-analysis module is a pure Decimal calculation layer and does not fetch, resample, or adjust data.
- The dividend module is likewise a pure calculation layer; dividend event persistence, calendar, and desktop UI are not connected.
- Screening, evidence-linked recommendations, extended financial statements, valuation, portfolio trade UI/valuation, Ollama, automation, reporting, backup/restore, and production packaging remain incomplete.

## Remaining validation work

- Dedicated instrument-review UI and evidence-artifact workflow.
- Observation-quality review that can promote a price to `VERIFIED`; the eligibility gate consumes but does not grant that state.
- Connecting the implemented eligibility gate to screening and portfolio valuation.
- Dividend event persistence, calendar, and end-to-end UI connection.
- Dependency lockfile and reproducible locked installation.
- Migration downgrade/upgrade and corruption recovery.
- Backup/restore, offline operation, security/dependency audit, and clean Windows environment installation.
- Full portfolio workflows and production packaging acceptance.
