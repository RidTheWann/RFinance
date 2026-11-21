from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from rfinance.analysis.portfolio.valuation import (
    DEFAULT_TARGETS,
    PriceQuote,
    ValuationCategory,
    quotes_from_eligible_candidates,
    value_portfolio,
)
from rfinance.domain.eligibility.observation import (
    ObservationCandidate,
    ObservationQuality,
)
from rfinance.domain.portfolio.ledger import LedgerReplayResult, PositionSnapshot

AS_OF = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
ZERO = Decimal("0")


def position(quantity: str, cost: str) -> PositionSnapshot:
    return PositionSnapshot(
        instrument_id="unused",
        quantity=Decimal(quantity),
        cost_basis=Decimal(cost),
    )


def snapshot(
    *,
    cash: str = "1000000",
    positions: dict[str, PositionSnapshot] | None = None,
    realized: str = "0",
) -> LedgerReplayResult:
    return LedgerReplayResult(
        currency="IDR",
        cash_balance=Decimal(cash),
        positions={} if positions is None else positions,
        realized_profit_loss=Decimal(realized),
        simulated_dividends=ZERO,
        total_fees=ZERO,
        total_taxes=ZERO,
        applied_events=1,
    )


def quote(instrument_id: str, close: str, **overrides: object) -> PriceQuote:
    values: dict[str, object] = {
        "instrument_id": instrument_id,
        "close": Decimal(close),
        "currency": "IDR",
        "observed_at": AS_OF - timedelta(hours=1),
        "quality": ObservationQuality.VERIFIED,
    }
    values.update(overrides)
    return PriceQuote(**values)  # type: ignore[arg-type]


def two_positions() -> dict[str, PositionSnapshot]:
    return {
        "IDX:A": position("100", "500000"),
        "IDX:B": position("10", "300000"),
    }


def test_complete_valuation_reconciles_cash_and_unrealized_pnl() -> None:
    result = value_portfolio(
        snapshot(positions=two_positions()),
        quotes=[quote("IDX:A", "6000"), quote("IDX:B", "25000")],
        categories={
            "IDX:A": ValuationCategory.DIVIDEND_EQUITY,
            "IDX:B": ValuationCategory.EQUITY_INDEX,
        },
        as_of=AS_OF,
        currency="IDR",
    )

    assert result.is_complete is True
    assert result.market_value == Decimal("850000")
    assert result.total_value == Decimal("1850000")
    assert result.unrealized_profit_loss == Decimal("50000")
    assert result.is_simulated is True
    valued = {item.instrument_id: item for item in result.positions}
    assert valued["IDX:A"].market_value == Decimal("600000")
    assert valued["IDX:A"].unrealized_profit_loss == Decimal("100000")
    assert valued["IDX:B"].market_value == Decimal("250000")
    assert valued["IDX:B"].unrealized_profit_loss == Decimal("-50000")


def test_allocation_compares_actual_weight_with_configured_target() -> None:
    result = value_portfolio(
        snapshot(positions=two_positions()),
        quotes=[quote("IDX:A", "6000"), quote("IDX:B", "25000")],
        categories={
            "IDX:A": ValuationCategory.DIVIDEND_EQUITY,
            "IDX:B": ValuationCategory.EQUITY_INDEX,
        },
        as_of=AS_OF,
        currency="IDR",
    )
    lines = {line.category: line for line in result.allocation}
    assert lines[ValuationCategory.DIVIDEND_EQUITY].weight > Decimal("0.32")
    assert (
        lines[ValuationCategory.DIVIDEND_EQUITY].target
        == DEFAULT_TARGETS[ValuationCategory.DIVIDEND_EQUITY]
    )
    assert lines[ValuationCategory.DIVIDEND_EQUITY].deviation > ZERO
    assert lines[ValuationCategory.EQUITY_INDEX].deviation < ZERO
    assert lines[ValuationCategory.MONEY_MARKET].deviation < ZERO
    assert lines[ValuationCategory.CASH].value == Decimal("1000000")


def test_missing_price_is_reported_not_valued_at_cost() -> None:
    result = value_portfolio(
        snapshot(positions=two_positions()),
        quotes=[quote("IDX:A", "6000")],
        categories={"IDX:A": ValuationCategory.DIVIDEND_EQUITY},
        as_of=AS_OF,
        currency="IDR",
    )
    assert result.is_complete is False
    assert result.unvalued_instruments == ("IDX:B",)
    assert result.market_value == Decimal("600000")
    assert result.total_value == Decimal("1600000")
    unvalued = next(item for item in result.positions if item.instrument_id == "IDX:B")
    assert unvalued.price is None
    assert unvalued.market_value is None
    assert unvalued.category is ValuationCategory.OTHER


