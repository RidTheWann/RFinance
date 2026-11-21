# Changelog

All notable changes to RFinance are documented here.

## Unreleased

- Established repository engineering policy and initial Python package foundation.
- Added local application paths, rotating logs, SQLite, and Alembic migrations.
- Added a minimal PySide6 desktop shell with Overview, Portfolio, and Settings views.
- Added provider-independent instrument/market-observation contracts and Decimal fundamental metric primitives.
- Added immutable portfolio event-ledger replay with weighted-average cost, verified lot-size evidence, cash and position invariants, and property-based tests.
- Added append-only SQLite ledger persistence with exact fixed-point Decimal storage, application-service validation, and database triggers against UPDATE/DELETE.
- Added Windows/Ubuntu CI and architecture, methodology, portfolio accounting, risk, security, privacy, data-source, and compatibility documentation.
