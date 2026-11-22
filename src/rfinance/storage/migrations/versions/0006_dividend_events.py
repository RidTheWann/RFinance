"""Add append-only dividend events and evidence-backed review ledger."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_dividend_events"
down_revision = "0005_observation_review"
branch_labels = None
depends_on = None

_QUALITY_VALUES = (
    "'VERIFIED', 'UNVERIFIED', 'ESTIMATED', 'STALE', 'INCOMPLETE', 'REJECTED', 'SIMULATED'"
)


def _create_append_only_triggers() -> None:
    for table in ("dividend_events", "dividend_review_events"):
        for action in ("UPDATE", "DELETE"):
            trigger = f"trg_{table}_no_{action.lower()}"
            op.execute(
                f"""
                CREATE TRIGGER {trigger}
                BEFORE {action} ON {table}
                BEGIN
                    SELECT RAISE(ABORT, '{table} is append-only');
                END;
                """
            )


def upgrade() -> None:
    op.create_table(
        "dividend_events",
        sa.Column("event_id", sa.String(length=36), primary_key=True),
        sa.Column("event_key", sa.String(length=128), nullable=False),
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
        sa.Column("dividend_type", sa.String(length=16), nullable=False),
        sa.Column("event_status", sa.String(length=16), nullable=False),
        sa.Column("amount_per_share", sa.Text(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("ex_date", sa.String(length=10), nullable=False),
        sa.Column("cum_date", sa.String(length=10), nullable=True),
        sa.Column("record_date", sa.String(length=10), nullable=True),
        sa.Column("payment_date", sa.String(length=10), nullable=True),
        sa.Column("quality_status", sa.String(length=24), nullable=False),
        sa.Column("acquired_at_utc", sa.String(length=40), nullable=False),
        sa.Column("announced_at_utc", sa.String(length=40), nullable=True),
        sa.Column("reporting_period_start", sa.String(length=10), nullable=True),
        sa.Column("reporting_period_end", sa.String(length=10), nullable=True),
        sa.Column("source_document_ref", sa.String(length=1024), nullable=True),
        sa.Column("original_value", sa.String(length=256), nullable=True),
        sa.Column("unit", sa.String(length=64), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("transformation_version", sa.String(length=64), nullable=False),
        sa.Column("created_at_utc", sa.String(length=40), nullable=False),
        sa.UniqueConstraint("source_id", "event_key", name="uq_dividend_event_source_key"),
        sa.CheckConstraint(
            "dividend_type IN ('CASH', 'INTERIM', 'FINAL', 'SPECIAL', 'STOCK', 'RIGHTS')",
            name="ck_dividend_event_type",
        ),
        sa.CheckConstraint(
            "event_status IN "
            "('ANNOUNCED', 'CONFIRMED', 'HISTORICAL', 'ESTIMATED', 'SIMULATED', 'CANCELLED')",
            name="ck_dividend_event_status",
        ),
        sa.CheckConstraint(
            f"quality_status IN ({_QUALITY_VALUES})",
            name="ck_dividend_event_quality_status",
        ),
        sa.CheckConstraint("length(currency) = 3", name="ck_dividend_event_currency_length"),
        sa.CheckConstraint("length(ex_date) = 10", name="ck_dividend_event_ex_date_format"),
        sa.CheckConstraint(
            "amount_per_share IS NULL OR length(amount_per_share) > 0",
            name="ck_dividend_event_amount_present",
        ),
    )
    op.create_index(
        "ix_dividend_event_instrument_ex",
        "dividend_events",
        ["instrument_id", "ex_date"],
    )
    op.create_index("ix_dividend_event_ex_date", "dividend_events", ["ex_date"])
    op.create_index("ix_dividend_event_status", "dividend_events", ["event_status"])

    op.create_table(
        "dividend_review_events",
        sa.Column("review_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "event_id",
            sa.String(length=36),
            sa.ForeignKey("dividend_events.event_id", ondelete="RESTRICT"),
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
            f"previous_quality IN ({_QUALITY_VALUES})",
            name="ck_dividend_review_previous_quality",
        ),
        sa.CheckConstraint(
            "decision IN ('VERIFIED', 'REJECTED')",
            name="ck_dividend_review_decision",
        ),
        sa.CheckConstraint(
            "length(trim(reviewer_label)) > 0",
            name="ck_dividend_review_reviewer",
        ),
        sa.CheckConstraint(
            "length(trim(evidence_reference)) > 0",
            name="ck_dividend_review_evidence",
        ),
        sa.CheckConstraint(
            "length(evidence_sha256) = 64 AND lower(evidence_sha256) NOT GLOB '*[^0-9a-f]*'",
            name="ck_dividend_review_evidence_sha256",
        ),
        sa.CheckConstraint(
            "length(trim(notes)) > 0",
            name="ck_dividend_review_notes",
        ),
        sa.UniqueConstraint("review_id", "event_id", name="uq_dividend_review_id_event"),
    )
    op.create_index(
        "ix_dividend_review_event_time",
        "dividend_review_events",
        ["event_id", "reviewed_at_utc"],
    )
    _create_append_only_triggers()


def downgrade() -> None:
    for table in ("dividend_review_events", "dividend_events"):
        for action in ("update", "delete"):
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_{action}")
    op.drop_index("ix_dividend_review_event_time", table_name="dividend_review_events")
    op.drop_table("dividend_review_events")
    for index in (
        "ix_dividend_event_status",
        "ix_dividend_event_ex_date",
        "ix_dividend_event_instrument_ex",
    ):
        op.drop_index(index, table_name="dividend_events")
    op.drop_table("dividend_events")
