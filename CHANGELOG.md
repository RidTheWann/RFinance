# Changelog

All notable changes to RFinance are documented here.

## Unreleased

- Corrected stale status documentation against verified source and Git state. `README.md`'s progress table, `ROADMAP.md`'s checkpoint, `TEST_REPORT.md`'s known boundaries and `IMPLEMENTATION_STATUS.md`'s repository/CI sections described features that are already implemented (API-key AI research, automation jobs, CSV/PDF reporting, confirmed dividend receipt posting, backup/restore, Windows build) and cited superseded commit hashes. README progress is recomputed to 86.2% and the milestone table now matches the implemented surface.

- Hardened the runtime path: removed 22 `assert`-based checks in ledger replay, risk controls, technical indicators, dividend analytics, automation retry, trading lot lookup and Qt result handling. Each is now an explicit `LedgerValidationError`, `TypeError`, `RuntimeError` or a guarded skip, so behaviour no longer changes under `python -O`. `bandit -r src` now reports zero findings; the sole prior medium (`B310`) was an allowlisted-endpoint false positive, documented inline with `# nosec`.

- Added the missing PyInstaller, altgraph and pefile entries to `docs/THIRD_PARTY_NOTICES.md` (PyInstaller ships a bootloader exception permitting use to distribute non-free programs while RFinance stays GPL-3.0-only).

- CI now runs `bandit -q -r src` and `pip-audit -r requirements.lock`, sets a 30-minute job timeout so a stalled runner fails fast instead of consuming the six-hour limit, installs `xvfb` alongside the Linux Qt libraries, and cancels superseded runs for the same ref. These were documented project gates that CI did not enforce.

- Fixed `scripts\setup_windows.ps1` failing on machines without Python 3.12: it now auto-detects a supported 3.12–3.15 interpreter, supports `-Python` override and `-DryRun`, and documents the PowerShell execution-policy workaround. A packaging test pins the supported range so the script cannot regress to a single hard-coded version, and `README.md` points at the setup script instead of literal `py -3.12` commands.

- Replaced the planned Ollama integration with optional API-key AI research (ADR 0005). A single verified OpenAI Chat Completions endpoint is allowlisted; the key is read only from `RFINANCE_AI_API_KEY` and never stored or logged. Structured output is validated against an application-owned schema and displayed as untrusted research aid only. Documented in `docs/AI_RESEARCH.md`.

- Added a reproducible Windows folder build: `installer/windows/rfinance.spec`, `scripts\build_windows.ps1`, pinned PyInstaller in the dev extra and regenerated `requirements.lock`. The frozen executable was smoke-tested with a fresh data directory: it stayed alive, created SQLite at Alembic `0012_instrument_category` with 22 tables, and wrote no startup errors. Documented in `docs/INSTALLATION.md`.

- Fixed a reporting-basis defect in the persisted-fundamentals path: `verified_inputs` keyed candidates only by metric name, so a newer quarterly figure could replace an annual one and feed a three-month denominator into an annual formula. It now keys by metric name and `reporting_basis`, honours an explicit basis filter, and `ScreeningEvaluationService.evaluate` rejects persisted fundamentals when no basis is declared. The Research Center gained a Reporting basis selector, and `test_financial_statements.py`/`test_screening_evaluation.py`/`test_research_page.py` cover the separation and the rejection.

- Added `instrument-metadata-evidence-v1`: an append-only `instrument_metadata_events` table (migration `0013_instrument_metadata_evidence`) recording explicit sampling-frequency and corporate-action adjustment claims per instrument/source pair, each backed by an archived evidence file SHA-256 and gated on an active VERIFIED instrument. Until evidence is recorded, `historical-price-series-v1` reports `UNKNOWN_AS_SUPPLIED` for both values instead of assuming an adjusted or resampled series; a verified decision replaces them and the Technical Analysis page displays both. Documented in `docs/DATA_ELIGIBILITY.md`.

- Added `instrument-category-v1`: append-only, evidence-backed instrument category and lot-size decisions (migration `0012_instrument_category`), projected into `allocation-plan-v1` as verified investables. A connected form in the Allocation plan panel archives evidence and records VERIFIED/REJECTED decisions; documented in `docs/INSTRUMENT_CATEGORY.md`.

