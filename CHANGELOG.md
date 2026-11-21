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
