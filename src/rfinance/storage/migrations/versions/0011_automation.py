# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Add append-only automation job definitions and run records."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011_automation"
down_revision = "0010_risk_events"
branch_labels = None
depends_on = None

_STATUSES = "'PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED'"


def _append_only(table: str) -> None:
    for action in ("UPDATE", "DELETE"):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_no_{action.lower()}
            BEFORE {action} ON {table}
            BEGIN
                SELECT RAISE(ABORT, '{table} is append-only');
            END;
            """
        )


def upgrade() -> None:
    op.create_table(
        "automation_jobs",
        sa.Column("job_id", sa.String(length=64), primary_key=True),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("created_at_utc", sa.String(length=40), nullable=False),
        sa.CheckConstraint("length(display_name) > 0", name="ck_automation_job_name"),
        sa.CheckConstraint("enabled IN (0, 1)", name="ck_automation_job_enabled"),
        sa.CheckConstraint("max_attempts BETWEEN 1 AND 5", name="ck_automation_job_attempts"),
        sa.CheckConstraint("timeout_seconds BETWEEN 1 AND 3600", name="ck_automation_job_timeout"),
    )
    _append_only("automation_jobs")

    op.create_table(
        "automation_runs",
        sa.Column("run_id", sa.String(length=64), primary_key=True),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("started_at_utc", sa.String(length=40), nullable=False),
        sa.Column("finished_at_utc", sa.String(length=40), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("methodology_version", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["automation_jobs.job_id"]),
        sa.CheckConstraint(f"status IN ({_STATUSES})", name="ck_automation_run_status"),
        sa.CheckConstraint("attempt BETWEEN 1 AND 5", name="ck_automation_run_attempt"),
        sa.CheckConstraint("length(started_at_utc) > 0", name="ck_automation_run_start"),
    )
    op.create_index("ix_automation_runs_job_time", "automation_runs", ["job_id", "started_at_utc"])
    _append_only("automation_runs")


def downgrade() -> None:
    op.drop_table("automation_runs")
    op.drop_table("automation_jobs")
