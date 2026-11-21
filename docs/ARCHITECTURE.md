# RFinance Architecture

## Current shape

RFinance starts as a **modular monolith**: one Windows desktop process, one local SQLite database, and explicit Python package boundaries. No remote application backend is required.

| Layer | Current responsibility | Boundary |
|---|---|---|
| Presentation | PySide6 main window and navigation | No calculations or provider transforms |
| Application | Composition root and lifecycle | Coordinates infrastructure |
| Domain / analysis | Decimal fundamental primitives | No Qt, SQLAlchemy, or network dependency |
| Data | Typed, provider-independent observations | Quality and units are explicit |
| Intelligence | Planned optional local AI | Must not become numerical authority |
| Persistence / security | SQLite, Alembic, local paths, logs | Local state remains outside installation directory |

## Startup sequence

1. Create QApplication.
2. Resolve persistent data path (RFINANCE_HOME, then Windows LOCALAPPDATA, then a development fallback).
3. Create data directories.
4. Configure rotating local logs.
5. Open SQLite with foreign keys, a bounded busy timeout, WAL, and FULL synchronous mode.
6. Apply Alembic migrations.
7. Display the desktop window.

A migration failure aborts startup and displays an actionable error. The application does not silently recreate or replace a database.

## Dependency direction

`ui -> application/core -> domain/data contracts`; infrastructure is composed at the application root. Domain calculations must remain importable without Qt or a database.

## Persistent paths

The default Windows data root is `%LOCALAPPDATA%\\RFinance`. `RFINANCE_HOME` relocates all persistent application state. Database, documents, cache, reports, backups, and logs are kept outside the program installation directory.

## Planned extensions

- Provider adapters and observation provenance.
- Ledger-backed simulated portfolio accounting.
- Deterministic screening and evidence-linked recommendation records.
- Background job orchestration that never blocks the Qt event loop.
- Ollama integration behind a local, optional interface.

These are roadmap items, not current features.
