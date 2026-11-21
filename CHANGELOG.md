# Changelog

All notable changes to RFinance are documented here.

## Unreleased

- Established repository engineering policy and initial Python package foundation.
- Added local application paths, rotating logs, SQLite, and Alembic migrations.
- Added a minimal PySide6 desktop shell with Overview, Portfolio, and Settings views.
- Added provider-independent instrument and market-observation contracts and Decimal fundamental metric primitives.
- Added immutable portfolio ledger replay with weighted-average cost, provenance-bearing verified lot-size evidence, cash/position invariants, and property-based tests.
- Added append-only SQLite ledger storage with exact fixed-point Decimal persistence, service validation, and database protections against UPDATE/DELETE.
- Added explicit first-run portfolio setup connected to the desktop UI and local ledger; the default capital is editable and is never booked automatically.
- Added an initial Indonesia data-access review. No IDX/OJK/KSEI scraper or automated adapter is enabled.
- Added Windows/Ubuntu CI and architecture, methodology, portfolio accounting, risk, security, privacy, data-source, and compatibility documentation.
