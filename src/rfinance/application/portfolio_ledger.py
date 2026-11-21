# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Application service coordinating ledger validation and local persistence."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from rfinance.domain.portfolio.ledger import (
    LedgerEvent,
    LedgerReplayResult,
    LedgerValidationError,
    replay_ledger,
)
from rfinance.storage.repositories.portfolio_ledger import LedgerRepository

if TYPE_CHECKING:
    from collections.abc import Mapping

    from rfinance.domain.portfolio.ledger import VerifiedLotSize


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
