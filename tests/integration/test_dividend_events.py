from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy

from rfinance.application.dividend_events import (
    DividendEventService,
    DividendReviewDecision,
)
from rfinance.data.contracts import DividendEventContract, DividendEventStatus, DividendType
from rfinance.storage.database import Database
from rfinance.storage.models.data_ingestion import SourceRegistryRecord
from rfinance.storage.models.dividend import DividendEventRecord, DividendReviewEventRecord
from rfinance.storage.models.instrument_registry import InstrumentRegistryRecord

NOW = datetime(2026, 11, 21, 10, 0, tzinfo=UTC)
DIGEST = "a" * 64
INSTRUMENT_ID = "IDX:BBCA"


def seed_instrument(database: Database, *, status: str = "VERIFIED") -> None:
    timestamp = NOW.isoformat()
    with database.sessions.begin() as session:
        session.add(
            InstrumentRegistryRecord(
                instrument_id=INSTRUMENT_ID,
                verification_status=status,
                created_at_utc=timestamp,
                updated_at_utc=timestamp,
            )
        )


def make_contract(
    *,
    event_key: str = "cash-2026-1",
    amount: Decimal | None = Decimal("150"),
    dividend_type: DividendType = DividendType.CASH,
    status: DividendEventStatus = DividendEventStatus.CONFIRMED,
    ex_date: date = date(2026, 5, 20),
    payment_date: date | None = date(2026, 6, 5),
    source_label: str = "Issuer annual report",
) -> DividendEventContract:
    return DividendEventContract(
        event_key=event_key,
        instrument_id=INSTRUMENT_ID,
        source_label=source_label,
        dividend_type=dividend_type,
        event_status=status,
        amount_per_share=amount,
        currency="IDR",
        ex_date=ex_date,
        payment_date=payment_date,
        acquired_at=NOW,
        original_value="Rp150 per share",
    )


def test_record_event_persists_provenance_without_promoting_quality(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "dividends.sqlite3")
    database.upgrade()
    seed_instrument(database)
    service = DividendEventService(database.sessions, data_directory=tmp_path / "data")

    result = service.record_event(make_contract(), recorded_at=NOW)

    assert result.raw_quality == "UNVERIFIED"
    events = service.list_events()
    assert len(events) == 1
    event = events[0]
    assert event.event_id == result.event_id
    assert event.dividend_type == "CASH"
    assert event.event_status == "CONFIRMED"
    assert event.amount_per_share == Decimal("150")
    assert event.ex_date == date(2026, 5, 20)
    assert event.payment_date == date(2026, 6, 5)
    assert event.effective_quality == "UNVERIFIED"
    assert event.unit == "PER_SHARE"
    assert event.source_label == "Issuer annual report"
    assert result.source_id == event.source_id
    with database.sessions() as session:
        source = session.get(SourceRegistryRecord, result.source_id)
    assert source is not None
    assert source.access_method == "MANUAL"
    assert source.policy_status == "UNREVIEWED"
    assert source.automated_access_allowed is False
    assert source.redistribution_allowed is False
    database.close()


def test_record_event_rejects_duplicate_and_unknown_instrument(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "dividends.sqlite3")
    database.upgrade()
    seed_instrument(database)
    service = DividendEventService(database.sessions, data_directory=tmp_path / "data")

    service.record_event(make_contract(), recorded_at=NOW)
    with pytest.raises(ValueError, match="already exists"):
        service.record_event(make_contract(), recorded_at=NOW)

    unknown = make_contract(event_key="other")
    unknown = unknown.model_copy(update={"instrument_id": "IDX:UNKNOWN"})
    with pytest.raises(ValueError, match="instrument_id must exist"):
        service.record_event(unknown, recorded_at=NOW)
    database.close()


