# RFinance Roadmap

Statuses reflect implemented behavior and test evidence, not folder names or UI placeholders.

| Milestone | Scope | Status |
|---|---|---|
| 0 | Repository bootstrap, agent policy, packaging, tooling, CI | Implemented; Windows/Ubuntu Python 3.12 CI validated |
| 1 | PySide6 shell, local paths, SQLite/Alembic startup | Initial desktop shell, local storage, migrations, and settings/portfolio navigation implemented |
| 2 | Source registry, provenance, instrument identity, data-quality pipeline, permitted import | Local CSV ingestion, archive/hash, row diagnostics, source/batch/observation persistence, Overview history, instrument placeholders, foreign-key linkage, evidence-backed instrument review UI, append-only observation-review ledger, and evidence-backed Observation Review desktop workflow implemented. Production feed approval remains |
| 3 | Fundamental, valuation, technical and dividend calculations | Decimal margin/ROE/debt-equity primitives, technical indicator suite, and `dividend-analytics-v1` calculation layer implemented with methodology docs and tests. Broader statements and valuation formulas remain |
| 4 | Screening and deterministic evidence-linked recommendations | Not started; eligibility gate and observation-review ledger implemented, but screening and recommendations are not built; they must consume only eligible inputs |
| 5 | Dividend event calendar and analytics | Deterministic calculation layer implemented; event persistence, calendar and desktop UI remain |
| 6 | Ledger-based simulated portfolio, allocation and risk | Immutable ledger replay, SQLite persistence, first-run cash setup, dashboard, `portfolio-valuation-v1`, persisted-observation eligibility integration, and desktop price valuation implemented; trade UI, verified instrument-to-category mapping, allocation execution and risk automation remain |
| 7 | Optional Ollama intelligence and secure document analysis | Not started |
| 8 | Local automation and reporting | Not started |
| 9 | Backup/restore, offline operation, reliability and security hardening | Not started |
| 10 | Windows installer, clean install, upgrade and data-preservation verification | Not started |

## Latest verified engineering checkpoint

- Latest application-code head validated by GitHub Actions: `b37a15ef78afe4885c4282384923e27c5b0b5bd6`.
- Windows and Ubuntu, Python 3.12: Ruff lint, Ruff format, and Mypy passed; **141 pytest tests passed on each OS**. See [push CI 44909356690](https://github.com/RidTheWann/RFinance/actions/runs/44909356690) and [PR CI 44909361649](https://github.com/RidTheWann/RFinance/actions/runs/44909361649).
- A prior Termux/Python 3.14 developer checkpoint reported 127 non-UI tests; it is historical context only and is superseded by the current cross-platform Python 3.12 result.
- PR #1 remains open and is not merged into `main`.

## Next implementation sequence

1. Connect the technical indicator calculation layer to consistently sampled, adjusted, quality-qualified historical series.
2. Persist dividend events with provenance and connect the dividend calculation layer to a calendar and desktop UI.
3. Extend fundamental statements and valuation calculations with formula versioning, input requirements and missing-data semantics.
4. Build deterministic screening and evidence-linked recommendations using only eligible observations.
5. Add verified instrument lot-size and category evidence, then complete simulated trade-entry, dividend receipt and position-management workflows.
6. Implement drawdown/allocation controls, risk-event audit, and portfolio review workflows.
7. Add optional local AI, automation, reporting, backup/restore, and production Windows delivery.
