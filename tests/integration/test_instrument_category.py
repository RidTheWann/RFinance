# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from rfinance.analysis.portfolio.valuation import ValuationCategory
from rfinance.application.allocation_planning import AllocationPlanningService
from rfinance.application.instrument_category import InstrumentCategoryService
from rfinance.application.portfolio_ledger import PortfolioLedgerService
from rfinance.application.portfolio_valuation import PortfolioValuationService
from rfinance.domain.portfolio.allocation import AllocationAction
from rfinance.storage.database import Database
from rfinance.storage.models.instrument_registry import InstrumentRegistryRecord
from rfinance.storage.repositories.portfolio_ledger import LedgerRepository

AS_OF = datetime(2026, 11, 23, 12, tzinfo=UTC)
HASH = "a" * 64


def seed(database: Database, *, status: str = "VERIFIED") -> None:
    with database.sessions.begin() as session:
        session.add(
            InstrumentRegistryRecord(
                instrument_id="IDX:BBCA",
                ticker="BBCA",
                exchange="IDX",
                instrument_type="EQUITY",
                company_name="Bank Central Asia",
                currency="IDR",
                sector="Financials",
                active=True,
                lot_size=100,
                minimum_investment=None,
                verification_status=status,
                created_at_utc=AS_OF.isoformat(),
                updated_at_utc=AS_OF.isoformat(),
            )
        )


def service(database: Database, data_directory: Path) -> InstrumentCategoryService:
    return InstrumentCategoryService(database.sessions, data_directory=data_directory)


def test_evidence_backed_decision_is_persisted_and_projected(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "category.sqlite3")
    database.upgrade()
    try:
        seed(database)
        categories = service(database, tmp_path / "data")
        decision = categories.record(
            "IDX:BBCA",
            category=ValuationCategory.EQUITY_INDEX,
            lot_size=Decimal("100"),
            decision="VERIFIED",
            reviewer_label="Operator",
            notes="Checked exchange lot rule",
            evidence_reference="Documents/CategoryEvidence/lot.pdf",
            evidence_sha256=HASH,
            decided_at=AS_OF,
        )

        assert decision.decision == "VERIFIED"
        latest = categories.latest_decisions()
        assert len(latest) == 1
        assert latest[0].category is ValuationCategory.EQUITY_INDEX
        investables = categories.verified_investables()
        assert len(investables) == 1
        assert investables[0].lot_size == Decimal("100")
        assert investables[0].price is None
    finally:
        database.close()


def test_newer_rejection_supersedes_verified_decision(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "category-reject.sqlite3")
    database.upgrade()
    try:
        seed(database)
        categories = service(database, tmp_path / "data")
        categories.record(
            "IDX:BBCA",
            category=ValuationCategory.EQUITY_INDEX,
            lot_size=Decimal("100"),
            decision="VERIFIED",
            reviewer_label="Operator",
            notes="Initial check",
            evidence_reference="doc-1",
            evidence_sha256=HASH,
            decided_at=AS_OF,
        )
        categories.record(
            "IDX:BBCA",
            category=ValuationCategory.EQUITY_INDEX,
            lot_size=Decimal("100"),
            decision="REJECTED",
            reviewer_label="Operator",
            notes="Evidence withdrawn",
            evidence_reference="doc-2",
            evidence_sha256="b" * 64,
            decided_at=datetime(2026, 11, 24, 12, tzinfo=UTC),
        )

        assert categories.verified_investables() == ()
    finally:
        database.close()


def test_unverified_instrument_cannot_receive_evidence(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "category-instrument.sqlite3")
    database.upgrade()
    try:
        seed(database, status="UNVERIFIED")
        with pytest.raises(ValueError, match="VERIFIED"):
            service(database, tmp_path / "data").record(
                "IDX:BBCA",
                category=ValuationCategory.EQUITY_INDEX,
                lot_size=Decimal("100"),
                decision="VERIFIED",
                reviewer_label="Operator",
                notes="Should be blocked",
                evidence_reference="doc-1",
                evidence_sha256=HASH,
                decided_at=AS_OF,
            )
    finally:
        database.close()


def test_category_events_are_append_only(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "category-append.sqlite3")
    database.upgrade()
    try:
        seed(database)
        service(database, tmp_path / "data").record(
            "IDX:BBCA",
            category=ValuationCategory.EQUITY_INDEX,
            lot_size=Decimal("100"),
            decision="VERIFIED",
            reviewer_label="Operator",
            notes="Checked",
            evidence_reference="doc-1",
            evidence_sha256=HASH,
            decided_at=AS_OF,
        )
        with database.sessions.begin() as session, pytest.raises(IntegrityError):
            session.execute(text("UPDATE instrument_category_events SET decision = 'REJECTED'"))
    finally:
        database.close()


def test_allocation_plan_uses_persisted_category_evidence(tmp_path: Path) -> None:
    database = Database.open(tmp_path / "category-allocation.sqlite3")
    database.upgrade()
    try:
        seed(database)
        ledger = PortfolioLedgerService(LedgerRepository(database.sessions), lot_sizes={})
        ledger.initialize_portfolio(Decimal("5000000"))
        categories = service(database, tmp_path / "data")
        categories.record(
            "IDX:BBCA",
            category=ValuationCategory.EQUITY_INDEX,
            lot_size=Decimal("100"),
            decision="VERIFIED",
            reviewer_label="Operator",
            notes="Checked",
            evidence_reference="doc-1",
            evidence_sha256=HASH,
            decided_at=AS_OF,
        )
        planning = AllocationPlanningService(
            PortfolioValuationService(database.sessions, ledger),
            instrument_categories=categories,
        )

        plan = planning.plan(as_of=AS_OF)

        assert plan.lines[0].instrument_id == "IDX:BBCA"
        assert plan.lines[0].action is AllocationAction.UNFILLED_TARGET
        assert "no eligible price" in plan.lines[0].reasons[0]
    finally:
        database.close()
