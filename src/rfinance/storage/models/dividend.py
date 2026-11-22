"""Append-only dividend event and review persistence models."""

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


class DividendEventRecord(Base):
    """A raw dividend observation retained with its original provenance.

    Events are never mutated. An operator decision is appended separately as a
    :class:`DividendReviewEventRecord`, so the effective quality is always
    derivable from the audit ledger rather than overwriting the source row.
    """

    __tablename__ = "dividend_events"
    __table_args__ = (
        UniqueConstraint("source_id", "event_key", name="uq_dividend_event_source_key"),
        CheckConstraint(
            "dividend_type IN ('CASH', 'INTERIM', 'FINAL', 'SPECIAL', 'STOCK', 'RIGHTS')",
            name="ck_dividend_event_type",
        ),
        CheckConstraint(
            "event_status IN "
            "('ANNOUNCED', 'CONFIRMED', 'HISTORICAL', 'ESTIMATED', 'SIMULATED', 'CANCELLED')",
            name="ck_dividend_event_status",
        ),
        CheckConstraint(
            "quality_status IN "
            "('VERIFIED', 'UNVERIFIED', 'ESTIMATED', 'STALE', 'INCOMPLETE', "
            "'REJECTED', 'SIMULATED')",
            name="ck_dividend_event_quality_status",
        ),
        CheckConstraint("length(currency) = 3", name="ck_dividend_event_currency_length"),
        CheckConstraint("length(ex_date) = 10", name="ck_dividend_event_ex_date_format"),
        CheckConstraint(
            "amount_per_share IS NULL OR length(amount_per_share) > 0",
            name="ck_dividend_event_amount_present",
        ),
        Index("ix_dividend_event_instrument_ex", "instrument_id", "ex_date"),
        Index("ix_dividend_event_ex_date", "ex_date"),
        Index("ix_dividend_event_status", "event_status"),
    )

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_key: Mapped[str] = mapped_column(String(128), nullable=False)
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
    dividend_type: Mapped[str] = mapped_column(String(16), nullable=False)
    event_status: Mapped[str] = mapped_column(String(16), nullable=False)
    amount_per_share: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    ex_date: Mapped[str] = mapped_column(String(10), nullable=False)
    cum_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    record_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    payment_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    quality_status: Mapped[str] = mapped_column(String(24), nullable=False)
    acquired_at_utc: Mapped[str] = mapped_column(String(40), nullable=False)
    announced_at_utc: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reporting_period_start: Mapped[str | None] = mapped_column(String(10), nullable=True)
    reporting_period_end: Mapped[str | None] = mapped_column(String(10), nullable=True)
    source_document_ref: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    original_value: Mapped[str | None] = mapped_column(String(256), nullable=True)
    unit: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    transformation_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at_utc: Mapped[str] = mapped_column(String(40), nullable=False)


class DividendReviewEventRecord(Base):
    """An evidence-backed, append-only decision about a dividend event."""

    __tablename__ = "dividend_review_events"
    __table_args__ = (
        CheckConstraint(
            "previous_quality IN "
            "('VERIFIED', 'UNVERIFIED', 'ESTIMATED', 'STALE', 'INCOMPLETE', "
            "'REJECTED', 'SIMULATED')",
            name="ck_dividend_review_previous_quality",
        ),
        CheckConstraint(
            "decision IN ('VERIFIED', 'REJECTED')",
            name="ck_dividend_review_decision",
        ),
        CheckConstraint("length(trim(reviewer_label)) > 0", name="ck_dividend_review_reviewer"),
        CheckConstraint(
            "length(trim(evidence_reference)) > 0",
            name="ck_dividend_review_evidence",
        ),
        CheckConstraint(
            "length(evidence_sha256) = 64 AND lower(evidence_sha256) NOT GLOB '*[^0-9a-f]*'",
            name="ck_dividend_review_evidence_sha256",
        ),
        CheckConstraint("length(trim(notes)) > 0", name="ck_dividend_review_notes"),
        Index("ix_dividend_review_event_time", "event_id", "reviewed_at_utc"),
        UniqueConstraint(
            "review_id",
            "event_id",
            name="uq_dividend_review_id_event",
        ),
    )

    review_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("dividend_events.event_id", ondelete="RESTRICT"),
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
