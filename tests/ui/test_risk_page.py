# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Risk Management desktop page tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication

from rfinance.analysis.portfolio.valuation import ValuationResult
from rfinance.application.portfolio_valuation import PortfolioValuationSnapshot
from rfinance.application.risk_monitoring import RiskMonitoringService
from rfinance.domain.risk.controls import RiskSnapshot
from rfinance.storage.database import Database
from rfinance.ui.risk_page import RiskPage

if TYPE_CHECKING:
    from pathlib import Path

    from pytestqt.qtbot import QtBot

_TRIGGERED = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)


def _snapshot(**overrides: object) -> RiskSnapshot:
    values: dict[str, object] = {
        "as_of": _TRIGGERED,
        "peak_value": Decimal("1000000"),
        "current_value": Decimal("900000"),
        "valuation_methodology": "portfolio-valuation-v1",
        "valuation_is_complete": True,
        "instrument_weights": {},
        "sector_weights": {},
        "allocation_deviations": {},
        "last_reviewed_at": None,
    }
    values.update(overrides)
    return RiskSnapshot(**values)  # type: ignore[arg-type]


def _valuation(total: Decimal, as_of: datetime) -> ValuationResult:
    return ValuationResult(
        as_of_utc=as_of.isoformat(),
        currency="IDR",
        cash=total,
        market_value=Decimal("0"),
        total_value=total,
        realized_profit_loss=Decimal("0"),
        unrealized_profit_loss=Decimal("0"),
        positions=(),
        allocation=(),
        unvalued_instruments=(),
        is_complete=True,
    )


class _ValuationProvider:
    def __init__(self, snapshots: list[ValuationResult]) -> None:
        self._snapshots = snapshots

    def value(self, *, as_of: datetime | None = None) -> PortfolioValuationSnapshot:
        snapshot = self._snapshots.pop(0)
        return PortfolioValuationSnapshot(
            valuation=snapshot,
            price_evidence=(),
            unvalued_positions=(),
            observations_considered=0,
            observations_rejected=0,
        )


@pytest.fixture()
def service(tmp_path: Path) -> RiskMonitoringService:
    database = Database.open(tmp_path / "db" / "risk.sqlite3")
    database.upgrade()
    try:
        yield RiskMonitoringService(database.sessions)  # type: ignore[misc]
    finally:
        database.close()


def test_page_displays_unresolved_events_and_clears_them_after_review(
    qtbot: QtBot, service: RiskMonitoringService
) -> None:
    service.evaluate(_snapshot(), triggered_at=_TRIGGERED)
    page = RiskPage(service)
    qtbot.addWidget(page)

    page.refresh()

    assert page.events_table.rowCount() == 1
    assert "REVIEW" in page.level_label.text()
    assert "ELEVATED_DRAWDOWN" in page.events_table.item(0, 1).text()

    page.events_table.selectRow(0)
    page.reviewer_input.setText("Portfolio operator")
    page.notes_input.setText("Reviewed the drawdown and allocation.")
    page.evidence_input.setText("Documents/RiskReview/2026-11.md")
    QApplication.processEvents()
    qtbot.mouseClick(page.review_button, Qt.MouseButton.LeftButton)

    assert service.active_events() == ()
    assert page.events_table.rowCount() == 0
    assert "review recorded" in page.status_label.text().lower()


def test_page_evaluates_a_valuation_on_a_worker(
    qtbot: QtBot, service: RiskMonitoringService
) -> None:
    earlier = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
    later = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
    provider = _ValuationProvider(
        [_valuation(Decimal("1000000"), earlier), _valuation(Decimal("900000"), later)]
    )
    page = RiskPage(service, valuation=provider)  # type: ignore[arg-type]
    qtbot.addWidget(page)

    for _ in range(2):
        page.evaluate()
        for _ in range(4000):
            QApplication.processEvents()
            if not page.is_busy:
                break
        else:
            pytest.fail("Risk evaluation did not finish on the worker thread")
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QApplication.processEvents()

    assert page.events_table.rowCount() == 1
    assert "ELEVATED_DRAWDOWN" in page.events_table.item(0, 1).text()