def test_only_verified_fresh_matching_prices_are_accepted() -> None:
    base = snapshot(positions={"IDX:A": position("100", "500000")})
    categories = {"IDX:A": ValuationCategory.DIVIDEND_EQUITY}
    with pytest.raises(ValueError, match="VERIFIED"):
        value_portfolio(
            base,
            quotes=[quote("IDX:A", "6000", quality=ObservationQuality.UNVERIFIED)],
            categories=categories,
            as_of=AS_OF,
            currency="IDR",
        )
    with pytest.raises(ValueError, match="freshness"):
        value_portfolio(
            base,
            quotes=[quote("IDX:A", "6000", observed_at=AS_OF - timedelta(days=30))],
            categories=categories,
            as_of=AS_OF,
            currency="IDR",
        )
    with pytest.raises(ValueError, match="freshness"):
        value_portfolio(
            base,
            quotes=[quote("IDX:A", "6000", observed_at=AS_OF + timedelta(hours=1))],
            categories=categories,
            as_of=AS_OF,
            currency="IDR",
        )
    with pytest.raises(ValueError, match="does not match"):
        value_portfolio(
            base,
            quotes=[quote("IDX:A", "6000", currency="USD")],
            categories=categories,
            as_of=AS_OF,
            currency="IDR",
        )


def test_invalid_prices_and_configuration_are_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        quote("IDX:A", "0")
    with pytest.raises(ValueError, match="positive"):
        quote("IDX:A", "-1")
    with pytest.raises(ValueError, match="finite"):
        quote("IDX:A", "NaN")
    with pytest.raises(ValueError, match="timezone-aware"):
        quote("IDX:A", "1", observed_at=datetime(2026, 11, 21, 12, 0))
    with pytest.raises(ValueError, match="target weights must sum to one"):
        value_portfolio(
            snapshot(),
            quotes=[],
            categories={},
            as_of=AS_OF,
            currency="IDR",
            target_allocation={ValuationCategory.CASH: Decimal("0.5")},
        )
    with pytest.raises(ValueError, match="snapshot currency"):
        value_portfolio(
            snapshot(),
            quotes=[],
            categories={},
            as_of=AS_OF,
            currency="USD",
        )


def test_eligible_candidates_convert_to_quotes() -> None:
    candidate = ObservationCandidate(
        instrument_id="IDX:A",
        observed_at=AS_OF - timedelta(hours=1),
        acquired_at=AS_OF - timedelta(minutes=30),
        close=Decimal("6000"),
        currency="IDR",
        source_id="src-1",
        quality=ObservationQuality.VERIFIED,
    )
    quotes = quotes_from_eligible_candidates([candidate])
    assert quotes[0].instrument_id == "IDX:A"
    assert quotes[0].close == Decimal("6000")
    with pytest.raises(ValueError, match="ObservationCandidate"):
        quotes_from_eligible_candidates(["not-a-candidate"])  # type: ignore[list-item]


@given(
    cash=st.decimals(min_value=0, max_value=10_000_000, places=0),
    first=st.decimals(min_value=1, max_value=100_000, places=0),
    second=st.decimals(min_value=1, max_value=100_000, places=0),
    quantity=st.integers(min_value=1, max_value=500),
)
def test_valuation_always_reconciles(
    cash: Decimal, first: Decimal, second: Decimal, quantity: int
) -> None:
    positions = {
        "IDX:A": PositionSnapshot("IDX:A", Decimal(quantity), Decimal(quantity) * first),
        "IDX:B": PositionSnapshot("IDX:B", Decimal(quantity), Decimal(quantity) * second),
    }
    result = value_portfolio(
        snapshot(cash=str(cash), positions=positions),
        quotes=[quote("IDX:A", str(first)), quote("IDX:B", str(second))],
        categories={},
        as_of=AS_OF,
        currency="IDR",
    )
    assert result.total_value == result.cash + result.market_value
    assert result.is_complete is True
    assert result.unrealized_profit_loss == ZERO
    weight_total = sum((line.weight for line in result.allocation), start=ZERO)
    assert abs(weight_total - Decimal("1")) < Decimal("0.0000000001")
