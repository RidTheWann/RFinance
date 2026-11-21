# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from rfinance.application.observation_review import (
    ObservationReviewDecision,
    ObservationReviewService,
)
from rfinance.application.portfolio_ledger import PortfolioLedgerService
from rfinance.application.portfolio_valuation import PortfolioValuationService
from rfinance.domain.portfolio.ledger import LedgerEvent, LedgerEventType, VerifiedLotSize
from rfinance.storage.database import Database
from rfinance.storage.models.data_ingestion import (
    DataImportBatchRecord,
    MarketObservationRecord,
    SourceRegistryRecord,
)
from rfinance.storage.models.instrument_registry import InstrumentRegistryRecord
from rfinance.storage.repositories.portfolio_ledger import LedgerRepository

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
DIGEST = "a" * 64
OBSERVATION_ID = "observation-bbca"


def seed_database(
    database: Database,
    *,
    raw_quality: str = "UNVERIFIED",
    observed_at: datetime | None = None,
    source_policy: str = "UNREVIEWED",
    instrument_status: str = "VERIFIED",
) -> None:
    observed = observed_at or (NOW - timedelta(hours=1))
    acquired = observed + timedelta(minutes=5)
    with database.sessions.begin() as session:
        session.add(
            SourceRegistryRecord(
                source_id="source-user-import",
                display_name="User-supplied BBCA file",
                access_method="USER_IMPORT",
                policy_status=source_policy,
                description="User-provided market data",
                terms_url=None,
                reviewed_at_utc=None,
                automated_access_allowed=False,
                redistribution_allowed=False,
                created_at_utc=NOW.isoformat(),
            )
        )
        session.flush()
        session.add(
            InstrumentRegistryRecord(
                instrument_id="IDX:BBCA",
                ticker="BBCA",
                exchange="IDX",
                instrument_type="EQUITY",
                company_name="Bank Central Asia",
                currency="IDR",
                sector="Financials",
                active=True,
                lot_size=100,
                minimum_investment=None,
                verification_status=instrument_status,
                created_at_utc=NOW.isoformat(),
                updated_at_utc=NOW.isoformat(),
            )
        )
        session.flush()
        session.add(
            DataImportBatchRecord(
                batch_id="batch-bbca",
                source_id="source-user-import",
                original_filename="prices.csv",
                file_sha256="b" * 64,
                document_relative_path="Documents/MarketImports/prices.csv",
                imported_at_utc=NOW.isoformat(),
                row_count=1,
                accepted_rows=1,
                rejected_rows=0,
            )
        )
        session.flush()
        session.add(
            MarketObservationRecord(
                observation_id=OBSERVATION_ID,
                batch_id="batch-bbca",
                source_id="source-user-import",
                instrument_id="IDX:BBCA",
                observed_at_utc=observed.astimezone(UTC).isoformat(),
                acquired_at_utc=acquired.astimezone(UTC).isoformat(),
                open=None,
                high=None,
                low=None,
                close="10000",
                volume=None,
                currency="IDR",
                quality_status=raw_quality,
                original_row_json="{}",
                transformation_version="csv-market-v1",
            )
        )


def make_ledger(database: Database) -> PortfolioLedgerService:
    lot_sizes = {
        "IDX:BBCA": VerifiedLotSize(
            size=Decimal("1"),
            source_reference="fixture:verified-lot-size",
            verified_at=NOW,
        )
    }
    service = PortfolioLedgerService(
        LedgerRepository(database.sessions),
        lot_sizes=lot_sizes,
    )
    service.initialize_portfolio(Decimal("1000000"))
    service.append(
        LedgerEvent(
            event_id="buy-bbca",
            sequence=2,
            occurred_at=NOW,
            event_type=LedgerEventType.BUY,
            currency="IDR",
            instrument_id="IDX:BBCA",
            quantity=Decimal("10"),
            unit_price=Decimal("9000"),
        )
    )
    return service


def test_valuation_uses_only_latest_evidence_backed_eligible_price(tmp_path) -> None:
    database = Database.open(tmp_path / "eligible.sqlite3")
    database.upgrade()
    try:
        seed_database(database)
        ledger = make_ledger(database)
        review = ObservationReviewService(database.sessions)
        review.review_observation(
            OBSERVATION_ID,
            decision=ObservationReviewDecision.VERIFIED,
            reviewer_label="Test reviewer",
            evidence_reference="Documents/ReviewEvidence/bbca.pdf",
            evidence_sha256=DIGEST,
            notes="Manually checked issuer document and price timestamp.",
            reviewed_at=NOW,
        )

        result = PortfolioValuationService(database.sessions, ledger).value(as_of=NOW)

        assert result.valuation.is_complete is True
        assert result.valuation.cash == Decimal("910000")
        assert result.valuation.market_value == Decimal("100000")
        assert result.valuation.total_value == Decimal("1010000")
        assert result.valuation.unrealized_profit_loss == Decimal("10000")
        assert len(result.price_evidence) == 1
        assert result.price_evidence[0].observation_id == OBSERVATION_ID
        assert result.price_evidence[0].source_name == "User-supplied BBCA file"
        assert result.price_evidence[0].effective_quality == "VERIFIED"
        assert result.eligibility_methodology == "eligibility-observation-v1"
    finally:
        database.close()


