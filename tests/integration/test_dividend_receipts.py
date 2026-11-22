# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Persistence tests for confirmed dividend receipts."""

from pathlib import Path

import pytest
import sqlalchemy as sa

from rfinance.storage.database import Database


def test_migration_extends_ledger_event_types_and_creates_receipt_table(
    tmp_path: Path,
) -> None:
    database = Database.open(tmp_path / "receipts.sqlite3")
    database.upgrade()

    with database.sessions.begin() as session:
        session.execute(
            sa.text(
                "INSERT INTO portfolio_ledger_events "
                "(event_id, sequence, occurred_at_utc, event_type, currency, amount, "
                "fees, taxes) VALUES "
                "('legacy', 1, '2026-11-21T00:00:00+00:00', 'CAPITAL_INJECTION', "
                "'IDR', '5000000', '0', '0')"
            )
        )

    with database.sessions.begin() as session:
        session.execute(
            sa.text(
                "INSERT INTO portfolio_ledger_events "
                "(event_id, sequence, occurred_at_utc, event_type, currency, amount, "
                "instrument_id, source_reference, fees, taxes) VALUES "
                "('receipt', 2, '2026-11-22T00:00:00+00:00', 'CONFIRMED_DIVIDEND', "
                "'IDR', '100000', 'IDX:BBCA', 'DIVIDEND_RECEIPT:event-1', '0', '0')"
            )
        )

    assert sa.inspect(database.engine).has_table("dividend_receipts") is True

    with database.sessions.begin() as session:
        session.execute(
            sa.text(
                "INSERT INTO dividend_receipts "
                "(receipt_id, dividend_event_id, instrument_id, net_amount, "
                "reinvestment, money_market, withdrawal, reinvest_weight, "
                "money_market_weight, withdrawal_weight, recorded_at_utc, "
                "methodology_version) VALUES "
                "('r1', 'event-1', 'IDX:BBCA', '100000', '50000', '30000', '20000', "
                "'0.5', '0.3', '0.2', '2026-11-22T00:00:00+00:00', 'dividend-receipt-v1')"
            )
        )
    with pytest.raises(sa.exc.IntegrityError), database.sessions.begin() as session:
        session.execute(
            sa.text(
                "INSERT INTO dividend_receipts "
                "(receipt_id, dividend_event_id, instrument_id, net_amount, "
                "reinvestment, money_market, withdrawal, reinvest_weight, "
                "money_market_weight, withdrawal_weight, recorded_at_utc, "
                "methodology_version) VALUES "
                "('r2', 'event-1', 'IDX:BBCA', '100000', '50000', '30000', '20000', "
                "'0.5', '0.3', '0.2', '2026-11-22T00:00:00+00:00', 'dividend-receipt-v1')"
            )
        )
    with pytest.raises(sa.exc.IntegrityError), database.sessions.begin() as session:
        session.execute(sa.text("UPDATE dividend_receipts SET net_amount = '1'"))
    database.close()


def _seed_verified_dividend(database: Database, *, status: str = "CONFIRMED") -> str:
    from datetime import UTC, datetime
    from decimal import Decimal

    from rfinance.application.dividend_events import (
        DividendEventService,
        DividendReviewDecision,
    )
    from rfinance.data.contracts import (
        DividendEventContract,
        DividendEventStatus,
        DividendType,
    )
    from rfinance.storage.models.instrument_registry import InstrumentRegistryRecord

    moment = datetime(2026, 11, 22, 10, tzinfo=UTC)
    with database.sessions.begin() as session:
        if session.get(InstrumentRegistryRecord, "IDX:BBCA") is None:
            session.add(
                InstrumentRegistryRecord(
                    instrument_id="IDX:BBCA",
                    verification_status="VERIFIED",
                    created_at_utc=moment.isoformat(),
                    updated_at_utc=moment.isoformat(),
                )
            )
    events = DividendEventService(database.sessions, data_directory=None)
    recorded = events.record_event(
        DividendEventContract(
            event_key=f"cash-{status}",
            instrument_id="IDX:BBCA",
            source_label="Issuer report",
            dividend_type=DividendType.CASH,
            event_status=DividendEventStatus(status),
            amount_per_share=Decimal("500"),
            currency="IDR",
            ex_date=__import__("datetime").date(2026, 5, 20),
            acquired_at=moment,
        ),
        recorded_at=moment,
    )
    if status in {"CONFIRMED", "HISTORICAL", "ANNOUNCED"}:
        events.review_event(
            recorded.event_id,
            decision=DividendReviewDecision.VERIFIED,
            reviewer_label="Operator",
            evidence_reference="Documents/report.pdf",
            evidence_sha256="a" * 64,
            notes="Checked issuer report",
        )
    return recorded.event_id


