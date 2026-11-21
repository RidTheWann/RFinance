# RFinance Roadmap

Status is based on implemented and verifiable behavior, not directory names or UI labels.

| Milestone | Scope | Status |
|---|---|---|
| 0 | Repository policy, Python packaging, tooling, CI foundation | Implemented in foundation branch; CI validation pending |
| 1 | PySide6 shell, persistent paths, SQLite/Alembic startup | Implemented in foundation branch; CI validation pending |
| 2 | Source registry, provider abstraction, quality and provenance persistence, permitted import | Not started |
| 3 | Fundamental, valuation, technical, and dividend calculations | Initial Decimal primitives only |
| 4 | Screening, deterministic ranking, evidence-linked recommendations | Not started |
| 5 | Dividend event center and dividend analytics | Not started |
| 6 | Ledger-based simulated portfolio and allocation | Pure replay engine implemented; persistence, services, UI, and reconciliation workflows remain |
| 7 | Optional Ollama integration and secure document intelligence | Not started |
| 8 | Local automation, reports, CSV/PDF exports | Not started |
| 9 | Backup/restore, offline and reliability hardening | Not started |
| 10 | Windows production package and clean-install verification | Not started |

## Near-term execution sequence

1. Validate and fix the foundation and ledger domain slices through Windows and Ubuntu CI.
2. Persist ledger events, implement an atomic repository, and prove replay reconstruction after restart.
3. Add explicit first-run simulation setup and portfolio commands with no assumed periodic contributions.
4. Implement source registry, provenance, quality events, and explicit manual data import.
5. Research and approve a compliant Indonesian-market data path before enabling any automated provider.
6. Expand deterministic calculations with documented formula contracts and industry-specific handling.
