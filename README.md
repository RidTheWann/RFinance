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

The current branch includes a functional PySide6 shell, local SQLite/Alembic storage, a Decimal-based simulated portfolio ledger, user-selected CSV market-data imports, and evidence-backed Instrument Review and Observation Review workflows. Portfolio valuation uses persisted observations only after freshness, quality, source, currency, and instrument checks; conflicting latest prices remain unvalued. The Portfolio Simulator exposes price provenance and partial-versus-complete valuation. A Technical Analysis desktop workflow now selects one instrument and one stored source, loads only eligible historical bars, and computes Decimal indicators with visible source, gap, and corporate-action-adjustment limitations. Historical prices are not rejected by the current-price freshness rule. Imported observations remain UNVERIFIED until separately reviewed.

No automated IDX/OJK/KSEI scraper or licensed market-data adapter is enabled. Publicly viewable data is not automatically approved for automated access or redistribution.

See IMPLEMENTATION_STATUS.md, ROADMAP.md, and TEST_REPORT.md for implementation and validation state. See docs/MARKET_CSV_IMPORT.md for the import schema and trust boundaries.

## Development

The initial supported development runtime is Python 3.12 on Windows 11 x64.

Use PowerShell:

    py -3.12 -m venv .venv
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

## Scope boundary

RFinance supports research, analysis, local records, and simulated portfolio operations only. It must not request broker credentials, bypass provider controls, submit orders, or move money.

## License

No license has been selected yet. Until a license is added, all rights are reserved by default.
