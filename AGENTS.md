# RFinance — Agent Engineering Policy

This file is the canonical repository-wide policy for every human and coding agent. Read it before making changes. Claude-specific startup guidance is in `CLAUDE.md`; it supplements, but never overrides, this file.

## Product invariants

1. RFinance is a local-first, no-login Windows desktop application for investment research and simulated portfolio management.
2. The initial market focus is Indonesia and IDR. Market coverage must be explicitly represented; never imply universal coverage.
3. No broker credentials, broker login, real-money orders, payments, leverage, short selling, or provider-control circumvention.
4. Financial calculations and portfolio accounting are deterministic. AI is optional, untrusted, and subordinate to deterministic controls.
5. Every material external observation must retain provenance, timestamps, units, currency, quality, and verification status.
6. Missing, stale, incomplete, estimated, rejected, and simulated data are distinct states. Never silently coerce missing values to zero or verified data.
7. Simulation is always labelled as simulation. An announcement, historical record, or forecast is not a confirmed cash receipt.
8. Never overwrite historical observations silently. Preserve source and transformation history.
9. Do not invent data providers, endpoints, fields, licenses, instrument availability, financial metrics, test results, or successful builds.

## Architecture boundaries

- Presentation: PySide6 only; no financial formulas or provider-specific transformations.
- Application services: use-case orchestration and job coordination.
- Domain/analysis: framework-independent financial rules, Decimal monetary arithmetic, explicit units and methodology versions.
- Data infrastructure: provider adapters, parsing, normalization, provenance, quality, and cache.
- Intelligence: deterministic scoring plus optional local AI; model outputs are untrusted proposals, never authority.
- Persistence/security: SQLite, migrations, repositories, backup/restore, audit, and integrity controls.

Prefer a modular monolith. Do not add microservices, dependency-injection frameworks, event buses, or abstractions without an implemented use case that requires them.

## Engineering workflow

For each coherent change:
1. Inspect the current branch, status, recent commits, repository instructions, and affected code.
2. Research uncertain library, Windows, financial, data-access, or security behavior using official current sources.
3. Implement a vertical slice with explicit contracts and error behavior.
4. Add focused tests, including edge cases and invariants.
5. Run tests, Ruff lint/format, Mypy, and relevant security/dependency checks.
6. Fix regressions; do not suppress failures merely to obtain green checks.
7. Update relevant docs, `IMPLEMENTATION_STATUS.md`, `ROADMAP.md`, `TEST_REPORT.md`, and `CHANGELOG.md`.
8. Commit a coherent unit on a focused branch and verify the resulting GitHub state.
9. Continue to the next valuable task; a report is not a stopping point.

Never claim a check was run unless its output was observed. Distinguish local checks, CI checks, manual review, and unverified assumptions.

## Repository and Git safety

- Inspect before editing. Preserve uncommitted work and unknown files.
- Never force-push, rewrite history, reset, or delete branches as a shortcut.
- Keep `main` stable. Use focused branches and reviewable PRs when possible.
- Never merge a PR with failing required checks.
- Never claim a push, PR, merge, release, or package build succeeded without verifying GitHub's response.
- Do not expose secrets, credentials, personal financial data, local database contents, or private documents in logs or commits.

## Financial correctness

- Use `Decimal` for money, prices, cash, fees, tax, and ledger amounts.
- Every formula must define numerator, denominator, units, sign convention, missing-data behavior, and methodology version.
- Guard zero/negative/invalid denominators explicitly.
- Do not mix reported, derived, forecast, analyst, AI-interpreted, and simulated values.
- Industry-specific interpretation is mandatory; bank metrics must not inherit industrial-company assumptions without justification.
- Recommendation confidence means evidence quality/completeness, not probability of profit.
- A BUY_CANDIDATE must be blocked by stale, unverified, or materially incomplete required evidence.

## Data acquisition and AI safety

- Prefer official documented APIs, official downloads, licensed providers, investor-relations documents, and user imports.
- Verify terms, licensing, rate limits, retention, and redistribution rights before enabling a provider.
- No authentication bypass, CAPTCHA/paywall evasion, anti-bot circumvention, or unrestricted crawling.
- Use a source allowlist. Retrieved pages, PDFs, spreadsheets, prompts, and model outputs are untrusted data.
- Never let AI select arbitrary URLs, read arbitrary local paths, run shell commands, mutate the ledger, or override controls.
- Validate structured model output against application-owned schemas and permissions.

## Dependencies and releases

- Verify Python and Windows compatibility, maintenance, security, and license before adding dependencies.
- Pin tested versions in a generated lockfile before calling an environment reproducible. Never fabricate or hand-wave a lockfile.
- Review Qt/PySide LGPL/GPL obligations before distributing a binary; record the selected compliance approach.
- Production claims require clean Windows installation, upgrade, data-preservation, backup, and restore evidence.

## Definition of a complete feature

A feature is complete only when its domain behavior, data flow, persistence, UI/application-service connection, error handling, tests, and documentation are all present and verified. An empty module, static demo value, placeholder button, or plan does not count.

## Agent tooling

- Project skills live in `.opencode/skills/`: the RFinance digests (`rfinance-invariants`, `rfinance-finance-qt`, `rfinance-quality`, `rfinance-docs`) plus the portable MIT-licensed Matt Pocock engineering/productivity skills. An OpenCode V2 Superpowers plugin is installed globally and supplies process skills (`brainstorming`, `writing-plans`, `test-driven-development`, `systematic-debugging`, `verification-before-completion`, code review). These digests and packs are never overrides of this policy.
- Editor recommendations are in `.vscode/extensions.json`; MCP setup and its security boundaries are documented in `docs/DEVELOPER_TOOLING.md`.
- No MCP or editor tool may expand the permitted action set: no broker/trading connectors, no arbitrary filesystem access, no unreviewed market-data ingestion, no automatic merge on failing checks.
