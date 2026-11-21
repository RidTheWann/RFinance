from decimal import Decimal

import pytest

from rfinance.application.portfolio_ledger import (
    DEFAULT_SIMULATION_CAPITAL,
    PortfolioLedgerService,
)
from rfinance.domain.portfolio.ledger import LedgerValidationError
from rfinance.storage.database import Database
from rfinance.storage.repositories.portfolio_ledger import LedgerRepository


def test_default_capital_is_a_suggestion_until_explicit_initialization(tmp_path) -> None:
    database = Database.open(tmp_path / "setup.sqlite3")
    database.upgrade()
    try:
        service = PortfolioLedgerService(LedgerRepository(database.sessions), lot_sizes={})

        assert DEFAULT_SIMULATION_CAPITAL == Decimal("5000000")
        assert service.events() == ()
        assert service.snapshot().cash_balance == Decimal("0")

        result = service.initialize_portfolio(DEFAULT_SIMULATION_CAPITAL)

        assert result.cash_balance == Decimal("5000000")
        assert len(service.events()) == 1
        assert result.applied_events == 1
        assert result.positions == {}
    finally:
        database.close()


def test_portfolio_cannot_be_initialized_twice_or_receive_implicit_monthly_capital(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "single-init.sqlite3")
    database.upgrade()
    try:
        service = PortfolioLedgerService(LedgerRepository(database.sessions), lot_sizes={})
        service.initialize_portfolio(Decimal("5000000"))

        with pytest.raises(LedgerValidationError, match="already initialized"):
            service.initialize_portfolio(Decimal("5000000"))

        assert len(service.events()) == 1
        assert service.snapshot().cash_balance == Decimal("5000000")
    finally:
        database.close()


@pytest.mark.parametrize(
    "capital",
    [Decimal("0"), Decimal("-1"), Decimal("NaN"), Decimal("Infinity")],
)
def test_portfolio_rejects_non_positive_or_non_finite_initial_capital(
    tmp_path, capital: Decimal
) -> None:
    database = Database.open(tmp_path / f"capital-{capital}.sqlite3")
    database.upgrade()
    try:
        service = PortfolioLedgerService(LedgerRepository(database.sessions), lot_sizes={})
        with pytest.raises(ValueError):
            service.initialize_portfolio(capital)
        assert service.events() == ()
    finally:
        database.close()
