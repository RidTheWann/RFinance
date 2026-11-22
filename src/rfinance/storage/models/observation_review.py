# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Append-only observation review audit records."""

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


class ObservationReviewEventRecord(Base):
    """A manual, evidence-backed decision about a market observation.

    Raw market observations are append-only. A review never mutates the stored
    observation; the effective quality is the most recent decision for it.
    """

    __tablename__ = "observation_review_events"
    __table_args__ = (
        CheckConstraint(
            "previous_quality IN "
            "('VERIFIED', 'UNVERIFIED', 'ESTIMATED', 'STALE', 'INCOMPLETE', "
            "'REJECTED', 'SIMULATED')",
            name="ck_observation_review_previous_quality",
        ),
        CheckConstraint(
            "decision IN ('VERIFIED', 'REJECTED')",
            name="ck_observation_review_decision",
        ),
        CheckConstraint("length(trim(reviewer_label)) > 0", name="ck_observation_review_reviewer"),
        CheckConstraint(
            "length(trim(evidence_reference)) > 0",
            name="ck_observation_review_evidence",
        ),
        CheckConstraint(
            "length(evidence_sha256) = 64 AND lower(evidence_sha256) NOT GLOB '*[^0-9a-f]*'",
            name="ck_observation_review_evidence_sha256",
        ),
        CheckConstraint("length(trim(notes)) > 0", name="ck_observation_review_notes"),
        Index("ix_observation_review_observation_time", "observation_id", "reviewed_at_utc"),
        UniqueConstraint(
            "review_id",
            "observation_id",
            name="uq_observation_review_id_observation",
        ),
    )

    review_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    observation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("market_observations.observation_id", ondelete="RESTRICT"),
        nullable=False,
    )
    instrument_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    previous_quality: Mapped[str] = mapped_column(String(24), nullable=False)
    decision: Mapped[str] = mapped_column(String(24), nullable=False)
    reviewed_at_utc: Mapped[str] = mapped_column(String(40), nullable=False)
    reviewer_label: Mapped[str] = mapped_column(String(256), nullable=False)
    evidence_reference: Mapped[str] = mapped_column(String(1024), nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
