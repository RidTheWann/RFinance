# RFinance

**Local-first investment research and simulated portfolio management for Windows 11.**

RFinance is designed as a native desktop application for Indonesian-market research, evidence-linked analysis, dividend monitoring, and local portfolio simulation. It does not connect to brokerage accounts or execute real-money transactions.

## Product principles

- **Local-first and no-login:** user data and core workflows run locally.
- **Deterministic finance:** calculations and accounting are performed by tested application code; AI is optional and subordinate.
- **Evidence and provenance:** financial observations retain source, timestamps, units, currency, quality, and verification state.
- **Explicit simulation:** simulated positions and cash flows are never presented as actual brokerage activity.
- **Safe acquisition:** data is obtained only through permitted APIs, downloads, licensed feeds, or user-provided documents.

## Development status

The repository is being bootstrapped. See [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md), [ROADMAP.md](ROADMAP.md), and [TEST_REPORT.md](TEST_REPORT.md) for verified implementation state. Features are not considered complete merely because a UI surface exists.

## Development

The initial supported development runtime is Python 3.12 on Windows 11 x64.

Once the project environment is established:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m rfinance
```

Run checks with:

```powershell
python -m pytest
ruff check .
ruff format --check .
mypy src
```

Dependency locking and the Windows package are gated on successful resolution and validation in the supported Windows environment. Do not treat an unvalidated lockfile or build as production evidence.

## Scope boundary

RFinance supports research, analysis, local records, and simulated portfolio operations only. It must not request broker credentials, bypass provider controls, submit orders, or move money.

## License

No license has been selected yet. Until a license is added, all rights are reserved by default.
