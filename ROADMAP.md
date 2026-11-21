# RFinance Roadmap

Statuses reflect code and test evidence, not folder names or UI placeholders.

| Milestone | Scope | Status |
|---|---|---|
| 0 | Repository bootstrap, agent policy, packaging, tooling, CI | Implemented; baseline validated on Windows and Ubuntu |
| 1 | PySide6 shell, local paths, SQLite/Alembic startup | Initial shell implemented; Windows/Ubuntu CI baseline passed |
| 2 | Source registry, provenance, data-quality pipeline, permitted import | Local CSV ingestion, archive/hash, row diagnostics, source/batch/observation persistence, and UI import history implemented; latest UI-history head CI pending. No automated market provider approved |
| 3 | Fundamental, valuation, technical and dividend calculations | Initial Decimal margins, ROE and debt/equity only; further formulas not implemented |
| 4 | Screening and deterministic evidence-linked recommendations | Not started |
| 5 | Dividend event calendar and analytics | Not started |
| 6 | Ledger-based simulated portfolio, allocation and risk | Immutable ledger replay, SQLite persistence, first-run cash setup and dashboard implemented; trade UI, valuations, allocation execution and risk automation remain |
| 7 | Optional Ollama intelligence and secure document analysis | Not started |
| 8 | Local automation and reporting | Not started |
| 9 | Backup/restore, offline operation, reliability and security hardening | Not started |
| 10 | Windows installer, clean install, upgrade and data-preservation verification | Not started |

## Next implementation sequence

1. Validate current import-history UI head across Windows and Ubuntu.
2. Add an instrument master and a separately controlled evidence-review workflow; user imports remain UNVERIFIED until a justified review is explicitly recorded.
3. Implement technical indicators and additional fundamental metrics with formula versioning, input requirements, warm-up behavior, and missing-data semantics.
4. Build deterministic screening and recommendation eligibility using only sufficiently fresh, quality-qualified observations.
5. Expand dividends, portfolio valuation/trade flows, drawdown and allocation controls.
6. Add optional local AI, automation, reporting, backup/restore, and production Windows delivery.
