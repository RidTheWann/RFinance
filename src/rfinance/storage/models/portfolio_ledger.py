# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Append-only SQLite representation of portfolio ledger events."""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from rfinance.storage.models.base import Base


class PortfolioLedgerRecord(Base):
    """A single persisted event; decimal values are stored as exact text.

    SQLite NUMERIC affinity can coerce values to binary floating point in some
    operations. Storing Decimal's fixed-point string form preserves the exact
    user-entered decimal representation; replay converts it back to Decimal.
    """

    __tablename__ = "portfolio_ledger_events"
    __table_args__ = (
        UniqueConstraint("sequence", name="uq_portfolio_ledger_sequence"),
        UniqueConstraint(
            "instrument_id",
            "source_reference",
            name="uq_portfolio_ledger_dividend_source",
        ),
        CheckConstraint("sequence > 0", name="ck_portfolio_ledger_sequence_positive"),
        CheckConstraint("length(currency) = 3", name="ck_portfolio_ledger_currency_length"),
        CheckConstraint(
            "event_type IN "
            "('CAPITAL_INJECTION', 'BUY', 'SELL', 'CASH_WITHDRAWAL', 'SIMULATED_DIVIDEND', "
            "'CONFIRMED_DIVIDEND')",
            name="ck_portfolio_ledger_event_type",
        ),
        Index(
            "ix_portfolio_ledger_instrument_sequence",
            "instrument_id",
            "sequence",
        ),
        Index(
            "ix_portfolio_ledger_event_type_sequence",
            "event_type",
            "sequence",
        ),
    )

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_at_utc: Mapped[str] = mapped_column(String(40), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    amount: Mapped[str | None] = mapped_column(Text, nullable=True)
    instrument_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    quantity: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit_price: Mapped[str | None] = mapped_column(Text, nullable=True)
    fees: Mapped[str] = mapped_column(Text, nullable=False, default="0")
    taxes: Mapped[str] = mapped_column(Text, nullable=False, default="0")
    source_reference: Mapped[str | None] = mapped_column(String(256), nullable=True)
