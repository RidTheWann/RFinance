# Security Model

## Trust boundaries

- Local user data is private application state.
- External pages, PDFs, spreadsheets, and imported data are untrusted.
- Local AI prompts and outputs are untrusted.
- Provider adapters receive only allowlisted source configuration.
- UI actions call application services; they do not execute SQL or shell commands directly.

## Controls

- No broker credentials or live-money capabilities.
- Resolve imported file paths and reject traversal outside an explicitly selected import destination.
- Limit file size, document type, parser time, and memory use for document ingestion.
- Do not execute macros, embedded scripts, shell commands, or active content in research documents.
- Validate all extracted values and model output against typed schemas and deterministic rules.
- Never let documents or AI output change allowlists, risk rules, permissions, or ledger records without a separate application-owned workflow.
- Keep logs free of secrets and unnecessary personal financial data.
- Use SQLite constraints, migrations, consistent backups, and restore tests.
- Audit state-changing portfolio, risk, configuration, and automation operations.

## Distribution gate

PySide6 is distributed under LGPL-3.0-only or GPL alternatives. Before binary distribution, review Qt/PySide obligations, any dynamically linked Qt modules/plugins, third-party notices, and any chosen commercial licensing. No legal compliance claim is made by this initial repository setup.
