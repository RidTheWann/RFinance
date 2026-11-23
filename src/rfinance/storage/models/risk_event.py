# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Append-only risk events, explicit reviews and valuation history."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from rfinance.storage.models.base import Base

_RULES = (
    "'ELEVATED_DRAWDOWN', 'CRITICAL_DRAWDOWN', "
    "'SINGLE_INSTRUMENT_CONCENTRATION', 'SECTOR_CONCENTRATION', "
    "'ALLOCATION_DEVIATION', 'REVIEW_OVERDUE', 'VALUATION_INCOMPLETE', "
    "'PROHIBITED_ACTIVITY'"
)


class RiskEventRecord(Base):
    """An immutable record of a triggered deterministic review rule."""

    __tablename__ = "risk_events"
    __table_args__ = (
        CheckConstraint(f"rule IN ({_RULES})", name="ck_risk_event_rule"),
        CheckConstraint(
            "severity IN ('INFO', 'WARNING', 'CRITICAL')", name="ck_risk_event_severity"
        ),
        CheckConstraint("length(triggered_at_utc) > 0", name="ck_risk_event_time"),
        Index("ix_risk_events_rule_time", "rule", "triggered_at_utc"),
    )

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    rule: Mapped[str] = mapped_column(String(48), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    triggered_at_utc: Mapped[str] = mapped_column(String(40), nullable=False)
    observed_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    threshold: Mapped[str | None] = mapped_column(Text, nullable=True)
    valuation_methodology: Mapped[str] = mapped_column(String(128), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_reference: Mapped[str] = mapped_column(Text, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(64), nullable=False)


class RiskReviewRecord(Base):
    """An explicit operator review that resolves one risk event."""

    __tablename__ = "risk_reviews"
    __table_args__ = (
        CheckConstraint("length(reviewer_label) > 0", name="ck_risk_review_reviewer"),
        CheckConstraint("length(notes) > 0", name="ck_risk_review_notes"),
        CheckConstraint("length(evidence_reference) > 0", name="ck_risk_review_evidence"),
        Index("ix_risk_reviews_event", "event_id"),
    )

    review_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewer_label: Mapped[str] = mapped_column(String(256), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_reference: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_at_utc: Mapped[str] = mapped_column(String(40), nullable=False)


class ValuationHistoryRecord(Base):
    """A recorded valuation used as the drawdown series."""

    __tablename__ = "portfolio_valuation_history"
    __table_args__ = (
        CheckConstraint("length(currency) = 3", name="ck_valuation_history_currency"),
        CheckConstraint("is_complete IN (0, 1)", name="ck_valuation_history_complete"),
        Index("ix_valuation_history_as_of", "as_of_utc"),
    )

    valuation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    as_of_utc: Mapped[str] = mapped_column(String(40), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    total_value: Mapped[str] = mapped_column(Text, nullable=False)
    is_complete: Mapped[int] = mapped_column(Integer, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(64), nullable=False)
    positions_json: Mapped[str] = mapped_column(Text, nullable=False)
    allocation_json: Mapped[str] = mapped_column(Text, nullable=False)
