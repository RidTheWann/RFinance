from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from rfinance.application.portfolio_ledger import PortfolioLedgerService
from rfinance.domain.portfolio.ledger import (
    InsufficientCashError,
    LedgerEvent,
    LedgerEventType,
    VerifiedLotSize,
)
from rfinance.storage.database import Database
from rfinance.storage.repositories.portfolio_ledger import LedgerRepository

NOW = datetime(2026, 11, 21, 9, 0, tzinfo=UTC)
LOT_SIZES = {
    "BBCA": VerifiedLotSize(
        size=Decimal("100"),
        source_reference="test-fixture:verified-lot-size",
        verified_at=NOW,
    )
}


def make_event(
    event_id: str,
    sequence: int,
    event_type: LedgerEventType,
    **kwargs: object,
) -> LedgerEvent:
    return LedgerEvent(
        event_id=event_id,
        sequence=sequence,
        occurred_at=NOW,
        event_type=event_type,
        **kwargs,
    )


def test_events_replay_identically_after_database_reopen(tmp_path) -> None:
    database_path = tmp_path / "portfolio.sqlite3"
    first_database = Database.open(database_path)
    first_database.upgrade()
    first_service = PortfolioLedgerService(
        LedgerRepository(first_database.sessions),
        lot_sizes=LOT_SIZES,
    )
    first_service.append(
        make_event(
            "capital",
            1,
            LedgerEventType.CAPITAL_INJECTION,
            amount=Decimal("2000000"),
        )
    )
    first_service.append(
        make_event(
            "buy",
            2,
            LedgerEventType.BUY,
            instrument_id="BBCA",
            quantity=Decimal("100"),
            unit_price=Decimal("9000.123456789123456789"),
            fees=Decimal("1000.000000000000000001"),
        )
    )
    before_restart = first_service.snapshot()
    first_database.close()

    second_database = Database.open(database_path)
    try:
        second_database.upgrade()
        second_service = PortfolioLedgerService(
            LedgerRepository(second_database.sessions),
            lot_sizes=LOT_SIZES,
        )
        after_restart = second_service.snapshot()

        assert second_service.next_sequence == 3
        assert second_service.events()[1].occurred_at == NOW
        assert after_restart.cash_balance == before_restart.cash_balance
        assert after_restart.positions == before_restart.positions
        assert after_restart.positions["BBCA"].cost_basis == Decimal("901012.345678912345678901")
    finally:
        second_database.close()


def test_invalid_append_rolls_back_without_persisting_an_event(tmp_path) -> None:
    database = Database.open(tmp_path / "atomic.sqlite3")
    database.upgrade()
    try:
        service = PortfolioLedgerService(
            LedgerRepository(database.sessions),
            lot_sizes=LOT_SIZES,
        )
        service.append(
            make_event(
                "capital",
                1,
                LedgerEventType.CAPITAL_INJECTION,
                amount=Decimal("100000"),
            )
        )

        with pytest.raises(InsufficientCashError):
            service.append(
                make_event(
                    "overspend",
                    2,
                    LedgerEventType.BUY,
                    instrument_id="BBCA",
                    quantity=Decimal("100"),
                    unit_price=Decimal("9000"),
                )
            )

        assert len(service.events()) == 1
        assert service.snapshot().cash_balance == Decimal("100000")
        assert service.next_sequence == 2
    finally:
        database.close()


def test_repository_rejects_duplicate_or_skipped_sequence(tmp_path) -> None:
    database = Database.open(tmp_path / "sequence.sqlite3")
    database.upgrade()
    try:
        repository = LedgerRepository(database.sessions)
        capital = make_event(
            "capital",
            1,
            LedgerEventType.CAPITAL_INJECTION,
            amount=Decimal("100000"),
        )
        repository.append(capital)

        skipped = make_event(
            "skipped",
            3,
            LedgerEventType.CAPITAL_INJECTION,
            amount=Decimal("100000"),
        )
        with pytest.raises(ValueError, match="next ledger sequence must be 2"):
            repository.append(skipped)

        duplicate = make_event(
            "capital",
            2,
            LedgerEventType.CAPITAL_INJECTION,
            amount=Decimal("100000"),
        )
        with pytest.raises(ValueError, match="duplicate event_id"):
            PortfolioLedgerService(
                repository,
                lot_sizes=LOT_SIZES,
            ).append(duplicate)
        assert len(repository.events()) == 1
    finally:
        database.close()


def test_database_triggers_reject_ledger_update_and_delete(tmp_path) -> None:
    database = Database.open(tmp_path / "append-only.sqlite3")
    database.upgrade()
    try:
        repository = LedgerRepository(database.sessions)
        repository.append(
            make_event(
                "capital",
                1,
                LedgerEventType.CAPITAL_INJECTION,
                amount=Decimal("100000"),
            )
        )

        with (
            database.engine.connect() as connection,
            pytest.raises(IntegrityError, match="portfolio ledger is append-only"),
        ):
            connection.execute(
                text("UPDATE portfolio_ledger_events SET amount = '1' WHERE event_id = 'capital'")
            )

        with (
            database.engine.connect() as connection,
            pytest.raises(IntegrityError, match="portfolio ledger is append-only"),
        ):
            connection.execute(
                text("DELETE FROM portfolio_ledger_events WHERE event_id = 'capital'")
            )

        assert len(repository.events()) == 1
    finally:
        database.close()
