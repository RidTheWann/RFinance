# RFinance

**Local-first investment research and simulated portfolio management for Windows 11.**

RFinance is a native desktop application in active development for Indonesian-market research, evidence-linked analysis, dividend monitoring, and local portfolio simulation. It does not connect to brokerage accounts or execute real-money transactions.

## Product principles

- **Local-first and no-login:** user data and core workflows run locally.
- **Deterministic finance:** calculations and accounting are performed by tested application code; AI is optional and subordinate.
- **Evidence and provenance:** financial observations retain source, timestamps, units, currency, quality, and verification state.
- **Explicit simulation:** simulated positions and cash flows are never presented as actual brokerage activity.
- **Safe acquisition:** data is obtained only through permitted APIs, licensed feeds, official downloads, or user-provided documents.

## Current development slice

The current branch includes a functional PySide6 shell, local SQLite/Alembic storage, a Decimal-based simulated portfolio ledger, user-selected CSV market-data imports, and evidence-backed Instrument Review and Observation Review workflows. Portfolio valuation uses persisted observations only after freshness, quality, source, currency, and instrument checks; conflicting latest prices remain unvalued. The Portfolio Simulator exposes price provenance and partial-versus-complete valuation. A Technical Analysis desktop workflow now selects one instrument and one stored source, loads only eligible historical bars, and computes Decimal indicators with visible source, gap, and corporate-action-adjustment limitations. Historical prices are not rejected by the current-price freshness rule. Imported observations remain UNVERIFIED until separately reviewed. A Dividend Center records user-supplied dividend events in an append-only ledger with evidence-backed review, a labelled ex-date/payment-date calendar, and analytics that use only verified observed cash events. Announced, estimated and simulated items are never presented as cash received. A deterministic Research Center stores evidence-linked recommendations with explicit risk flags and invalidation conditions; confidence describes evidence quality, never profit probability.

No automated IDX/OJK/KSEI scraper or licensed market-data adapter is enabled. Publicly viewable data is not automatically approved for automated access or redistribution.

See IMPLEMENTATION_STATUS.md, ROADMAP.md, and TEST_REPORT.md for implementation and validation state. Import trust boundaries are in docs/MARKET_CSV_IMPORT.md; dividend event semantics are in docs/DIVIDEND_EVENTS.md; screening rules are in docs/SCREENING.md.

## Progress Project

Estimated progress toward a **publish-ready release**: **86.2%** (updated 2026-11-24, recomputed from the milestone table below and verified against `origin/main` at `8949344`).

"Publish-ready" means: a tested Windows 11 x64 installer, reproducible locked
dependencies, verified backup/restore, clean-install and upgrade evidence,
passing Windows + Ubuntu CI, complete user documentation, and no unresolved
critical accounting or security defect. The percentage is a weighted estimate
from verified repository evidence, not a promise or a schedule.

| # | Milestone | Weight | Complete | Contribution | Evidence / remaining gap |
|---|---|---:|---:|---:|---|
| 0 | Repository bootstrap, policy, CI | 5% | 100% | 5.0% | AGENTS.md, pyproject, CI green |
| 1 | Desktop shell, config, SQLite/Alembic | 8% | 100% | 8.0% | PySide6 shell with ten connected pages, migrations `0001`–`0013`, first-run setup |
| 2 | Data provenance, import, eligibility | 10% | 78% | 7.8% | CSV import + review gates done; no licensed/official automated feed |
| 3 | Deterministic financial engine | 14% | 82% | 11.5% | Fundamental/technical/dividend/valuation + reviewed filing metrics; broader statement coverage pending |
| 4 | Screening and recommendations | 10% | 92% | 9.2% | Engine, append-only records, guided evaluation, verified filing inputs; no backtesting yet |
| 5 | Dividend Center | 8% | 92% | 7.4% | Events, calendar, analytics, confirmed receipts; no automated dividend feed |
| 6 | Portfolio simulator and risk | 14% | 86% | 12.0% | Ledger, valuation, receipts, evidence-gated trades and auditable drawdown/concentration controls; rebalancing execution pending |
| 7 | Optional AI | 8% | 88% | 7.0% | `ai-research-summary-v1` allowlisted endpoint + schema-validated untrusted summary in Research Center; document analysis and further providers remain |
| 8 | Automation and reporting | 10% | 88% | 8.8% | `automation-jobs-v1` + connected Automation Center; `ledger-csv-v1` and `portfolio-pdf-v1` exports wired to Portfolio Simulator; automatic scheduling/monthly reports remain |
| 9 | Security and reliability | 8% | 85% | 6.8% | 19 append-only tables with triggers, `sqlite-backup-v1` verified backup/non-destructive restore, pip-audit clean; in-place restore, offline acceptance and signed package remain |
| 10 | Windows production delivery | 5% | 60% | 3.0% | Reproducible PyInstaller folder build, pinned lockfile, frozen binary smoke-tested on a fresh data directory; separate-machine clean install, in-place upgrade/data preservation and code signing remain |
| | **Total** | **100%** | | **86.2%** | |

The next objectives are recorded in [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md):
allocation-target execution and rebalancing, then automation/reporting,
backup/restore and Windows packaging. Risk review semantics are documented in
[docs/RISK_POLICY.md](docs/RISK_POLICY.md). Progress is recomputed after each
substantial slice.

## Development

Supported development runtimes are Python 3.12–3.15 on Windows 11 x64; 3.13 is preferred.

Use PowerShell:

    .\scripts\setup_windows.ps1
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    python -m pip install -e ".[dev]"
    python -m rfinance

Run checks with:

    python -m pytest
    ruff check .
    ruff format --check .
    mypy src

Dependency locking and the Windows production package remain validation gates. Do not treat an unvalidated lockfile, test run, or build as production evidence.

Recommended editor extensions, project agent skills, and MCP setup with its security boundaries are documented in [docs/DEVELOPER_TOOLING.md](docs/DEVELOPER_TOOLING.md).

## Scope boundary

RFinance supports research, analysis, local records, and simulated portfolio operations only. It must not request broker credentials, bypass provider controls, submit orders, or move money.

## License

RFinance is free software licensed under the **GNU General Public License, version 3 only** (`GPL-3.0-only`). See [LICENSE](LICENSE) for the complete license text, [docs/ADR/0003-license-gpl-3.md](docs/ADR/0003-license-gpl-3.md) for the decision rationale and Qt/PySide6 compliance approach, and [docs/THIRD_PARTY_NOTICES.md](docs/THIRD_PARTY_NOTICES.md) for dependency license notices.

No contributor account, broker credential, or cloud subscription is required to run the core application. The license governs the software only; it is not investment advice.