- Added `portfolio-pdf-v1` reporting: `PortfolioReportService` assembles ledger, valuation, risk-control and recommendation data into an explicit report; `QPdfWriter` renders it to PDF with no new dependency. A connected Portfolio Simulator button exports the file, and the contract is documented in `docs/REPORTING.md`.

- Added `automation-jobs-v1`: code-defined local job registry, append-only `automation_jobs`/`automation_runs` tables (migration `0011_automation`), deterministic run IDs, retry policy, and a connected Automation Center with manual run execution and run history. Documented in `docs/AUTOMATION.md`.

- Added `sqlite-backup-v1`: consistent online SQLite backups with SHA-256 manifests, read-only integrity/schema verification, and non-destructive restore into a new folder. Connected worker-backed controls in Settings and documented in `docs/BACKUP_RESTORE.md`.
- Recorded ADR 0004: for this phase the coding assistant fulfils the optional AI role; no Ollama runtime, model download or AI-owned state mutation is introduced. Deterministic engines remain authoritative.

- Added `allocation-plan-v1`: deterministic target-versus-current gap planning from persisted valuations. Positive gaps remain `UNFILLED_TARGET` unless an evidence-backed verified instrument and eligible price exist; overweight categories require review; active risk events block investable lines. Connected to a worker-backed Portfolio Simulator view and documented in `docs/ALLOCATION_PLANNING.md`.
- Stabilised the three worker-thread Qt UI tests with a short post-completion settle wait. All 16 UI tests now pass consistently under both offscreen and native Windows platforms; no assertion was weakened.

- Added `ledger-csv-v1` reporting: a connected Portfolio Simulator button exports the authoritative simulated ledger to CSV with `SIMULATED` labels, explicit methodology version, empty cells for missing values, currency/sequence validation and spreadsheet-formula neutralisation for user-supplied text. Documented in `docs/REPORTING.md`.

- Connected persisted risk controls to deterministic screening end-to-end. `RiskMonitoringService.screening_controls()` projects active risk events and the drawdown derived from complete stored valuations into `RiskControlEvidence`; `ScreeningEvaluationService` supplies it on every desktop evaluation. A buy-suspending rule raises `RISK_REVIEW_REQUIRED` and cites `risk:<event_id>`; a critical event produces `AVOID`; an explicit review lifts the block on the next evaluation. The Research Center shows the active review state. Screening methodology is now `screening-deterministic-v2`.
- Fixed a racy Qt UI test that asserted worker cleanup before waiting for it; two worker-thread UI files still abort intermittently on this Windows/PySide6 6.12 host under both offscreen and native platforms. See TEST_REPORT.md.
- Added a generated `requirements.lock` from the verified Windows/Python 3.13 development environment and `scripts\regenerate_lock.ps1` to reproduce it.

