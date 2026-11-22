"""Add append-only observation review audit events."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_observation_review"
down_revision = "0004_instrument_master"
branch_labels = None
depends_on = None


def _create_append_only_triggers() -> None:
    for trigger, action in (
        ("trg_observation_review_events_no_update", "UPDATE"),
        ("trg_observation_review_events_no_delete", "DELETE"),
    ):
        op.execute(
            f"""
            CREATE TRIGGER {trigger}
            BEFORE {action} ON observation_review_events
            BEGIN
                SELECT RAISE(ABORT, 'observation_review_events is append-only');
            END;
            """
        )


def upgrade() -> None:
    op.create_table(
        "observation_review_events",
        sa.Column("review_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "observation_id",
            sa.String(length=36),
            sa.ForeignKey("market_observations.observation_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("instrument_id", sa.String(length=128), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("previous_quality", sa.String(length=24), nullable=False),
        sa.Column("decision", sa.String(length=24), nullable=False),
        sa.Column("reviewed_at_utc", sa.String(length=40), nullable=False),
        sa.Column("reviewer_label", sa.String(length=256), nullable=False),
        sa.Column("evidence_reference", sa.String(length=1024), nullable=False),
        sa.Column("evidence_sha256", sa.String(length=64), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("reviewed_metadata_json", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "previous_quality IN "
            "('VERIFIED', 'UNVERIFIED', 'ESTIMATED', 'STALE', 'INCOMPLETE', "
            "'REJECTED', 'SIMULATED')",
            name="ck_observation_review_previous_quality",
        ),
        sa.CheckConstraint(
            "decision IN ('VERIFIED', 'REJECTED')",
            name="ck_observation_review_decision",
        ),
        sa.CheckConstraint(
            "length(trim(reviewer_label)) > 0",
            name="ck_observation_review_reviewer",
        ),
        sa.CheckConstraint(
            "length(trim(evidence_reference)) > 0",
            name="ck_observation_review_evidence",
        ),
        sa.CheckConstraint(
            "length(evidence_sha256) = 64 AND lower(evidence_sha256) NOT GLOB '*[^0-9a-f]*'",
            name="ck_observation_review_evidence_sha256",
        ),
        sa.CheckConstraint(
            "length(trim(notes)) > 0",
            name="ck_observation_review_notes",
        ),
        sa.UniqueConstraint(
            "review_id",
            "observation_id",
            name="uq_observation_review_id_observation",
        ),
    )
    op.create_index(
        "ix_observation_review_observation_time",
        "observation_review_events",
        ["observation_id", "reviewed_at_utc"],
    )
    _create_append_only_triggers()


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_observation_review_events_no_update")
    op.execute("DROP TRIGGER IF EXISTS trg_observation_review_events_no_delete")
    op.drop_index(
        "ix_observation_review_observation_time",
        table_name="observation_review_events",
    )
    op.drop_table("observation_review_events")
