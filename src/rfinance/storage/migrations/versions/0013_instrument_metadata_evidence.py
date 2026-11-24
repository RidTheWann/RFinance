# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Add append-only sampling-frequency and adjustment-evidence decisions."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013_instrument_metadata_evidence"
down_revision = "0012_instrument_category"
branch_labels = None
depends_on = None

_FREQUENCIES = "'DAILY', 'WEEKLY', 'MONTHLY', 'INTRADAY', 'UNKNOWN_AS_SUPPLIED'"
_ADJUSTMENTS = "'NONE_CONFIRMED', 'ADJUSTED', 'UNKNOWN_AS_SUPPLIED'"
_DECISIONS = "'VERIFIED', 'REJECTED'"


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
        "instrument_metadata_events",
        sa.Column("event_id", sa.String(length=64), primary_key=True),
        sa.Column("instrument_id", sa.String(length=128), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("sampling_frequency", sa.String(length=32), nullable=False),
        sa.Column("adjustment_status", sa.String(length=32), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("reviewer_label", sa.String(length=256), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("evidence_reference", sa.Text(), nullable=False),
        sa.Column("evidence_sha256", sa.String(length=64), nullable=False),
        sa.Column("decided_at_utc", sa.String(length=40), nullable=False),
        sa.Column("methodology_version", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["instrument_id"], ["instrument_registry.instrument_id"]),
        sa.CheckConstraint(
            f"sampling_frequency IN ({_FREQUENCIES})",
            name="ck_instrument_metadata_frequency",
        ),
        sa.CheckConstraint(
            f"adjustment_status IN ({_ADJUSTMENTS})",
            name="ck_instrument_metadata_adjustment",
        ),
        sa.CheckConstraint(f"decision IN ({_DECISIONS})", name="ck_instrument_metadata_decision"),
        sa.CheckConstraint("length(source_id) > 0", name="ck_instrument_metadata_source"),
        sa.CheckConstraint("length(decided_at_utc) > 0", name="ck_instrument_metadata_time"),
    )
    op.create_index(
        "ix_instrument_metadata_instrument_source_time",
        "instrument_metadata_events",
        ["instrument_id", "source_id", "decided_at_utc"],
    )
    _append_only("instrument_metadata_events")


def downgrade() -> None:
    op.drop_table("instrument_metadata_events")
