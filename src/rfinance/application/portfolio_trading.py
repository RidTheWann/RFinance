# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Audited simulated trade entry using verified lot-size evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select

from rfinance.application.portfolio_ledger import PortfolioLedgerService
from rfinance.domain.portfolio.ledger import (
    LedgerEvent,
    LedgerEventType,
    LedgerReplayResult,
    LedgerValidationError,
    VerifiedLotSize,
)
from rfinance.storage.models.instrument_registry import (
    InstrumentRegistryRecord,
    InstrumentReviewEventRecord,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker

    from rfinance.storage.repositories.portfolio_ledger import LedgerRepository


class VerifiedLotSizeService:
    """Derive tradable lot sizes only from verified, evidence-backed reviews."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def lot_sizes(self) -> dict[str, VerifiedLotSize]:
        """Return all instruments with a verified lot rule and its evidence."""

        with self._sessions() as session:
            instruments = session.scalars(
                select(InstrumentRegistryRecord).where(
                    InstrumentRegistryRecord.verification_status == "VERIFIED",
                    InstrumentRegistryRecord.lot_size.is_not(None),
                )
            ).all()
            result: dict[str, VerifiedLotSize] = {}
            for instrument in instruments:
                assert instrument.lot_size is not None
                rule = self._rule_for(session, instrument)
                if rule is not None:
                    result[instrument.instrument_id] = rule
            return result

    def lot_size_for(self, instrument_id: str) -> VerifiedLotSize | None:
        with self._sessions() as session:
            instrument = session.get(InstrumentRegistryRecord, instrument_id)
            if instrument is None:
                return None
            return self._rule_for(session, instrument)

    @staticmethod
    def _rule_for(session: Session, instrument: InstrumentRegistryRecord) -> VerifiedLotSize | None:
        if instrument.verification_status != "VERIFIED" or instrument.lot_size is None:
            return None
        if instrument.active is False:
            return None
        review = session.scalar(
            select(InstrumentReviewEventRecord)
            .where(
                InstrumentReviewEventRecord.instrument_id == instrument.instrument_id,
                InstrumentReviewEventRecord.decision == "VERIFIED",
            )
            .order_by(
                InstrumentReviewEventRecord.reviewed_at_utc.desc(),
                InstrumentReviewEventRecord.review_id.desc(),
            )
            .limit(1)
        )
        if review is None or not review.evidence_reference.strip():
            return None
        return VerifiedLotSize(
            size=Decimal(instrument.lot_size),
            source_reference=review.evidence_reference,
            verified_at=datetime.fromisoformat(review.reviewed_at_utc),
        )


class PortfolioTradingService:
    """Append simulated BUY/SELL events after checking verified lot evidence."""

    def __init__(
        self,
        repository: LedgerRepository,
        *,
        lot_sizes: VerifiedLotSizeService,
        base_currency: str = "IDR",
    ) -> None:
        self._repository = repository
        self._lot_sizes = lot_sizes
        self._base_currency = base_currency

    def events(self) -> tuple[LedgerEvent, ...]:
        return self._repository.events()

    def _ledger(self) -> PortfolioLedgerService:
        return PortfolioLedgerService(
            self._repository,
            lot_sizes=self._lot_sizes.lot_sizes(),
            base_currency=self._base_currency,
        )

    def _validate(
        self,
        instrument_id: str,
        quantity: Decimal,
        unit_price: Decimal,
        fees: Decimal,
        taxes: Decimal,
    ) -> VerifiedLotSize:
        rule = self._lot_sizes.lot_size_for(instrument_id)
        if rule is None:
            raise ValueError(
                f"verified lot-size evidence is required for {instrument_id} "
                "before a simulated trade can be recorded"
            )
        if not isinstance(quantity, Decimal) or not quantity.is_finite() or quantity <= 0:
            raise LedgerValidationError("quantity must be a positive finite Decimal")
        if quantity % rule.size != Decimal("0"):
            raise LedgerValidationError(
                f"quantity for {instrument_id} must be a multiple of lot size {rule.size}"
            )
        if not isinstance(unit_price, Decimal) or not unit_price.is_finite() or unit_price <= 0:
            raise LedgerValidationError("unit_price must be a positive finite Decimal")
        if fees < 0 or taxes < 0:
            raise LedgerValidationError("fees and taxes cannot be negative")
        return rule

    def buy(
        self,
        instrument_id: str,
        *,
        quantity: Decimal,
        unit_price: Decimal,
        fees: Decimal = Decimal("0"),
        taxes: Decimal = Decimal("0"),
        occurred_at: datetime | None = None,
    ) -> LedgerReplayResult:
        self._validate(instrument_id, quantity, unit_price, fees, taxes)
        moment = occurred_at or datetime.now(UTC)
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        event = LedgerEvent(
            event_id=str(uuid4()),
            sequence=len(self._repository.events()) + 1,
            occurred_at=moment.astimezone(UTC),
            event_type=LedgerEventType.BUY,
            currency=self._base_currency,
            instrument_id=instrument_id,
            quantity=quantity,
            unit_price=unit_price,
            fees=fees,
            taxes=taxes,
        )
        return self._ledger().append(event)

    def sell(
        self,
        instrument_id: str,
        *,
        quantity: Decimal,
        unit_price: Decimal,
        fees: Decimal = Decimal("0"),
        taxes: Decimal = Decimal("0"),
        occurred_at: datetime | None = None,
    ) -> LedgerReplayResult:
        self._validate(instrument_id, quantity, unit_price, fees, taxes)
        moment = occurred_at or datetime.now(UTC)
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        event = LedgerEvent(
            event_id=str(uuid4()),
            sequence=len(self._repository.events()) + 1,
            occurred_at=moment.astimezone(UTC),
            event_type=LedgerEventType.SELL,
            currency=self._base_currency,
            instrument_id=instrument_id,
            quantity=quantity,
            unit_price=unit_price,
            fees=fees,
            taxes=taxes,
        )
        return self._ledger().append(event)
