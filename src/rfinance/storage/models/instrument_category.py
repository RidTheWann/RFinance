# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Append-only instrument category and lot-size evidence decisions."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from rfinance.storage.models.base import Base

_CATEGORIES = "'EQUITY_INDEX', 'DIVIDEND_EQUITY', 'MONEY_MARKET'"
_DECISIONS = "'VERIFIED', 'REJECTED'"


class InstrumentCategoryEventRecord(Base):
    """An immutable, evidence-backed category decision for one instrument."""

    __tablename__ = "instrument_category_events"
    __table_args__ = (
        CheckConstraint(f"category IN ({_CATEGORIES})", name="ck_instrument_category"),
        CheckConstraint(f"decision IN ({_DECISIONS})", name="ck_instrument_category_decision"),
        CheckConstraint("length(lot_size) > 0", name="ck_instrument_category_lot"),
        CheckConstraint("length(decided_at_utc) > 0", name="ck_instrument_category_time"),
        Index("ix_instrument_category_instrument_time", "instrument_id", "decided_at_utc"),
    )

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    instrument_id: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    lot_size: Mapped[str] = mapped_column(Text, nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    reviewer_label: Mapped[str] = mapped_column(String(256), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_reference: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    decided_at_utc: Mapped[str] = mapped_column(String(40), nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(64), nullable=False)
