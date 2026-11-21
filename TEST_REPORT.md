# Test Report

Last updated: 2026-11-21

## Current status

**No interactive local execution.** There is no mounted checkout or Python project runtime in this execution session. The latest GitHub Actions run must be inspected for the current branch head before calling any check successful.

## Test coverage added

- Explicit/environment application data path selection and directory creation.
- Alembic initial schema creation and database reopen.
- Decimal margin, ROE, and debt-to-equity edge behavior.
- Market-observation timezone, OHLC, currency, and quality-state validation.
- PySide6 main-window navigation smoke test.
- Portfolio ledger cash/position reconciliation, weighted-average cost, lot-size validation, oversell and overspend rejection, duplicate simulated-dividend rejection, currency/sequence/idempotency, and Hypothesis-generated buy/sell round trips.

## Automated CI

The foundation branch defines Windows and Ubuntu jobs using Python 3.12. Each job installs the project and development extras, then runs Ruff lint, Ruff format check, Mypy, and pytest. Linux CI installs Qt runtime libraries needed for offscreen UI tests.

## Outstanding validation

- Current-head Windows and Ubuntu CI completion.
- Dependency lockfile generated and verified with Windows Python 3.12.
- Migration downgrade/upgrade and corruption recovery.
- SQL ledger persistence, atomicity, idempotency, and reopen/replay integration.
- Backup/restore.
- Security/dependency audit.
- Full UI workflow and clean-install tests.
