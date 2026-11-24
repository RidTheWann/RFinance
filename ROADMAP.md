# RFinance Roadmap

Statuses reflect implemented behavior and test evidence, not folder names or UI placeholders.

| Milestone | Scope | Status |
|---|---|---|
| 0 | Repository bootstrap, agent policy, packaging, tooling, CI | Implemented; Windows/Ubuntu Python 3.12 CI validated |
| 1 | PySide6 shell, local paths, SQLite/Alembic startup | Initial desktop shell, local storage, migrations, and settings/portfolio navigation implemented |
| 2 | Source registry, provenance, instrument identity, data-quality pipeline, permitted import | Local CSV ingestion, archive/hash, row diagnostics, source/batch/observation persistence, Overview history, instrument placeholders, foreign-key linkage, evidence-backed instrument review UI, append-only observation-review ledger, and evidence-backed Observation Review desktop workflow implemented. Production feed approval remains |
| 3 | Fundamental, valuation, technical and dividend calculations | `fundamental-metrics-v1`, `dividend-analytics-v1`, technical indicator suite, and append-only reviewed financial statement metrics connected to screening implemented. Broader statement coverage, sampling-frequency and corporate-action metadata remain |
| 4 | Screening and deterministic evidence-linked recommendations | `screening-deterministic-v1`, append-only persistence, Research Center inspection and a guided evidence-assembly workflow implemented; verified financial-statement inputs remain |
| 5 | Dividend event calendar and analytics | `dividend-analytics-v1`, append-only event/review persistence, labelled calendar, connected Dividend Center, and `dividend-receipt-v1` confirmed-receipt posting with 50/30/20 split and duplicate protection implemented; automated provider feed remains |
| 6 | Ledger-based simulated portfolio, allocation and risk | Immutable ledger replay, first-run cash setup, `portfolio-valuation-v1`, `allocation-plan-v1` gap planning with explicit unfilled targets and risk blocking, `instrument-category-v1` evidence decisions feeding the plan, confirmed dividend receipts, evidence-gated simulated trades, and `risk-controls-v1` events with explicit reviews and connected desktop pages implemented; automatic rebalancing execution, verified sector mapping and risk automation remain |
| 7 | Optional AI intelligence and secure document analysis | `ai-research-summary-v1` API-key research aid with one allowlisted HTTPS endpoint, schema-validated output, untrusted labelling, no key storage and an optional capability disabled by default; document analysis and additional providers remain |
| 8 | Local automation and reporting | `automation-jobs-v1` code-defined jobs, append-only run ledger and connected Automation Center with manual runs/history; `ledger-csv-v1` and `portfolio-pdf-v1` exports connected to the Portfolio Simulator. Automatic scheduling and monthly/broader reports remain |
| 9 | Backup/restore, offline operation, reliability and security hardening | `sqlite-backup-v1` verified backup with SHA-256 manifest and non-destructive restore connected to Settings; 19 append-only tables with triggers; pip-audit clean. In-place restore, offline acceptance and deeper hardening remain |
| 10 | Windows installer, clean install, upgrade and data-preservation verification | Reproducible PyInstaller folder build (`installer/windows/rfinance.spec`, `scripts/build_windows.ps1`), pinned lockfile, frozen binary smoke-tested on a fresh data directory reaching migration `0013` with 23 tables. Signed installer, separate-machine clean install, in-place upgrade and data-preservation acceptance remain |

## Latest local engineering checkpoint (2026-11-24)

- Verified `origin/main`: `89493444ea128715b17fabc6187bf22bdca2d10b` (merge of PR #20), **238 commits**. `gh` is authenticated as `RidTheWann`.
- Windows 11 x64 / Python 3.13.16: Ruff lint/format clean, Mypy strict clean on 111 source files, `pytest -q` → **332 passed**. `pip-audit -r requirements.lock` clean; `bandit` one medium false positive (`B310`) + 21 lows.
- Delivered across PRs #19–#21: `setup_windows.ps1` interpreter autodetect; `instrument-metadata-evidence-v1` (sampling-frequency and adjustment evidence feeding `historical-price-series-v1`); reporting-basis separation so quarterly values cannot feed annual formulas.
- CI stalls recorded as runner infrastructure, not code: two Ubuntu jobs hung for the full six-hour timeout or were cancelled mid-`Tests` while same-SHA runs passed.
- Earlier aarch64/Python 3.14 checkpoints and the 246-test / 215-test counts are superseded by the current cross-platform Python 3.12 CI plus the local 332-test gate.

## Historical verified engineering checkpoint

- Latest application-code head validated by GitHub Actions: `eaef966d4d542d44275c4cab91e025431b63d18d`.
- Windows and Ubuntu, Python 3.12: Ruff lint, Ruff format, and Mypy passed; **156 pytest tests passed on each OS**. Ruff format reports 101 files already formatted and Mypy checks 57 source files. See [push CI 44911435637](https://github.com/RidTheWann/RFinance/actions/runs/44911435637) and [PR CI 44911439980](https://github.com/RidTheWann/RFinance/actions/runs/44911439980).
- A prior Termux/Python 3.14 developer checkpoint reported 127 non-UI tests; it is historical context only and is superseded by the current cross-platform Python 3.12 result.
- PR #1 is closed and unmerged; its implementation was preserved locally and development continued from it.

## Next implementation sequence

1. ~~Connect persisted active risk events to screening evaluation end-to-end so a required review blocks BUY_CANDIDATE promotion from the desktop.~~ Implemented via `screening-deterministic-v2`; see IMPLEMENTATION_STATUS.md.
2. ~~Add allocation-target execution and rebalancing using verified instruments and instrument-to-category evidence.~~ Gap planning implemented via `allocation-plan-v1`; automatic rebalancing execution and persisted category evidence remain.
3. Add explicit sampling-frequency, sector and corporate-action adjustment evidence to the instrument/observation model before supporting additional historical providers.
4. Extend fundamental statements and valuation calculations with formula versioning, input requirements and missing-data semantics.
5. Post the reinvestment and money-market legs of confirmed dividends into verified instruments once such instruments exist.
6. Add optional local AI, automation, reporting, backup/restore, lockfile, and production Windows delivery.
