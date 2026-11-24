# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Append-only sampling-frequency and corporate-action evidence decisions."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from rfinance.storage.models.base import Base

_FREQUENCIES = "'DAILY', 'WEEKLY', 'MONTHLY', 'INTRADAY', 'UNKNOWN_AS_SUPPLIED'"
_ADJUSTMENTS = "'NONE_CONFIRMED', 'ADJUSTED', 'UNKNOWN_AS_SUPPLIED'"
_DECISIONS = "'VERIFIED', 'REJECTED'"


class InstrumentMetadataEventRecord(Base):
    """An immutable, evidence-backed metadata decision for one instrument/source."""

    __tablename__ = "instrument_metadata_events"
    __table_args__ = (
        CheckConstraint(
            f"sampling_frequency IN ({_FREQUENCIES})",
            name="ck_instrument_metadata_frequency",
        ),
        CheckConstraint(
            f"adjustment_status IN ({_ADJUSTMENTS})",
            name="ck_instrument_metadata_adjustment",
        ),
        CheckConstraint(f"decision IN ({_DECISIONS})", name="ck_instrument_metadata_decision"),
        CheckConstraint("length(source_id) > 0", name="ck_instrument_metadata_source"),
        CheckConstraint("length(decided_at_utc) > 0", name="ck_instrument_metadata_time"),
        Index(
            "ix_instrument_metadata_instrument_source_time",
            "instrument_id",
            "source_id",
            "decided_at_utc",
        ),
    )

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    instrument_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sampling_frequency: Mapped[str] = mapped_column(String(32), nullable=False)
    adjustment_status: Mapped[str] = mapped_column(String(32), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    reviewer_label: Mapped[str] = mapped_column(String(256), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_reference: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    decided_at_utc: Mapped[str] = mapped_column(String(40), nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(64), nullable=False)
