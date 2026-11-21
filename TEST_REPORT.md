# Test Report

Last updated: 2026-11-21

## Current status

**Not executed in this environment.** There is no mounted local checkout or Python runtime attached to the current execution session. The tests below are committed but have not yet been observed passing.

## Test coverage added

- Explicit/environment application data path selection and directory creation.
- Alembic initial schema creation and database reopen.
- Decimal margin, ROE, and debt-to-equity edge behavior.
- Market-observation timezone, OHLC, currency, and quality-state validation.
- PySide6 main-window navigation smoke test.

## Automated CI

The foundation branch defines Windows and Ubuntu jobs using Python 3.12. Each job installs the project and development extras, then runs Ruff lint, Ruff format check, Mypy, and pytest. Results must be inspected before describing this branch as validated.

## Outstanding validation

- Dependency resolution and lockfile generation.
- Full Windows test and launch.
- Migration downgrade/upgrade and corruption recovery.
- Backup/restore.
- Security/dependency audit.
- UI interaction and clean-install tests.