def test_review_promotes_only_verified_observed_events(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "dividends.sqlite3")
    database.upgrade()
    seed_instrument(database)
    service = DividendEventService(database.sessions, data_directory=tmp_path / "data")
    recorded = service.record_event(make_contract(), recorded_at=NOW)

    with pytest.raises(ValueError, match="instrument identity must be VERIFIED"):
        unverified_db = Database.open(tmp_path / "unverified.sqlite3")
        unverified_db.upgrade()
        seed_instrument(unverified_db, status="UNVERIFIED")
        unverified_service = DividendEventService(unverified_db.sessions)
        pending = unverified_service.record_event(make_contract(), recorded_at=NOW)
        unverified_service.review_event(
            pending.event_id,
            decision=DividendReviewDecision.VERIFIED,
            reviewer_label="Operator",
            evidence_reference="Documents/report.pdf",
            evidence_sha256=DIGEST,
            notes="Checked issuer report",
        )
        unverified_db.close()

    result = service.review_event(
        recorded.event_id,
        decision=DividendReviewDecision.VERIFIED,
        reviewer_label="Operator",
        evidence_reference="Documents/report.pdf",
        evidence_sha256=DIGEST,
        notes="Checked issuer report",
        reviewed_at=NOW,
    )
    assert result.decision == "VERIFIED"
    assert service.effective_quality(recorded.event_id) == "VERIFIED"
    history = service.review_history(recorded.event_id)
    assert len(history) == 1
    assert history[0].previous_quality == "UNVERIFIED"
    assert service.list_events()[0].effective_quality == "VERIFIED"

    estimate = service.record_event(
        make_contract(event_key="estimate-1", status=DividendEventStatus.ESTIMATED),
        recorded_at=NOW,
    )
    with pytest.raises(ValueError, match="estimate, simulation or cancellation"):
        service.review_event(
            estimate.event_id,
            decision=DividendReviewDecision.VERIFIED,
            reviewer_label="Operator",
            evidence_reference="Documents/report.pdf",
            evidence_sha256=DIGEST,
            notes="Estimated only",
        )
    database.close()


def test_review_appends_audit_and_raw_rows_are_append_only(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "dividends.sqlite3")
    database.upgrade()
    seed_instrument(database)
    service = DividendEventService(database.sessions, data_directory=tmp_path / "data")
    recorded = service.record_event(make_contract(), recorded_at=NOW)
    service.review_event(
        recorded.event_id,
        decision=DividendReviewDecision.REJECTED,
        reviewer_label="Operator",
        evidence_reference="Documents/report.pdf",
        evidence_sha256=DIGEST,
        notes="Source document did not match",
        reviewed_at=NOW,
    )

    with database.sessions.begin() as session:
        raw = session.get(DividendEventRecord, recorded.event_id)
        assert raw is not None
        assert raw.quality_status == "UNVERIFIED"
        assert raw.amount_per_share == "150"
        review = session.scalar(sqlalchemy.select(DividendReviewEventRecord))
        assert review is not None
        assert review.previous_quality == "UNVERIFIED"
        assert review.decision == "REJECTED"

    with pytest.raises(sqlalchemy.exc.IntegrityError), database.sessions.begin() as session:
        raw = session.get(DividendEventRecord, recorded.event_id)
        assert raw is not None
        raw.amount_per_share = "1"
    with pytest.raises(sqlalchemy.exc.IntegrityError), database.sessions.begin() as session:
        review = session.scalar(sqlalchemy.select(DividendReviewEventRecord))
        assert review is not None
        session.delete(review)
    database.close()


def test_review_from_file_archives_and_hashes_evidence(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "dividends.sqlite3")
    database.upgrade()
    seed_instrument(database)
    data_directory = tmp_path / "data"
    service = DividendEventService(database.sessions, data_directory=data_directory)
    recorded = service.record_event(make_contract(), recorded_at=NOW)
    evidence = tmp_path / "issuer-report.txt"
    evidence.write_text("Confirmed dividend of Rp150 per share.", encoding="utf-8")

    result = service.review_event_from_file(
        recorded.event_id,
        decision=DividendReviewDecision.VERIFIED,
        reviewer_label="Operator",
        evidence_file=evidence,
        notes="Matched the issuer report",
        reviewed_at=NOW,
    )

    archived = data_directory / result.evidence_reference
    assert archived.is_file()
    assert archived.read_bytes() == evidence.read_bytes()
    assert len(result.evidence_sha256) == 64
    assert result.evidence_sha256 != DIGEST
    assert service.effective_quality(recorded.event_id) == "VERIFIED"
    database.close()


