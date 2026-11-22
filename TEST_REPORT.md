# Test Report

Last updated: 2026-11-22

## Local verification checkpoint (2026-11-22)

Environment: Ubuntu 26.04.1 aarch64, Python 3.14.4, PySide6 6.12.0. This is a
local Linux/ARM checkpoint, not a Windows production or CI result.

| Check | Result |
|---|---|
| Ruff lint | Passed, 183 files |
| Ruff format check | Passed, 183 files |
| Mypy strict | Passed, 70 source files |
| `tests/unit` + `tests/integration` | **205 passed** |
| Targeted Qt tests (main window, Dividend Center, Research Center) | **6 passed** |
| Full Qt UI suite | 2–3 `waitUntil` timeouts and one interpreter crash across repeated runs on this aarch64/offscreen runtime; the same tests passed in prior Windows/Ubuntu x64 CI. Treated as an environment limitation, not as verified UI correctness. |
| Clean-start launch (`python -m rfinance`, fresh `RFINANCE_HOME`, offscreen Qt) | Passed: event loop stayed alive until the 8-second timeout; `Database/rfinance.sqlite3`, WAL/SHM files and `Logs/rfinance.log` were created; Alembic at `0007_recommendations` with all 13 tables present. This is a Linux aarch64 launch check, not a Windows installation test. |

New local coverage in this checkpoint:

- `tests/unit/test_dividend_contracts.py` (12 tests): frozen extra-forbid validation, default `UNVERIFIED` quality, cash/non-cash amount rules, timezone-aware acquisition, invalid currency and reporting period.
- `tests/integration/test_dividend_events.py` (7 tests): provenance persistence with deny-by-default MANUAL source, duplicate and unknown-instrument rejection, promotion gates, append-only raw rows and review ledger, evidence file archiving/hashing, calendar confirmation/estimate labels, and analytics using only verified observed cash events with `None` for missing inputs.
- `tests/ui/test_dividend_page.py` (1 test): rendering of persisted events, review history, calendar interpretation labels and deterministic analytics output.
- `tests/unit/test_fundamental_metrics.py` (10 additional tests): all 17 computed metrics with full inputs, input/formula reproducibility, missing-input and unusable-denominator statuses, financial-sector exclusions, rejection of non-finite inputs, primitive edge cases, and Hypothesis invariants for ratio, growth and margin behavior. A test caught and fixed an argument-order defect in earnings quality.

## Confirmed dividend receipt coverage (2026-11-22)

Built test-first (RED → GREEN) with the Superpowers TDD workflow:

- `tests/unit/test_portfolio_ledger.py` (3 tests): event validation, cash credit and `confirmed_dividend_income` accumulation, duplicate `(instrument, source_reference)` rejection.
- `tests/integration/test_dividend_receipts.py` (4 tests): migration preserves legacy rows and accepts the new event type, receipt table uniqueness and append-only triggers, verified/observed gating (unverified and `ANNOUNCED` rejected), exact 50/30/20 split with the withdrawal leg booked, duplicate and invalid-amount rejection.
- `tests/ui/test_dividend_page.py` (1 test): receipt form posts and displays the allocation, and ledger income reconciles.

## Qt worker race fix (2026-11-22)

Windows CI intermittently failed `test_observation_review_page_rejects...` with a 10-second `waitUntil` timeout. Root cause was a production race, not slow CI: `is_busy` reported false as soon as `QThread.isRunning()` became false, while the submit guard still saw `_thread` set until the queued `finished` handler cleared it. The second click was therefore silently ignored. Fixed in `ObservationReviewPage`, `PortfolioValuationPage`, `TechnicalAnalysisPage` and `DividendPage`; added a regression test covering the stopped-thread cleanup gap and raised UI wait timeouts to 30 seconds.

## Latest cross-platform CI checkpoint (after history rebuild)

