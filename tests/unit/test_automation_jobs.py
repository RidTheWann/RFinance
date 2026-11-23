# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from __future__ import annotations

import pytest

from rfinance.domain.automation.jobs import (
    FORMULA_VERSION,
    JobDefinition,
    JobRun,
    JobStatus,
    can_transition,
    is_terminal,
    should_retry,
)


def definition(**overrides: object) -> JobDefinition:
    values: dict[str, object] = {
        "job_id": "BACKUP_CREATE",
        "display_name": "Create verified backup",
        "description": "Local backup with provenance",
    }
    values.update(overrides)
    return JobDefinition(**values)  # type: ignore[arg-type]


def test_job_definition_defaults_and_validation() -> None:
    job = definition()
    assert job.max_attempts == 1
    assert job.timeout_seconds == 60
    assert job.enabled is True
    with pytest.raises(ValueError, match="max_attempts"):
        definition(max_attempts=6)
    with pytest.raises(ValueError, match="timeout_seconds"):
        definition(timeout_seconds=0)
    with pytest.raises(ValueError, match="job_id"):
        definition(job_id="  ")


def test_run_state_transitions_are_explicit() -> None:
    assert can_transition(JobStatus.PENDING, JobStatus.RUNNING)
    assert can_transition(JobStatus.RUNNING, JobStatus.SUCCEEDED)
    assert can_transition(JobStatus.RUNNING, JobStatus.FAILED)
    assert not can_transition(JobStatus.RUNNING, JobStatus.PENDING)
    assert not can_transition(JobStatus.SUCCEEDED, JobStatus.FAILED)
    assert is_terminal(JobStatus.SUCCEEDED)
    assert is_terminal(JobStatus.CANCELLED)
    assert not is_terminal(JobStatus.RUNNING)


def test_retry_policy_uses_configured_attempt_limit() -> None:
    job = definition(max_attempts=3)
    assert should_retry(job, 1) is True
    assert should_retry(job, 2) is True
    assert should_retry(job, 3) is False
    with pytest.raises(ValueError, match="attempt"):
        should_retry(job, 4)


def test_job_run_carries_methodology_and_rejects_invalid_data() -> None:
    run = JobRun(
        run_id="run-1",
        job_id="BACKUP_CREATE",
        status=JobStatus.RUNNING,
        attempt=1,
        started_at_utc="2026-11-23T12:00:00+00:00",
    )
    assert run.methodology_version == FORMULA_VERSION
    with pytest.raises(ValueError, match="attempt"):
        JobRun("r", "j", JobStatus.PENDING, 0, "2026-11-23T12:00:00+00:00")
