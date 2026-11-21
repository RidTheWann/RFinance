# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from datetime import UTC, datetime
from decimal import Decimal

import sqlalchemy
import pytest

from rfinance.application.instrument_review import (
    InstrumentReviewDecision,
    InstrumentReviewService,
)
from rfinance.data.contracts import InstrumentContract, InstrumentType
from rfinance.storage.database import Database
from rfinance.storage.models.instrument_registry import (
    InstrumentRegistryRecord,
    InstrumentReviewEventRecord,
)


NOW = datetime(2026, 11, 21, 10, 0, tzinfo=UTC)
EVIDENCE_SHA256 = "a" * 64


def create_placeholder(database: Database, instrument_id: str = "IDX:BBCA") -> None:
    with database.sessions.begin() as session:
        session.add(
            InstrumentRegistryRecord(
                instrument_id=instrument_id,
                verification_status="UNVERIFIED",
                created_at_utc=NOW.isoformat(),
                updated_at_utc=NOW.isoformat(),
            )
        )


def verified_contract(instrument_id: str = "IDX:BBCA") -> InstrumentContract:
    return InstrumentContract(
        instrument_id=instrument_id,
        ticker="BBCA",
        exchange="IDX",
        instrument_type=InstrumentType.EQUITY,
        company_name="PT Bank Central Asia Tbk",
        currency="IDR",
        sector="Financials",
        active=True,
        lot_size=100,
        minimum_investment=Decimal("50000"),
    )


def test_verified_decision_requires_complete_contract_and_evidence(tmp_path) -> None:
    database = Database.open(tmp_path / "review.sqlite3")
    database.upgrade()
    create_placeholder(database)
    try:
        service = InstrumentReviewService(database.sessions)

        with pytest.raises(ValueError, match="complete InstrumentContract"):
            service.review_instrument(
                "IDX:BBCA",
                decision=InstrumentReviewDecision.VERIFIED,
                reviewer_label="Local operator",
                evidence_reference="Documents/ReviewEvidence/BBCA.pdf",
                evidence_sha256=EVIDENCE_SHA256,
                notes="Reviewed official issuer and exchange instrument details.",
            )

        with pytest.raises(ValueError, match="does not match"):
            service.review_instrument(
                "IDX:BBCA",
                decision=InstrumentReviewDecision.VERIFIED,
                reviewer_label="Local operator",
                evidence_reference="Documents/ReviewEvidence/BBCA.pdf",
                evidence_sha256=EVIDENCE_SHA256,
                notes="Wrong instrument supplied.",
                verified_instrument=verified_contract("IDX:BBRI"),
            )

        with pytest.raises(ValueError, match="SHA-256"):
            service.review_instrument(
                "IDX:BBCA",
                decision=InstrumentReviewDecision.VERIFIED,
                reviewer_label="Local operator",
                evidence_reference="Documents/ReviewEvidence/BBCA.pdf",
                evidence_sha256="not-a-hash",
                notes="Invalid evidence digest.",
                verified_instrument=verified_contract(),
            )

        with database.sessions() as session:
            instrument = session.get(InstrumentRegistryRecord, "IDX:BBCA")
            assert instrument is not None
            assert instrument.verification_status == "UNVERIFIED"
            assert session.scalar(sqlalchemy.select(InstrumentReviewEventRecord)) is None
    finally:
        database.close()


