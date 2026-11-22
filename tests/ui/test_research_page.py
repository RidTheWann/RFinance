# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import Qt

from rfinance.application.recommendations import RecommendationService
from rfinance.domain.recommendations.screening import (
    EvidenceItem,
    EvidenceKind,
    ScreeningInput,
)
from rfinance.storage.database import Database
from rfinance.ui.research_page import ResearchPage

AS_OF = datetime(2026, 11, 22, 10, tzinfo=UTC)


def test_research_page_shows_persisted_recommendation_and_evidence(qtbot, tmp_path: Path) -> None:
    database = Database.open(tmp_path / "research.sqlite3")
    database.upgrade()
    try:
        service = RecommendationService(database.sessions)
        service.evaluate(
            ScreeningInput(
                instrument_id="IDX:BBCA",
                as_of=AS_OF,
                currency="IDR",
                metrics=(),
                price_observation_age_days=None,
                price_quality=None,
                evidence=(
                    EvidenceItem(
                        evidence_id="fin-1",
                        kind=EvidenceKind.FUNDAMENTAL_METRIC,
                        reference="report.pdf",
                        quality="VERIFIED",
                    ),
                ),
            ),
            generated_at=AS_OF,
        )
        page = ResearchPage(service)
        qtbot.addWidget(page)
        page.show()

        assert page.table.rowCount() == 1
        assert page.table.item(0, 1).text() == "IDX:BBCA"
        assert page.table.item(0, 2).text() == "INSUFFICIENT_DATA"
        assert "fin-1" in page.detail_label.text()
        assert "Add verified financial statement inputs" in page.detail_label.text()
        assert page.empty_label.isHidden()
        page.close()
    finally:
        database.close()


def test_research_page_runs_guided_evaluation_and_shows_evidence(
    qtbot, tmp_path, monkeypatch
) -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    from rfinance.domain.recommendations.screening import (
        Recommendation,
        RecommendationAction,
    )
    from rfinance.storage.database import Database
    from rfinance.ui.research_page import ResearchPage

    database = Database.open(tmp_path / "research-eval.sqlite3")
    database.upgrade()
    result = Recommendation(
        instrument_id="IDX:BBCA",
        action=RecommendationAction.BUY_CANDIDATE,
        generated_at=datetime(2026, 11, 22, 12, tzinfo=UTC),
        evidence_ids=("metric:RETURN_ON_EQUITY", "price:obs-1"),
        risk_flags=(),
        confidence_level=Decimal("0.5"),
        explanation="4 of 5 fundamental signals passed.",
        invalidation_conditions=("Evidence becomes stale.",),
        data_freshness=None,
        fundamental_assessment="5 usable metric(s).",
        price_assessment="Verified price available.",
        dividend_assessment="No verified dividend evidence.",
    )

    class StubEvaluationService:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def evaluate(self, instrument_id: str, **kwargs: object) -> Recommendation:
            self.calls.append({"instrument_id": instrument_id, **kwargs})
            return result

    stub = StubEvaluationService()
    try:
        page = ResearchPage(
            RecommendationService(database.sessions),
            evaluation=stub,  # type: ignore[arg-type]
        )
        monkeypatch.setattr(
            page,
            "_start_worker",
            lambda operation, on_success: on_success(operation()),
        )
        qtbot.addWidget(page)
        page.show()

        page.use_filings_checkbox.setChecked(True)
        page.evaluate_instrument_input.setText("IDX:BBCA")
        page.evaluate_revenue_input.setText("1000")
        page.evaluate_previous_revenue_input.setText("800")
        page.evaluate_net_income_input.setText("150")
        page.evaluate_average_equity_input.setText("750")
        page.evaluate_total_debt_input.setText("300")
        page.evaluate_total_equity_input.setText("750")
        page.evaluate_eps_input.setText("5")
        page.evaluate_price_input.setText("50")
        qtbot.mouseClick(page.evaluate_button, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(
            lambda: "BUY_CANDIDATE" in page.evaluation_detail_label.text(),
            timeout=30000,
        )

        assert "price:obs-1" in page.evaluation_detail_label.text()
        assert stub.calls and stub.calls[0]["instrument_id"] == "IDX:BBCA"
        assert stub.calls[0]["use_persisted_fundamentals"] is True
        page.close()
    finally:
        database.close()
