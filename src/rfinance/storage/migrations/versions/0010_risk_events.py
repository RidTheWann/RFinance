# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Add append-only risk events, reviews and valuation history."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010_risk_events"
down_revision = "0009_financial_metrics"
branch_labels = None
depends_on = None

_RULES = (
    "'ELEVATED_DRAWDOWN', 'CRITICAL_DRAWDOWN', "
    "'SINGLE_INSTRUMENT_CONCENTRATION', 'SECTOR_CONCENTRATION', "
    "'ALLOCATION_DEVIATION', 'REVIEW_OVERDUE', 'VALUATION_INCOMPLETE', "
    "'PROHIBITED_ACTIVITY'"
)


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
        "risk_events",
        sa.Column("event_id", sa.String(length=64), primary_key=True),
        sa.Column("rule", sa.String(length=48), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("triggered_at_utc", sa.String(length=40), nullable=False),
        sa.Column("observed_value", sa.Text(), nullable=True),
        sa.Column("threshold", sa.Text(), nullable=True),
        sa.Column("valuation_methodology", sa.String(length=128), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("evidence_reference", sa.Text(), nullable=False),
        sa.Column("methodology_version", sa.String(length=64), nullable=False),
        sa.CheckConstraint(f"rule IN ({_RULES})", name="ck_risk_event_rule"),
        sa.CheckConstraint(
            "severity IN ('INFO', 'WARNING', 'CRITICAL')", name="ck_risk_event_severity"
        ),
        sa.CheckConstraint("length(triggered_at_utc) > 0", name="ck_risk_event_time"),
    )
    op.create_index("ix_risk_events_rule_time", "risk_events", ["rule", "triggered_at_utc"])
    _append_only("risk_events")

    op.create_table(
        "risk_reviews",
        sa.Column("review_id", sa.String(length=36), primary_key=True),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("reviewer_label", sa.String(length=256), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("evidence_reference", sa.Text(), nullable=False),
        sa.Column("reviewed_at_utc", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["risk_events.event_id"]),
        sa.CheckConstraint("length(review_id) > 0", name="ck_risk_review_id"),
        sa.CheckConstraint("length(reviewer_label) > 0", name="ck_risk_review_reviewer"),
        sa.CheckConstraint("length(notes) > 0", name="ck_risk_review_notes"),
        sa.CheckConstraint("length(evidence_reference) > 0", name="ck_risk_review_evidence"),
        sa.UniqueConstraint("event_id", name="uq_risk_review_event"),
    )
    op.create_index("ix_risk_reviews_event", "risk_reviews", ["event_id"])
    _append_only("risk_reviews")

    op.create_table(
        "portfolio_valuation_history",
        sa.Column("valuation_id", sa.String(length=64), primary_key=True),
        sa.Column("as_of_utc", sa.String(length=40), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("total_value", sa.Text(), nullable=False),
        sa.Column("is_complete", sa.Integer(), nullable=False),
        sa.Column("methodology_version", sa.String(length=64), nullable=False),
        sa.Column("positions_json", sa.Text(), nullable=False),
        sa.Column("allocation_json", sa.Text(), nullable=False),
        sa.CheckConstraint("length(currency) = 3", name="ck_valuation_history_currency"),
        sa.CheckConstraint("is_complete IN (0, 1)", name="ck_valuation_history_complete"),
    )
    op.create_index("ix_valuation_history_as_of", "portfolio_valuation_history", ["as_of_utc"])
    _append_only("portfolio_valuation_history")


def downgrade() -> None:
    for table in ("portfolio_valuation_history", "risk_reviews", "risk_events"):
        for action in ("update", "delete"):
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_{action}")
    op.drop_table("portfolio_valuation_history")
    op.drop_table("risk_reviews")
    op.drop_table("risk_events")
