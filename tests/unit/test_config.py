from pathlib import Path

from rfinance.core.config import AppPaths


def test_resolve_uses_explicit_path(tmp_path: Path) -> None:
    paths = AppPaths.resolve(tmp_path / "custom-rfinance")
    assert paths.root == (tmp_path / "custom-rfinance").resolve()
    assert paths.database_file.name == "rfinance.sqlite3"


def test_resolve_uses_environment_override(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("RFINANCE_HOME", str(tmp_path / "from-env"))
    paths = AppPaths.resolve()
    assert paths.root == (tmp_path / "from-env").resolve()


def test_ensure_directories_creates_persistent_layout(tmp_path: Path) -> None:
    paths = AppPaths.resolve(tmp_path / "rfinance")
    paths.ensure_directories()
    assert paths.database_dir.is_dir()
    assert paths.documents_dir.is_dir()
    assert paths.cache_dir.is_dir()
    assert paths.backups_dir.is_dir()
    assert paths.logs_dir.is_dir()
