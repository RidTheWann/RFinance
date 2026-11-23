# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Persisted, non-secret AI configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rfinance.intelligence.client import AIConfig
from rfinance.storage.models.app_setting import AppSetting

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker

SETTING_KEY = "intelligence.api_key_provider"


@dataclass(frozen=True, slots=True)
class AISettings:
    provider: str = "OPENAI"
    model: str = "gpt-4o-mini"
    enabled: bool = False

    def __post_init__(self) -> None:
        AIConfig(provider=self.provider, model=self.model)


class AISettingsService:
    """Store only model choice and enablement; the API key stays in the environment."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def get(self) -> AISettings:
        with self._sessions() as session:
            record = session.get(AppSetting, SETTING_KEY)
        if record is None:
            return AISettings()
        value = record.value_json
        return AISettings(
            provider=str(value.get("provider", "OPENAI")),
            model=str(value.get("model", "gpt-4o-mini")),
            enabled=bool(value.get("enabled", False)),
        )

    def save(self, settings: AISettings) -> None:
        with self._sessions.begin() as session:
            record = session.get(AppSetting, SETTING_KEY)
            if record is None:
                session.add(
                    AppSetting(
                        key=SETTING_KEY,
                        value_json={
                            "provider": settings.provider,
                            "model": settings.model,
                            "enabled": settings.enabled,
                        },
                    )
                )
            else:
                record.value_json = {
                    "provider": settings.provider,
                    "model": settings.model,
                    "enabled": settings.enabled,
                }
