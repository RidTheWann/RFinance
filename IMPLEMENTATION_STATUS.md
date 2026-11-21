# Implementation Status

Last verified against the repository: 2026-11-21

## Repository state

- Repository: RidTheWann/RFinance
- Default branch: main
- Working branch: foundation/bootstrap-core
- Active foundation PR: https://github.com/RidTheWann/RFinance/pull/1
- Latest GitHub Actions validated application-code commit: e5cff0a979bf75a8c8a8b3b949123a491896e0d6
- All work remains on the dedicated foundation branch. PR #1 is open and has not been merged into `main`.
- Earlier development used GitHub API edits and hosted GitHub Actions; this session has a mounted local checkout and a Python 3.14 runtime, so local verification is now possible.
- Python 3.12 CI has not yet run for the commits after `e5cff0a`; those are verified locally only.

## Implemented in the foundation branch

### Application foundation

- Canonical repository-wide `AGENTS.md` and Claude Code `CLAUDE.md`.
- Python package metadata, Ruff, Mypy, pytest, pytest-qt, Hypothesis, Bandit, pip-audit configuration, Windows scripts, and Windows/Ubuntu CI.
- Windows per-user persistent data paths, environment override, rotating logs, SQLite, and Alembic migrations.
- PySide6 desktop shell with Overview, Portfolio Simulator, and Settings navigation.
- Application composition root wires persistence, portfolio ledger, and market CSV importer.

### Deterministic financial and portfolio logic

- Typed instrument and market-observation contracts with explicit currency, timestamps, quality, and OHLC validation.
- Decimal primitives for profit margins, ROE, and debt-to-equity.
- Immutable portfolio ledger with explicit capital, buy, sell, cash withdrawal, and simulated-dividend events.
- Weighted-average cost, realized P/L, cash and position invariants, unique event IDs, and strict event ordering.
- Trade events require a provenance-bearing `VerifiedLotSize`; missing or unverified lot metadata blocks trading.
- Append-only SQLite event storage with exact fixed-point Decimal text persistence, UTC timestamps, uniqueness constraints, and update/delete protection triggers.
- First-run capital setup is connected to the UI and ledger. Rp5,000,000 is an editable suggested value; only explicit user action records opening cash. No assets or recurring contributions are generated automatically.
- Portfolio UI reads balances from ledger replay; the 50/20/30 allocation is shown as a target, not actual holdings.

### Data provenance, instrument identity, and local import

- Source registry with access-method and policy-status fields. User-import sources are unreviewed by default; database constraints prohibit automated access or redistribution permissions for them.
- Import-batch, source, market-observation, and row-issue persistence through Alembic migrations.
- Strict local CSV parser for canonical instrument ID, timezone-aware observation timestamp, currency, close, and optional OHLC/volume columns.
- Row-level validation and rejection diagnostics; duplicate source/instrument/time observations are rejected rather than overwritten.
- User-selected CSV files are archived under local Documents/MarketImports, hashed with SHA-256, and linked to source, import batch, acquisition timestamp, raw input cells, and transformation version.
- New identifiers discovered in imports create one instrument-master placeholder per instrument ID, initially `UNVERIFIED`. A batch flushes the instrument placeholder and import metadata before inserting observations that reference them through foreign keys.
- Imported market observations always remain `UNVERIFIED`; successful parsing or verification of instrument identity does not certify price truth, source licensing, historical completeness, or corporate-action adjustment.
- Instrument master fields and verification lifecycle are persisted through Alembic migration `0004_instrument_master`. Existing observation identifiers are backfilled as `UNVERIFIED` instruments, and market observations reference the master through a foreign key.
- `InstrumentReviewService` supports explicit operator decisions (`VERIFIED` or `REJECTED`). A `VERIFIED` decision requires a complete validated `InstrumentContract` whose ID matches the reviewed instrument.
- Every review appends an immutable audit event containing the previous state, decision, reviewer label, evidence reference, SHA-256 digest, notes, timestamp, and reviewed metadata snapshot. Database triggers prevent review-event updates/deletes.
- The desktop now exposes an instrument-review queue with evidence-file selection, SHA-256 digest computation, reviewer/notes entry, and review-history display; long-running review work executes on a Qt worker thread.
- Manual instrument identity verification remains separate from price-observation verification and does not promote imported market observations from `UNVERIFIED`.
- File size and row-count limits, archive path containment checks, and a Qt worker thread keep import processing out of the UI thread.
- Overview displays recent import history, source labels, filenames, UTC timestamps, accepted/rejected counts, and trust status. Batch ID, SHA-256, and archive path are available in row tooltips.
- Indonesia data-access review documents why IDX scraping/crawling is not enabled and why official/licensed feed terms must be verified before an automated adapter is introduced.

