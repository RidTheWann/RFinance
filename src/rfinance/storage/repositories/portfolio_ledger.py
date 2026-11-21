# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""SQLite repository for immutable portfolio ledger events."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from rfinance.domain.portfolio.ledger import LedgerEvent, LedgerEventType, LedgerValidationError
from rfinance.storage.models.portfolio_ledger import PortfolioLedgerRecord

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker


class LedgerRepository:
    """Append-only persistence adapter for a single simulated portfolio ledger."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    @staticmethod
    def _to_record(event: LedgerEvent) -> PortfolioLedgerRecord:
        def decimal_text(value: Decimal | None) -> str | None:
            return None if value is None else format(value, "f")

        return PortfolioLedgerRecord(
            event_id=event.event_id,
            sequence=event.sequence,
            occurred_at_utc=event.occurred_at.astimezone(UTC).isoformat(),
            event_type=event.event_type.value,
            currency=event.currency,
            amount=decimal_text(event.amount),
            instrument_id=event.instrument_id,
            quantity=decimal_text(event.quantity),
            unit_price=decimal_text(event.unit_price),
            fees=format(event.fees, "f"),
            taxes=format(event.taxes, "f"),
            source_reference=event.source_reference,
        )

    @staticmethod
    def _from_record(record: PortfolioLedgerRecord) -> LedgerEvent:
        def decimal_value(value: str | None) -> Decimal | None:
            return None if value is None else Decimal(value)

        occurred_at = datetime.fromisoformat(record.occurred_at_utc)
        if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
            raise LedgerValidationError(
                f"persisted event {record.event_id} has a timestamp without timezone"
            )

        return LedgerEvent(
            event_id=record.event_id,
            sequence=record.sequence,
            occurred_at=occurred_at,
            event_type=LedgerEventType(record.event_type),
            currency=record.currency,
            amount=decimal_value(record.amount),
            instrument_id=record.instrument_id,
            quantity=decimal_value(record.quantity),
            unit_price=decimal_value(record.unit_price),
            fees=Decimal(record.fees),
            taxes=Decimal(record.taxes),
            source_reference=record.source_reference,
        )

    def events(self) -> tuple[LedgerEvent, ...]:
        """Return all recorded events in immutable ledger order."""

        with self._sessions() as session:
            records = session.scalars(
                select(PortfolioLedgerRecord).order_by(PortfolioLedgerRecord.sequence)
            ).all()
            return tuple(self._from_record(record) for record in records)

    def append(self, event: LedgerEvent) -> None:
        """Persist one new event, requiring the next contiguous sequence.

        Domain validation is performed by PortfolioLedgerService before this
        method is called. Database uniqueness is the final concurrency guard.
        """

        try:
            with self._sessions.begin() as session:
                latest_sequence = session.scalar(
                    select(func.max(PortfolioLedgerRecord.sequence))
                )
                expected_sequence = 1 if latest_sequence is None else latest_sequence + 1
                if event.sequence != expected_sequence:
                    raise LedgerValidationError(
                        f"next ledger sequence must be {expected_sequence}, "
                        f"not {event.sequence}"
                    )
                session.add(self._to_record(event))
        except IntegrityError as error:
            raise LedgerValidationError(
                "ledger event conflicts with an existing event or dividend source reference"
            ) from error
