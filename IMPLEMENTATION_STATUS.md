# Implementation Status

Last verified against the repository: 2026-11-21

## Repository state

- Repository: RidTheWann/RFinance
- Default branch: main
- Working branch: foundation/bootstrap-core
- Active foundation PR: https://github.com/RidTheWann/RFinance/pull/1
- Latest GitHub Actions validated application-code commit: `3a9dc774f0ad0ad5bc80501f249ce681c5fa34e6` (Windows and Ubuntu, Python 3.12; Ruff lint/format and Mypy passed; 156 tests passed on each OS).
- All work remains on the dedicated foundation branch. PR #1 is open and has not been merged into `main`.
- This session has no mounted local checkout. Changes were committed to the feature branch through GitHub repository operations and verified with hosted Windows/Ubuntu CI; no local test or build result is claimed.

## Implemented in the foundation branch

### Application foundation

- Canonical repository-wide `AGENTS.md` and Claude Code `CLAUDE.md`.
- Python package metadata, Ruff, Mypy, pytest, pytest-qt, Hypothesis, Bandit, pip-audit configuration, Windows scripts, and Windows/Ubuntu CI.
- Windows per-user persistent data paths, environment override, rotating logs, SQLite, and Alembic migrations.
- PySide6 desktop navigation includes Overview, Portfolio Simulator, Instrument Review, Observation Review, Technical Analysis, and Settings.
- Application composition root wires SQLite persistence, portfolio ledger, CSV ingestion, instrument review, observation review, persisted-observation portfolio valuation, and historical technical-analysis services.

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
- `HistoricalPriceSeriesService` connects local persisted observations to technical analysis using the separate `historical-price-eligibility-v1` gate. It selects one instrument/source pair, uses the latest append-only price-review decision, rejects future observations, unverified prices, unverified/inactive instrument identities, currency mismatches, and blocked/restricted sources, but deliberately does not apply the current-quote 7-day staleness rule to historical bars.
- A large calendar gap inserts a `None` separator before indicator calculation, restarting rolling warm-up windows. Periods count stored observations, not inferred trading days. No source blending, resampling, interpolation, frequency inference, or corporate-action adjustment is performed; adjustment remains `UNKNOWN_AS_SUPPLIED`.
- The Technical Analysis desktop page loads the locally available instrument/source catalogue and runs indicator calculations on a Qt worker thread. Each report displays source identity, period, rejected-row diagnostics, gap count, formula version, and adjustment limitation.

### Dividend analytics

- Added `dividend-analytics-v1`, a Decimal-only, dependency-free calculation layer in `src/rfinance/analysis/dividend/analytics.py` documented in `docs/DIVIDEND_ANALYTICS.md`.
- Implemented cash-dividend eligibility selection with currency filtering, quality gating, duplicate-event collapse, conflict rejection, and deterministic ordering.
- Implemented trailing dividend per share, trailing yield, explicitly labelled forward yield, net amount under a known withholding rate, payout ratio, earnings and free-cash-flow coverage, growth, CAGR, consecutive distribution years, and consistency summaries.
- Implemented clearly labelled simulated dividend cash projection and exact-reconciliation allocation for **confirmed** net receipts only.
- Missing observations and unusable denominators return `None`; no missing value is converted to zero. Forward estimates, simulations, and confirmed receipts are distinct labelled states.

### Observation eligibility gates

- Added `eligibility-observation-v1`, a dependency-free domain policy in `src/rfinance/domain/eligibility/observation.py` documented in `docs/DATA_ELIGIBILITY.md`.
- `evaluate_observation` reports every failed gate (instrument identity, instrument status/activity/currency, observation quality, currency match, look-ahead, staleness, acquisition lag, close validity, and source policy) instead of silently dropping a value.
- Instrument identity verification and observation verification are independent gates; verifying an instrument cannot promote a price.
- `select_eligible_observations` partitions observations into usable and diagnosed rejections without mutation, giving downstream screening a single eligibility boundary.

### Observation review workflow

- Added migration `0005_observation_review` and an append-only `observation_review_events` ledger. Raw market observations remain immutable; effective quality is derived from the latest decision.
- `ObservationReviewService` promotes or rejects a price only with explicit reviewer, evidence reference, SHA-256 digest, and notes. Promotion additionally requires a raw `UNVERIFIED` observation, a `VERIFIED` instrument identity, and a source policy that is neither `BLOCKED` nor `RESTRICTED`.
- Added evidence-file archiving under the per-user data directory, review history, raw-versus-effective candidate listing, and `candidates_for_eligibility` to connect persisted reviews to the domain eligibility gate.
- The workflow has no AI decision path and no automatic promotion; instrument identity verification still cannot certify a price.

