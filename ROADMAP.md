# RFinance Roadmap

Status is based on implemented and verifiable behavior, not directory names or UI labels.

| Milestone | Scope | Status |
|---|---|---|
| 0 | Repository policy, Python packaging, tooling, CI foundation | Implemented in foundation branch; awaiting checks |
| 1 | PySide6 shell, persistent paths, SQLite/Alembic startup | Implemented in foundation branch; awaiting checks |
| 2 | Source registry, provider abstraction, quality and provenance persistence, permitted import | Not started |
| 3 | Fundamental, valuation, technical, and dividend calculations | Initial Decimal primitives only |
| 4 | Screening, deterministic ranking, evidence-linked recommendations | Not started |
| 5 | Dividend event center and dividend analytics | Not started |
| 6 | Ledger-based simulated portfolio and allocation | Not started |
| 7 | Optional Ollama integration and secure document intelligence | Not started |
| 8 | Local automation, reports, CSV/PDF exports | Not started |
| 9 | Backup/restore, offline and reliability hardening | Not started |
| 10 | Windows production package and clean-install verification | Not started |

## Near-term execution sequence

1. Validate and fix the foundation branch through CI.
2. Implement ledger primitives and property-based accounting invariants.
3. Persist transactions and rebuild balances from the ledger.
4. Implement source registry, provenance, quality events, and explicit manual data import.
5. Research and approve a compliant Indonesian-market data path before enabling any automated provider.
6. Expand deterministic calculations with documented formula contracts and industry-specific handling.
