# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Application-owned schemas for untrusted model output."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

FORMULA_VERSION = "ai-research-summary-v1"


class ResearchSummary(BaseModel):
    """A display-only research aid, never an authority on financial figures."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    summary: str = Field(min_length=1, max_length=2000)
    facts: list[str] = Field(default_factory=list, max_length=20)
    assumptions: list[str] = Field(default_factory=list, max_length=20)
    unanswered_questions: list[str] = Field(default_factory=list, max_length=20)


RESEARCH_SUMMARY_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "facts": {"type": "array", "items": {"type": "string"}},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "unanswered_questions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "facts", "assumptions", "unanswered_questions"],
    "additionalProperties": False,
}
