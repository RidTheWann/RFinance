# Implementation Status

Last verified against the repository: 2026-11-21

## Repository state

- Repository: RidTheWann/RFinance
- Default branch: main
- Initial README commit: c3d556a34852922c147d136e49fdc05526b178e5
- Working branch: foundation/bootstrap-core
- Active foundation PR: https://github.com/RidTheWann/RFinance/pull/1
- Latest fully validated application-code commit: 930226d6939b5ad8ab243aa8ab25d11eaabc7ff0
- Development uses GitHub API edits and hosted GitHub Actions; no mounted local checkout or local Python runtime was available in the execution session.
- The remote was verified empty before bootstrap. All work remains on the dedicated foundation branch and has not been merged into main.

## Implemented in the foundation branch

### Application foundation
- Canonical repository-wide AGENTS.md and Claude Code CLAUDE.md.
- Python package metadata, Ruff, Mypy, pytest, pytest-qt, Hypothesis, Bandit, pip-audit configuration, Windows scripts, and Windows/Ubuntu CI.
- Windows per-user persistent data paths, environment override, rotating logs, SQLite, and Alembic migrations.
- PySide6 desktop shell with Overview, Portfolio Simulator, and Settings navigation.
- Application composition root wires persistence, portfolio ledger, and market CSV importer.

### Deterministic financial and portfolio logic
- Typed instrument and market-observation contracts with explicit currency, timestamps, quality, and OHLC validation.
- Decimal primitives for profit margins, ROE, and debt-to-equity.
- Immutable portfolio ledger with explicit capital, buy, sell, cash withdrawal, and simulated-dividend events.
- Weighted-average cost, realized P/L, cash and position invariants, unique event IDs, and strict event ordering.
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
- Overview displays recent import history, source labels, filenames, UTC timestamps, accepted/rejected counts, and trust status. Batch ID, SHA-256, and archive path are available in row tooltips.
- Indonesia data-access review documents why IDX scraping/crawling is not enabled and why official/licensed feed terms must be verified before an automated adapter is introduced.

## Verified CI

Commit 930226d6939b5ad8ab243aa8ab25d11eaabc7ff0 completed successfully on Windows and Ubuntu using Python 3.12.

| Check | Windows | Ubuntu |
|---|---:|---:|
| Dependency installation | Passed | Passed |
| Ruff lint | Passed | Passed |
| Ruff format | Passed; 63 files formatted | Passed; 63 files formatted |
| Mypy | Passed | Passed |
| pytest | 42 passed | 42 passed |

The documentation-only synchronization commits after 930226d do not change application code. The PR remains open for review and has not been merged.

## Not implemented yet

- Generated, resolver-verified dependency lockfile.
- Production instrument master/source registry verification workflow, verified historical market-feed entitlement, or automated Indonesian market-data adapter.
- Explicit user-led review workflow that can promote imported observations from UNVERIFIED to a reviewed quality state with immutable audit evidence.
- Full financial statements, valuation metrics, technical indicators, dividend intelligence, screening, and evidence-linked recommendations.
- Portfolio trade-entry UI, market valuation, unrealized P/L, corporate actions, rebalancing, allocation execution, and full risk controls.
- Ollama integration, document analysis, automation scheduler, reporting, verified backup/restore, and Windows production installer.
- Clean-install, upgrade, offline, security, and production packaging acceptance.

## Next engineering objectives

1. Add an instrument master and a separately controlled evidence-review workflow; imports and AI must never self-certify as VERIFIED.
2. Implement the next deterministic technical-analysis vertical slice with documented formulas, warm-up/missing-data rules, and independent tests.
3. Connect verified inputs to evidence-linked screening only after data eligibility and freshness gates exist.
4. Continue portfolio valuation/trade flows, dividend analytics, risk controls, automation, reporting, backup/restore, and Windows packaging in tested vertical slices.