def test_calendar_labels_confirmed_and_estimated_events(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "dividends.sqlite3")
    database.upgrade()
    seed_instrument(database)
    service = DividendEventService(database.sessions, data_directory=tmp_path / "data")
    confirmed = service.record_event(make_contract(), recorded_at=NOW)
    service.review_event(
        confirmed.event_id,
        decision=DividendReviewDecision.VERIFIED,
        reviewer_label="Operator",
        evidence_reference="Documents/report.pdf",
        evidence_sha256=DIGEST,
        notes="Confirmed",
    )
    service.record_event(
        make_contract(
            event_key="estimate-1",
            status=DividendEventStatus.ESTIMATED,
            ex_date=date(2026, 9, 10),
            payment_date=None,
        ),
        recorded_at=NOW,
    )

    entries = service.calendar(start=date(2026, 1, 1), end=date(2026, 12, 31))
    by_key = {(item.event_id, item.date_kind): item for item in entries}
    assert len(entries) == 3
    assert by_key[(confirmed.event_id, "EX_DATE")].is_confirmed_cash is True
    assert by_key[(confirmed.event_id, "PAYMENT_DATE")].is_confirmed_cash is True
    estimate = next(item for item in entries if item.date_kind == "EX_DATE" and item.is_estimate)
    assert estimate.is_confirmed_cash is False
    assert estimate.effective_quality == "UNVERIFIED"
    database.close()


def test_analytics_uses_only_verified_observed_cash_events(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "dividends.sqlite3")
    database.upgrade()
    seed_instrument(database)
    service = DividendEventService(database.sessions, data_directory=tmp_path / "data")

    empty = service.analytics(
        instrument_id=INSTRUMENT_ID,
        as_of=date(2026, 11, 21),
        currency="IDR",
        price=Decimal("9500"),
    )
    assert empty.trailing_dividend_per_share is None
    assert empty.trailing_yield is None
    assert empty.verified_cash_event_count == 0
    assert empty.consistency.consecutive_years == 0

    for key, amount, ex_date in (
        ("cash-2025", Decimal("100"), date(2025, 5, 20)),
        ("cash-2026", Decimal("150"), date(2026, 5, 20)),
    ):
        recorded = service.record_event(
            make_contract(event_key=key, amount=amount, ex_date=ex_date),
            recorded_at=NOW,
        )
        service.review_event(
            recorded.event_id,
            decision=DividendReviewDecision.VERIFIED,
            reviewer_label="Operator",
            evidence_reference="Documents/report.pdf",
            evidence_sha256=DIGEST,
            notes="Confirmed",
        )
    unconfirmed = service.record_event(
        make_contract(
            event_key="announced-1",
            amount=Decimal("999"),
            status=DividendEventStatus.ANNOUNCED,
            ex_date=date(2026, 10, 1),
        ),
        recorded_at=NOW,
    )
    assert unconfirmed.event_id

    report = service.analytics(
        instrument_id=INSTRUMENT_ID,
        as_of=date(2026, 11, 21),
        currency="IDR",
        price=Decimal("9500"),
        estimated_annual_dividend=Decimal("200"),
        withholding_rate=Decimal("0.10"),
    )
    # The 365-day trailing window includes only the 2026 event; the 2025 event
    # remains in the annual consistency history but is not trailing cash.
    assert report.trailing_dividend_per_share == Decimal("150")
    assert report.trailing_yield is not None
    assert report.trailing_yield.basis == "TRAILING"
    assert report.trailing_yield.is_estimate is False
    assert report.forward_yield is not None
    assert report.forward_yield.basis == "FORWARD"
    assert report.forward_yield.is_estimate is True
    assert report.net_trailing_per_share == Decimal("135.0")
    assert report.verified_cash_event_count == 2
    assert report.consistency.years_observed == 2
    assert report.consistency.consecutive_years == 2
    assert report.annual_dividends == {2025: Decimal("100"), 2026: Decimal("150")}

    gross_only = service.analytics(
        instrument_id=INSTRUMENT_ID,
        as_of=date(2026, 11, 21),
        currency="IDR",
    )
    assert gross_only.net_trailing_per_share is None
    assert gross_only.trailing_yield is None
    database.close()
