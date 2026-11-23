# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Deterministic local automation job policy.

Formula version: ``automation-jobs-v1``. This module defines explicit job
contracts and run-state transitions. It never executes commands, expands a
source allowlist, or turns a failed run into a success.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

FORMULA_VERSION = "automation-jobs-v1"


class JobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


_TERMINAL = frozenset({JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED})
_ALLOWED: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.PENDING: frozenset({JobStatus.RUNNING, JobStatus.CANCELLED}),
    JobStatus.RUNNING: frozenset({JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED}),
    JobStatus.SUCCEEDED: frozenset(),
    JobStatus.FAILED: frozenset(),
    JobStatus.CANCELLED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class JobDefinition:
    """A deny-by-default registered job with explicit retry and timeout limits."""

    job_id: str
    display_name: str
    description: str
    max_attempts: int = 1
    timeout_seconds: int = 60
    enabled: bool = True

    def __post_init__(self) -> None:
        for name in ("job_id", "display_name", "description"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty")
        if not 1 <= self.max_attempts <= 5:
            raise ValueError("max_attempts must be between 1 and 5")
        if not 1 <= self.timeout_seconds <= 3600:
            raise ValueError("timeout_seconds must be between 1 and 3600")


@dataclass(frozen=True, slots=True)
class JobRun:
    """One immutable attempt of a registered job."""

    run_id: str
    job_id: str
    status: JobStatus
    attempt: int
    started_at_utc: str
    finished_at_utc: str | None = None
    error: str | None = None
    detail: str | None = None
    methodology_version: str = FORMULA_VERSION

    def __post_init__(self) -> None:
        if not self.run_id.strip() or not self.job_id.strip():
            raise ValueError("run_id and job_id must not be empty")
        if not 1 <= self.attempt <= 5:
            raise ValueError("attempt must be between 1 and 5")
        if not self.started_at_utc:
            raise ValueError("started_at_utc must not be empty")


def is_terminal(status: JobStatus) -> bool:
    return status in _TERMINAL


def can_transition(current: JobStatus, next_status: JobStatus) -> bool:
    return next_status in _ALLOWED[current]


def should_retry(definition: JobDefinition, attempt: int) -> bool:
    """Return whether another attempt is allowed after a failed attempt."""

    if not 1 <= attempt <= definition.max_attempts:
        raise ValueError("attempt is outside the configured retry range")
    return attempt < definition.max_attempts
