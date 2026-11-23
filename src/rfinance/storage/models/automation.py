# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Append-only automation job and run persistence models."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from rfinance.storage.models.base import Base

_STATUSES = "'PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED'"


class AutomationJobRecord(Base):
    """A registered, code-defined local job."""

    __tablename__ = "automation_jobs"
    __table_args__ = (
        CheckConstraint("length(display_name) > 0", name="ck_automation_job_name"),
        CheckConstraint("enabled IN (0, 1)", name="ck_automation_job_enabled"),
        CheckConstraint("max_attempts BETWEEN 1 AND 5", name="ck_automation_job_attempts"),
        CheckConstraint("timeout_seconds BETWEEN 1 AND 3600", name="ck_automation_job_timeout"),
    )

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at_utc: Mapped[str] = mapped_column(String(40), nullable=False)


class AutomationRunRecord(Base):
    """An immutable record of one job attempt."""

    __tablename__ = "automation_runs"
    __table_args__ = (
        CheckConstraint(f"status IN ({_STATUSES})", name="ck_automation_run_status"),
        CheckConstraint("attempt BETWEEN 1 AND 5", name="ck_automation_run_attempt"),
        CheckConstraint("length(started_at_utc) > 0", name="ck_automation_run_start"),
        Index("ix_automation_runs_job_time", "job_id", "started_at_utc"),
    )

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at_utc: Mapped[str] = mapped_column(String(40), nullable=False)
    finished_at_utc: Mapped[str | None] = mapped_column(String(40), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    methodology_version: Mapped[str] = mapped_column(String(64), nullable=False)
