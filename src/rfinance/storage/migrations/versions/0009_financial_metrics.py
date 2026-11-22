# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Add reviewed financial statement metrics with provenance."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_financial_metrics"
down_revision = "0008_confirmed_dividend_receipts"
branch_labels = None
depends_on = None

_QUALITY = "'VERIFIED', 'UNVERIFIED', 'ESTIMATED', 'STALE', 'INCOMPLETE', 'REJECTED', 'SIMULATED'"


def upgrade() -> None:
    op.create_table(
        "financial_metrics",
        sa.Column("metric_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "instrument_id",
            sa.String(length=128),
            sa.ForeignKey("instrument_registry.instrument_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            sa.String(length=36),
            sa.ForeignKey("source_registry.source_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("metric_name", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("unit", sa.String(length=64), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("period_start", sa.String(length=10), nullable=False),
        sa.Column("period_end", sa.String(length=10), nullable=False),
        sa.Column("reporting_basis", sa.String(length=16), nullable=False),
        sa.Column("quality_status", sa.String(length=24), nullable=False),
        sa.Column("acquired_at_utc", sa.String(length=40), nullable=False),
        sa.Column("source_document_ref", sa.String(length=1024), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("transformation_version", sa.String(length=64), nullable=False),
        sa.Column("created_at_utc", sa.String(length=40), nullable=False),
        sa.CheckConstraint(f"quality_status IN ({_QUALITY})", name="ck_financial_metric_quality"),
        sa.CheckConstraint("length(currency) = 3", name="ck_financial_metric_currency"),
        sa.CheckConstraint(
            "reporting_basis IN ('ANNUAL', 'QUARTERLY', 'TTM')",
            name="ck_financial_metric_basis",
        ),
        sa.UniqueConstraint(
            "source_id",
            "instrument_id",
            "metric_name",
            "period_start",
            "period_end",
            "reporting_basis",
            name="uq_financial_metric_observation",
        ),
    )
    op.create_index(
        "ix_financial_metric_instrument_name",
        "financial_metrics",
        ["instrument_id", "metric_name", "period_end"],
    )
    op.create_table(
        "financial_metric_reviews",
        sa.Column("review_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "metric_id",
            sa.String(length=36),
            sa.ForeignKey("financial_metrics.metric_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("previous_quality", sa.String(length=24), nullable=False),
        sa.Column("decision", sa.String(length=24), nullable=False),
        sa.Column("reviewed_at_utc", sa.String(length=40), nullable=False),
        sa.Column("reviewer_label", sa.String(length=256), nullable=False),
        sa.Column("evidence_reference", sa.String(length=1024), nullable=False),
        sa.Column("evidence_sha256", sa.String(length=64), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("reviewed_metadata_json", sa.Text(), nullable=True),
        sa.CheckConstraint(
            f"previous_quality IN ({_QUALITY})", name="ck_financial_review_previous_quality"
        ),
        sa.CheckConstraint(
            "decision IN ('VERIFIED', 'REJECTED')", name="ck_financial_review_decision"
        ),
        sa.CheckConstraint(
            "length(evidence_sha256) = 64 AND lower(evidence_sha256) NOT GLOB '*[^0-9a-f]*'",
            name="ck_financial_review_sha256",
        ),
    )
    op.create_index(
        "ix_financial_review_metric_time",
        "financial_metric_reviews",
        ["metric_id", "reviewed_at_utc"],
    )
    for table in ("financial_metrics", "financial_metric_reviews"):
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


def downgrade() -> None:
    for table in ("financial_metric_reviews", "financial_metrics"):
        for action in ("update", "delete"):
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_{action}")
    op.drop_index("ix_financial_review_metric_time", table_name="financial_metric_reviews")
    op.drop_table("financial_metric_reviews")
    op.drop_index("ix_financial_metric_instrument_name", table_name="financial_metrics")
    op.drop_table("financial_metrics")
