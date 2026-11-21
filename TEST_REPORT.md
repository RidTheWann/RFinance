# Test Report

Last updated: 2026-11-21

## Last fully verified CI checkpoint

Commit 38bd85bf6280f9fdde53a701cc3770189d2fab7a:
- Windows / Python 3.12: Ruff lint passed, 49 files formatted, Mypy passed (26 source files), pytest **24 passed**.
- Ubuntu / Python 3.12: Ruff lint passed, 49 files formatted, Mypy passed (26 source files), pytest **24 passed**.

The current SQLite persistence increment is newer than that checkpoint and awaits its own Windows and Ubuntu CI results.

## Test coverage added

- Explicit/environment application data path selection and directory creation.
- Alembic migration creation and database reopen.
- Decimal margin, ROE, and debt-to-equity edge behavior.
- Market-observation timezone, OHLC, currency, and quality-state validation.
- PySide6 main-window navigation smoke test.
- Portfolio ledger cash/position reconciliation, weighted-average cost, verified lot-size enforcement, oversell and overspend rejection, duplicate simulated-dividend rejection, currency/sequence checks, and Hypothesis-generated buy/sell round trips.
- SQLite portfolio-ledger migration, exact Decimal persistence through database reopen, atomic rejection of invalid events, sequence/idempotency behavior, and append-only update/delete triggers.

## Outstanding validation

- Current-head Windows and Ubuntu CI completion for the persistence increment.
- Dependency lockfile generated and verified with Windows Python 3.12.
- Migration downgrade/upgrade and corruption recovery.
- Backup/restore.
- Security/dependency audit.
- Full first-run portfolio and UI workflow tests.
- Clean-install and production packaging tests.
