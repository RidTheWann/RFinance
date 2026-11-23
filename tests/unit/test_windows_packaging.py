# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_pyinstaller_is_pinned_as_a_development_dependency() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dev = data["project"]["optional-dependencies"]["dev"]
    assert any(item.startswith("pyinstaller>=") for item in dev)
    lock = (ROOT / "requirements.lock").read_text(encoding="utf-8")
    assert "pyinstaller==" in lock


def test_windows_build_assets_bundle_license_and_migrations() -> None:
    spec = (ROOT / "installer" / "windows" / "rfinance.spec").read_text(encoding="utf-8")
    script = (ROOT / "scripts" / "build_windows.ps1").read_text(encoding="utf-8")

    assert "MIGRATIONS" in spec
    assert "rfinance/storage/migrations" in spec
    assert "LICENSE" in spec
    assert "THIRD_PARTY_NOTICES.md" in spec
    assert "console=False" in spec
    assert "PyInstaller" in script
    assert "build_windows.ps1" in script or "rfinance.spec" in script