### Technical analysis

- Decimal-only, provider-independent implementations are documented in `docs/TECHNICAL_ANALYSIS.md` with formula version `technical-decimal-v1`.
- Implemented indicators: SMA, EMA, Wilder RSI, MACD, Bollinger Bands, True Range, Wilder ATR, rolling sample volatility, drawdown, maximum drawdown, price momentum, and relative strength versus a benchmark.
- Warm-up alignment, missing-data resets, positivity/finite-value validation, look-ahead limitations, units, and standard-deviation conventions are documented and tested.
- EMA preserves a constant series without accumulating Decimal rounding drift. MACD tests account for finite Decimal-context rounding with a tight Decimal tolerance.
- The technical module is a pure calculation layer: it does not fetch market data, infer sampling frequency, adjust corporate actions, or certify the quality/freshness of its inputs.

### Dividend analytics

- Added `dividend-analytics-v1`, a Decimal-only, dependency-free calculation layer in `src/rfinance/analysis/dividend/analytics.py` documented in `docs/DIVIDEND_ANALYTICS.md`.
- Implemented cash-dividend eligibility selection with currency filtering, quality gating, duplicate-event collapse, conflict rejection, and deterministic ordering.
- Implemented trailing dividend per share, trailing yield, explicitly labelled forward yield, net amount under a known withholding rate, payout ratio, earnings and free-cash-flow coverage, growth, CAGR, consecutive distribution years, and consistency summaries.
- Implemented clearly labelled simulated dividend cash projection and exact-reconciliation allocation for **confirmed** net receipts only.
- Missing observations and unusable denominators return `None`; no missing value is converted to zero. Forward estimates, simulations, and confirmed receipts are distinct labelled states.

## Verified CI

Application-code commit `e5cff0a979bf75a8c8a8b3b949123a491896e0d6` completed successfully on Windows and Ubuntu using Python 3.12.

| Check | Windows | Ubuntu |
|---|---:|---:|
| Dependency installation | Passed | Passed |
| Ruff lint | Passed | Passed |
| Ruff format | Passed; 71 files formatted | Passed; 71 files formatted |
| Mypy | Passed | Passed |
| pytest | 65 passed | 65 passed |

The tested head includes the instrument-master foreign-key import path, single-placeholder-per-instrument-per-batch handling, review audit workflow, and the technical-indicator test suite. The PR remains open for review and has not been merged.

## Local verification (current session)

- Branch `foundation/bootstrap-core`; Python 3.14 editable install with `--no-deps`.
- Ruff 0.17.6 lint and format checks: passed on `src` and `tests`.
- Mypy: no issues in `src/rfinance/analysis/dividend/analytics.py`; the six remaining diagnostics are pre-existing PySide6-stub artifacts because PySide6 is not installable on this Termux/Android runtime.
- pytest: 89 passed (62 pre-existing non-UI tests plus 27 new dividend tests). UI tests were not run locally because PySide6 is unavailable.

## Not implemented yet

- A separate price-observation review process. Manual instrument identity verification must not automatically promote imported market observations from `UNVERIFIED`.
- Official/licensed historical market-data entitlement, automated Indonesian market-data adapters, and source-policy approvals for any production feed.
- Generated, resolver-verified dependency lockfile.
- Full financial statements, broader valuation metrics, dividend event persistence/calendar/UI, screening, and evidence-linked recommendations. The dividend calculation layer exists but is not yet connected to persistence or the desktop.
- Portfolio trade-entry UI, market valuation, unrealized P/L, corporate actions, rebalancing, allocation execution, and full risk controls.
- Ollama integration, document analysis, automation scheduler, reporting, verified backup/restore, and Windows production installer.
- Clean-install, upgrade, offline, security, and production packaging acceptance.

## Next engineering objectives

1. Implement separate market-observation quality review, source eligibility, and freshness gates; never infer price verification from instrument identity verification.
2. Connect technical indicators to consistently sampled, corporate-action-aware, quality-qualified historical series, with currency and methodology metadata preserved.
3. Persist dividend events with provenance and add a dividend calendar/UI connected to the calculation layer.
4. Extend fundamental statements and valuation metrics with documented formula versions and independent tests.
5. Build deterministic screening and evidence-linked recommendations only after data eligibility gates exist.
6. Continue portfolio valuation/trade flows, risk controls, automation, reporting, backup/restore, and Windows packaging in tested vertical slices.
