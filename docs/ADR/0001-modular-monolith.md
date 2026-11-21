# ADR 0001: Start with a modular monolith

- Status: Accepted
- Date: 2026-11-21

## Context

RFinance is a single-user, local-first Windows desktop application. Its principal concerns are financial correctness, local persistence, predictable startup, and clear separation of the UI, financial rules, data adapters, and optional AI.

## Decision

Use one Python process and a modular package structure. Use PySide6 for the desktop shell, SQLite for local persistence, SQLAlchemy for mapping, and Alembic for schema evolution. Keep financial calculations independent of Qt and SQLAlchemy.

## Consequences

- No service deployment or remote database is required for core use.
- Cross-layer access is controlled through package boundaries and application services.
- Provider integrations and AI remain optional adapters.
- A process split is reconsidered only when a concrete isolation, reliability, or performance requirement exists.
