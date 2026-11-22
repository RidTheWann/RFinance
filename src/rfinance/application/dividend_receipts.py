# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Post explicitly confirmed net dividend receipts into the simulated ledger."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select

from rfinance.analysis.dividend.analytics import allocate_confirmed_dividend
from rfinance.data.contracts import (
    CASH_DIVIDEND_TYPES,
    OBSERVED_DIVIDEND_STATUSES,
    DataQualityStatus,
)
from rfinance.domain.portfolio.ledger import LedgerEvent, LedgerEventType
from rfinance.storage.models.dividend import DividendReceiptRecord

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker

    from rfinance.application.dividend_events import DividendEventService
    from rfinance.application.portfolio_ledger import PortfolioLedgerService

FORMULA_VERSION = "dividend-receipt-v1"
REINVEST_WEIGHT = Decimal("0.50")
MONEY_MARKET_WEIGHT = Decimal("0.30")
WITHDRAWAL_WEIGHT = Decimal("0.20")


@dataclass(frozen=True, slots=True)
class DividendReceiptResult:
    receipt_id: str
    dividend_event_id: str
    instrument_id: str
    net_amount: Decimal
    reinvestment: Decimal
    money_market: Decimal
    withdrawal: Decimal
    ledger_receipt_event_id: str
    ledger_withdrawal_event_id: str
    methodology_version: str = FORMULA_VERSION


class DividendReceiptService:
    """Convert verified, confirmed cash events into auditable ledger receipts."""

    def __init__(
        self,
        sessions: sessionmaker[Session],
        *,
        dividend_events: DividendEventService,
        portfolio_ledger: PortfolioLedgerService,
    ) -> None:
        self._sessions = sessions
        self._dividend_events = dividend_events
        self._portfolio_ledger = portfolio_ledger

    def post_receipt(
        self,
        dividend_event_id: str,
        *,
        net_amount: Decimal,
        received_at: datetime | None = None,
    ) -> DividendReceiptResult:
        """Append the receipt and its withdrawal leg after checking all gates."""

        if not isinstance(net_amount, Decimal) or not net_amount.is_finite():
            raise ValueError("net_amount must be a finite decimal.Decimal")
        if net_amount <= Decimal("0"):
            raise ValueError("net_amount must be positive")
        moment = received_at or datetime.now(UTC)
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("received_at must be timezone-aware")

        candidate = next(
            (
                item
                for item in self._dividend_events.list_events(limit=2_000)
                if item.event_id == dividend_event_id
            ),
            None,
        )
        if candidate is None:
            raise ValueError("dividend event does not exist")
        if candidate.effective_quality != DataQualityStatus.VERIFIED.value:
            raise ValueError("dividend event must be VERIFIED before a receipt can be posted")
        if candidate.event_status not in OBSERVED_DIVIDEND_STATUSES:
            raise ValueError("only a CONFIRMED or HISTORICAL dividend event is an observed receipt")
        if candidate.dividend_type not in {item.value for item in CASH_DIVIDEND_TYPES}:
            raise ValueError("only cash dividend events can be posted as receipts")
        if candidate.amount_per_share is None:
            raise ValueError("dividend event has no verified amount per share")

        with self._sessions() as session:
            existing = session.scalar(
                select(DividendReceiptRecord.receipt_id).where(
                    DividendReceiptRecord.dividend_event_id == dividend_event_id
                )
            )
            if existing is not None:
                raise ValueError("a receipt for this dividend event is already posted")

        allocation = allocate_confirmed_dividend(
            net_amount,
            reinvest=REINVEST_WEIGHT,
            money_market=MONEY_MARKET_WEIGHT,
            withdrawal=WITHDRAWAL_WEIGHT,
        )
        occurred_at = moment.astimezone(UTC)
        receipt_event = LedgerEvent(
            event_id=str(uuid4()),
            sequence=self._portfolio_ledger.next_sequence,
            occurred_at=occurred_at,
            event_type=LedgerEventType.CONFIRMED_DIVIDEND,
            currency=self._portfolio_ledger.base_currency,
            amount=net_amount,
            instrument_id=candidate.instrument_id,
            source_reference=f"DIVIDEND_RECEIPT:{dividend_event_id}",
        )
        self._portfolio_ledger.append(receipt_event)

        withdrawal_event = LedgerEvent(
            event_id=str(uuid4()),
            sequence=self._portfolio_ledger.next_sequence,
            occurred_at=occurred_at,
            event_type=LedgerEventType.CASH_WITHDRAWAL,
            currency=self._portfolio_ledger.base_currency,
            amount=allocation.withdrawal,
        )
        self._portfolio_ledger.append(withdrawal_event)

        receipt_id = str(uuid4())
        with self._sessions.begin() as session:
            session.add(
                DividendReceiptRecord(
                    receipt_id=receipt_id,
                    dividend_event_id=dividend_event_id,
                    instrument_id=candidate.instrument_id,
                    net_amount=format(net_amount, "f"),
                    reinvestment=format(allocation.reinvestment, "f"),
                    money_market=format(allocation.money_market, "f"),
                    withdrawal=format(allocation.withdrawal, "f"),
                    reinvest_weight=format(REINVEST_WEIGHT, "f"),
                    money_market_weight=format(MONEY_MARKET_WEIGHT, "f"),
                    withdrawal_weight=format(WITHDRAWAL_WEIGHT, "f"),
                    recorded_at_utc=occurred_at.isoformat(),
                    methodology_version=FORMULA_VERSION,
                )
            )

        return DividendReceiptResult(
            receipt_id=receipt_id,
            dividend_event_id=dividend_event_id,
            instrument_id=candidate.instrument_id,
            net_amount=net_amount,
            reinvestment=allocation.reinvestment,
            money_market=allocation.money_market,
            withdrawal=allocation.withdrawal,
            ledger_receipt_event_id=receipt_event.event_id,
            ledger_withdrawal_event_id=withdrawal_event.event_id,
        )

    def receipt_for_event(self, dividend_event_id: str) -> DividendReceiptResult | None:
        """Return the stored receipt for an event, if one was posted."""

        with self._sessions() as session:
            record = session.scalar(
                select(DividendReceiptRecord).where(
                    DividendReceiptRecord.dividend_event_id == dividend_event_id
                )
            )
            if record is None:
                return None
            return DividendReceiptResult(
                receipt_id=record.receipt_id,
                dividend_event_id=record.dividend_event_id,
                instrument_id=record.instrument_id,
                net_amount=Decimal(record.net_amount),
                reinvestment=Decimal(record.reinvestment),
                money_market=Decimal(record.money_market),
                withdrawal=Decimal(record.withdrawal),
                ledger_receipt_event_id="",
                ledger_withdrawal_event_id="",
                methodology_version=record.methodology_version,
            )
