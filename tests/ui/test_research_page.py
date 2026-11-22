# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from datetime import UTC, datetime
from pathlib import Path

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
    finally:
        database.close()
