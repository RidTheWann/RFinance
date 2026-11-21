# Test Report

Last updated: 2026-11-21

## Fully verified CI checkpoint

Commit e6a024ece766d741567624cd42fcd5dbe6cc4df2 completed on both Windows and Ubuntu with Python 3.12:

| Check | Windows | Ubuntu |
|---|---:|---:|
| Dependency installation | Passed | Passed |
| Ruff lint | Passed | Passed |
| Ruff format check | Passed | Passed |
| Mypy | Passed | Passed |
| pytest | 42 passed | 42 passed |

This checkpoint includes the repository foundation, local portfolio ledger and persistence, CSV parser/provenance pipeline, and Windows archive path containment hardening.

## Latest development head

Latest recorded head for this report: 930226d6939b5ad8ab243aa8ab25d11eaabc7ff0.

The later increment adds a recent-import-history query and a table in the Overview page, with batch ID, SHA-256, source label, and archive path available in row tooltips. Current-head Ubuntu Ruff, format, Mypy, and pytest results are passing; the full Windows matrix has not yet been confirmed completed at this report timestamp.

## Coverage

- Local application path resolution and directory creation.
- SQLite schema migrations and database reopen.
- Decimal margin, ROE, and debt/equity edge behavior.
- Market observation timestamp, OHLC, currency, and data-quality validation.
- Portfolio ledger reconciliation, weighted-average cost, fees/taxes, lot-size evidence, cash/position limits, duplicate dividend prevention, sequence and event ID integrity.
- Property-based buy/sell replay reconciliation.
- Exact Decimal persistence through SQLite close/reopen.
- Atomic rejection of invalid ledger events and append-only database triggers.
- Explicit one-time simulation initialization and invalid-capital rejection.
- CSV schema/timezone/numeric validation, row-level rejection, duplicate handling, archive SHA-256, source provenance, unverified quality state, user-import policy constraints, and file-size/type limits.
- Asynchronous UI import and recent import history display, including batch/source/hash tooltip information.

## Outstanding validation

- Current-head Windows CI completion for import-history UI and tests.
- Dependency lockfile and reproducible locked installation.
- Import-history persistence/reopen workflow in the current CI head.
- Migration downgrade/upgrade and corruption recovery.
- Backup/restore and data integrity recovery.
- Security/dependency audit and clean Windows environment installation.
- Source verification/instrument-master tests, financial indicator formula tests, full portfolio workflows, and production packaging.
