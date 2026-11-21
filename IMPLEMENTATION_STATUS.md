# Implementation Status

Last verified against the repository: 2026-11-21

## Repository state

- Repository: RidTheWann/RFinance
- Default branch: main
- Initial README commit: c3d556a34852922c147d136e49fdc05526b178e5
- Working branch: foundation/bootstrap-core
- Latest recorded development commit at this status update: 930226d6939b5ad8ab243aa8ab25d11eaabc7ff0
- Active foundation PR: https://github.com/RidTheWann/RFinance/pull/1
- The execution environment has no mounted checkout; repository operations are performed through GitHub APIs and validation through GitHub Actions.
- The remote was verified empty before bootstrap. The first commit established the repository; all engineering changes are on the dedicated branch and have not been merged into main.

## Implemented in the foundation branch

### Application foundation
- Canonical repository-wide AGENTS.md and Claude Code CLAUDE.md.
- Python package metadata, Ruff, Mypy, pytest, pytest-qt, Hypothesis, Bandit, pip-audit configuration, and Windows scripts.
- Windows per-user persistent data paths, environment override, rotating logs, SQLite, and Alembic migrations.
- PySide6 desktop shell with Overview, Portfolio Simulator, and Settings navigation.
- Application composition root wires persistence, portfolio ledger, and market CSV importer.

### Deterministic financial and portfolio logic
- Typed instrument and market-observation contracts with explicit currency, timestamps, quality, and OHLC validation.
- Decimal primitives for profit margins, ROE, and debt-to-equity.
- Immutable portfolio ledger with explicit capital, buy, sell, cash withdrawal, and simulated-dividend events.
- Weighted-average cost, realized P/L, cash and position invariants, unique event IDs, and sequence order.
- Trade events require a provenance-bearing VerifiedLotSize; missing or unverified lot metadata blocks trading.
- Append-only SQLite event storage with exact fixed-point Decimal text persistence, UTC timestamps, uniqueness constraints, and update/delete protection triggers.
- First-run capital setup is connected to the UI and ledger. Rp5,000,000 is an editable suggested value; only explicit user action records opening cash. No assets or recurring contributions are generated automatically.
- Portfolio UI reads balances from ledger replay; the 50/20/30 allocation is shown as a target, not actual holdings.

### Data provenance and local import
- Source registry with access-method and policy-status fields. User-import sources are unreviewed by default and database constraints prohibit automated access or redistribution permissions for them.
- Import-batch, source, market-observation, and row-issue persistence through Alembic migration.
- Strict local CSV parser for canonical instrument ID, timezone-aware observation timestamp, currency, close, and optional OHLC/volume columns.
- Row-level validation and rejection diagnostics; duplicate instrument/time observations are rejected rather than overwritten.
- User-selected CSV files are archived under local Documents/MarketImports, hashed with SHA-256, and linked to source, import batch, acquisition timestamp, raw input cells, and transformation version.
- Imported market observations always start as UNVERIFIED; successful parsing is not evidence of data truth, source licensing, instrument existence, or corporate-action adjustment.
- File size and row-count limits, archive path containment checks, and a Qt worker thread keep import processing out of the UI thread.
- Overview displays recent import history, row counts, trust status, and provenance details (batch, SHA-256, and archived path in tooltips).
- An Indonesia data-access review records why IDX scraping/crawling is not enabled and why official/licensed feed terms must be verified before an automated adapter is introduced.

## Verified CI checkpoints

- Commit e6a024ece766d741567624cd42fcd5dbe6cc4df2: Windows and Ubuntu, Python 3.12, both completed successfully. Ruff lint, Ruff format, Mypy, and pytest all passed; 42 tests passed on each platform.
- Latest import-history UI/test head 930226d6939b5ad8ab243aa8ab25d11eaabc7ff0: Ubuntu Ruff lint, format, and Mypy have passed; full Ubuntu test suite passed on the latest run. Windows and the complete current-head matrix are still running at this status update. Do not infer final current-head success from the earlier checkpoint.

## Not implemented yet

- Generated, resolver-verified dependency lockfile.
- Production instrument master/source registry verification workflow, verified historical market-feed entitlement, or an automated Indonesian market-data adapter.
- Explicit user-led review workflow that can promote an imported observation from UNVERIFIED to a reviewed quality state with immutable audit evidence.
- Full fundamental statements, valuation metrics, technical indicators, dividend intelligence, screening, and evidence-linked recommendations.
- Portfolio trade-entry UI, market valuation, unrealized P/L, corporate actions, rebalancing, allocation implementation, and full risk controls.
- Ollama integration, document analysis, automation scheduler, reporting, verified backup/restore, and Windows production installer.
- Clean-install, upgrade, offline, security, and production packaging acceptance.

## Next engineering objectives

1. Finish and inspect current-head Windows and Ubuntu CI for the import-history increment.
2. Expand the data-quality review model and instrument master without allowing imports or AI to self-certify as VERIFIED.
3. Implement the next deterministic analysis vertical slice with documented formulas, warm-up/missing-data rules, and independent tests.
4. Connect verified inputs to evidence-linked screening only after data eligibility and freshness gates exist.
5. Continue portfolio, dividend, automation, backup/restore, and Windows packaging in tested vertical slices.
