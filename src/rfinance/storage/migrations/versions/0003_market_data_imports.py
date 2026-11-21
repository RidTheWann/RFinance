"""Create source registry and append-only user-imported market data."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_market_data_imports"
down_revision = "0002_portfolio_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_registry",
        sa.Column("source_id", sa.String(length=36), primary_key=True),
        sa.Column("display_name", sa.String(length=256), nullable=False),
        sa.Column("access_method", sa.String(length=32), nullable=False),
        sa.Column("policy_status", sa.String(length=24), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("terms_url", sa.Text(), nullable=True),
        sa.Column("reviewed_at_utc", sa.String(length=40), nullable=True),
        sa.Column(
            "automated_access_allowed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "redistribution_allowed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("created_at_utc", sa.String(length=40), nullable=False),
        sa.CheckConstraint(
            "access_method IN "
            "('USER_IMPORT', 'OFFICIAL_API', 'OFFICIAL_DOWNLOAD', 'LICENSED_PROVIDER', 'MANUAL')",
            name="ck_source_registry_access_method",
        ),
        sa.CheckConstraint(
            "policy_status IN ('UNREVIEWED', 'APPROVED', 'RESTRICTED', 'BLOCKED')",
            name="ck_source_registry_policy_status",
        ),
        sa.CheckConstraint(
            "access_method != 'USER_IMPORT' OR "
            "(automated_access_allowed = 0 AND redistribution_allowed = 0)",
            name="ck_user_import_no_automation_or_redistribution",
        ),
        sa.CheckConstraint(
            "automated_access_allowed = 0 OR "
            "(policy_status = 'APPROVED' AND terms_url IS NOT NULL "
            "AND reviewed_at_utc IS NOT NULL)",
            name="ck_automated_source_requires_approval",
        ),
        sa.UniqueConstraint(
            "display_name",
            "access_method",
            name="uq_source_registry_name_method",
        ),
    )

    op.create_table(
        "data_import_batches",
        sa.Column("batch_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "source_id",
            sa.String(length=36),
            sa.ForeignKey("source_registry.source_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("document_relative_path", sa.String(length=1024), nullable=False),
        sa.Column("imported_at_utc", sa.String(length=40), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("accepted_rows", sa.Integer(), nullable=False),
        sa.Column("rejected_rows", sa.Integer(), nullable=False),
        sa.CheckConstraint("length(file_sha256) = 64", name="ck_import_batch_sha256_length"),
        sa.CheckConstraint("row_count >= 0", name="ck_import_batch_rows_nonnegative"),
        sa.CheckConstraint("accepted_rows >= 0", name="ck_import_batch_accepted_nonnegative"),
        sa.CheckConstraint("rejected_rows >= 0", name="ck_import_batch_rejected_nonnegative"),
        sa.CheckConstraint(
            "accepted_rows + rejected_rows = row_count",
            name="ck_import_batch_rows_reconcile",
        ),
    )
    op.create_index(
        "ix_import_batch_source_time",
        "data_import_batches",
        ["source_id", "imported_at_utc"],
    )

    op.create_table(
        "market_observations",
        sa.Column("observation_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "batch_id",
            sa.String(length=36),
            sa.ForeignKey("data_import_batches.batch_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            sa.String(length=36),
            sa.ForeignKey("source_registry.source_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("instrument_id", sa.String(length=128), nullable=False),
        sa.Column("observed_at_utc", sa.String(length=40), nullable=False),
        sa.Column("acquired_at_utc", sa.String(length=40), nullable=False),
        sa.Column("open", sa.Text(), nullable=True),
        sa.Column("high", sa.Text(), nullable=True),
        sa.Column("low", sa.Text(), nullable=True),
        sa.Column("close", sa.Text(), nullable=False),
        sa.Column("volume", sa.Text(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("quality_status", sa.String(length=24), nullable=False),
        sa.Column("original_row_json", sa.Text(), nullable=False),
        sa.Column("transformation_version", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "quality_status IN "
            "('VERIFIED', 'UNVERIFIED', 'ESTIMATED', 'STALE', 'INCOMPLETE', "
            "'REJECTED', 'SIMULATED')",
            name="ck_market_observation_quality_status",
        ),
        sa.CheckConstraint(
            "length(currency) = 3",
            name="ck_market_observation_currency_length",
        ),
        sa.UniqueConstraint(
            "source_id",
            "instrument_id",
            "observed_at_utc",
            name="uq_market_observation_source_instrument_time",
        ),
    )
    op.create_index(
        "ix_market_observation_instrument_time",
        "market_observations",
        ["instrument_id", "observed_at_utc"],
    )
    op.create_index(
        "ix_market_observation_source_time",
        "market_observations",
        ["source_id", "observed_at_utc"],
    )

    op.create_table(
        "data_import_issues",
        sa.Column("issue_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "batch_id",
            sa.String(length=36),
            sa.ForeignKey("data_import_batches.batch_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("original_row_json", sa.Text(), nullable=False),
        sa.CheckConstraint("row_number > 1", name="ck_import_issue_row_number"),
        sa.UniqueConstraint("batch_id", "row_number", name="uq_import_issue_batch_row"),
    )
    op.create_index(
        "ix_import_issue_batch_row",
        "data_import_issues",
        ["batch_id", "row_number"],
    )

    for table in ("data_import_batches", "market_observations", "data_import_issues"):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_no_update
            BEFORE UPDATE ON {table}
            BEGIN
                SELECT RAISE(ABORT, '{table} is append-only');
            END;
            """
        )
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_no_delete
            BEFORE DELETE ON {table}
            BEGIN
                SELECT RAISE(ABORT, '{table} is append-only');
            END;
            """
        )


def downgrade() -> None:
    for table in ("data_import_issues", "market_observations", "data_import_batches"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_delete")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_update")
    op.drop_index("ix_import_issue_batch_row", table_name="data_import_issues")
    op.drop_table("data_import_issues")
    op.drop_index(
        "ix_market_observation_source_time",
        table_name="market_observations",
    )
    op.drop_index(
        "ix_market_observation_instrument_time",
        table_name="market_observations",
    )
    op.drop_table("market_observations")
    op.drop_index("ix_import_batch_source_time", table_name="data_import_batches")
    op.drop_table("data_import_batches")
    op.drop_table("source_registry")
