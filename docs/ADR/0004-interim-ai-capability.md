# ADR 0004 — Interim AI capability

- Status: Accepted
- Date: 2026-11-23

## Context

RFinance specifies hybrid intelligence: deterministic financial engines remain
authoritative, with optional local AI (initially Ollama) for document
summarisation, extraction and research synthesis. No Ollama runtime or model is
provisioned in the current environment, and automatic model downloads are
prohibited without user awareness.

## Decision

For this development phase, the AI research role is fulfilled by the coding
assistant working on the repository. No Ollama client, model configuration or
AI-owned state mutation is introduced. The deterministic engines retain sole
authority over all numerical results, recommendations and risk controls.

## Consequences

- No new dependency, model download or GPU requirement is added.
- The product remains fully functional without AI, as required.
- Product-side AI features (local inference, document extraction, research
  synthesis) stay deferred and are recorded as such in `ROADMAP.md`.
- This decision is temporary and is revisited when the owner requests native
  local inference.
