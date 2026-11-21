# RFinance Roadmap

Status is based on implemented and verifiable behavior, not directory names or UI labels.

| Milestone | Scope | Status |
|---|---|---|
| 0 | Repository policy, Python packaging, tooling, CI foundation | Implemented in foundation branch; previous checkpoint passed Windows/Ubuntu CI |
| 1 | PySide6 shell, persistent paths, SQLite/Alembic startup | Implemented in foundation branch; previous checkpoint passed Windows/Ubuntu CI |
| 2 | Source registry, provenance, provider abstraction, quality and permitted import | Research policy added; persistence and import not implemented |
| 3 | Fundamental, valuation, technical, and dividend calculations | Initial Decimal margin/ROE/debt-to-equity primitives only |
| 4 | Screening, deterministic ranking, evidence-linked recommendations | Not started |
| 5 | Dividend event center and dividend analytics | Not started |
| 6 | Ledger-based simulated portfolio and allocation | Domain replay, SQLite persistence, application service, and explicit first-run cash initialization/UI implemented; latest persistence/UI CI pending |
| 7 | Optional Ollama integration and secure document intelligence | Not started |
| 8 | Local automation, reports, CSV/PDF exports | Not started |
| 9 | Backup/restore, offline and reliability hardening | Not started |
| 10 | Windows production package and clean-install verification | Not started |

## Near-term execution sequence

1. Confirm current-head Windows and Ubuntu CI for the SQLite ledger and first-run portfolio workflow.
2. Add source registry/provenance persistence and a user-supplied CSV import path with row-level diagnostics and UNVERIFIED default status.
3. Research and approve specific Indonesian data products before enabling automated acquisition; the initial access review does not approve a crawler or feed.
4. Implement documented, independently tested technical and fundamental calculations with explicit missing-data/industry behavior.
5. Add evidence-linked deterministic screening and dividend intelligence.
6. Expand portfolio services with verified instrument metadata, simulated trade workflows, valuation, risk controls, and reconciliation.
7. Add optional Ollama research assistance, secure document workflows, local automation, reporting, backup/restore, and production packaging.
