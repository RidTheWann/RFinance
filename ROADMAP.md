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
| 6 | Ledger-based simulated portfolio, allocation and risk | Immutable ledger replay, first-run cash setup, `portfolio-valuation-v1`, confirmed dividend receipts, evidence-gated simulated trades, and `risk-controls-v1` drawdown/concentration events with explicit reviews and a connected Risk Management page implemented; rebalancing execution, verified sector mapping and risk automation remain |
| 7 | Optional Ollama intelligence and secure document analysis | Not started |
| 8 | Local automation and reporting | `ledger-csv-v1` simulated-ledger export connected to the Portfolio Simulator and documented; automation scheduler and PDF/broader reports remain |
| 9 | Backup/restore, offline operation, reliability and security hardening | Not started |
| 10 | Windows installer, clean install, upgrade and data-preservation verification | Not started |

## Latest local engineering checkpoint (2026-11-23)

- Verified remote/local `main`: `753308bb87b58c076fc9cf9d189c7e2a9a14d053` (203 commits), merge of PR #6. Earlier notes claiming `f005c911...` / 179 commits were an outdated checkpoint. `gh` is unauthenticated here, so this session's commits are local and no push/PR/merge is claimed.
- Linux aarch64 / Python 3.14: Ruff lint and format pass, Mypy strict passes on 82 source files, 246 unit/integration tests pass, 13 UI tests pass with one pre-existing aarch64/offscreen worker-timing failure reproduced on clean HEAD.
- Delivered in this session: `risk-controls-v1`, append-only risk events/reviews and valuation history, and a connected Risk Management page.
- Full Qt worker-thread suite remains timing-unreliable on this aarch64/offscreen runtime; historical Windows/Ubuntu x64 CI at Python 3.12 passed 215 tests.

## Historical verified engineering checkpoint

- Latest application-code head validated by GitHub Actions: `eaef966d4d542d44275c4cab91e025431b63d18d`.
- Windows and Ubuntu, Python 3.12: Ruff lint, Ruff format, and Mypy passed; **156 pytest tests passed on each OS**. Ruff format reports 101 files already formatted and Mypy checks 57 source files. See [push CI 44911435637](https://github.com/RidTheWann/RFinance/actions/runs/44911435637) and [PR CI 44911439980](https://github.com/RidTheWann/RFinance/actions/runs/44911439980).
- A prior Termux/Python 3.14 developer checkpoint reported 127 non-UI tests; it is historical context only and is superseded by the current cross-platform Python 3.12 result.
- PR #1 is closed and unmerged; its implementation was preserved locally and development continued from it.

## Next implementation sequence

1. ~~Connect persisted active risk events to screening evaluation end-to-end so a required review blocks BUY_CANDIDATE promotion from the desktop.~~ Implemented via `screening-deterministic-v2`; see IMPLEMENTATION_STATUS.md.
2. Add allocation-target execution and rebalancing using verified instruments and instrument-to-category evidence.
3. Add explicit sampling-frequency, sector and corporate-action adjustment evidence to the instrument/observation model before supporting additional historical providers.
4. Extend fundamental statements and valuation calculations with formula versioning, input requirements and missing-data semantics.
5. Post the reinvestment and money-market legs of confirmed dividends into verified instruments once such instruments exist.
6. Add optional local AI, automation, reporting, backup/restore, lockfile, and production Windows delivery.
