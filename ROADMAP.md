# RFinance Roadmap

Statuses reflect implemented behavior and test evidence, not folder names or UI placeholders.

| Milestone | Scope | Status |
|---|---|---|
| 0 | Repository bootstrap, agent policy, packaging, tooling, CI | Implemented; Windows/Ubuntu Python 3.12 CI validated |
| 1 | PySide6 shell, local paths, SQLite/Alembic startup | Initial desktop shell, local storage, migrations, and settings/portfolio navigation implemented |
| 2 | Source registry, provenance, instrument identity, data-quality pipeline, permitted import | Local CSV ingestion, archive/hash, row diagnostics, source/batch/observation persistence, Overview history, instrument placeholders, foreign-key linkage, evidence-backed review service, and desktop evidence-review queue implemented. Price-observation review and production feed approval remain |
| 3 | Fundamental, valuation, technical and dividend calculations | Decimal margin/ROE/debt-equity primitives, technical indicator suite, and `dividend-analytics-v1` calculation layer implemented with methodology docs and tests. Broader statements and valuation formulas remain |
| 4 | Screening and deterministic evidence-linked recommendations | Not started; `eligibility-observation-v1` gate implemented, but screening and recommendations are not built; they must consume only eligible inputs |
| 5 | Dividend event calendar and analytics | Deterministic calculation layer implemented; event persistence, calendar and desktop UI remain |
| 6 | Ledger-based simulated portfolio, allocation and risk | Immutable ledger replay, SQLite persistence, first-run cash setup and dashboard implemented; trade UI, valuations, allocation execution and risk automation remain |
| 7 | Optional Ollama intelligence and secure document analysis | Not started |
| 8 | Local automation and reporting | Not started |
| 9 | Backup/restore, offline operation, reliability and security hardening | Not started |
| 10 | Windows installer, clean install, upgrade and data-preservation verification | Not started |

## Latest verified engineering checkpoint

- Last GitHub Actions validated application-code head: `e5cff0a979bf75a8c8a8b3b949123a491896e0d6`
- Windows and Ubuntu, Python 3.12: Ruff lint, Ruff format, and Mypy passed; 65 pytest tests passed on each OS.
- Local checkpoint (Python 3.14, Termux): Ruff 0.17.6 lint/format passed, Mypy clean for new modules, 106 non-UI pytest tests passed. UI tests and Python 3.12 CI have not been run for post-`e5cff0a` commits.
- PR #1 remains open and is not merged into `main`.

## Next implementation sequence

1. Add a separate observation-quality review workflow that can promote a price to `VERIFIED` with explicit evidence, and wire the implemented eligibility gate into screening and valuation. Verifying an instrument must not certify historical prices.
2. Connect the technical indicator calculation layer to consistently sampled, adjusted, quality-qualified historical series.
3. Persist dividend events with provenance and connect the dividend calculation layer to a calendar and desktop UI.
4. Extend fundamental statements and valuation calculations with formula versioning, input requirements and missing-data semantics.
5. Build deterministic screening and evidence-linked recommendations using only eligible observations.
6. Expand dividends, portfolio valuation/trade flows, drawdown and allocation controls.
7. Add optional local AI, automation, reporting, backup/restore, and production Windows delivery.
