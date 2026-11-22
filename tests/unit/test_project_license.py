# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Regression checks for the project's machine-readable license metadata."""

from __future__ import annotations

import tomllib
from importlib.metadata import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPDX_HEADER = "SPDX-License-Identifier: GPL-3.0-only"


def test_license_file_contains_verbatim_gplv3() -> None:
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "GNU GENERAL PUBLIC LICENSE" in license_text
    assert "Version 3, 29 June 2007" in license_text
    assert "END OF TERMS AND CONDITIONS" in license_text


def test_pyproject_declares_spdx_expression_and_license_files() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]
    assert project["license"] == "GPL-3.0-only"
    assert project["license-files"] == ["LICENSE"]
    build_requires = pyproject["build-system"]["requires"]
    assert any("setuptools>=77" in requirement for requirement in build_requires)


def test_installed_distribution_exposes_license_expression() -> None:
    installed = metadata("rfinance")
    assert installed.get("License-Expression") == "GPL-3.0-only"
    assert installed.get_all("License-File") == ["LICENSE"]


def test_all_python_sources_carry_spdx_header() -> None:
    sources = sorted([*(ROOT / "src").rglob("*.py"), *(ROOT / "tests").rglob("*.py")])
    assert sources
    missing = [
        str(path.relative_to(ROOT))
        for path in sources
        if SPDX_HEADER not in path.read_text(encoding="utf-8")
    ]
    assert missing == []
