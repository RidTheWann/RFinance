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

## Known boundaries

- Instrument identity review is implemented as an application service and database audit workflow; a dedicated desktop review UI and evidence-file acquisition/hash-computation flow are not yet wired.
- Instrument verification does not promote market observations to VERIFIED. Price/source quality, freshness, corporate-action adjustment, and provider entitlement remain separate gates.
- No IDX scraper or automated market-data provider is enabled.
- The technical-analysis module is a pure Decimal calculation layer and does not fetch, resample, or adjust data.
- Screening, evidence-linked recommendations, extended financial statements, valuation, dividend analytics, portfolio trade UI/valuation, Ollama, automation, reporting, backup/restore, and production packaging remain incomplete.

## Remaining validation work

- Dedicated instrument-review UI and evidence-artifact workflow.
- Observation-quality review, source-policy approval, and freshness/eligibility gates.
- Dependency lockfile and reproducible locked installation.
- Migration downgrade/upgrade and corruption recovery.
- Backup/restore, offline operation, security/dependency audit, and clean Windows environment installation.
- Full portfolio workflows and production packaging acceptance.
