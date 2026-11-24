# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""API-key client for an allowlisted OpenAI-compatible Chat Completions endpoint.

Verified against the official OpenAI API reference (2026-11-23):
``POST /chat/completions`` with a Bearer token and an optional
``response_format`` JSON schema. No arbitrary URL can be supplied by a user,
document or model. The API key is read from the process environment and is
never logged or persisted by RFinance.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

if TYPE_CHECKING:
    from collections.abc import Mapping

ALLOWED_ENDPOINTS: dict[str, str] = {
    "OPENAI": "https://api.openai.com/v1/chat/completions",
}
API_KEY_ENV = "RFINANCE_AI_API_KEY"
FORMULA_VERSION = "api-key-ai-client-v1"
MAX_RESPONSE_BYTES = 256 * 1024


@dataclass(frozen=True, slots=True)
class AIConfig:
    """Non-secret model configuration; the key is never part of this object."""

    provider: str = "OPENAI"
    model: str = "gpt-4o-mini"
    timeout_seconds: int = 30

    def __post_init__(self) -> None:
        if self.provider not in ALLOWED_ENDPOINTS:
            raise ValueError("provider is not in the application-owned allowlist")
        if not self.model.strip():
            raise ValueError("model must not be empty")
        if not 1 <= self.timeout_seconds <= 300:
            raise ValueError("timeout_seconds must be between 1 and 300")

    @property
    def endpoint(self) -> str:
        return ALLOWED_ENDPOINTS[self.provider]


def api_key_from_environment() -> str | None:
    """Return the configured key or None; never echo or log its value."""

    import os

    value = os.environ.get(API_KEY_ENV, "").strip()
    return value or None


def complete_json(
    config: AIConfig,
    *,
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    schema_name: str,
    schema: Mapping[str, object],
) -> dict[str, object]:
    """Call the allowlisted endpoint and return a parsed JSON object."""

    if not api_key.strip():
        raise ValueError("an API key is required")
    body = {
        "model": config.model,
        "temperature": 0,
        "store": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "schema": dict(schema),
                "strict": True,
            },
        },
    }
    request = Request(
        config.endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        # B310 is expected here: the URL comes only from the application-owned
        # ALLOWED_ENDPOINTS table (fixed HTTPS values), never from user input.
        with urlopen(  # nosec B310
            request, timeout=config.timeout_seconds
        ) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        # Do not include headers or the request object: they contain the key.
        raise RuntimeError(f"AI request failed: {type(error).__name__}") from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("AI response exceeded the configured size limit")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("AI response was not a JSON object")
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("AI response had no assistant message") from error
    if not isinstance(content, str):
        raise ValueError("AI message content was not text")
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("AI message content was not a JSON object")
    return parsed
