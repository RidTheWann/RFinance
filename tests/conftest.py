from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def use_offscreen_qt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", os.environ.get("QT_QPA_PLATFORM", "offscreen"))
