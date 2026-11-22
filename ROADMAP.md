# RFinance Roadmap

Statuses reflect implemented behavior and test evidence, not folder names or UI placeholders.

| Milestone | Scope | Status |
|---|---|---|
| 0 | Repository bootstrap, agent policy, packaging, tooling, CI | Implemented; Windows/Ubuntu Python 3.12 CI validated |
| 1 | PySide6 shell, local paths, SQLite/Alembic startup | Initial desktop shell, local storage, migrations, and settings/portfolio navigation implemented |
| 2 | Source registry, provenance, instrument identity, data-quality pipeline, permitted import | Local CSV ingestion, archive/hash, row diagnostics, source/batch/observation persistence, Overview history, instrument placeholders, foreign-key linkage, evidence-backed instrument review UI, append-only observation-review ledger, and evidence-backed Observation Review desktop workflow implemented. Production feed approval remains |
| 3 | Fundamental, valuation, technical and dividend calculations | Decimal fundamental primitives, `dividend-analytics-v1`, and technical indicator suite implemented. Historical series now load from persisted review-qualified observations into the Technical Analysis desktop workflow; full statements, wider valuation, explicit frequency and corporate-action metadata remain |
| 4 | Screening and deterministic evidence-linked recommendations | Not started; eligibility gate and observation-review ledger implemented, but screening and recommendations are not built; they must consume only eligible inputs |
| 5 | Dividend event calendar and analytics | `dividend-analytics-v1` calculations, append-only event/review persistence with migration `0006_dividend_events`, labelled calendar, and connected Dividend Center desktop page implemented; confirmed-receipt cash posting and automated provider feed remain |
| 6 | Ledger-based simulated portfolio, allocation and risk | Immutable ledger replay, SQLite persistence, first-run cash setup, dashboard, `portfolio-valuation-v1`, persisted-observation eligibility integration, and desktop price valuation implemented; trade UI, verified instrument-to-category mapping, allocation execution and risk automation remain |
| 7 | Optional Ollama intelligence and secure document analysis | Not started |
| 8 | Local automation and reporting | Not started |
| 9 | Backup/restore, offline operation, reliability and security hardening | Not started |
| 10 | Windows installer, clean install, upgrade and data-preservation verification | Not started |

## Latest local engineering checkpoint (2026-11-22)

- Local branch `rfinance-dev`, based on the preserved head of the closed, unmerged PR #1. No push access in this session; no push or merge is claimed.
- Ubuntu 26.04 aarch64 / Python 3.14.4: Ruff lint and format pass (109 files), Mypy strict passes (62 source files), 169 unit/integration tests and 4 targeted Qt tests pass.
- Delivered: append-only dividend event and review persistence, evidence-backed review gates, labelled calendar, verified-event analytics, and a connected Dividend Center desktop tab.
- Full Qt worker-thread suite is timing-unreliable on this aarch64/offscreen runtime; historical Windows/Ubuntu x64 CI at Python 3.12 passed 156 tests.

## Historical verified engineering checkpoint

- Latest application-code head validated by GitHub Actions: `3a9dc774f0ad0ad5bc80501f249ce681c5fa34e6`.
- Windows and Ubuntu, Python 3.12: Ruff lint, Ruff format, and Mypy passed; **156 pytest tests passed on each OS**. Ruff format reports 101 files already formatted and Mypy checks 57 source files. See [push CI 44911435637](https://github.com/RidTheWann/RFinance/actions/runs/44911435637) and [PR CI 44911439980](https://github.com/RidTheWann/RFinance/actions/runs/44911439980).
- A prior Termux/Python 3.14 developer checkpoint reported 127 non-UI tests; it is historical context only and is superseded by the current cross-platform Python 3.12 result.
- PR #1 is closed and unmerged; its implementation was preserved locally and development continued from it.

## Next implementation sequence

1. Post confirmed net dividend receipts to the ledger with duplicate protection and the documented 50/30/20 distribution preference.
2. Add explicit sampling-frequency and corporate-action adjustment evidence to the instrument/observation model before supporting additional historical providers.
3. Extend fundamental statements and valuation calculations with formula versioning, input requirements and missing-data semantics.
4. Build deterministic screening and evidence-linked recommendations using only eligible observations.
5. Add verified instrument lot-size and category evidence, then complete simulated trade-entry and position-management workflows.
6. Implement drawdown/allocation controls, risk-event audit, and portfolio review workflows.
7. Add optional local AI, automation, reporting, backup/restore, lockfile, and production Windows delivery.
