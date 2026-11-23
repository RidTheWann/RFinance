# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Local job orchestration with append-only run records and retry policy."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from rfinance.domain.automation.jobs import (
    FORMULA_VERSION,
    JobRun,
    JobStatus,
    should_retry,
)
from rfinance.storage.models.automation import AutomationJobRecord, AutomationRunRecord

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from sqlalchemy.orm import Session, sessionmaker

    from rfinance.domain.automation.jobs import JobDefinition


@dataclass(frozen=True, slots=True)
class RunSummary:
    """A stored automation run for inspection."""

    run_id: str
    job_id: str
    status: str
    attempt: int
    started_at_utc: str
    finished_at_utc: str | None
    error: str | None
    detail: str | None
    methodology_version: str


class AutomationService:
    """Execute only registered, local, code-defined jobs and audit each attempt."""

    def __init__(
        self,
        sessions: sessionmaker[Session],
        definitions: Mapping[str, JobDefinition],
        operations: Mapping[str, Callable[[], str]],
    ) -> None:
        if set(definitions) != set(operations):
            raise ValueError("every registered job must have exactly one local operation")
        self._sessions = sessions
        self._definitions = dict(definitions)
        self._operations = dict(operations)

    def register_jobs(self) -> None:
        """Register configured jobs idempotently; definitions remain code-owned."""

        moment = datetime.now(UTC).isoformat()
        with self._sessions.begin() as session:
            for definition in self._definitions.values():
                if session.get(AutomationJobRecord, definition.job_id) is None:
                    session.add(
                        AutomationJobRecord(
                            job_id=definition.job_id,
                            display_name=definition.display_name,
                            description=definition.description,
                            enabled=1 if definition.enabled else 0,
                            max_attempts=definition.max_attempts,
                            timeout_seconds=definition.timeout_seconds,
                            created_at_utc=moment,
                        )
                    )

    def definitions(self) -> tuple[JobDefinition, ...]:
        return tuple(self._definitions.values())

    def run(
        self,
        job_id: str,
        *,
        started_at: datetime | None = None,
    ) -> JobRun:
        """Run a registered job, recording every attempt with retry semantics."""

        definition = self._definitions.get(job_id)
        if definition is None or not definition.enabled:
            raise ValueError(f"job is not registered or is disabled: {job_id}")
        moment = started_at or datetime.now(UTC)
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("started_at must be timezone-aware")
        moment_utc = moment.astimezone(UTC)
        operation = self._operations[job_id]

        last: JobRun | None = None
        for attempt in range(1, definition.max_attempts + 1):
            run_id = hashlib.sha256(
                f"{job_id}|{moment_utc.isoformat()}|{attempt}".encode()
            ).hexdigest()[:32]
            record = AutomationRunRecord(
                run_id=run_id,
                job_id=job_id,
                status=JobStatus.RUNNING.value,
                attempt=attempt,
                started_at_utc=moment_utc.isoformat(),
                finished_at_utc=None,
                error=None,
                detail=None,
                methodology_version=FORMULA_VERSION,
            )
            with self._sessions.begin() as session:
                session.add(record)

            finished = datetime.now(UTC)
            try:
                detail = operation()
                if not isinstance(detail, str):
                    raise TypeError("job operation must return a detail string")
                self._finish(
                    run_id,
                    definition.job_id,
                    attempt,
                    moment_utc.isoformat(),
                    JobStatus.SUCCEEDED,
                    finished,
                    detail=detail,
                )
                last = JobRun(
                    run_id=run_id,
                    job_id=job_id,
                    status=JobStatus.SUCCEEDED,
                    attempt=attempt,
                    started_at_utc=moment_utc.isoformat(),
                    finished_at_utc=finished.isoformat(),
                    detail=detail,
                )
                return last
            except Exception as error:
                message = f"{type(error).__name__}: {error}"
                self._finish(
                    run_id,
                    definition.job_id,
                    attempt,
                    moment_utc.isoformat(),
                    JobStatus.FAILED,
                    finished,
                    error=message,
                )
                last = JobRun(
                    run_id=run_id,
                    job_id=job_id,
                    status=JobStatus.FAILED,
                    attempt=attempt,
                    started_at_utc=moment_utc.isoformat(),
                    finished_at_utc=finished.isoformat(),
                    error=message,
                )
                if not should_retry(definition, attempt):
                    return last
        assert last is not None
        return last

    def _finish(
        self,
        run_id: str,
        job_id: str,
        attempt: int,
        started_at_utc: str,
        status: JobStatus,
        finished: datetime,
        *,
        detail: str | None = None,
        error: str | None = None,
    ) -> None:
        # Run rows are append-only, so completion is a new audit row with a
        # derived ID. The original RUNNING row remains as the start evidence.
        completion_id = hashlib.sha256(f"{run_id}|{status.value}".encode()).hexdigest()[:32]
        with self._sessions.begin() as session:
            session.add(
                AutomationRunRecord(
                    run_id=completion_id,
                    job_id=job_id,
                    status=status.value,
                    attempt=attempt,
                    started_at_utc=started_at_utc,
                    finished_at_utc=finished.astimezone(UTC).isoformat(),
                    detail=detail,
                    error=error,
                    methodology_version=FORMULA_VERSION,
                )
            )

    def recent_runs(self, *, limit: int = 50) -> tuple[RunSummary, ...]:
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        with self._sessions() as session:
            rows = session.scalars(
                select(AutomationRunRecord)
                .order_by(
                    AutomationRunRecord.started_at_utc.desc(),
                    AutomationRunRecord.run_id.desc(),
                )
                .limit(limit)
            ).all()
        return tuple(
            RunSummary(
                run_id=row.run_id,
                job_id=row.job_id,
                status=row.status,
                attempt=row.attempt,
                started_at_utc=row.started_at_utc,
                finished_at_utc=row.finished_at_utc,
                error=row.error,
                detail=row.detail,
                methodology_version=row.methodology_version,
            )
            for row in rows
        )
