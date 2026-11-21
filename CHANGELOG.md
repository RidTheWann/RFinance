# Changelog

All notable changes to RFinance are documented here.

## Unreleased

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
- Added integration and Qt tests for persisted valuation, eligibility rejection, source conflicts, and the desktop refresh workflow; CI validation is pending for this change set.
