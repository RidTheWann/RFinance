# Optional AI Research Assistance

Formula version: `ai-research-summary-v1`. ADR 0005 records the owner's
decision to replace the planned Ollama runtime with an API-key model provider.

## Boundaries

AI is optional and untrusted. All deterministic calculations, recommendations,
risk rules and ledger records remain authoritative and cannot be changed by a
model. Core functionality works fully offline with no API key.

- Endpoint allowlist: exactly one application-owned URL,
  `https://api.openai.com/v1/chat/completions`, verified against the official
  OpenAI API reference on 2026-11-23. No document, model output or UI input can
  add another endpoint.
- API key: read only from the `RFINANCE_AI_API_KEY` environment variable. It is
  never written to SQLite, backups, logs, reports, screenshots or settings.
- Persisted settings: provider, model and enablement only, under
  `application_settings` key `intelligence.api_key_provider`.
- Request: Chat Completions with `response_format = json_schema` (`strict`),
  temperature 0, `store = false`, no tools, and a system prompt that treats the
  evidence block as data rather than instructions.
- Output: parsed with the application-owned `ResearchSummary` Pydantic schema
  (`extra="forbid"`, bounded lengths) before any display. Invalid output is
  rejected, never repaired by guesswork.

## Use

1. Set `RFINANCE_AI_API_KEY` in the process environment before launching
   RFinance.
2. In Settings, enable optional AI research and choose a model (default
   `gpt-4o-mini`). The page shows only whether a key is present, never the key.
3. In the Research Center, paste stored evidence text and choose "Summarize
   evidence (optional AI)".

The network call occurs only on that explicit action. The result is labelled
`UNTRUSTED AI SUMMARY` and separated into `summary`, `facts`, `assumptions` and
`unanswered_questions`. It is a reading aid, not a recommendation, valuation or
evidence record.

## Not implemented

Document summarisation from files, automated research jobs, additional
providers (each requires allowlist verification), and any form of model-driven
state change remain out of scope.
