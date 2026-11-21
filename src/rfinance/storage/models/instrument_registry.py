# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Instrument master and append-only manual verification evidence."""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from rfinance.storage.models.base import Base


class InstrumentRegistryRecord(Base):
    """Canonical instrument identity with an explicit verification lifecycle."""

    __tablename__ = "instrument_registry"
    __table_args__ = (
        CheckConstraint(
            "verification_status IN ('UNVERIFIED', 'VERIFIED', 'REJECTED')",
            name="ck_instrument_registry_verification_status",
        ),
        CheckConstraint(
            "instrument_type IS NULL OR instrument_type IN "
            "('EQUITY', 'ETF', 'MUTUAL_FUND', 'BOND', 'MONEY_MARKET', 'INDEX', 'OTHER')",
            name="ck_instrument_registry_type",
        ),
        CheckConstraint(
            "currency IS NULL OR length(currency) = 3",
            name="ck_instrument_registry_currency",
        ),
        CheckConstraint(
            "lot_size IS NULL OR lot_size > 0",
            name="ck_instrument_registry_lot_size",
        ),
        CheckConstraint(
            "minimum_investment IS NULL OR CAST(minimum_investment AS NUMERIC) > 0",
            name="ck_instrument_registry_minimum_investment",
        ),
    )

    instrument_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    ticker: Mapped[str | None] = mapped_column(String(32), nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(32), nullable=True)
    instrument_type: Mapped[str | None] = mapped_column(String(24), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(128), nullable=True)
    active: Mapped[bool | None] = mapped_column(nullable=True)
    lot_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    minimum_investment: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="UNVERIFIED",
    )
    created_at_utc: Mapped[str] = mapped_column(String(40), nullable=False)
    updated_at_utc: Mapped[str] = mapped_column(String(40), nullable=False)
    last_reviewed_at_utc: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_review_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class InstrumentReviewEventRecord(Base):
    """Immutable audit event describing a manual, evidence-backed review decision."""

    __tablename__ = "instrument_review_events"
    __table_args__ = (
        CheckConstraint(
            "previous_status IN ('UNVERIFIED', 'VERIFIED', 'REJECTED')",
            name="ck_instrument_review_previous_status",
        ),
        CheckConstraint(
            "decision IN ('VERIFIED', 'REJECTED')",
            name="ck_instrument_review_decision",
        ),
        CheckConstraint("length(trim(reviewer_label)) > 0", name="ck_instrument_review_reviewer"),
        CheckConstraint("length(trim(evidence_reference)) > 0", name="ck_instrument_review_evidence"),
        CheckConstraint(
            "length(evidence_sha256) = 64 AND "
            "lower(evidence_sha256) NOT GLOB '*[^0-9a-f]*'",
            name="ck_instrument_review_evidence_sha256",
        ),
        CheckConstraint("length(trim(notes)) > 0", name="ck_instrument_review_notes"),
        Index("ix_instrument_review_instrument_time", "instrument_id", "reviewed_at_utc"),
        UniqueConstraint("review_id", "instrument_id", name="uq_instrument_review_id_instrument"),
    )

    review_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    instrument_id: Mapped[str] = mapped_column(
        ForeignKey("instrument_registry.instrument_id", ondelete="RESTRICT"),
        nullable=False,
    )
    previous_status: Mapped[str] = mapped_column(String(24), nullable=False)
    decision: Mapped[str] = mapped_column(String(24), nullable=False)
    reviewed_at_utc: Mapped[str] = mapped_column(String(40), nullable=False)
    reviewer_label: Mapped[str] = mapped_column(String(256), nullable=False)
    evidence_reference: Mapped[str] = mapped_column(String(1024), nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
