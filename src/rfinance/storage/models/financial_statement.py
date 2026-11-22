# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Append-only financial statement metrics and their review ledger."""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from rfinance.storage.models.base import Base


class FinancialMetricRecord(Base):
    """One reported metric with provenance; raw values are never overwritten."""

    __tablename__ = "financial_metrics"
    __table_args__ = (
        CheckConstraint(
            "quality_status IN "
            "('VERIFIED', 'UNVERIFIED', 'ESTIMATED', 'STALE', 'INCOMPLETE', "
            "'REJECTED', 'SIMULATED')",
            name="ck_financial_metric_quality",
        ),
        CheckConstraint("length(currency) = 3", name="ck_financial_metric_currency"),
        CheckConstraint(
            "reporting_basis IN ('ANNUAL', 'QUARTERLY', 'TTM')",
            name="ck_financial_metric_basis",
        ),
        UniqueConstraint(
            "source_id",
            "instrument_id",
            "metric_name",
            "period_start",
            "period_end",
            "reporting_basis",
            name="uq_financial_metric_observation",
        ),
        Index(
            "ix_financial_metric_instrument_name",
            "instrument_id",
            "metric_name",
            "period_end",
        ),
    )

    metric_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    instrument_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("instrument_registry.instrument_id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("source_registry.source_id", ondelete="RESTRICT"),
        nullable=False,
    )
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str] = mapped_column(String(64), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    period_start: Mapped[str] = mapped_column(String(10), nullable=False)
    period_end: Mapped[str] = mapped_column(String(10), nullable=False)
    reporting_basis: Mapped[str] = mapped_column(String(16), nullable=False)
    quality_status: Mapped[str] = mapped_column(String(24), nullable=False)
    acquired_at_utc: Mapped[str] = mapped_column(String(40), nullable=False)
    source_document_ref: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    transformation_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at_utc: Mapped[str] = mapped_column(String(40), nullable=False)


class FinancialMetricReviewRecord(Base):
    """An evidence-backed append-only decision about a reported metric."""

    __tablename__ = "financial_metric_reviews"
    __table_args__ = (
        CheckConstraint(
            "previous_quality IN "
            "('VERIFIED', 'UNVERIFIED', 'ESTIMATED', 'STALE', 'INCOMPLETE', "
            "'REJECTED', 'SIMULATED')",
            name="ck_financial_review_previous_quality",
        ),
        CheckConstraint(
            "decision IN ('VERIFIED', 'REJECTED')", name="ck_financial_review_decision"
        ),
        CheckConstraint(
            "length(evidence_sha256) = 64 AND lower(evidence_sha256) NOT GLOB '*[^0-9a-f]*'",
            name="ck_financial_review_sha256",
        ),
        Index("ix_financial_review_metric_time", "metric_id", "reviewed_at_utc"),
    )

    review_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    metric_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("financial_metrics.metric_id", ondelete="RESTRICT"),
        nullable=False,
    )
    previous_quality: Mapped[str] = mapped_column(String(24), nullable=False)
    decision: Mapped[str] = mapped_column(String(24), nullable=False)
    reviewed_at_utc: Mapped[str] = mapped_column(String(40), nullable=False)
    reviewer_label: Mapped[str] = mapped_column(String(256), nullable=False)
    evidence_reference: Mapped[str] = mapped_column(String(1024), nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
