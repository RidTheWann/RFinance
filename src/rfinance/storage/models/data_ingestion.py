"""Persistence model for source registry and user-imported market observations."""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
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


class SourceRegistryRecord(Base):
    """Source identity and policy decision; automated access is deny-by-default."""

    __tablename__ = "source_registry"
    __table_args__ = (
        UniqueConstraint(
            "display_name",
            "access_method",
            name="uq_source_registry_name_method",
        ),
        CheckConstraint(
            "access_method IN "
            "('USER_IMPORT', 'OFFICIAL_API', 'OFFICIAL_DOWNLOAD', 'LICENSED_PROVIDER', 'MANUAL')",
            name="ck_source_registry_access_method",
        ),
        CheckConstraint(
            "policy_status IN ('UNREVIEWED', 'APPROVED', 'RESTRICTED', 'BLOCKED')",
            name="ck_source_registry_policy_status",
        ),
        CheckConstraint(
            "access_method != 'USER_IMPORT' OR "
            "(automated_access_allowed = 0 AND redistribution_allowed = 0)",
            name="ck_user_import_no_automation_or_redistribution",
        ),
        CheckConstraint(
            "automated_access_allowed = 0 OR "
            "(policy_status = 'APPROVED' AND terms_url IS NOT NULL "
            "AND reviewed_at_utc IS NOT NULL)",
            name="ck_automated_source_requires_approval",
        ),
    )

    source_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    access_method: Mapped[str] = mapped_column(String(32), nullable=False)
    policy_status: Mapped[str] = mapped_column(String(24), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    terms_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at_utc: Mapped[str | None] = mapped_column(String(40), nullable=True)
    automated_access_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    redistribution_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at_utc: Mapped[str] = mapped_column(String(40), nullable=False)


class DataImportBatchRecord(Base):
    """Immutable metadata describing one local file import."""

    __tablename__ = "data_import_batches"
    __table_args__ = (
        CheckConstraint("row_count >= 0", name="ck_import_batch_rows_nonnegative"),
        CheckConstraint("accepted_rows >= 0", name="ck_import_batch_accepted_nonnegative"),
        CheckConstraint("rejected_rows >= 0", name="ck_import_batch_rejected_nonnegative"),
        CheckConstraint(
            "accepted_rows + rejected_rows = row_count",
            name="ck_import_batch_rows_reconcile",
        ),
        Index("ix_import_batch_source_time", "source_id", "imported_at_utc"),
    )

    batch_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        ForeignKey("source_registry.source_id", ondelete="RESTRICT"),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    document_relative_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    imported_at_utc: Mapped[str] = mapped_column(String(40), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    accepted_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    rejected_rows: Mapped[int] = mapped_column(Integer, nullable=False)


class MarketObservationRecord(Base):
    """Raw and normalized market observation with immutable source provenance."""

    __tablename__ = "market_observations"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "instrument_id",
            "observed_at_utc",
            name="uq_market_observation_source_instrument_time",
        ),
        CheckConstraint(
            "quality_status IN "
            "('VERIFIED', 'UNVERIFIED', 'ESTIMATED', 'STALE', 'INCOMPLETE', 'REJECTED', 'SIMULATED')",
            name="ck_market_observation_quality_status",
        ),
        CheckConstraint("length(currency) = 3", name="ck_market_observation_currency_length"),
        Index("ix_market_observation_instrument_time", "instrument_id", "observed_at_utc"),
        Index("ix_market_observation_source_time", "source_id", "observed_at_utc"),
    )

    observation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("data_import_batches.batch_id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_id: Mapped[str] = mapped_column(
        ForeignKey("source_registry.source_id", ondelete="RESTRICT"),
        nullable=False,
    )
    instrument_id: Mapped[str] = mapped_column(String(128), nullable=False)
    observed_at_utc: Mapped[str] = mapped_column(String(40), nullable=False)
    acquired_at_utc: Mapped[str] = mapped_column(String(40), nullable=False)
    open: Mapped[str | None] = mapped_column(Text, nullable=True)
    high: Mapped[str | None] = mapped_column(Text, nullable=True)
    low: Mapped[str | None] = mapped_column(Text, nullable=True)
    close: Mapped[str] = mapped_column(Text, nullable=False)
    volume: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    quality_status: Mapped[str] = mapped_column(String(24), nullable=False)
    original_row_json: Mapped[str] = mapped_column(Text, nullable=False)
    transformation_version: Mapped[str] = mapped_column(String(64), nullable=False)


class DataImportIssueRecord(Base):
    """Row-level import rejection or duplicate diagnostic."""

    __tablename__ = "data_import_issues"
    __table_args__ = (
        UniqueConstraint("batch_id", "row_number", name="uq_import_issue_batch_row"),
        Index("ix_import_issue_batch_row", "batch_id", "row_number"),
    )

    issue_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("data_import_batches.batch_id", ondelete="RESTRICT"),
        nullable=False,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    original_row_json: Mapped[str] = mapped_column(Text, nullable=False)
