"""Create append-only portfolio ledger storage."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_portfolio_ledger"
down_revision = "0001_initial_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portfolio_ledger_events",
        sa.Column("event_id", sa.String(length=128), primary_key=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("occurred_at_utc", sa.String(length=40), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("amount", sa.Text(), nullable=True),
        sa.Column("instrument_id", sa.String(length=128), nullable=True),
        sa.Column("quantity", sa.Text(), nullable=True),
        sa.Column("unit_price", sa.Text(), nullable=True),
        sa.Column("fees", sa.Text(), nullable=False, server_default="0"),
        sa.Column("taxes", sa.Text(), nullable=False, server_default="0"),
        sa.Column("source_reference", sa.String(length=256), nullable=True),
        sa.CheckConstraint("sequence > 0", name="ck_portfolio_ledger_sequence_positive"),
        sa.CheckConstraint("length(currency) = 3", name="ck_portfolio_ledger_currency_length"),
        sa.CheckConstraint(
            "event_type IN "
            "('CAPITAL_INJECTION', 'BUY', 'SELL', 'CASH_WITHDRAWAL', 'SIMULATED_DIVIDEND')",
            name="ck_portfolio_ledger_event_type",
        ),
        sa.UniqueConstraint("sequence", name="uq_portfolio_ledger_sequence"),
        sa.UniqueConstraint(
            "instrument_id",
            "source_reference",
            name="uq_portfolio_ledger_dividend_source",
        ),
    )
    op.create_index(
        "ix_portfolio_ledger_instrument_sequence",
        "portfolio_ledger_events",
        ["instrument_id", "sequence"],
    )
    op.create_index(
        "ix_portfolio_ledger_event_type_sequence",
        "portfolio_ledger_events",
        ["event_type", "sequence"],
    )
    op.execute(
        """
        CREATE TRIGGER trg_portfolio_ledger_no_update
        BEFORE UPDATE ON portfolio_ledger_events
        BEGIN
            SELECT RAISE(ABORT, 'portfolio ledger is append-only');
        END;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_portfolio_ledger_no_delete
        BEFORE DELETE ON portfolio_ledger_events
        BEGIN
            SELECT RAISE(ABORT, 'portfolio ledger is append-only');
        END;
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_portfolio_ledger_no_delete")
    op.execute("DROP TRIGGER IF EXISTS trg_portfolio_ledger_no_update")
    op.drop_index(
        "ix_portfolio_ledger_event_type_sequence",
        table_name="portfolio_ledger_events",
    )
    op.drop_index(
        "ix_portfolio_ledger_instrument_sequence",
        table_name="portfolio_ledger_events",
    )
    op.drop_table("portfolio_ledger_events")
