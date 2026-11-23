# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Consistent online SQLite backup, verification and non-destructive restore.

Formula version: ``sqlite-backup-v1``. Backups use SQLite's online backup API
rather than copying an open database file. A sidecar manifest records the
source, creation time, digest and schema version; verification compares the
recomputed digest with that manifest. Restore never overwrites an existing
database — it writes a verified copy to a new location so user data cannot be
destroyed by a mistaken selection.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

FORMULA_VERSION = "sqlite-backup-v1"
_MANIFEST_SUFFIX = ".manifest.json"


@dataclass(frozen=True, slots=True)
class BackupVerification:
    """Observed properties of a backup file, never an assumed success."""

    path: Path
    sha256: str
    size_bytes: int
    integrity_check: str
    alembic_version: str | None
    ledger_event_count: int
    manifest_matches: bool | None
    created_at_utc: str | None

    @property
    def is_ok(self) -> bool:
        return (
            self.integrity_check == "ok"
            and self.alembic_version is not None
            and self.manifest_matches is not False
        )


@dataclass(frozen=True, slots=True)
class RestoreResult:
    """A verified database copy written to a new location."""

    path: Path
    sha256: str
    alembic_version: str | None
    ledger_event_count: int
    integrity_check: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_path(path: Path) -> Path:
    return path.with_name(path.name + _MANIFEST_SUFFIX)


def _read_manifest(path: Path) -> Mapping[str, object] | None:
    manifest_file = _manifest_path(path)
    if not manifest_file.is_file():
        return None
    data = json.loads(manifest_file.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("backup manifest must be a JSON object")
    return data


def _inspect(path: Path) -> tuple[str, str | None, int]:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        integrity = " ".join(row[0] for row in connection.execute("PRAGMA integrity_check"))
        has_version = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'alembic_version'"
        ).fetchone()
        version = (
            connection.execute("SELECT version_num FROM alembic_version LIMIT 1").fetchone()[0]
            if has_version
            else None
        )
        has_ledger = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'portfolio_ledger_events'"
        ).fetchone()
        count = (
            int(connection.execute("SELECT COUNT(*) FROM portfolio_ledger_events").fetchone()[0])
            if has_ledger
            else 0
        )
        return integrity, version, count
    finally:
        connection.close()


def verify_backup(path: Path) -> BackupVerification:
    """Open a backup read-only and report its measured properties."""

    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"backup file does not exist: {resolved}")
    integrity, version, count = _inspect(resolved)
    manifest = _read_manifest(resolved)
    manifest_matches: bool | None = None
    created_at: str | None = None
    if manifest is not None:
        recorded = manifest.get("sha256")
        manifest_matches = isinstance(recorded, str) and recorded == _sha256(resolved)
        stamp = manifest.get("created_at_utc")
        created_at = stamp if isinstance(stamp, str) else None
    return BackupVerification(
        path=resolved,
        sha256=_sha256(resolved),
        size_bytes=resolved.stat().st_size,
        integrity_check=integrity,
        alembic_version=version,
        ledger_event_count=count,
        manifest_matches=manifest_matches,
        created_at_utc=created_at,
    )


class BackupService:
    """Create and restore verified local backups of the SQLite database."""

    def __init__(self, database_file: Path, backups_dir: Path) -> None:
        self._database_file = database_file.resolve()
        self._backups_dir = backups_dir.resolve()

    @property
    def backups_dir(self) -> Path:
        return self._backups_dir

    def create_backup(self, *, name: str | None = None) -> BackupVerification:
        """Create a consistent backup plus provenance manifest."""

        if not self._database_file.is_file():
            raise FileNotFoundError(f"database does not exist: {self._database_file}")
        self._backups_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        filename = f"rfinance-{stamp}.sqlite3" if name is None else f"{name}.sqlite3"
        target = self._backups_dir / filename
        if target.exists():
            raise FileExistsError(f"backup already exists: {target}")

        source = sqlite3.connect(f"file:{self._database_file}?mode=ro", uri=True)
        destination = sqlite3.connect(target)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()

        verification = verify_backup(target)
        manifest = {
            "methodology_version": FORMULA_VERSION,
            "created_at_utc": datetime.now(UTC).isoformat(),
            "source_database": str(self._database_file),
            "sha256": verification.sha256,
            "alembic_version": verification.alembic_version,
            "ledger_event_count": verification.ledger_event_count,
        }
        _manifest_path(target).write_text(
            json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
        )
        return verify_backup(target)

    def restore_to(self, backup_path: Path, target_dir: Path) -> RestoreResult:
        """Copy a verified backup into a new folder without overwriting data."""

        source_verification = verify_backup(backup_path)
        if not source_verification.is_ok:
            raise ValueError("backup verification failed; restore was not attempted")
        destination_dir = target_dir.resolve()
        destination_dir.mkdir(parents=True, exist_ok=True)
        target = destination_dir / "rfinance.sqlite3"
        if target.exists():
            raise FileExistsError(f"refusing to overwrite existing database: {target}")

        source = sqlite3.connect(f"file:{source_verification.path}?mode=ro", uri=True)
        destination = sqlite3.connect(target)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()

        restored = verify_backup(target)
        if restored.sha256 != source_verification.sha256:
            target.unlink(missing_ok=True)
            raise ValueError("restored database digest does not match the backup")
        return RestoreResult(
            path=target,
            sha256=restored.sha256,
            alembic_version=restored.alembic_version,
            ledger_event_count=restored.ledger_event_count,
            integrity_check=restored.integrity_check,
        )