### Portfolio valuation

- Added `portfolio-valuation-v1` in `src/rfinance/analysis/portfolio/valuation.py`, documented in `docs/PORTFOLIO_VALUATION.md`.
- Values ledger positions only from verified, currency-matching, fresh quotes that passed the eligibility gate; unverified, stale, future, or wrong-currency quotes are rejected.
- Reports unvalued positions explicitly instead of valuing them at cost or zero, with `is_complete`, per-position market value and unrealized P/L, portfolio totals, and allocation versus configurable targets.
- `quotes_from_eligible_candidates` connects gated observation candidates to valuation quotes. No currency conversion, brokerage claim, or rebalancing is performed.
- `PortfolioValuationService` joins persisted observations to instrument/source policy and append-only price-review decisions, then applies `eligibility-observation-v1` before selecting the newest eligible quote.
- Conflicting latest prices from different sources are not resolved arbitrarily; the position remains unvalued with a diagnostic. Instrument type is mapped conservatively; generic equities and ETFs are not assumed to be dividend stocks or index trackers.
- The Portfolio Simulator now has a background valuation refresh and displays price provenance, observation age, price, market value, unrealized P/L, and eligibility diagnostics. Partial totals are explicitly labeled; missing positions are not substituted at cost or zero.

## Verified CI

Application-code commit `b37a15ef78afe4885c4282384923e27c5b0b5bd6` completed successfully on Windows and Ubuntu using Python 3.12. See [push CI 44909356690](https://github.com/RidTheWann/RFinance/actions/runs/44909356690) and [PR CI 44909361649](https://github.com/RidTheWann/RFinance/actions/runs/44909361649).

| Check | Windows | Ubuntu |
|---|---:|---:|
| Dependency installation | Passed | Passed |
| Ruff lint | Passed | Passed |
| Ruff format | Passed; 94 files already formatted | Passed; 94 files already formatted |
| Mypy | Passed; 53 source files | Passed; 53 source files |
| pytest | **141 passed** | **141 passed** |

The tested head includes persisted-observation portfolio valuation, append-only price-review integration, source and instrument eligibility, explicit latest-price conflict rejection, historical-series eligibility and loading, the Technical Analysis Qt workflow, and indicator warm-up resets across large date gaps. The PR remains open for review and has not been merged.

## Historical local developer checkpoint (previous Termux session)

- Branch `foundation/bootstrap-core`; Python 3.14 editable install with `--no-deps`.
- Ruff 0.17.6 lint and format checks: passed on `src` and `tests`.
- Mypy: no issues in `src/rfinance/analysis/dividend/analytics.py`; the six remaining diagnostics are pre-existing PySide6-stub artifacts because PySide6 is not installable on this Termux/Android runtime.
- pytest: 127 passed (62 pre-existing non-UI tests plus 27 dividend, 17 eligibility, 14 observation-review and 7 valuation tests). UI tests were not run locally because PySide6 is unavailable.

## Not implemented yet

- Official/licensed historical market-data entitlement, automated Indonesian market-data adapters, and source-policy approvals for any production feed.
- Generated, resolver-verified dependency lockfile.
- Full financial statements, broader valuation metrics, dividend event persistence/calendar/UI, screening, and evidence-linked recommendations. The dividend calculation layer exists but is not yet connected to persistence or the desktop.
- Portfolio trade-entry UI, corporate actions, rebalancing, allocation execution, and full risk controls remain incomplete. Portfolio market valuation is now connected to persisted review-adjusted observations and the desktop, but its source values still depend on lawfully obtained and manually reviewable data.
- Ollama integration, document analysis, automation scheduler, reporting, verified backup/restore, and Windows production installer.
- Clean-install, upgrade, offline, security, and production packaging acceptance.

## Next engineering objectives

1. Persist dividend events with provenance and add a dividend calendar/UI connected to the existing Decimal calculation layer.
2. Add explicit instrument and observation sampling-frequency/adjustment metadata, then define any compliant historical data ingestion path without inferring split/dividend adjustment.
3. Extend fundamental statements and valuation metrics with documented formula versions and independent tests.
4. Build deterministic screening and evidence-linked recommendations only after data eligibility gates exist.
5. Add verified-instrument metadata to portfolio-trade eligibility, then implement auditable simulated trade-entry and position management without inferred lot-size rules.
6. Continue risk controls, automation, reporting, backup/restore, and Windows packaging in tested vertical slices.
