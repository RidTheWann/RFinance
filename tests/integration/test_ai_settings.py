# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from sqlalchemy import text

from rfinance.intelligence.settings import AISettings, AISettingsService
from rfinance.storage.database import Database

if TYPE_CHECKING:
    from pathlib import Path


def test_ai_settings_persist_without_storing_a_key(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "ai-settings.sqlite3")
    database.upgrade()
    try:
        service = AISettingsService(database.sessions)
        assert service.get() == AISettings()

        service.save(AISettings(provider="OPENAI", model="gpt-4o-mini", enabled=True))
        assert service.get() == AISettings(provider="OPENAI", model="gpt-4o-mini", enabled=True)

        with database.sessions() as session:
            row = session.execute(
                text(
                    "SELECT value_json FROM application_settings "
                    "WHERE key = 'intelligence.api_key_provider'"
                )
            ).one()
        stored = row[0]
        if isinstance(stored, str):
            stored = json.loads(stored)
        assert "api_key" not in stored
        assert stored["enabled"] is True
    finally:
        database.close()
