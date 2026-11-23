# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from rfinance.application.portfolio_ledger import PortfolioLedgerService
from rfinance.security.backup import BackupService, verify_backup
from rfinance.storage.database import Database
from rfinance.storage.repositories.portfolio_ledger import LedgerRepository


def _database(path: Path) -> Database:
    database = Database.open(path)
    database.upgrade()
    return database


def test_backup_is_verified_with_provenance(tmp_path: Path) -> None:
    database = _database(tmp_path / "data" / "rfinance.sqlite3")
    try:
        ledger = PortfolioLedgerService(LedgerRepository(database.sessions), lot_sizes={})
        ledger.initialize_portfolio(Decimal("5000000"))
        service = BackupService(
            Path(str(database.engine.url.database)), tmp_path / "data" / "Backups"
        )

        backup = service.create_backup(name="checkpoint")

        assert backup.is_ok is True
        assert backup.integrity_check == "ok"
        assert backup.alembic_version == "0010_risk_events"
        assert backup.ledger_event_count == 1
        assert backup.manifest_matches is True
        assert len(backup.sha256) == 64
        assert backup.path.name == "checkpoint.sqlite3"
        assert backup.path.with_name("checkpoint.sqlite3.manifest.json").is_file()
    finally:
        database.close()


def test_restore_creates_a_new_verified_database(tmp_path: Path) -> None:
    database = _database(tmp_path / "data" / "rfinance.sqlite3")
    try:
        ledger = PortfolioLedgerService(LedgerRepository(database.sessions), lot_sizes={})
        ledger.initialize_portfolio(Decimal("5000000"))
        service = BackupService(
            Path(str(database.engine.url.database)), tmp_path / "data" / "Backups"
        )
        backup = service.create_backup(name="restore-source")

        restored = service.restore_to(backup.path, tmp_path / "restored")

        assert restored.sha256 == backup.sha256
        assert restored.ledger_event_count == 1
        assert restored.integrity_check == "ok"
        copy = _database(restored.path)
        try:
            copy_ledger = PortfolioLedgerService(LedgerRepository(copy.sessions), lot_sizes={})
            snapshot = copy_ledger.snapshot()
            assert snapshot.cash_balance == Decimal("5000000")
            assert len(copy_ledger.events()) == 1
        finally:
            copy.close()
    finally:
        database.close()


def test_restore_refuses_to_overwrite_existing_database(tmp_path: Path) -> None:
    database = _database(tmp_path / "data" / "rfinance.sqlite3")
    try:
        service = BackupService(
            Path(str(database.engine.url.database)), tmp_path / "data" / "Backups"
        )
        backup = service.create_backup(name="no-overwrite")

        service.restore_to(backup.path, tmp_path / "restored")
        with pytest.raises(FileExistsError, match="refusing to overwrite"):
            service.restore_to(backup.path, tmp_path / "restored")
    finally:
        database.close()


def test_manifest_tampering_makes_verification_fail(tmp_path: Path) -> None:
    database = _database(tmp_path / "data" / "rfinance.sqlite3")
    try:
        service = BackupService(
            Path(str(database.engine.url.database)), tmp_path / "data" / "Backups"
        )
        backup = service.create_backup(name="tampered")
        manifest_path = backup.path.with_name("tampered.sqlite3.manifest.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        verification = verify_backup(backup.path)

        assert verification.manifest_matches is False
        assert verification.is_ok is False
        with pytest.raises(ValueError, match="verification failed"):
            service.restore_to(backup.path, tmp_path / "restored")
        assert not (tmp_path / "restored" / "rfinance.sqlite3").exists()
    finally:
        database.close()


def test_missing_backup_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="backup file"):
        verify_backup(tmp_path / "missing.sqlite3")