- Added `risk-controls-v1`: deterministic drawdown, concentration, allocation-deviation, review-cadence and prohibited-activity review triggers with explicit thresholds and no coercion of missing valuations to zero.
- Added append-only `risk_events`, explicit one-per-event `risk_reviews` and `portfolio_valuation_history` (migration `0010_risk_events`), with deterministic event IDs, idempotent same-day evaluation and explicit review required to lift a suspension.
- Connected a Risk Management desktop page to valuation and risk services; nine navigation areas now. README weighted progress updated to 65%.
- Added evidence-gated simulated trade entry: verified lot sizes are derived from instrument review evidence, and BUY/SELL ledger events are appended only when lot, cash and position invariants hold. A connected Portfolio Simulator form shows the verified rule and labels every trade as simulated. README progress updated to 64%.
- Added reviewed financial statement persistence (`0009_financial_metrics`) with append-only metrics and evidence-backed review ledger. Screening can now use verified local filing values instead of operator-supplied inputs, with an explicit Research Center selector. Added a weighted, evidence-based "Progress Project" table to the README.
- Added `screening-evaluation-v1`: a guided workflow that assembles instrument identity, review-adjusted price, verified dividend evidence and operator-supplied fundamentals into the deterministic recommendation engine, with a Research Center evaluation form. Fundamental inputs are explicitly labelled as operator-supplied, not verified filings.
- Added `dividend-receipt-v1`: a confirmed net dividend can be posted into the simulated ledger only from a verified, observed cash event, split exactly 50/30/20, recorded in an append-only audit table, and protected against duplicates in the service, replay and database. The withdrawal leg leaves the simulation so cash reconciles; no forecast or simulated amount can be posted.
- Added `CONFIRMED_DIVIDEND` ledger event type and migration `0008_confirmed_dividend_receipts` (ledger table rebuild plus `dividend_receipts`), and a connected Dividend Center "Confirmed receipt" tab.
- Installed the MIT-licensed Superpowers process skills as an OpenCode V2 plugin and copied the MIT-licensed Matt Pocock engineering/productivity skill pack into `.opencode/skills/`; documented precedence (`AGENTS.md` canonical) and harness reload behaviour in `docs/DEVELOPER_TOOLING.md`.
- Fixed a Qt worker-thread race in all four worker-backed pages: `is_busy` now remains true until the thread's queued `finished` cleanup clears `_thread`, so a second submit cannot be silently ignored in the gap between thread stop and cleanup. Added a regression test and raised UI wait timeouts to 30s for slower CI runners.
- Added verified developer tooling: `.vscode/extensions.json` (official Qt Python pack, Python/Pylance, Ruff, Mypy, TOML, SQLite, Error Lens, GitLens, TODO Tree, pytest explorers, Markdown), four project skills under `.opencode/skills/` (`rfinance-invariants`, `rfinance-finance-qt`, `rfinance-quality`, `rfinance-docs`), an inert MCP config template, and `docs/DEVELOPER_TOOLING.md` with verified setup commands and security boundaries. Context7 MCP was installed globally and verified connected.
- Rebuilt the commit history at the owner's request so the GPLv3 `LICENSE` and per-file SPDX headers exist from the root commit (`beb02dae1acd2dfa7c2e5f87b748ba64a7a877b4`) onward; closed the separate license PR, removed stale branches, and force-pushed `main` with `--force-with-lease`. CI on the final tree passed on Windows and Ubuntu (206 tests per OS).
- Selected `GPL-3.0-only` as the project license: added verbatim GPLv3 `LICENSE`, PEP 639 metadata (`license` + `license-files`, setuptools >= 77), SPDX headers on every source file, ADR 0003, third-party notices, and regression tests for license metadata. PySide6's `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only` licensing is compatible with the selected GPLv3 license; Windows binary distribution obligations are recorded in the ADR.
- Established repository engineering policy, Python package metadata, CI, and Windows development scripts.
- Added Windows per-user persistent data paths, rotating logs, SQLite, and Alembic migrations.
- Added a PySide6 desktop shell with Overview, Portfolio Simulator, and Settings.
- Added provider-independent instrument and market-observation contracts with explicit data-quality states.
- Added Decimal fundamental metric primitives for margin, ROE, and debt-to-equity.
- Added an immutable simulated portfolio ledger with weighted-average cost, exact Decimal persistence, cash/position/lot-size invariants, duplicate simulated-dividend protection, and property-based tests.
- Connected explicit first-run simulation capital setup to the desktop and local ledger; Rp5,000,000 remains an editable suggestion and is never booked automatically.
- Added source registry, import batches, market-observation provenance, row-level import diagnostics, append-only database protections, and a strict user-supplied CSV path.
- Added local CSV archive and SHA-256, UNVERIFIED default status, duplicate rejection, archive-path containment, and off-thread desktop import workflow.
- Added Overview import history with recent source/file/row-count/trust details and provenance tooltips.
- Documented Indonesia financial-data access restrictions; no IDX scraper or automated data provider is enabled.
- Added an instrument master with UNVERIFIED placeholders, a foreign-key link from market observations, and migration backfill for existing identifiers.
- Added an explicit instrument-review service with VERIFIED/REJECTED decisions, complete-contract checks, SHA-256 evidence metadata, and append-only review audit events.
- Added Decimal technical indicators: SMA, EMA, Wilder RSI, MACD, Bollinger Bands, True Range, ATR, rolling volatility, drawdown, momentum, and benchmark-relative strength.
- Documented technical formulas, units, warm-up and missing-data semantics, and input-quality limitations.
- Hardened local CSV ingestion with explicit flush ordering for foreign-key parent rows and one placeholder per new instrument per import batch.
- Expanded cross-platform CI validation to 65 passing pytest tests on Windows and Ubuntu with Ruff and Mypy passing.
- Added a desktop instrument-review queue with evidence-file selection, SHA-256 digest computation, reviewer notes, and review history on a worker thread.
- Added `dividend-analytics-v1`: Decimal-only trailing/forward yield, net-dividend, payout/coverage, growth/CAGR, consistency, simulated cash projection, and confirmed-receipt allocation, with documented formulas and 27 new tests.
- Added `eligibility-observation-v1`: dependency-free observation eligibility gates for quality, identity, source policy, currency, look-ahead and freshness, with 17 new tests.
- Added an append-only observation-review ledger and service (`0005_observation_review`) requiring explicit evidence, a verified instrument, and an eligible source before a price can be verified; 14 new integration tests.
- Added `portfolio-valuation-v1`: ledger-based market value, unrealized P/L, explicit unvalued positions, and allocation-versus-target diagnostics using only eligible prices, with 7 new tests.
- Added a dedicated Observation Review desktop workflow with an evidence-backed VERIFIED/REJECTED decision path, local evidence archiving, SHA-256 verification, append-only history, and off-thread file/database work.
- Connected successful CSV import completion to refresh both instrument and observation review queues immediately, without requiring an application restart.
- Fixed outdated UI test wiring/navigation expectations and verified the complete 131-test suite on Windows and Ubuntu with Ruff, format, and Mypy checks passing.
- Connected persisted observations and review-adjusted quality to portfolio valuation through the full instrument, source, currency, freshness, and data-quality eligibility gates.
- Added safe handling for conflicting latest prices, evidence-linked valuation diagnostics, and a background Portfolio Simulator valuation view with partial-total disclosure.
- Added integration and Qt tests for persisted valuation, eligibility rejection, source conflicts, and the desktop refresh workflow; **141 tests passed on Windows and Ubuntu**, with Ruff lint/format and Mypy passing.

