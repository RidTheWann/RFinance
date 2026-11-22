# Changelog

All notable changes to RFinance are documented here.

## Unreleased

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
