import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy

from rfinance.application.observation_review import (
    ObservationReviewDecision,
    ObservationReviewService,
)
from rfinance.domain.eligibility.observation import ObservationQuality
from rfinance.storage.database import Database
from rfinance.storage.models.data_ingestion import (
    DataImportBatchRecord,
    MarketObservationRecord,
    SourceRegistryRecord,
)
from rfinance.storage.models.instrument_registry import InstrumentRegistryRecord
from rfinance.storage.models.observation_review import ObservationReviewEventRecord

NOW = datetime(2026, 11, 21, 10, 0, tzinfo=UTC)
DIGEST = "a" * 64
OBSERVATION_ID = "obs-1"


def seed(
    database: Database,
    *,
    instrument_status: str = "VERIFIED",
    source_policy: str = "UNREVIEWED",
    raw_quality: str = "UNVERIFIED",
) -> None:
    timestamp = NOW.isoformat()
    with database.sessions.begin() as session:
        session.add(
            SourceRegistryRecord(
                source_id="src-1",
                display_name="Local CSV",
                access_method="USER_IMPORT",
                policy_status=source_policy,
                description=None,
                terms_url=None,
                reviewed_at_utc=None,
                automated_access_allowed=False,
                redistribution_allowed=False,
                created_at_utc=timestamp,
            )
        )
        session.flush()
        session.add(
            InstrumentRegistryRecord(
                instrument_id="IDX:BBCA",
                verification_status=instrument_status,
                created_at_utc=timestamp,
                updated_at_utc=timestamp,
            )
        )
        session.flush()
        session.add(
            DataImportBatchRecord(
                batch_id="batch-1",
                source_id="src-1",
                original_filename="prices.csv",
                file_sha256="b" * 64,
                document_relative_path="Documents/MarketImports/prices.csv",
                imported_at_utc=timestamp,
                row_count=1,
                accepted_rows=1,
                rejected_rows=0,
            )
        )
        session.flush()
        session.add(
            MarketObservationRecord(
                observation_id=OBSERVATION_ID,
                batch_id="batch-1",
                source_id="src-1",
                instrument_id="IDX:BBCA",
                observed_at_utc=timestamp,
                acquired_at_utc=timestamp,
                open=None,
                high=None,
                low=None,
                close="9500",
                volume=None,
                currency="IDR",
                quality_status=raw_quality,
                original_row_json="{}",
                transformation_version="csv-market-v1",
            )
        )


@pytest.fixture
def database_factory(tmp_path: Path):
    created: list[Database] = []

    def make(**kwargs: str) -> Database:
        database = Database.open(tmp_path / f"{uuid4()}.sqlite3")
        database.upgrade()
        seed(database, **kwargs)
        created.append(database)
        return database

    yield make
    for database in created:
        database.close()


def review(
    service: ObservationReviewService,
    decision: ObservationReviewDecision = ObservationReviewDecision.VERIFIED,
    **overrides: object,
):
    values: dict[str, object] = {
        "decision": decision,
        "reviewer_label": "Local operator",
        "evidence_reference": "Documents/ReviewEvidence/price.pdf",
        "evidence_sha256": DIGEST,
        "notes": "Checked the source document and timestamp manually.",
        "reviewed_at": NOW,
    }
    values.update(overrides)
    return service.review_observation(OBSERVATION_ID, **values)  # type: ignore[arg-type]


def test_verified_review_appends_evidence_without_mutating_raw_row(database_factory) -> None:
    database = database_factory()
    service = ObservationReviewService(database.sessions)

    result = review(service)

    assert result.previous_quality == "UNVERIFIED"
    assert result.decision == "VERIFIED"
    assert result.reviewed_at_utc == NOW.isoformat()
    assert service.effective_quality(OBSERVATION_ID) == "VERIFIED"

    with database.sessions() as session:
        observation = session.get(MarketObservationRecord, OBSERVATION_ID)
        event = session.get(ObservationReviewEventRecord, result.review_id)
        assert observation is not None
        assert observation.quality_status == "UNVERIFIED"
        assert event is not None
        assert event.previous_quality == "UNVERIFIED"
        assert event.decision == "VERIFIED"
        assert event.evidence_sha256 == DIGEST
        snapshot = json.loads(event.reviewed_metadata_json or "{}")
        assert snapshot["close"] == "9500"
        assert snapshot["currency"] == "IDR"
        assert snapshot["source_id"] == "src-1"

    candidates = service.candidates_for_eligibility()
    assert len(candidates) == 1
    assert candidates[0].quality is ObservationQuality.VERIFIED
    queue = service.list_candidates()
    assert queue[0].raw_quality == "UNVERIFIED"
    assert queue[0].effective_quality == "VERIFIED"


