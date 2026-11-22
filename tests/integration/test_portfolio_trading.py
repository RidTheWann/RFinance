# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Verified lot-size derivation and audited simulated trade entry."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from rfinance.application.portfolio_trading import (
    PortfolioTradingService,
    VerifiedLotSizeService,
)
from rfinance.domain.portfolio.ledger import LedgerValidationError
from rfinance.storage.database import Database
from rfinance.storage.models.instrument_registry import (
    InstrumentRegistryRecord,
    InstrumentReviewEventRecord,
)
from rfinance.storage.repositories.portfolio_ledger import LedgerRepository

NOW = datetime(2026, 11, 22, 12, tzinfo=UTC)


def seed_instrument(
    database: Database,
    *,
    status: str = "VERIFIED",
    lot_size: int | None = 100,
    reviewed: bool = True,
) -> None:
    with database.sessions.begin() as session:
        session.add(
            InstrumentRegistryRecord(
                instrument_id="IDX:BBCA",
                verification_status=status,
                lot_size=lot_size,
                active=True,
                currency="IDR",
                created_at_utc=NOW.isoformat(),
                updated_at_utc=NOW.isoformat(),
                last_reviewed_at_utc=NOW.isoformat() if reviewed else None,
                last_review_id="review-1" if reviewed else None,
            )
        )
        if reviewed:
            session.add(
                InstrumentReviewEventRecord(
                    review_id="review-1",
                    instrument_id="IDX:BBCA",
                    previous_status="UNVERIFIED",
                    decision="VERIFIED",
                    reviewed_at_utc=NOW.isoformat(),
                    reviewer_label="Operator",
                    evidence_reference="Documents/IDX-lot-rule.pdf",
                    evidence_sha256="a" * 64,
                    notes="Verified the IDX lot rule",
                )
            )


def trading_service(database: Database) -> PortfolioTradingService:
    return PortfolioTradingService(
        LedgerRepository(database.sessions),
        lot_sizes=VerifiedLotSizeService(database.sessions),
    )


def test_verified_lot_size_requires_evidence_and_verified_identity(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "lots.sqlite3")
    database.upgrade()
    seed_instrument(database)
    lots = VerifiedLotSizeService(database.sessions)

    rule = lots.lot_size_for("IDX:BBCA")
    assert rule is not None
    assert rule.size == Decimal("100")
    assert rule.source_reference == "Documents/IDX-lot-rule.pdf"
    assert rule.verified_at == NOW
    database.close()

    unverified = Database.open(tmp_path / "lots-unverified.sqlite3")
    unverified.upgrade()
    seed_instrument(unverified, status="UNVERIFIED")
    assert VerifiedLotSizeService(unverified.sessions).lot_size_for("IDX:BBCA") is None
    unverified.close()


def test_buy_uses_verified_lot_size_and_updates_ledger(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "buy.sqlite3")
    database.upgrade()
    seed_instrument(database)
    service = trading_service(database)
    from rfinance.application.portfolio_ledger import PortfolioLedgerService

    PortfolioLedgerService(LedgerRepository(database.sessions), lot_sizes={}).initialize_portfolio(
        Decimal("5000000")
    )

    result = service.buy(
        "IDX:BBCA",
        quantity=Decimal("200"),
        unit_price=Decimal("9500"),
        fees=Decimal("1000"),
        occurred_at=NOW,
    )

    assert result.cash_balance == Decimal("3099000")
    assert result.positions["IDX:BBCA"].quantity == Decimal("200")
    assert result.total_fees == Decimal("1000")
    events = service.events()
    assert events[-1].event_type.value == "BUY"
    database.close()


def test_sell_requires_held_position_and_lot_multiple(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "sell.sqlite3")
    database.upgrade()
    seed_instrument(database)
    service = trading_service(database)
    from rfinance.application.portfolio_ledger import PortfolioLedgerService

    PortfolioLedgerService(LedgerRepository(database.sessions), lot_sizes={}).initialize_portfolio(
        Decimal("5000000")
    )
    service.buy("IDX:BBCA", quantity=Decimal("100"), unit_price=Decimal("9000"), occurred_at=NOW)

    with pytest.raises(LedgerValidationError, match="lot size"):
        service.sell(
            "IDX:BBCA", quantity=Decimal("50"), unit_price=Decimal("9500"), occurred_at=NOW
        )
    result = service.sell(
        "IDX:BBCA",
        quantity=Decimal("100"),
        unit_price=Decimal("9500"),
        occurred_at=NOW,
    )
    assert result.positions == {}
    assert result.cash_balance > Decimal("4900000")
    database.close()


def test_trade_without_verified_lot_evidence_is_blocked(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "blocked.sqlite3")
    database.upgrade()
    seed_instrument(database, lot_size=None)
    from rfinance.application.portfolio_ledger import PortfolioLedgerService

    PortfolioLedgerService(LedgerRepository(database.sessions), lot_sizes={}).initialize_portfolio(
        Decimal("5000000")
    )
    service = trading_service(database)
    with pytest.raises(ValueError, match="lot"):
        service.buy(
            "IDX:BBCA", quantity=Decimal("100"), unit_price=Decimal("9000"), occurred_at=NOW
        )
    database.close()