def test_unreviewed_price_is_not_substituted_with_cost_or_zero(tmp_path) -> None:
    database = Database.open(tmp_path / "unverified.sqlite3")
    database.upgrade()
    try:
        seed_database(database)
        ledger = make_ledger(database)

        result = PortfolioValuationService(database.sessions, ledger).value(as_of=NOW)

        assert result.valuation.is_complete is False
        assert result.valuation.market_value == Decimal("0")
        assert result.valuation.total_value == Decimal("910000")
        assert result.valuation.unrealized_profit_loss == Decimal("0")
        assert result.price_evidence == ()
        assert result.unvalued_positions[0].instrument_id == "IDX:BBCA"
        assert "OBSERVATION_UNVERIFIED" in result.unvalued_positions[0].reasons
    finally:
        database.close()


def test_stale_price_is_rejected_even_when_raw_status_is_verified(tmp_path) -> None:
    database = Database.open(tmp_path / "stale.sqlite3")
    database.upgrade()
    try:
        seed_database(
            database,
            raw_quality="VERIFIED",
            observed_at=NOW - timedelta(days=12),
        )
        ledger = make_ledger(database)

        result = PortfolioValuationService(database.sessions, ledger).value(as_of=NOW)

        assert result.valuation.is_complete is False
        assert result.price_evidence == ()
        assert "STALE_OBSERVATION" in result.unvalued_positions[0].reasons
    finally:
        database.close()


def test_blocked_source_is_rejected_and_reported(tmp_path) -> None:
    database = Database.open(tmp_path / "blocked-source.sqlite3")
    database.upgrade()
    try:
        seed_database(database, raw_quality="VERIFIED", source_policy="BLOCKED")
        ledger = make_ledger(database)

        result = PortfolioValuationService(database.sessions, ledger).value(as_of=NOW)

        assert result.valuation.is_complete is False
        assert "SOURCE_BLOCKED" in result.unvalued_positions[0].reasons
    finally:
        database.close()


def test_unverified_instrument_cannot_supply_a_price(tmp_path) -> None:
    database = Database.open(tmp_path / "unverified-instrument.sqlite3")
    database.upgrade()
    try:
        seed_database(
            database,
            raw_quality="VERIFIED",
            instrument_status="UNVERIFIED",
        )
        ledger = make_ledger(database)

        result = PortfolioValuationService(database.sessions, ledger).value(as_of=NOW)

        assert result.valuation.is_complete is False
        assert "INSTRUMENT_UNVERIFIED" in result.unvalued_positions[0].reasons
    finally:
        database.close()


def test_conflicting_latest_verified_sources_do_not_choose_a_price_arbitrarily(tmp_path) -> None:
    database = Database.open(tmp_path / "conflicting.sqlite3")
    database.upgrade()
    try:
        seed_database(database, raw_quality="VERIFIED")
        with database.sessions.begin() as session:
            session.add(
                SourceRegistryRecord(
                    source_id="source-second",
                    display_name="Second source",
                    access_method="MANUAL",
                    policy_status="APPROVED",
                    description="Independent test source",
                    terms_url="https://example.invalid/policy",
                    reviewed_at_utc=NOW.isoformat(),
                    automated_access_allowed=False,
                    redistribution_allowed=False,
                    created_at_utc=NOW.isoformat(),
                )
            )
            session.flush()
            session.add(
                DataImportBatchRecord(
                    batch_id="batch-second",
                    source_id="source-second",
                    original_filename="second-prices.csv",
                    file_sha256="c" * 64,
                    document_relative_path="Documents/MarketImports/second-prices.csv",
                    imported_at_utc=NOW.isoformat(),
                    row_count=1,
                    accepted_rows=1,
                    rejected_rows=0,
                )
            )
            session.flush()
            session.add(
                MarketObservationRecord(
                    observation_id="observation-conflict",
                    batch_id="batch-second",
                    source_id="source-second",
                    instrument_id="IDX:BBCA",
                    observed_at_utc=(NOW - timedelta(hours=1)).isoformat(),
                    acquired_at_utc=(NOW - timedelta(minutes=50)).isoformat(),
                    open=None,
                    high=None,
                    low=None,
                    close="10100",
                    volume=None,
                    currency="IDR",
                    quality_status="VERIFIED",
                    original_row_json="{}",
                    transformation_version="manual-v1",
                )
            )
        ledger = make_ledger(database)

        result = PortfolioValuationService(database.sessions, ledger).value(as_of=NOW)

        assert result.valuation.is_complete is False
        assert result.price_evidence == ()
        assert result.unvalued_positions[0].reasons == (
            "CONFLICTING_LATEST_OBSERVATIONS",
        )
    finally:
        database.close()


def test_empty_position_portfolio_values_cash_without_external_data(tmp_path) -> None:
    database = Database.open(tmp_path / "cash-only.sqlite3")
    database.upgrade()
    try:
        ledger = PortfolioLedgerService(
            LedgerRepository(database.sessions),
            lot_sizes={},
        )
        ledger.initialize_portfolio(Decimal("5000000"))

        result = PortfolioValuationService(database.sessions, ledger).value(as_of=NOW)

        assert result.valuation.is_complete is True
        assert result.valuation.cash == Decimal("5000000")
        assert result.valuation.total_value == Decimal("5000000")
        assert result.valuation.positions == ()
        assert result.observations_considered == 0
    finally:
        database.close()


@pytest.mark.parametrize("currency", ["USD", "EUR"])
def test_mismatched_portfolio_currency_is_rejected(tmp_path, currency: str) -> None:
    database = Database.open(tmp_path / f"{currency}.sqlite3")
    database.upgrade()
    try:
        ledger = PortfolioLedgerService(
            LedgerRepository(database.sessions),
            lot_sizes={},
            base_currency=currency,
        )
        ledger.initialize_portfolio(Decimal("1000"))
        with pytest.raises(ValueError, match="does not match"):
            PortfolioValuationService(
                database.sessions,
                ledger,
                base_currency="IDR",
            ).value(as_of=NOW)
    finally:
        database.close()