def test_verified_review_requires_verified_instrument(database_factory) -> None:
    database = database_factory(instrument_status="UNVERIFIED")
    service = ObservationReviewService(database.sessions)
    with pytest.raises(ValueError, match="instrument identity must be VERIFIED"):
        review(service)
    with database.sessions() as session:
        assert session.scalar(sqlalchemy.select(ObservationReviewEventRecord)) is None


@pytest.mark.parametrize("policy", ["BLOCKED", "RESTRICTED"])
def test_source_policy_blocks_price_verification(database_factory, policy: str) -> None:
    database = database_factory(source_policy=policy)
    service = ObservationReviewService(database.sessions)
    with pytest.raises(ValueError, match="source policy"):
        review(service)


@pytest.mark.parametrize("quality", ["SIMULATED", "ESTIMATED", "STALE", "REJECTED", "INCOMPLETE"])
def test_only_raw_unverified_prices_can_be_promoted(database_factory, quality: str) -> None:
    database = database_factory(raw_quality=quality)
    service = ObservationReviewService(database.sessions)
    with pytest.raises(ValueError, match="raw UNVERIFIED"):
        review(service)


def test_double_verification_is_blocked(database_factory) -> None:
    database = database_factory()
    service = ObservationReviewService(database.sessions)
    review(service)
    with pytest.raises(ValueError, match="already verified"):
        review(service, reviewed_at=datetime(2026, 11, 21, 11, 0, tzinfo=UTC))


def test_rejected_review_is_recorded_and_can_be_superseded(database_factory) -> None:
    database = database_factory()
    service = ObservationReviewService(database.sessions)
    rejection = review(service, ObservationReviewDecision.REJECTED)
    assert rejection.decision == "REJECTED"
    assert service.effective_quality(OBSERVATION_ID) == "REJECTED"

    verification = review(
        service,
        reviewed_at=datetime(2026, 11, 21, 11, 0, tzinfo=UTC),
    )
    assert verification.previous_quality == "REJECTED"
    assert service.effective_quality(OBSERVATION_ID) == "VERIFIED"

    history = service.review_history(OBSERVATION_ID)
    assert [item.decision for item in history] == ["VERIFIED", "REJECTED"]
    assert [item.previous_quality for item in history] == ["REJECTED", "UNVERIFIED"]


def test_review_events_are_append_only(database_factory) -> None:
    database = database_factory()
    result = review(ObservationReviewService(database.sessions))
    with (
        database.engine.connect() as connection,
        pytest.raises(
            sqlalchemy.exc.IntegrityError,
            match="observation_review_events is append-only",
        ),
    ):
        connection.execute(
            sqlalchemy.text(
                "UPDATE observation_review_events SET notes = 'tampered' "
                "WHERE review_id = :review_id"
            ),
            {"review_id": result.review_id},
        )


def test_review_validation(database_factory) -> None:
    service = ObservationReviewService(database_factory().sessions)
    with pytest.raises(ValueError, match="SHA-256"):
        review(service, evidence_sha256="not-a-hash")
    with pytest.raises(ValueError, match="reviewer_label"):
        review(service, reviewer_label=" ")
    with pytest.raises(ValueError, match="timezone-aware"):
        review(service, reviewed_at=datetime(2026, 11, 21, 10, 0))
    with pytest.raises(TypeError, match="ObservationReviewDecision"):
        review(service, decision="VERIFIED")  # type: ignore[arg-type]


def test_file_based_review_archives_evidence(database_factory, tmp_path: Path) -> None:
    data_directory = tmp_path / "data"
    evidence = tmp_path / "price evidence.pdf"
    evidence.write_bytes(b"%PDF-1.7 sample evidence")
    database = database_factory()
    service = ObservationReviewService(database.sessions, data_directory=data_directory)

    result = service.review_observation_from_file(
        OBSERVATION_ID,
        decision=ObservationReviewDecision.VERIFIED,
        reviewer_label="Local operator",
        evidence_file=evidence,
        notes="Archived source document reviewed.",
        reviewed_at=NOW,
    )

    archive = data_directory / result.evidence_reference
    assert archive.is_file()
    assert archive.read_bytes() == evidence.read_bytes()
    assert result.evidence_sha256 != DIGEST
