"""Explicit operator-driven instrument review with immutable evidence audit."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import uuid4

from rfinance.storage.models.instrument_registry import (
    InstrumentRegistryRecord,
    InstrumentReviewEventRecord,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker

    from rfinance.data.contracts import InstrumentContract


_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


class InstrumentReviewDecision(StrEnum):
    """Allowed manual review outcomes; there is deliberately no AI outcome."""

    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class InstrumentReviewResult:
    instrument_id: str
    previous_status: str
    verification_status: str
    review_id: str
    reviewed_at_utc: str


class InstrumentReviewService:
    """Promote or reject a placeholder only through an explicit evidence-backed review."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def review_instrument(
        self,
        instrument_id: str,
        *,
        decision: InstrumentReviewDecision,
        reviewer_label: str,
        evidence_reference: str,
        evidence_sha256: str,
        notes: str,
        verified_instrument: InstrumentContract | None = None,
        reviewed_at: datetime | None = None,
    ) -> InstrumentReviewResult:
        """Record a review and update current registry status in one transaction.

        A VERIFIED decision requires a complete, validated InstrumentContract that
        matches the placeholder ID. REJECTED requires no replacement metadata.
        Evidence references are recorded, not fetched; the caller supplies the
        SHA-256 fingerprint of the evidence artifact they inspected.
        """

        if not isinstance(decision, InstrumentReviewDecision):
            raise TypeError("decision must be an explicit InstrumentReviewDecision")
        normalized_id = instrument_id.strip()
        if not normalized_id or len(normalized_id) > 128:
            raise ValueError("instrument_id must contain 1 to 128 characters")

        normalized_reviewer = reviewer_label.strip()
        if not normalized_reviewer or len(normalized_reviewer) > 256:
            raise ValueError("reviewer_label must contain 1 to 256 characters")
        normalized_reference = evidence_reference.strip()
        if not normalized_reference or len(normalized_reference) > 1024:
            raise ValueError("evidence_reference must contain 1 to 1024 characters")
        normalized_digest = evidence_sha256.strip().lower()
        if not _SHA256_PATTERN.fullmatch(normalized_digest):
            raise ValueError("evidence_sha256 must be a 64-character SHA-256 hex digest")
        normalized_notes = notes.strip()
        if not normalized_notes or len(normalized_notes) > 2048:
            raise ValueError("notes must contain 1 to 2048 characters")

        if decision is InstrumentReviewDecision.VERIFIED:
            if verified_instrument is None:
                raise ValueError("VERIFIED decisions require a complete InstrumentContract")
            if verified_instrument.instrument_id != normalized_id:
                raise ValueError("verified InstrumentContract ID does not match the reviewed ID")
        elif verified_instrument is not None:
            raise ValueError("REJECTED decisions cannot replace instrument metadata")

        review_time = reviewed_at or datetime.now(UTC)
        if review_time.tzinfo is None or review_time.utcoffset() is None:
            raise ValueError("reviewed_at must be timezone-aware")
        reviewed_at_utc = review_time.astimezone(UTC).isoformat()
        review_id = str(uuid4())
        reviewed_metadata_json = (
            None if verified_instrument is None else verified_instrument.model_dump_json()
        )

        with self._sessions.begin() as session:
            instrument = session.get(InstrumentRegistryRecord, normalized_id)
            if instrument is None:
                raise ValueError(
                    "instrument must exist in the registry before it can be reviewed"
                )

            previous_status = instrument.verification_status
            event = InstrumentReviewEventRecord(
                review_id=review_id,
                instrument_id=normalized_id,
                previous_status=previous_status,
                decision=decision.value,
                reviewed_at_utc=reviewed_at_utc,
                reviewer_label=normalized_reviewer,
                evidence_reference=normalized_reference,
                evidence_sha256=normalized_digest,
                notes=normalized_notes,
                reviewed_metadata_json=reviewed_metadata_json,
            )
            session.add(event)

            instrument.verification_status = decision.value
            instrument.updated_at_utc = reviewed_at_utc
            instrument.last_reviewed_at_utc = reviewed_at_utc
            instrument.last_review_id = review_id

            if verified_instrument is not None:
                instrument.ticker = verified_instrument.ticker
                instrument.exchange = verified_instrument.exchange
                instrument.instrument_type = verified_instrument.instrument_type.value
                instrument.company_name = verified_instrument.company_name
                instrument.currency = verified_instrument.currency
                instrument.sector = verified_instrument.sector
                instrument.active = verified_instrument.active
                instrument.lot_size = verified_instrument.lot_size
                instrument.minimum_investment = (
                    None
                    if verified_instrument.minimum_investment is None
                    else format(verified_instrument.minimum_investment, "f")
                )

        return InstrumentReviewResult(
            instrument_id=normalized_id,
            previous_status=previous_status,
            verification_status=decision.value,
            review_id=review_id,
            reviewed_at_utc=reviewed_at_utc,
        )
