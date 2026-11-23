# Implementation Status

Last verified against the repository: 2026-11-23

## Repository state

- Repository: RidTheWann/RFinance (public). Verified local and `origin/main` HEAD on 2026-11-23: `753308bb87b58c076fc9cf9d189c7e2a9a14d053` (**203 commits**), the merge of PR #6 (`feature/verified-trade-entry`). The working tree was clean before this session's work; `git fetch --all --prune` deleted only the stale `origin/pr-1` ref. **Correction:** the earlier claim in this file that `main` was at `f005c911...` with 179 commits did not match the remote on 2026-11-23 and is treated as an outdated checkpoint, not the current state.
- GitHub access was restored for this session via a temporary token held outside the repository. Branch `feature/risk-controls` was pushed and PR [#7](https://github.com/RidTheWann/RFinance/pull/7) was opened. The first CI attempt failed only on Windows (`test_page_evaluates_a_valuation_on_a_worker` exhausted a busy-loop before queued Qt signals arrived); commit `987b46f` replaced it with a 30-second real-time wait. Both Windows and Ubuntu jobs then passed, the PR was `MERGEABLE`/`CLEAN`, and it was merged into `main` at `94a8c87e885a36ed6577633413f122055cd8a21d` on 2026-11-23. No token is stored in the repository.
- **History rebuild:** at the owner's request, all 178 commits were rewritten so that the verbatim GPLv3 `LICENSE` and per-file SPDX headers exist from the root commit `beb02dae1acd2dfa7c2e5f87b748ba64a7a877b4` onward. The earlier "license" PR #3 was closed without merging and its branch deleted; the license was never absent from any commit in the final history. `main` was force-pushed with `--force-with-lease` after the stale branches were removed.
- License: `GPL-3.0-only` (ADR 0003, verbatim `LICENSE`, PEP 639 metadata, SPDX headers, third-party notices). PySide6 6.12 Community licensing is compatible; frozen Windows builds must retain Qt notices and provide Corresponding Source per GPLv3 §6.
- PR #2 (foundation + dividend/fundamental/screening slices) was merged before the rebuild; its content is fully preserved in the rewritten history. PR #1 (`foundation/bootstrap-core`) remains closed and unmerged but its 172 commits were preserved and rebuilt.
- All commits are pushed. A short-lived PAT was supplied by the owner, used only locally for push/PR/merge, and removed from disk afterward; no token or personal email is present in the repository.
- Agent/editor tooling (2026-11-22): committed `.vscode/extensions.json`, four OpenCode V2 project skills, an inert `.opencode/opencode.jsonc.example`, and `docs/DEVELOPER_TOOLING.md` with verified extension IDs and MCP setup. Context7 MCP installed globally and verified `connected`. Marketplace IDs and MCP package names were checked against official docs; the deprecated `seanwu.vscode-qt-for-python` was deliberately excluded.
- Latest CI: push run `45007901317` — Windows and Ubuntu both **success** (Ruff lint/format, Mypy, **215 tests per OS**). An earlier Windows attempt exposed a real Qt submit race, now fixed; another attempt aborted inside `pytestqt._process_events` and passed on rerun with a byte-identical tree.
- Local verification (Ubuntu 26.04 aarch64, Python 3.14.4): Ruff lint/format and Mypy pass; 219 unit/integration and 8 targeted Qt tests pass. Qt worker-thread UI tests are timing-unreliable on this aarch64/offscreen runtime; see [TEST_REPORT.md](TEST_REPORT.md).

## Dependency lock (this session, 2026-11-23)

- Added `requirements.lock`, generated with `pip freeze --exclude-editable` from the verified Windows 11 x64 / Python 3.13.16 development environment. The editable `rfinance` package is intentionally excluded.
- Added `scripts/regenerate_lock.ps1` so the lock can be reproduced from the active virtual environment instead of being hand-maintained.

## Backup and restore (this session, 2026-11-23)

- Added `sqlite-backup-v1` in `src/rfinance/security/backup.py`: online SQLite backup, SHA-256 sidecar manifest with provenance, read-only `integrity_check`/schema/ledger-count verification, manifest-tamper detection, and non-destructive restore into a new folder with digest comparison. No live database is overwritten.
- Connected worker-backed Settings controls (`BackupPage`) and documented the contract in `docs/BACKUP_RESTORE.md`.
- Recorded the owner's decision in ADR 0004: the optional AI role is fulfilled by the coding assistant for now; no Ollama integration or model download is introduced, and deterministic engines remain authoritative.
- Verified locally: 279 unit/integration tests and 17 UI tests pass; Ruff lint/format and Mypy strict pass.

## Allocation gap planning (this session, 2026-11-23)

- Added `allocation-plan-v1` in `src/rfinance/domain/portfolio/allocation.py` with explicit target amounts, current values, differences, evidence-backed investable instruments, floor-rounded lot quantities, overweight review flags and risk-event blocking. Unfilled targets are never replaced with fabricated products.
- `AllocationPlanningService` combines `PortfolioValuationService` with `RiskMonitoringService.screening_controls()`; `RiskControlEvidence` now carries `allocation_changes_suspended` explicitly. Bootstrap and the Portfolio Simulator desktop view are wired.
- Documented in `docs/ALLOCATION_PLANNING.md`. Verified locally: 274 unit/integration tests and 16 UI tests pass; Ruff lint/format and Mypy strict pass.
- Stabilised the worker-thread Qt UI tests (including the new allocation page) with a short settle wait after completion; all UI tests now pass repeatedly on both offscreen and native Windows platforms.

## Simulated ledger CSV reporting (this session, 2026-11-23)

- Added `ledger-csv-v1` (`src/rfinance/reporting/csv.py`) and `LedgerReportService`, connected to an "Export simulated ledger (CSV)" button in the Portfolio Simulator. Every row is labelled `SIMULATED`, carries the methodology version and UTC generation time, keeps missing values empty, rejects currency mismatches and duplicate sequences, and neutralises spreadsheet-formula prefixes in user-supplied text.
- Documented the export contract in `docs/REPORTING.md`. Verified locally: 255 unit/integration tests and 13 stable UI tests pass; Ruff lint/format and Mypy strict pass.

## Implemented in the foundation branch

### Application foundation

- Canonical repository-wide `AGENTS.md` and Claude Code `CLAUDE.md`.
- Python package metadata, Ruff, Mypy, pytest, pytest-qt, Hypothesis, Bandit, pip-audit configuration, Windows scripts, and Windows/Ubuntu CI.
- Windows per-user persistent data paths, environment override, rotating logs, SQLite, and Alembic migrations.
- PySide6 desktop navigation includes Overview, Portfolio Simulator, Instrument Review, Observation Review, Technical Analysis, and Settings.
- Application composition root wires SQLite persistence, portfolio ledger, CSV ingestion, instrument review, observation review, persisted-observation portfolio valuation, and historical technical-analysis services.

### Deterministic financial and portfolio logic

- Typed instrument and market-observation contracts with explicit currency, timestamps, quality, and OHLC validation.
- `fundamental-metrics-v1`: 17 reproducible Decimal fundamental metrics (growth, margins, ROE/ROA/ROIC, leverage, interest coverage, cash-flow measures, P/E, P/B, EV/EBITDA) with explicit formula/input/status records, missing-data and unusable-denominator handling, and a financial-sector applicability gate that excludes industrial leverage/cash-flow metrics for banks. Unit and property tests cover the invariants.
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

### Confirmed dividend receipt posting (`dividend-receipt-v1`)

- Added `CONFIRMED_DIVIDEND` ledger event with an explicit net amount, required `DIVIDEND_RECEIPT:<event_id>` source reference, zero fees/taxes, and replay that accumulates `confirmed_dividend_income` while rejecting duplicate receipts.
- Added Alembic migration `0008_confirmed_dividend_receipts`, which rebuilds the ledger table to extend its CHECK constraint, recreates indexes and append-only triggers, and adds an append-only `dividend_receipts` table unique on `dividend_event_id`. Legacy rows are preserved.
- `DividendReceiptService` posts only from verified, observed cash dividend events, splits the confirmed net amount 50/30/20 with exact Decimal arithmetic, books the withdrawal leg as a separate `CASH_WITHDRAWAL`, and exposes the stored receipt for inspection. An explicit user-supplied net amount is required; no forecast or simulated value can be posted.
- Connected a "Confirmed receipt" tab in the Dividend Center with worker-backed posting and visible allocation.

### Evidence-gated simulated trade entry

- `VerifiedLotSizeService` derives tradable lot sizes only from a `VERIFIED` instrument whose latest evidence-backed review supplies a lot size and evidence reference; unverified, inactive or unevidenced instruments yield no rule.
- `PortfolioTradingService` appends `BUY`/`SELL` ledger events only when such a rule exists, the quantity is a positive multiple of it, and price/costs are valid. Replay still enforces cash and position invariants.
- The Portfolio Simulator now hosts a connected trade-entry form showing the verified lot rule and evidence, with worker-backed submission and explicit simulated-only labelling.

### Reviewed financial statement metrics

- Added migration `0009_financial_metrics`: append-only `financial_metrics` and `financial_metric_reviews` tables with provenance, periods, reporting basis, exact Decimal text, quality states and evidence-backed review audit.
- `FinancialStatementService` records raw metrics as `UNVERIFIED`, promotes only raw `UNVERIFIED` values with a verified instrument, allowed source policy, reviewer, evidence reference and SHA-256 digest; estimates cannot be promoted. `verified_inputs` returns the newest verified value per metric name, excluding future periods.
- Guided screening can now use verified local filings instead of operator-supplied numbers; a Research Center checkbox selects the source and evidence is labelled accordingly.

### Guided screening evaluation

- `ScreeningEvaluationService` assembles a `ScreeningInput` only from persisted evidence: instrument master identity/status/currency, latest review-adjusted observation with age and source policy, verified cash dividend event IDs, and metrics from operator-supplied fundamentals. No price fetch, no inferred metric, no AI authority.
- The assembled input is delegated unchanged to `RecommendationService.evaluate`, preserving all blocking rules. Unverified instruments, stale prices and missing fundamentals are covered by integration tests.
- The Research Center gained an "Evaluate from local evidence" form running on a Qt worker thread, with visible action, evidence IDs, risk flags and invalidation conditions.

### Deterministic risk controls (`risk-controls-v1`)

- Added a framework-independent engine in `src/rfinance/domain/risk/controls.py`: configurable review thresholds (10% individual stock, 20% sector, 6-month review, 5-point allocation deviation, 10% elevated drawdown, 15% critical drawdown), explicit snapshots, deterministic findings and Decimal `risk-controls-v1` drawdown arithmetic. Incomplete valuation yields `VALUATION_INCOMPLETE` and **no** drawdown number; no missing value is coerced to zero.
- Added `RiskMonitoringService` with append-only `risk_events`, explicit one-per-event `risk_reviews`, and `portfolio_valuation_history` (`0010_risk_events`). Event IDs are deterministic SHA-256 digests (rule, severity, UTC date, methodology, evidence reference), so repeated evaluation on one UTC date is idempotent; a worsened severity creates a new event. Only an explicit reviewer, notes and evidence reference resolve an event and lift its suspension.
- Drawdown uses only complete `portfolio-valuation-v1` points; instrument weights come from valued positions, sector weights remain empty until verified sector evidence exists, and allocation deviations come from the valuation result. Critical drawdown or prohibited activity suspends simulated allocation changes; elevated drawdown or concentration suspends new BUY_CANDIDATE promotion. Active persisted events also drive suspension after a restart.
- Connected a Risk Management desktop page that evaluates the current ledger valuation off the UI thread, lists unresolved events with observed value, threshold and severity, and records explicit reviews. Wired through bootstrap, `main.py` and the main-window navigation (nine areas).

### Deterministic screening and evidence-linked recommendations

- Added `screening-deterministic-v1` as a framework-independent domain engine. `ScreeningInput` carries only explicit evidence: verified-fundamental metrics, price age/quality, dividend references, portfolio drawdown and evidence items.
- Transparent actions (`BUY_CANDIDATE`, `HOLD`, `WATCH`, `AVOID`, `INSUFFICIENT_DATA`), machine-readable risk flags, deterministically ordered evidence IDs, invalidation conditions and a confidence fraction that measures evidence quality/completeness, never profit probability.
- Hard blocks: missing fundamental inputs, unusable denominators, unverified or stale price evidence, and elevated/critical drawdown prevent `BUY_CANDIDATE`. Missing inputs remain `None`; no zero or fabricated value enters a score. Critical drawdown, or negative earnings with excessive leverage, produces `AVOID`.
- Added Alembic migration `0007_recommendations` with an append-only audit table. `RecommendationService.evaluate` runs the engine and persists the result; `recent` and `get` reconstruct stored recommendations with their evidence and diagnostics.
- Added a Research Center desktop tab that lists stored recommendations and exposes explanation, evidence, risk flags and invalidation conditions. Generating a recommendation from assembled evidence remains an application-service operation.

### Dividend event persistence, calendar and analytics connection

- Added `dividend-event-v1` ingestion through the frozen, extra-forbid `DividendEventContract` (Pydantic v2) with explicit source, acquisition/announcement timestamps, gross per-share amount, currency, ex/payment dates, lifecycle status, quality state, original value, unit and transformation version. Cash types require an amount; `STOCK`/`RIGHTS` cannot carry one; naive timestamps and invalid currencies/periods are rejected.
- Added Alembic migration `0006_dividend_events` with an append-only `dividend_events` table, an append-only `dividend_review_events` audit ledger, foreign keys to the instrument master and source registry, uniqueness on `(source_id, event_key)`, indexes for instrument/ex-date and status lookups, and SQLite triggers blocking updates and deletes.
- `DividendEventService` atomically records events with default `UNVERIFIED` quality, creates/reuses a deny-by-default `MANUAL` source (no automated access or redistribution), rejects duplicate keys and unknown instruments, and validates all review gates before appending a decision.
- Evidence-backed review archives a user-selected document under `Documents/DividendReviewEvidence`, copies with a bounded chunk loop, computes SHA-256, and appends an immutable review. Promotion requires a raw `UNVERIFIED` event, a `VERIFIED` instrument identity, an allowed source policy, a non-estimate/non-simulated/non-cancelled status, and complete reviewer/evidence/notes. There is no automatic or AI promotion path.
- `calendar()` returns ex-dates and payment dates with explicit `is_confirmed_cash` and `is_estimate` labels; announced or unverified items are never presented as confirmed receipts. `analytics()` maps only effectively `VERIFIED`, observed, cash events into `dividend-analytics-v1`, returning labelled trailing/forward yields, net amount only when withholding is known, annual consistency, and `None` for missing inputs.
- Connected the Dividend Center desktop tab to these services with event, calendar, analytics and evidence-review views. All displayed values are read from local storage or calculated from verified events; long-running work runs on Qt worker threads.

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

## Risk-control to screening connection (this session, 2026-11-23)

- Added `RiskControlEvidence` to the screening domain and `RISK_REVIEW_REQUIRED` as a blocking flag. An explicit caller drawdown still takes precedence; persisted drawdown is used only as a fallback, and an unknown drawdown is never zero.
- `RiskMonitoringService.screening_controls()` derives buy-suspension, criticality, drawdown and active event IDs from append-only risk events and the complete valuation series. `ScreeningEvaluationService` consumes it when the risk service is configured; bootstrap wires it, so every desktop evaluation is gated.
- The Research Center displays active risk-review state and evidence-linked reasons. Screening methodology bumped to `screening-deterministic-v2` because recommendation outcomes can change.
- Verified on Windows 11 x64 / Python 3.13: 253 unit/integration tests and 14 UI tests pass; Ruff lint/format and Mypy strict pass. Full offscreen Qt suite still aborts intermittently on this host; native `windows` platform passes. See TEST_REPORT.md.

## Local verification (this session, 2026-11-23)

Environment: Linux aarch64, Python 3.14, PySide6 6.12, SQLAlchemy 2.1, Alembic 1.20, pytest 9.2, Ruff, Mypy.

| Check | Result |
|---|---|
| Ruff lint | Passed (195 files) |
| Ruff format check | Passed (195 files) |
| Mypy strict | Passed (76 source files) |
| Unit + integration pytest | **246 passed** (219 baseline + 19 risk engine + 8 risk service) |
| Targeted UI pytest (`test_risk_page.py` + `test_main_window.py`) | **5 passed** |
| Full UI suite | Environment-unreliable on aarch64/offscreen: one run had 13 passed / 1 pre-existing failure; later runs crashed inside `pytestqt.plugin::_process_events`. Crash reproduced on a clean worktree at `753308b`, so it is not a regression from the risk slice. No assertion was weakened to hide it. |
| Clean-start launch (fresh data directory, offscreen Qt) | Stayed alive; SQLite, WAL/SHM, logs and all 13 tables at migration `0007_recommendations` created |
| Full Qt suite | Timing-unreliable on this aarch64/offscreen runtime; see TEST_REPORT.md |

The local checkpoint includes the new dividend event slice: 7 integration tests, 12 contract unit tests, and a Dividend Center Qt rendering test.

## Verified CI (historical, prior session)

Application-code commit `b7ebce23511dcf6a48f919b22f03cd62ffd6e456` completed successfully on Windows and Ubuntu using Python 3.12. See [push CI 44909356690](https://github.com/RidTheWann/RFinance/actions/runs/44909356690) and [PR CI 44909361649](https://github.com/RidTheWann/RFinance/actions/runs/44909361649).

| Check | Windows | Ubuntu |
|---|---:|---:|
| Dependency installation | Passed | Passed |
| Ruff lint | Passed | Passed |
| Ruff format | Passed; 94 files already formatted | Passed; 94 files already formatted |
| Mypy | Passed; 53 source files | Passed; 53 source files |
| pytest | **141 passed** | **141 passed** |

The tested head includes persisted-observation portfolio valuation, append-only price-review integration, source and instrument eligibility, explicit latest-price conflict rejection, historical-series eligibility and loading, the Technical Analysis Qt workflow, and indicator warm-up resets across large date gaps. That PR was subsequently closed without merging; its work was preserved locally and development continued from it.

## Historical local developer checkpoint (previous Termux session)

- Branch `foundation/bootstrap-core`; Python 3.14 editable install with `--no-deps`.
- Ruff 0.17.6 lint and format checks: passed on `src` and `tests`.
- Mypy: no issues in `src/rfinance/analysis/dividend/analytics.py`; the six remaining diagnostics are pre-existing PySide6-stub artifacts because PySide6 is not installable on this Termux/Android runtime.
- pytest: 127 passed (62 pre-existing non-UI tests plus 27 dividend, 17 eligibility, 14 observation-review and 7 valuation tests). UI tests were not run locally because PySide6 is unavailable.

## Not implemented yet

- Official/licensed historical market-data entitlement, automated Indonesian market-data adapters, and source-policy approvals for any production feed.
- Full financial statement persistence, broader valuation metrics, and the UI workflow that assembles all local evidence into a screening evaluation. The deterministic engine, persistence and inspection view exist, but evaluation is currently an application-service operation. The dividend calculation layer has no automated provider feed.
- Corporate actions, allocation execution/rebalancing, verified sector mapping and risk review automation remain incomplete. Deterministic drawdown/concentration controls with append-only events and explicit reviews are implemented; they do not constitute loss limits. Portfolio market valuation depends on lawfully obtained, manually reviewable data.
- Native Ollama integration, document analysis, automation scheduler, PDF and broader reporting beyond the simulated-ledger CSV export, destructive in-place restore, and Windows production installer. Per ADR 0004, the AI role is currently fulfilled by the coding assistant.
- Clean-install, upgrade, offline, security, and production packaging acceptance.

## Next engineering objectives

1. ~~Add allocation-target execution and a rebalancing workflow using verified instruments, without fabricating investable products.~~ **Implemented this session** as `allocation-plan-v1` gap planning with explicit unfilled targets and risk-event blocking; automatic order execution and persistence of category evidence remain out of scope.
2. ~~Connect active risk events to screening so a required review blocks BUY_CANDIDATE promotion end-to-end from the desktop.~~ **Implemented this session** via `RiskControlEvidence`, persisted suspension projection, bootstrap wiring and a Research Center banner.
3. Add explicit instrument and observation sampling-frequency/adjustment metadata, then define any compliant historical data ingestion path without inferring split/dividend adjustment.
4. Extend fundamental statements and valuation metrics with documented formula versions and independent tests.
5. Post the reinvestment and money-market legs of confirmed dividends into verified instruments once such instruments exist, instead of leaving them as cash targets.
6. Continue automation, reporting, backup/restore, reproducible lockfile, and Windows packaging in tested vertical slices.