def test_post_receipt_splits_exactly_and_books_withdrawal(tmp_path: Path) -> None:
    from decimal import Decimal

    from rfinance.application.dividend_events import DividendEventService
    from rfinance.application.dividend_receipts import DividendReceiptService
    from rfinance.application.portfolio_ledger import PortfolioLedgerService
    from rfinance.storage.repositories.portfolio_ledger import LedgerRepository

    database = Database.open(tmp_path / "post.sqlite3")
    database.upgrade()
    dividend_event_id = _seed_verified_dividend(database)
    ledger = PortfolioLedgerService(LedgerRepository(database.sessions), lot_sizes={})
    ledger.initialize_portfolio(Decimal("5000000"))
    service = DividendReceiptService(
        database.sessions,
        dividend_events=DividendEventService(database.sessions),
        portfolio_ledger=ledger,
    )

    result = service.post_receipt(dividend_event_id, net_amount=Decimal("100000"))

    assert result.net_amount == Decimal("100000")
    assert result.reinvestment == Decimal("50000.0")
    assert result.money_market == Decimal("30000.0")
    assert result.withdrawal == Decimal("20000.0")
    snapshot = ledger.snapshot()
    assert snapshot.confirmed_dividend_income == Decimal("100000")
    assert snapshot.cash_balance == Decimal("5080000")
    assert service.receipt_for_event(dividend_event_id) is not None
    database.close()


def test_post_receipt_rejects_unverified_and_announced_events(tmp_path: Path) -> None:
    from decimal import Decimal

    from rfinance.application.dividend_events import DividendEventService
    from rfinance.application.dividend_receipts import DividendReceiptService
    from rfinance.application.portfolio_ledger import PortfolioLedgerService
    from rfinance.storage.repositories.portfolio_ledger import LedgerRepository

    database = Database.open(tmp_path / "gate.sqlite3")
    database.upgrade()
    ledger = PortfolioLedgerService(LedgerRepository(database.sessions), lot_sizes={})
    service = DividendReceiptService(
        database.sessions,
        dividend_events=DividendEventService(database.sessions),
        portfolio_ledger=ledger,
    )

    unverified = _seed_verified_dividend_unverified(database)
    with pytest.raises(ValueError, match="VERIFIED"):
        service.post_receipt(unverified, net_amount=Decimal("1000"))

    announced = _seed_verified_dividend(database, status="ANNOUNCED")
    with pytest.raises(ValueError, match="observed"):
        service.post_receipt(announced, net_amount=Decimal("1000"))
    database.close()


def _seed_verified_dividend_unverified(database: Database) -> str:
    from datetime import UTC, datetime
    from decimal import Decimal

    from rfinance.application.dividend_events import DividendEventService
    from rfinance.data.contracts import (
        DividendEventContract,
        DividendEventStatus,
        DividendType,
    )
    from rfinance.storage.models.instrument_registry import InstrumentRegistryRecord

    moment = datetime(2026, 11, 22, 10, tzinfo=UTC)
    with database.sessions.begin() as session:
        session.add(
            InstrumentRegistryRecord(
                instrument_id="IDX:BBCA",
                verification_status="VERIFIED",
                created_at_utc=moment.isoformat(),
                updated_at_utc=moment.isoformat(),
            )
        )
    return (
        DividendEventService(database.sessions)
        .record_event(
            DividendEventContract(
                event_key="cash-unverified",
                instrument_id="IDX:BBCA",
                source_label="Issuer report",
                dividend_type=DividendType.CASH,
                event_status=DividendEventStatus.CONFIRMED,
                amount_per_share=Decimal("500"),
                currency="IDR",
                ex_date=__import__("datetime").date(2026, 5, 20),
                acquired_at=moment,
            ),
            recorded_at=moment,
        )
        .event_id
    )


def test_post_receipt_rejects_duplicate_and_invalid_amount(tmp_path: Path) -> None:
    from decimal import Decimal

    from rfinance.application.dividend_events import DividendEventService
    from rfinance.application.dividend_receipts import DividendReceiptService
    from rfinance.application.portfolio_ledger import PortfolioLedgerService
    from rfinance.storage.repositories.portfolio_ledger import LedgerRepository

    database = Database.open(tmp_path / "dup.sqlite3")
    database.upgrade()
    event_id = _seed_verified_dividend(database)
    ledger = PortfolioLedgerService(LedgerRepository(database.sessions), lot_sizes={})
    ledger.initialize_portfolio(Decimal("5000000"))
    service = DividendReceiptService(
        database.sessions,
        dividend_events=DividendEventService(database.sessions),
        portfolio_ledger=ledger,
    )
    service.post_receipt(event_id, net_amount=Decimal("100000"))

    with pytest.raises(ValueError, match="already posted"):
        service.post_receipt(event_id, net_amount=Decimal("100000"))
    with pytest.raises(ValueError, match="positive"):
        service.post_receipt("other-event", net_amount=Decimal("0"))
    database.close()
