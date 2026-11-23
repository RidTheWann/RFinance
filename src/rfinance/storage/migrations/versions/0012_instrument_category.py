# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Add append-only instrument category and lot-size evidence decisions."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012_instrument_category"
down_revision = "0011_automation"
branch_labels = None
depends_on = None

_CATEGORIES = "'EQUITY_INDEX', 'DIVIDEND_EQUITY', 'MONEY_MARKET'"
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
        "instrument_category_events",
        sa.Column("event_id", sa.String(length=64), primary_key=True),
        sa.Column("instrument_id", sa.String(length=128), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("lot_size", sa.Text(), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("reviewer_label", sa.String(length=256), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("evidence_reference", sa.Text(), nullable=False),
        sa.Column("evidence_sha256", sa.String(length=64), nullable=False),
        sa.Column("decided_at_utc", sa.String(length=40), nullable=False),
        sa.Column("methodology_version", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["instrument_id"], ["instrument_registry.instrument_id"]),
        sa.CheckConstraint(f"category IN ({_CATEGORIES})", name="ck_instrument_category"),
        sa.CheckConstraint(f"decision IN ({_DECISIONS})", name="ck_instrument_category_decision"),
        sa.CheckConstraint("length(lot_size) > 0", name="ck_instrument_category_lot"),
        sa.CheckConstraint("length(decided_at_utc) > 0", name="ck_instrument_category_time"),
    )
    op.create_index(
        "ix_instrument_category_instrument_time",
        "instrument_category_events",
        ["instrument_id", "decided_at_utc"],
    )
    _append_only("instrument_category_events")


def downgrade() -> None:
    op.drop_table("instrument_category_events")