Current `main` HEAD (Qt race fix + tooling): [push CI run 45003901279](https://github.com/RidTheWann/RFinance/actions/runs/45003901279) — Windows and Ubuntu both **success**, Python 3.12, **207 tests passed per OS**, Ruff lint/format and Mypy passed.

Earlier checkpoint `f005c9113510466fc5ea09da4d8d78818ad3b6a6`, tree `d15813a111829b8b7917ac8ee83d95d580297047`: [push CI run 45001539029](https://github.com/RidTheWann/RFinance/actions/runs/45001539029) — Windows and Ubuntu both **success**, 206 tests per OS.

The first Windows attempt aborted inside `pytestqt/plugin.py::_process_events` (Qt runner flake) with no assertion failure. `gh run rerun --failed` passed on retry against the byte-identical tree. This is recorded as an environment flake, not a product defect; earlier PR #2 CI at `eaef966d4d542d44275c4cab91e025431b63d18d` also passed 202 tests on both OSes.

## Historical cross-platform CI checkpoint

Application-code commit `eaef966d4d542d44275c4cab91e025431b63d18d` completed successfully on Windows and Ubuntu using Python 3.12. [Push CI run 44911435637](https://github.com/RidTheWann/RFinance/actions/runs/44911435637) and [PR CI run 44911439980](https://github.com/RidTheWann/RFinance/actions/runs/44911439980).

| Check | Windows | Ubuntu |
|---|---:|---:|
| Dependency installation | Passed | Passed |
| Ruff lint | Passed | Passed |
| Ruff format check | Passed; 101 files already formatted | Passed; 101 files already formatted |
| Mypy | Passed; 57 source files | Passed; 57 source files |
| pytest | **156 passed** | **156 passed** |

The verified commit includes the persisted-observation PortfolioValuationService and background valuation view, a separate historical-price eligibility gate, persisted single-source historical series loading, and the Technical Analysis desktop page. All 156 tests pass on both operating systems.

## Historical developer checkpoint

A prior Termux/Python 3.14 session reported Ruff lint/format passing, Mypy passing for new dividend modules, and 127 non-UI pytest tests passing. PySide6 was unavailable in that environment, so this historical checkpoint did not validate UI behavior. It is superseded by the current Windows and Ubuntu Python 3.12 CI run above.

## Current verified implementation slice

The persisted-observation valuation service joins ledger positions to stored prices, current instrument/source policy, and append-only review decisions; conflicting latest prices remain unvalued. The historical-series service uses its own no-look-ahead and provenance gate without applying the current-price staleness rule, selects one source per series, and inserts gap separators so rolling indicator windows cannot bridge long missing intervals. The Technical Analysis page computes the existing Decimal indicators off the UI thread and exposes source, freshness/eligibility diagnostics, gap information, and the unknown-as-supplied adjustment state. Both feature slices are covered by the 156-test Windows/Ubuntu checkpoint above.

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
- Historical technical analysis is connected to local persisted observations through a single-source series service and `historical-price-eligibility-v1`; it does not fetch, blend sources, resample, interpolate, infer frequency, or adjust corporate actions. The adjustment state is `UNKNOWN_AS_SUPPLIED` until source evidence says otherwise.
- The dividend calculation layer is connected to append-only event/review persistence, a labelled calendar and the Dividend Center desktop page. It has no automated provider feed, and confirmed dividend receipts are not yet posted to the portfolio cash ledger.
- The screening engine, append-only persistence and Research Center inspection view exist; the guided workflow that assembles all persisted evidence into an evaluation is not yet connected. Extended financial statements, portfolio trade UI, Ollama, automation, reporting, backup/restore, and production packaging remain incomplete.

## Remaining validation work

- Connecting persisted instrument state, eligible prices, fundamentals and dividend evidence into a guided screening evaluation from the desktop.
- Explicit sampling-frequency and corporate-action adjustment metadata, including verified adjusted/unadjusted source semantics.
- Confirmed dividend receipt posting to the cash ledger with duplicate protection and the 50/30/20 preference.
- Dependency lockfile and reproducible locked installation.
- Migration downgrade/upgrade and corruption recovery.
- Backup/restore, offline operation, security/dependency audit, and clean Windows environment installation.
- Full portfolio workflows and production packaging acceptance.
