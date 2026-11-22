# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Add persisted evidence-linked recommendations."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_recommendations"
down_revision = "0006_dividend_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recommendations",
        sa.Column("recommendation_id", sa.String(length=36), primary_key=True),
        sa.Column("instrument_id", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("generated_at_utc", sa.String(length=40), nullable=False),
        sa.Column("evidence_ids_json", sa.Text(), nullable=False),
        sa.Column("risk_flags_json", sa.Text(), nullable=False),
        sa.Column("confidence_level", sa.String(length=64), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("invalidation_conditions_json", sa.Text(), nullable=False),
        sa.Column("data_freshness_utc", sa.String(length=40), nullable=True),
        sa.Column("methodology_version", sa.String(length=64), nullable=False),
        sa.Column("fundamental_assessment", sa.Text(), nullable=False),
        sa.Column("price_assessment", sa.Text(), nullable=False),
        sa.Column("dividend_assessment", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "action IN ('BUY_CANDIDATE', 'HOLD', 'WATCH', 'AVOID', 'INSUFFICIENT_DATA')",
            name="ck_recommendation_action",
        ),
        sa.CheckConstraint("length(instrument_id) > 0", name="ck_recommendation_instrument"),
        sa.CheckConstraint("length(confidence_level) > 0", name="ck_recommendation_confidence"),
    )
    op.create_index(
        "ix_recommendation_instrument_time",
        "recommendations",
        ["instrument_id", "generated_at_utc"],
    )
    for action in ("UPDATE", "DELETE"):
        trigger = f"trg_recommendations_no_{action.lower()}"
        op.execute(
            f"""
            CREATE TRIGGER {trigger}
            BEFORE {action} ON recommendations
            BEGIN
                SELECT RAISE(ABORT, 'recommendations is append-only');
            END;
            """
        )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_recommendations_no_update")
    op.execute("DROP TRIGGER IF EXISTS trg_recommendations_no_delete")
    op.drop_index("ix_recommendation_instrument_time", table_name="recommendations")
    op.drop_table("recommendations")