- Added a separate `historical-price-eligibility-v1` gate so old, verified historical bars are not incorrectly rejected by current-quote staleness rules; future bars, unverified observations/instruments, currency mismatches, and blocked/restricted sources remain ineligible.
- Connected persisted single-instrument/single-source historical bars to Decimal technical reports and the Technical Analysis desktop page, with asynchronous loading/calculation and visible provenance/rejection diagnostics.
- Added gap sentinels so rolling indicator windows restart after configured large calendar gaps; no source blending, resampling, interpolation, frequency inference, or automatic corporate-action adjustment occurs.
- Added 15 historical-eligibility, persisted-series, technical-analysis and Qt workflow tests. Full Windows/Ubuntu Python 3.12 CI passed at `eaef966d4d542d44275c4cab91e025431b63d18d`: 156 tests passed on each OS.
- Preserved the closed PR #1 implementation locally (172 commits) and continued development from its head without discarding prior work.
- Added migration `0006_dividend_events` with append-only dividend events and evidence-backed review audit ledger, foreign keys, uniqueness, indexes and update/delete triggers.
- Added the frozen `DividendEventContract` with explicit provenance, lifecycle status, currency, unit and quality validation, rejecting naive timestamps and invalid cash/non-cash amounts.
- Added `DividendEventService` with atomic ingest, deny-by-default MANUAL source creation, evidence file archiving and SHA-256, explicit promotion gates, labelled calendar, and verified-event analytics connected to `dividend-analytics-v1`.
- Connected a Dividend Center desktop tab with Events, Calendar, Analytics and Evidence review views; all values come from local storage or deterministic calculations.
- Verified locally on Ubuntu aarch64 / Python 3.14: Ruff lint and format, Mypy strict, 169 unit/integration tests and 4 targeted Qt tests pass.
- Expanded `metrics.py` from three primitives to 17 reproducible fundamental metrics with `fundamental-metrics-v1`, explicit input/formula/status records, unusable-denominator handling, and a financial-sector applicability gate that excludes industrial leverage/cash-flow metrics for banks.
- Added 10 fundamental unit/property tests; a test caught and fixed an argument-order defect in the earnings-quality computation.
- Added `screening-deterministic-v1`: evidence-linked deterministic recommendations with transparent actions, risk flags, evidence quality confidence (not profit probability), explicit invalidation conditions and hard BUY_CANDIDATE blocking for stale/unverified/incomplete evidence.
- Added migration `0007_recommendations` with an append-only audit table; `RecommendationService` evaluates candidates and persists results with evidence and risk diagnostics.
- Connected a Research Center desktop tab that lists stored recommendations and exposes their evidence, reasoning and invalidation conditions.