def test_explicit_verified_review_updates_master_and_appends_evidence(tmp_path) -> None:
    database = Database.open(tmp_path / "verified.sqlite3")
    database.upgrade()
    create_placeholder(database)
    try:
        service = InstrumentReviewService(database.sessions)
        result = service.review_instrument(
            "IDX:BBCA",
            decision=InstrumentReviewDecision.VERIFIED,
            reviewer_label="Ridwan / manual review",
            evidence_reference="Documents/ReviewEvidence/BBCA-profile.pdf",
            evidence_sha256=EVIDENCE_SHA256,
            notes="Ticker, issuer, exchange, currency, and lot metadata checked manually.",
            verified_instrument=verified_contract(),
            reviewed_at=NOW,
        )

        assert result.previous_status == "UNVERIFIED"
        assert result.verification_status == "VERIFIED"
        assert result.reviewed_at_utc == NOW.isoformat()

        with database.sessions() as session:
            instrument = session.get(InstrumentRegistryRecord, "IDX:BBCA")
            review = session.get(InstrumentReviewEventRecord, result.review_id)
            assert instrument is not None
            assert instrument.verification_status == "VERIFIED"
            assert instrument.ticker == "BBCA"
            assert instrument.exchange == "IDX"
            assert instrument.company_name == "PT Bank Central Asia Tbk"
            assert instrument.currency == "IDR"
            assert instrument.instrument_type == "EQUITY"
            assert instrument.lot_size == 100
            assert instrument.minimum_investment == "50000"
            assert instrument.last_review_id == result.review_id
            assert review is not None
            assert review.previous_status == "UNVERIFIED"
            assert review.decision == "VERIFIED"
            assert review.reviewer_label == "Ridwan / manual review"
            assert review.evidence_sha256 == EVIDENCE_SHA256
            assert review.evidence_reference.endswith("BBCA-profile.pdf")
            assert '"ticker":"BBCA"' in (review.reviewed_metadata_json or "")
    finally:
        database.close()


def test_rejected_review_is_recorded_and_can_be_replaced_by_later_verified_review(tmp_path) -> None:
    database = Database.open(tmp_path / "re-review.sqlite3")
    database.upgrade()
    create_placeholder(database)
    try:
        service = InstrumentReviewService(database.sessions)
        rejected = service.review_instrument(
            "IDX:BBCA",
            decision=InstrumentReviewDecision.REJECTED,
            reviewer_label="Local operator",
            evidence_reference="Documents/ReviewEvidence/rejection-note.pdf",
            evidence_sha256=EVIDENCE_SHA256,
            notes="Available evidence did not establish the instrument identity.",
            reviewed_at=NOW,
        )
        assert rejected.verification_status == "REJECTED"

        verified = service.review_instrument(
            "IDX:BBCA",
            decision=InstrumentReviewDecision.VERIFIED,
            reviewer_label="Local operator",
            evidence_reference="Documents/ReviewEvidence/official-profile.pdf",
            evidence_sha256="b" * 64,
            notes="New authoritative evidence reviewed; identity confirmed.",
            verified_instrument=verified_contract(),
            reviewed_at=datetime(2026, 11, 21, 11, 0, tzinfo=UTC),
        )
        assert verified.previous_status == "REJECTED"
        assert verified.verification_status == "VERIFIED"

        with database.sessions() as session:
            events = session.scalars(
                sqlalchemy.select(InstrumentReviewEventRecord).order_by(
                    InstrumentReviewEventRecord.reviewed_at_utc
                )
            ).all()
            assert [event.decision for event in events] == ["REJECTED", "VERIFIED"]
            assert [event.previous_status for event in events] == ["UNVERIFIED", "REJECTED"]
    finally:
        database.close()


def test_review_events_are_append_only(tmp_path) -> None:
    database = Database.open(tmp_path / "append-only.sqlite3")
    database.upgrade()
    create_placeholder(database)
    try:
        result = InstrumentReviewService(database.sessions).review_instrument(
            "IDX:BBCA",
            decision=InstrumentReviewDecision.VERIFIED,
            reviewer_label="Local operator",
            evidence_reference="Documents/ReviewEvidence/BBCA.pdf",
            evidence_sha256=EVIDENCE_SHA256,
            notes="Evidence reviewed.",
            verified_instrument=verified_contract(),
            reviewed_at=NOW,
        )

        with (
            database.engine.connect() as connection,
            pytest.raises(
                sqlalchemy.exc.IntegrityError,
                match="instrument_review_events is append-only",
            ),
        ):
            connection.execute(
                sqlalchemy.text(
                    "UPDATE instrument_review_events SET notes = 'tampered' "
                    "WHERE review_id = :review_id"
                ),
                {"review_id": result.review_id},
            )

        with (
            database.engine.connect() as connection,
            pytest.raises(sqlalchemy.exc.IntegrityError, match="instrument_review_events is append-only"),
        ):
            connection.execute(
                sqlalchemy.text(
                    "DELETE FROM instrument_review_events WHERE review_id = :review_id"
                ),
                {"review_id": result.review_id},
            )
    finally:
        database.close()
