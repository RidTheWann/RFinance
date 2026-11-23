# ADR 0005 — API-key AI provider replaces Ollama

- Status: Accepted (2026-11-23)
- Supersedes ADR 0004 (interim assistant role)

## Context

The owner decided that RFinance should support an API-key model provider
instead of a local Ollama runtime. The product invariants still require that
AI remain optional, subordinate to deterministic controls, and unable to become
a source of financial truth. No cloud key is needed for any core workflow.

## Decision

- Replace the planned Ollama integration with an OpenAI-compatible Chat
  Completions client using a Bearer API key.
- Allow exactly one application-owned endpoint:
  `https://api.openai.com/v1/chat/completions` (verified against the official
  OpenAI API reference on 2026-11-23). User documents, model output and UI
  input cannot add endpoints.
- Read the key only from the `RFINANCE_AI_API_KEY` environment variable. Never
  store it in SQLite, backups, logs, screenshots or reports. Persist only
  provider, model and enablement in `application_settings`.
- Use structured JSON output with an application-owned Pydantic schema
  (`ai-research-summary-v1`), strict validation and `extra="forbid"`.
- Wrap evidence in explicit untrusted-data delimiters, disable tools, set
  temperature 0, and treat every model string as display-only research aid.
  Model output cannot modify the ledger, valuation, risk controls or settings.

## Consequences

- Core functionality stays fully offline and usable without a key.
- Network use occurs only when the user explicitly enables AI and requests a
  summary; no automatic background calls are made.
- The endpoint allowlist must be extended deliberately after verifying official
  documentation for any additional provider.
- This is a paid external service from the user's perspective; RFinance does
  not manage billing, quotas or model availability.
