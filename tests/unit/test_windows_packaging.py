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
    assert "RFinance.exe" in script
    assert "--smoke-test" in script
    assert "Compress-Archive" in script
    assert "SHA256SUMS.txt" in script


def test_setup_script_selects_only_supported_python_runtimes() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    requires_python = pyproject["project"]["requires-python"]
    assert requires_python == ">=3.12,<3.16"

    script = (ROOT / "scripts" / "setup_windows.ps1").read_text(encoding="utf-8")

    # The interpreter gate must be derived from the supported range, never a
    # single hard-coded version.
    assert '[version]"3.12"' in script
    assert '[version]"3.16"' in script
    assert '[string]$Python = ""' in script  # no hard-coded interpreter default
    assert "[switch]$DryRun" in script
    assert "Dry run: no environment was created." in script
    installation = (ROOT / "docs" / "INSTALLATION.md").read_text(encoding="utf-8")
    assert "setup_windows.ps1" in installation


def test_inno_setup_is_per_user_and_preserves_application_data() -> None:
    iss = (ROOT / "installer" / "windows" / "rfinance.iss").read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in iss
    assert "DefaultDirName={localappdata}\\Programs\\RFinance" in iss
    assert "RFinance-Setup-{#AppVersion}-win-x64" in iss
    assert "{autoprograms}" in iss
    assert "{autodesktop}" in iss

    build = (ROOT / "scripts" / "build_windows.ps1").read_text(encoding="utf-8")
    assert "[switch]$CreateInstaller" in build
    assert "ISCC_PATH" in build
    assert "RFINANCE_HOME" in build
    assert "SHA256SUMS.txt" in build


def test_windows_package_workflow_builds_artifact_and_publishes_version_tags() -> None:
    workflow = (ROOT / ".github" / "workflows" / "windows-package.yml").read_text(encoding="utf-8")
    assert "windows-latest" in workflow
    assert "choco install innosetup" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "softprops/action-gh-release@v2" in workflow
    assert 'tags: ["v*"]' in workflow


def test_packaging_smoke_switch_bootstraps_database_without_gui() -> None:
    main = (ROOT / "src" / "rfinance" / "main.py").read_text(encoding="utf-8")
    assert '"--smoke-test"' in main
    assert "alembic_version" in main
    assert "context.close()" in main


def test_smoke_test_switch_runs_bootstrap_and_closes_context(monkeypatch) -> None:
    from types import SimpleNamespace

    import rfinance.main as main_module

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        @staticmethod
        def exec_driver_sql(statement: str):
            assert "alembic_version" in statement
            return SimpleNamespace(scalar_one_or_none=lambda: "0013_head")

    class _Engine:
        @staticmethod
        def connect():
            return _Connection()

    class _Logger:
        @staticmethod
        def info(*_args: object) -> None:
            return None

    closed: list[bool] = []
    context = SimpleNamespace(
        database=SimpleNamespace(engine=_Engine()),
        logger=_Logger(),
        close=lambda: closed.append(True),
    )
    monkeypatch.setattr(main_module, "create_application_context", lambda: context)

    assert main_module.main(["RFinance", "--smoke-test"]) == 0
    assert closed == [True]
