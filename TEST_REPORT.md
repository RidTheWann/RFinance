# Test Report

Last updated: 2026-11-21

## Last fully verified CI checkpoint

Commit 38bd85bf6280f9fdde53a701cc3770189d2fab7a:
- Windows / Python 3.12: Ruff lint passed, Ruff format check passed, Mypy passed (26 source files), pytest **24 passed**.
- Ubuntu / Python 3.12: Ruff lint passed, Ruff format check passed, Mypy passed (26 source files), pytest **24 passed**.

The newer SQLite persistence and first-run UI branch changes are not recorded as passing until the latest current-head GitHub Actions run has completed successfully on both runners.

## Test coverage added

- Explicit/environment application data path selection and directory creation.
- Alembic migrations and database reopen.
- Decimal margin, ROE, and debt-to-equity edge behavior.
- Market-observation timezone, OHLC, currency, and quality-state validation.
- PySide6 navigation and first-run portfolio setup workflow.
- Portfolio ledger cash/position reconciliation, weighted-average cost, verified lot-size evidence, oversell and overspend rejection, duplicate simulated-dividend rejection, currency/sequence checks, and Hypothesis-generated buy/sell round trips.
- SQLite portfolio-ledger migration, exact Decimal persistence through database reopen, atomic rejection of invalid events, sequence/idempotency behavior, and append-only update/delete triggers.
- Explicit initial-capital setup, one-time initialization, invalid/non-finite capital rejection, and absence of implicit monthly contributions.

## CI configuration

Python 3.12 is tested on Windows and Ubuntu. Both jobs run Ruff lint, Ruff format check, Mypy, and pytest. Linux installs Qt runtime libraries for offscreen PySide6 tests.

## Outstanding validation

- Current-head Windows and Ubuntu CI completion.
- Dependency lockfile generated and verified with Windows Python 3.12.
- Migration downgrade/upgrade and corruption recovery.
- Backup/restore.
- Security/dependency audit.
- Full source-provider contract tests and permitted import workflow.
- Full trade, valuation, risk, and portfolio reconciliation UI workflows.
- Clean-install and production packaging tests.
