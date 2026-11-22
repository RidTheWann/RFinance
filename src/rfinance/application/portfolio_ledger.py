# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Application service coordinating ledger validation and local persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import MappingProxyType
from typing import TYPE_CHECKING
from uuid import uuid4

from rfinance.domain.portfolio.ledger import (
    LedgerEvent,
    LedgerEventType,
    LedgerReplayResult,
    LedgerValidationError,
    replay_ledger,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from rfinance.domain.portfolio.ledger import VerifiedLotSize
    from rfinance.storage.repositories.portfolio_ledger import LedgerRepository


DEFAULT_SIMULATION_CAPITAL = Decimal("5000000")


class PortfolioLedgerService:
    """Validates every event against the full ledger before committing it."""

    def __init__(
        self,
        repository: LedgerRepository,
        *,
        lot_sizes: Mapping[str, VerifiedLotSize],
        base_currency: str = "IDR",
    ) -> None:
        self._repository = repository
        self._lot_sizes = MappingProxyType(dict(lot_sizes))
        self._base_currency = base_currency

    @property
    def next_sequence(self) -> int:
        return len(self._repository.events()) + 1

    def events(self) -> tuple[LedgerEvent, ...]:
        return self._repository.events()

    def snapshot(self) -> LedgerReplayResult:
        return replay_ledger(
            self._repository.events(),
            lot_sizes=self._lot_sizes,
            base_currency=self._base_currency,
        )

    def initialize_portfolio(self, initial_capital: Decimal) -> LedgerReplayResult:
        """Create the one explicit opening-capital event for a new simulation."""

        if self._repository.events():
            raise LedgerValidationError("portfolio is already initialized")
        opening_event = LedgerEvent(
            event_id=str(uuid4()),
            sequence=1,
            occurred_at=datetime.now(UTC),
            event_type=LedgerEventType.CAPITAL_INJECTION,
            currency=self._base_currency,
            amount=initial_capital,
        )
        return self.append(opening_event)

    def append(self, event: LedgerEvent) -> LedgerReplayResult:
        existing = self._repository.events()
        expected_sequence = len(existing) + 1
        if event.sequence != expected_sequence:
            raise LedgerValidationError(
                f"next ledger sequence must be {expected_sequence}, not {event.sequence}"
            )

        proposed_snapshot = replay_ledger(
            (*existing, event),
            lot_sizes=self._lot_sizes,
            base_currency=self._base_currency,
        )
        self._repository.append(event)
        return proposed_snapshot
