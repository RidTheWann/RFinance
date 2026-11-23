# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from rfinance.application.automation import AutomationService
from rfinance.domain.automation.jobs import JobDefinition, JobStatus
from rfinance.storage.database import Database

if TYPE_CHECKING:
    from pathlib import Path

START = datetime(2026, 11, 23, 12, tzinfo=UTC)


def registered_job(**overrides: object) -> JobDefinition:
    values: dict[str, object] = {
        "job_id": "BACKUP_CREATE",
        "display_name": "Create verified backup",
        "description": "Local backup with provenance",
    }
    values.update(overrides)
    return JobDefinition(**values)  # type: ignore[arg-type]


def build_service(
    database: Database,
    definition: JobDefinition,
    operation: object,
) -> AutomationService:
    return AutomationService(
        database.sessions,
        definitions={definition.job_id: definition},
        operations={definition.job_id: operation},  # type: ignore[dict-item]
    )


def test_register_jobs_is_idempotent(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "automation.sqlite3")
    database.upgrade()
    try:
        service = build_service(database, registered_job(), lambda: "done")
        service.register_jobs()
        service.register_jobs()
        with database.sessions() as session:
            count = session.scalar(text("SELECT COUNT(*) FROM automation_jobs"))
        assert count == 1
    finally:
        database.close()


def test_successful_run_records_start_and_completion(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "automation-success.sqlite3")
    database.upgrade()
    try:
        service = build_service(database, registered_job(), lambda: "backup-1.sqlite3")
        service.register_jobs()
        run = service.run("BACKUP_CREATE", started_at=START)

        assert run.status is JobStatus.SUCCEEDED
        assert run.detail == "backup-1.sqlite3"
        statuses = [row.status for row in service.recent_runs()]
        assert sorted(statuses) == ["RUNNING", "SUCCEEDED"]
    finally:
        database.close()


def test_failed_run_retries_up_to_configured_attempts(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "automation-retry.sqlite3")
    database.upgrade()
    calls: list[int] = []

    def failing() -> str:
        calls.append(1)
        raise RuntimeError("source unavailable")

    try:
        service = build_service(database, registered_job(max_attempts=3), failing)
        service.register_jobs()
        run = service.run("BACKUP_CREATE", started_at=START)

        assert run.status is JobStatus.FAILED
        assert run.attempt == 3
        assert len(calls) == 3
        assert "source unavailable" in (run.error or "")
        statuses = sorted(row.status for row in service.recent_runs())
        assert statuses == ["FAILED", "FAILED", "FAILED", "RUNNING", "RUNNING", "RUNNING"]
    finally:
        database.close()


def test_run_rows_are_append_only(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "automation-append.sqlite3")
    database.upgrade()
    try:
        service = build_service(database, registered_job(), lambda: "ok")
        service.register_jobs()
        service.run("BACKUP_CREATE", started_at=START)
        with database.sessions.begin() as session, pytest.raises(IntegrityError):
            session.execute(text("UPDATE automation_runs SET status = 'SUCCEEDED'"))
    finally:
        database.close()


def test_definitions_and_operations_must_match(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "automation-mismatch.sqlite3")
    database.upgrade()
    try:
        with pytest.raises(ValueError, match="exactly one"):
            AutomationService(
                database.sessions,
                definitions={"A": registered_job(job_id="A")},
                operations={},
            )
    finally:
        database.close()
