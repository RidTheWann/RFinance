"""Add instrument master, manual review audit, and observation foreign key."""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0004_instrument_master"
down_revision = "0003_market_data_imports"
branch_labels = None
depends_on = None


def _create_observation_append_only_triggers() -> None:
    op.execute(
        """
        CREATE TRIGGER trg_market_observations_no_update
        BEFORE UPDATE ON market_observations
        BEGIN
            SELECT RAISE(ABORT, 'market_observations is append-only');
        END;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_market_observations_no_delete
        BEFORE DELETE ON market_observations
        BEGIN
            SELECT RAISE(ABORT, 'market_observations is append-only');
        END;
        """
    )


def upgrade() -> None:
    op.create_table(
        "instrument_registry",
        sa.Column("instrument_id", sa.String(length=128), primary_key=True),
        sa.Column("ticker", sa.String(length=32), nullable=True),
        sa.Column("exchange", sa.String(length=32), nullable=True),
        sa.Column("instrument_type", sa.String(length=24), nullable=True),
        sa.Column("company_name", sa.String(length=256), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("sector", sa.String(length=128), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=True),
        sa.Column("lot_size", sa.Integer(), nullable=True),
        sa.Column("minimum_investment", sa.Text(), nullable=True),
        sa.CheckConstraint("lot_size IS NULL OR lot_size > 0", name="ck_instrument_registry_lot_size"),
        sa.CheckConstraint(
            "minimum_investment IS NULL OR CAST(minimum_investment AS NUMERIC) > 0",
            name="ck_instrument_registry_minimum_investment",
        ),
        sa.Column("verification_status", sa.String(length=24), nullable=False),
        sa.Column("created_at_utc", sa.String(length=40), nullable=False),
        sa.Column("updated_at_utc", sa.String(length=40), nullable=False),
        sa.Column("last_reviewed_at_utc", sa.String(length=40), nullable=True),
        sa.Column("last_review_id", sa.String(length=36), nullable=True),
        sa.CheckConstraint(
            "verification_status IN ('UNVERIFIED', 'VERIFIED', 'REJECTED')",
            name="ck_instrument_registry_verification_status",
        ),
        sa.CheckConstraint(
            "instrument_type IS NULL OR instrument_type IN "
            "('EQUITY', 'ETF', 'MUTUAL_FUND', 'BOND', 'MONEY_MARKET', 'INDEX', 'OTHER')",
            name="ck_instrument_registry_type",
        ),
        sa.CheckConstraint(
            "currency IS NULL OR length(currency) = 3",
            name="ck_instrument_registry_currency",
        ),
    )

    migration_time = datetime.now(UTC).isoformat()
    op.get_bind().execute(
        sa.text(
            """
            INSERT INTO instrument_registry (
                instrument_id,
                ticker,
                exchange,
                instrument_type,
                company_name,
                currency,
                sector,
                active,
                verification_status,
                created_at_utc,
                updated_at_utc,
                last_reviewed_at_utc,
                last_review_id
            )
            SELECT DISTINCT
                instrument_id,
                NULL,
                NULL,
                NULL,
                NULL,
                NULL,
                NULL,
                NULL,
                'UNVERIFIED',
                :migration_time,
                :migration_time,
                NULL,
                NULL
            FROM market_observations
            """
        ),
        {"migration_time": migration_time},
    )

    op.create_table(
        "instrument_review_events",
        sa.Column("review_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "instrument_id",
            sa.String(length=128),
            sa.ForeignKey("instrument_registry.instrument_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("previous_status", sa.String(length=24), nullable=False),
        sa.Column("decision", sa.String(length=24), nullable=False),
        sa.Column("reviewed_at_utc", sa.String(length=40), nullable=False),
        sa.Column("reviewer_label", sa.String(length=256), nullable=False),
        sa.Column("evidence_reference", sa.String(length=1024), nullable=False),
        sa.Column("evidence_sha256", sa.String(length=64), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("reviewed_metadata_json", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "previous_status IN ('UNVERIFIED', 'VERIFIED', 'REJECTED')",
            name="ck_instrument_review_previous_status",
        ),
        sa.CheckConstraint(
            "decision IN ('VERIFIED', 'REJECTED')",
            name="ck_instrument_review_decision",
        ),
        sa.CheckConstraint(
            "length(trim(reviewer_label)) > 0",
            name="ck_instrument_review_reviewer",
        ),
        sa.CheckConstraint(
            "length(trim(evidence_reference)) > 0",
            name="ck_instrument_review_evidence",
        ),
        sa.CheckConstraint(
            "length(evidence_sha256) = 64 AND "
            "lower(evidence_sha256) NOT GLOB '*[^0-9a-f]*'",
            name="ck_instrument_review_evidence_sha256",
        ),
        sa.CheckConstraint(
            "length(trim(notes)) > 0",
            name="ck_instrument_review_notes",
        ),
        sa.UniqueConstraint(
            "review_id",
            "instrument_id",
            name="uq_instrument_review_id_instrument",
        ),
    )
    op.create_index(
        "ix_instrument_review_instrument_time",
        "instrument_review_events",
        ["instrument_id", "reviewed_at_utc"],
    )

    # The SQLite table rebuild removes existing triggers, so recreate them after
    # the foreign key has been attached to the historical observations table.
    op.execute("DROP TRIGGER IF EXISTS trg_market_observations_no_update")
    op.execute("DROP TRIGGER IF EXISTS trg_market_observations_no_delete")
    with op.batch_alter_table("market_observations", recreate="always") as batch_op:
        batch_op.create_foreign_key(
            "fk_market_observation_instrument_registry",
            "instrument_registry",
            ["instrument_id"],
            ["instrument_id"],
            ondelete="RESTRICT",
        )
    _create_observation_append_only_triggers()

    for trigger, action in (
        ("trg_instrument_review_events_no_update", "UPDATE"),
        ("trg_instrument_review_events_no_delete", "DELETE"),
    ):
        op.execute(
            f"""
            CREATE TRIGGER {trigger}
            BEFORE {action} ON instrument_review_events
            BEGIN
                SELECT RAISE(ABORT, 'instrument_review_events is append-only');
            END;
            """
        )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_instrument_review_events_no_update")
    op.execute("DROP TRIGGER IF EXISTS trg_instrument_review_events_no_delete")
    op.drop_index(
        "ix_instrument_review_instrument_time",
        table_name="instrument_review_events",
    )
    op.drop_table("instrument_review_events")

    op.execute("DROP TRIGGER IF EXISTS trg_market_observations_no_update")
    op.execute("DROP TRIGGER IF EXISTS trg_market_observations_no_delete")
    with op.batch_alter_table("market_observations", recreate="always") as batch_op:
        batch_op.drop_constraint(
            "fk_market_observation_instrument_registry",
            type_="foreignkey",
        )
    _create_observation_append_only_triggers()
    op.drop_table("instrument_registry")
