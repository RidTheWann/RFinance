"""Local application paths and environment-backed configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppPaths:
    """Resolved per-user RFinance directories."""

    root: Path

    @classmethod
    def resolve(cls, root: str | Path | None = None) -> AppPaths:
        if root is not None:
            resolved = Path(root).expanduser()
        elif configured := os.environ.get("RFINANCE_HOME"):
            resolved = Path(configured).expanduser()
        elif local_app_data := os.environ.get("LOCALAPPDATA"):
            resolved = Path(local_app_data).expanduser() / "RFinance"
        elif os.name == "nt":
            resolved = Path.home() / "AppData" / "Local" / "RFinance"
        else:
            resolved = Path.home() / ".local" / "share" / "RFinance"
        return cls(root=resolved.resolve())

    @property
    def database_dir(self) -> Path:
        return self.root / "Database"

    @property
    def database_file(self) -> Path:
        return self.database_dir / "rfinance.sqlite3"

    @property
    def documents_dir(self) -> Path:
        return self.root / "Documents"

    @property
    def cache_dir(self) -> Path:
        return self.root / "Cache"

    @property
    def reports_dir(self) -> Path:
        return self.root / "Reports"

    @property
    def backups_dir(self) -> Path:
        return self.root / "Backups"

    @property
    def logs_dir(self) -> Path:
        return self.root / "Logs"

    def ensure_directories(self) -> None:
        for directory in (
            self.database_dir,
            self.documents_dir,
            self.cache_dir,
            self.reports_dir,
            self.backups_dir,
            self.logs_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
