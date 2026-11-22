# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Extend ledger event types and add confirmed dividend receipts."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_confirmed_dividend_receipts"
down_revision = "0007_recommendations"
branch_labels = None
depends_on = None

_OLD_EVENT_TYPES = (
    "'CAPITAL_INJECTION', 'BUY', 'SELL', 'CASH_WITHDRAWAL', 'SIMULATED_DIVIDEND'"
)
_NEW_EVENT_TYPES = (
    "'CAPITAL_INJECTION', 'BUY', 'SELL', 'CASH_WITHDRAWAL', 'SIMULATED_DIVIDEND', "
    "'CONFIRMED_DIVIDEND'"
)


def _drop_ledger_objects() -> None:
    for action in ("update", "delete"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_portfolio_ledger_no_{action}")
    for index in (
        "ix_portfolio_ledger_instrument_sequence",
        "ix_portfolio_ledger_event_type_sequence",
    ):
        op.drop_index(index, table_name="portfolio_ledger_events")


def _recreate_ledger_objects() -> None:
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
    for action in ("UPDATE", "DELETE"):
        op.execute(
            f"""
            CREATE TRIGGER trg_portfolio_ledger_no_{action.lower()}
            BEFORE {action} ON portfolio_ledger_events
            BEGIN
                SELECT RAISE(ABORT, 'portfolio ledger is append-only');
            END;
            """
        )


def _rebuild(event_types: str) -> None:
    _drop_ledger_objects()
    op.create_table(
        "portfolio_ledger_events_new",
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
            f"event_type IN ({event_types})",
            name="ck_portfolio_ledger_event_type",
        ),
        sa.UniqueConstraint("sequence", name="uq_portfolio_ledger_sequence"),
        sa.UniqueConstraint(
            "instrument_id",
            "source_reference",
            name="uq_portfolio_ledger_dividend_source",
        ),
    )
    op.execute(
        """
        INSERT INTO portfolio_ledger_events_new
        (event_id, sequence, occurred_at_utc, event_type, currency, amount,
         instrument_id, quantity, unit_price, fees, taxes, source_reference)
        SELECT event_id, sequence, occurred_at_utc, event_type, currency, amount,
               instrument_id, quantity, unit_price, fees, taxes, source_reference
        FROM portfolio_ledger_events
        """
    )
    op.execute("DROP TABLE portfolio_ledger_events")
    op.execute("ALTER TABLE portfolio_ledger_events_new RENAME TO portfolio_ledger_events")
    _recreate_ledger_objects()


def _create_receipt_table() -> None:
    op.create_table(
        "dividend_receipts",
        sa.Column("receipt_id", sa.String(length=36), primary_key=True),
        sa.Column("dividend_event_id", sa.String(length=36), nullable=False),
        sa.Column("instrument_id", sa.String(length=128), nullable=False),
        sa.Column("net_amount", sa.Text(), nullable=False),
        sa.Column("reinvestment", sa.Text(), nullable=False),
        sa.Column("money_market", sa.Text(), nullable=False),
        sa.Column("withdrawal", sa.Text(), nullable=False),
        sa.Column("reinvest_weight", sa.String(length=32), nullable=False),
        sa.Column("money_market_weight", sa.String(length=32), nullable=False),
        sa.Column("withdrawal_weight", sa.String(length=32), nullable=False),
        sa.Column("recorded_at_utc", sa.String(length=40), nullable=False),
        sa.Column("methodology_version", sa.String(length=64), nullable=False),
        sa.UniqueConstraint(
            "dividend_event_id", name="uq_dividend_receipt_event"
        ),
    )
    for action in ("UPDATE", "DELETE"):
        op.execute(
            f"""
            CREATE TRIGGER trg_dividend_receipts_no_{action.lower()}
            BEFORE {action} ON dividend_receipts
            BEGIN
                SELECT RAISE(ABORT, 'dividend_receipts is append-only');
            END;
            """
        )


def upgrade() -> None:
    _rebuild(_NEW_EVENT_TYPES)
    _create_receipt_table()


def downgrade() -> None:
    for action in ("update", "delete"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_dividend_receipts_no_{action}")
    op.drop_table("dividend_receipts")
    _rebuild(_OLD_EVENT_TYPES)
