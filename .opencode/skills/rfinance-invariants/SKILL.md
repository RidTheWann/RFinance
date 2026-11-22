---
name: RFinance Invariants
description: Canonical RFinance product invariants and engineering policy digest. Load before any code, data, AI, security, or documentation change in this repository.
---

# RFinance invariants (digest)

`AGENTS.md` at the repository root is the canonical policy. `CLAUDE.md`
supplements it. This skill is an actionable digest; read the canonical files
when a detail is missing. Never treat this digest as overriding them.

## Product invariants

1. Local-first, no-login Windows desktop application for research and **simulated** portfolio management.
2. Initial market focus is Indonesia and IDR. Market coverage must be explicit; never imply universal coverage.
3. No broker credentials, broker login, real orders, payments, leverage, short selling, or provider-control circumvention.
4. Financial calculations and accounting are deterministic. AI is optional, untrusted, and subordinate.
5. Every material external observation retains provenance: source, timestamps, units, currency, quality, verification.
6. `VERIFIED`, `UNVERIFIED`, `ESTIMATED`, `STALE`, `INCOMPLETE`, `REJECTED`, `SIMULATED` are distinct states. Never coerce missing values to zero or to verified.
7. Simulation is always labelled. An announcement, historical record, forecast or projection is not confirmed cash received.
8. Never overwrite historical observations silently. Preserve source and transformation history.
9. Never invent providers, endpoints, fields, licences, instrument availability, metrics, test results, or builds.

## Layer boundaries

Presentation (PySide6) contains no financial formulas or provider transformations. Application services orchestrate use cases. Domain/analysis is framework-independent and Decimal-based. Data infrastructure owns parsing, provenance, quality and cache. Intelligence outputs are untrusted proposals. Persistence owns SQLite, migrations, backups, audit and integrity.

Prefer a modular monolith. Do not add microservices, DI frameworks, event buses, or abstractions without a concrete use case.

## Hard prohibitions

- No broker passwords, CAPTCHA/paywall bypass, anti-bot circumvention, scraping, real trades, or money movement.
- No AI-selected URLs, arbitrary local file reads, shell execution, ledger mutation, or risk-threshold override.
- No silent promotion of `UNVERIFIED` data; no fundamental approval from unverified statements.
- No `BUY_CANDIDATE` on stale, unverified or materially incomplete required evidence.
- No source expansion by retrieved documents or model output; source allowlist is application-owned.

## Engineering loop

Inspect branch/status/recent commits → research uncertain behaviour from official sources → implement a vertical slice → add focused tests → run Ruff, format, Mypy and pytest → fix regressions → update status docs → commit coherently → continue.

## Definition of done

Domain behaviour, data flow, persistence, application/UI connection, error handling, tests and documentation are all present and verified. An empty module, static demo value, placeholder button or plan does not count.

## Supporting references

- `AGENTS.md`, `CLAUDE.md`
- `docs/ARCHITECTURE.md`, `docs/MASTER_SPECIFICATION.md`
- `docs/FINANCIAL_METHODOLOGY.md`, `docs/RISK_POLICY.md`, `docs/SECURITY_MODEL.md`, `docs/DATA_SOURCE_POLICY.md`
- `docs/ADR/` for recorded decisions
