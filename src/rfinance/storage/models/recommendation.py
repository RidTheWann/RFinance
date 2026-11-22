# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Persisted, evidence-linked deterministic recommendations."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from rfinance.storage.models.base import Base


class RecommendationRecord(Base):
    """An append-only research result with its evidence and risk diagnostics."""

    __tablename__ = "recommendations"
    __table_args__ = (
        CheckConstraint(
            "action IN ('BUY_CANDIDATE', 'HOLD', 'WATCH', 'AVOID', 'INSUFFICIENT_DATA')",
            name="ck_recommendation_action",
        ),
        CheckConstraint("length(instrument_id) > 0", name="ck_recommendation_instrument"),
        CheckConstraint("length(confidence_level) > 0", name="ck_recommendation_confidence"),
        Index(
            "ix_recommendation_instrument_time",
            "instrument_id",
            "generated_at_utc",
        ),
    )

    recommendation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    instrument_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(24), nullable=False)
    generated_at_utc: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    risk_flags_json: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_level: Mapped[str] = mapped_column(String(64), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    invalidation_conditions_json: Mapped[str] = mapped_column(Text, nullable=False)
    data_freshness_utc: Mapped[str | None] = mapped_column(String(40), nullable=True)
    methodology_version: Mapped[str] = mapped_column(String(64), nullable=False)
    fundamental_assessment: Mapped[str] = mapped_column(Text, nullable=False)
    price_assessment: Mapped[str] = mapped_column(Text, nullable=False)
    dividend_assessment: Mapped[str] = mapped_column(Text, nullable=False)
