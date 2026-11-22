---
name: RFinance Quality Gates
description: Test-first quality workflow for RFinance: unit, integration, contract, property and UI tests, plus lint, typing, security and dependency checks. Use before committing or when changing financial logic.
---

# Quality gates

## Local commands (Windows PowerShell or POSIX shell)

```sh
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
mypy src
python -m pytest
python -m pytest tests/unit tests/integration
bandit -q -r src
pip-audit
```

CI runs Windows + Ubuntu, Python 3.12: Ruff lint, Ruff format, Mypy, and the full pytest suite. Merge only when all are green.

## Required test coverage by area

- **Financial formulas**: exact Decimal results, zero/negative denominators, missing inputs, industry exceptions, formula version and reproducibility record.
- **Ledger/valuation**: cash reconciliation, weighted-average cost, lot-size evidence, duplicate dividend protection, append-only triggers, unvalued positions, partial-total disclosure.
- **Property-based (Hypothesis)**: allocation sums, reconciliation preserved after replay, no duplicate dividend credit, no unsupported capital, stale/unverified observations never become eligible, net amount never exceeds gross.
- **Data/provenance**: schema validation, rejected rows, duplicate rejection, archived SHA-256, source policy constraints, review gates, append-only audit events.
- **AI**: structured output must pass application-owned schemas; prompt-injection text must never mutate state or override controls.
- **UI**: workflows connect to services; verify off-thread work and busy states. Qt worker tests may flake on aarch64/offscreen — cross-check CI before assigning blame.

## Rules

- Add or extend tests in the same change as the implementation.
- Test invariants and edge cases, not just happy paths.
- Never suppress a failure to obtain green checks; fix the cause.
- Never claim a check was run unless its output was observed. Distinguish local, CI, manual review and assumption.
- Keep fixtures deterministic; no network in tests; use temporary directories for SQLite and evidence files.

## Reporting

Update `TEST_REPORT.md` with observed results, environment, and any known flakiness. Update `IMPLEMENTATION_STATUS.md`, `ROADMAP.md`, and `CHANGELOG.md` when behaviour changes.
