# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from rfinance.analysis.dividend.analytics import (
    CASH_DIVIDEND_TYPES,
    VERIFIED_QUALITIES,
    DividendConsistency,
    DividendQuality,
    DividendRecord,
    DividendType,
    allocate_confirmed_dividend,
    consecutive_distribution_years,
    dividend_cagr,
    dividend_consistency,
    dividend_growth,
    dividend_yield,
    earnings_coverage,
    forward_yield,
    free_cash_flow_coverage,
    net_dividend_amount,
    payout_ratio,
    project_dividend_cash,
    select_cash_dividends,
    trailing_dividend_per_share,
    trailing_yield,
)

AS_OF = date(2025, 12, 31)
ZERO = Decimal("0")


def record(
    event_id: str,
    amount: str,
    ex_date: date,
    *,
    currency: str = "IDR",
    dividend_type: DividendType = DividendType.CASH,
    quality: DividendQuality = DividendQuality.VERIFIED,
    source_id: str = "source-1",
) -> DividendRecord:
    return DividendRecord(
        event_id=event_id,
        amount_per_share=Decimal(amount),
        ex_date=ex_date,
        currency=currency,
        dividend_type=dividend_type,
        quality=quality,
        source_id=source_id,
    )


def test_trailing_dividend_sums_only_eligible_cash_events() -> None:
    records = [
        record("cash-1", "100", date(2025, 1, 1)),
        record("final-1", "50", date(2025, 6, 1), dividend_type=DividendType.FINAL),
        record("stock-1", "999", date(2025, 7, 1), dividend_type=DividendType.STOCK),
        record("rights-1", "999", date(2025, 8, 1), dividend_type=DividendType.RIGHTS),
        record("unverified-1", "999", date(2025, 9, 1), quality=DividendQuality.UNVERIFIED),
        record("estimated-1", "999", date(2025, 10, 1), quality=DividendQuality.ESTIMATED),
        record("simulated-1", "999", date(2025, 11, 1), quality=DividendQuality.SIMULATED),
        record("other-currency", "999", date(2025, 5, 1), currency="USD"),
    ]
    assert trailing_dividend_per_share(records, as_of=AS_OF, currency="IDR") == Decimal("150")


def test_missing_eligible_dividend_is_none_not_zero() -> None:
    records = [record("cash-1", "100", date(2025, 1, 1), quality=DividendQuality.ESTIMATED)]
    assert trailing_dividend_per_share(records, as_of=AS_OF, currency="IDR") is None


def test_window_is_inclusive_at_as_of_and_exclusive_at_lower_bound() -> None:
    window = 365
    earliest = AS_OF - timedelta(days=window)
    records = [
        record("inside", "10", AS_OF),
        record("lower", "20", earliest),
        record("outside", "30", earliest - timedelta(days=1)),
    ]
    assert trailing_dividend_per_share(
        records, as_of=AS_OF, currency="IDR", window_days=window
    ) == Decimal("10")


def test_unbounded_window_includes_all_prior_events() -> None:
    records = [record("old", "10", date(1990, 1, 1))]
    assert trailing_dividend_per_share(
        records, as_of=AS_OF, currency="IDR", window_days=None
    ) == Decimal("10")


def test_future_ex_date_is_excluded() -> None:
    records = [record("future", "10", AS_OF + timedelta(days=1))]
    assert trailing_dividend_per_share(records, as_of=AS_OF, currency="IDR") is None


def test_duplicate_event_id_is_collapsed() -> None:
    records = [
        record("same", "100", date(2025, 1, 1)),
        record("same", "100", date(2025, 1, 1)),
    ]
    assert trailing_dividend_per_share(records, as_of=AS_OF, currency="IDR") == Decimal("100")


def test_conflicting_event_id_is_rejected() -> None:
    records = [
        record("same", "100", date(2025, 1, 1)),
        record("same", "200", date(2025, 1, 1)),
    ]
    with pytest.raises(ValueError, match="conflicting records"):
        select_cash_dividends(records, as_of=AS_OF, currency="IDR")


def test_selection_is_ordered_by_ex_date_and_event_id() -> None:
    records = [
        record("b", "10", date(2025, 1, 1)),
        record("a", "10", date(2025, 1, 1)),
        record("c", "10", date(2025, 2, 1)),
    ]
    selected = select_cash_dividends(records, as_of=AS_OF, currency="IDR")
    assert [item.event_id for item in selected] == ["a", "b", "c"]


def test_caller_can_expand_eligible_qualities_explicitly() -> None:
    records = [record("est", "100", date(2025, 1, 1), quality=DividendQuality.ESTIMATED)]
    assert trailing_dividend_per_share(
        records,
        as_of=AS_OF,
        currency="IDR",
        eligible_qualities=frozenset({DividendQuality.ESTIMATED}),
    ) == Decimal("100")


def test_cash_types_exclude_stock_and_rights() -> None:
    assert DividendType.STOCK not in CASH_DIVIDEND_TYPES
    assert DividendType.RIGHTS not in CASH_DIVIDEND_TYPES
    assert DividendQuality.VERIFIED in VERIFIED_QUALITIES


def test_record_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="amount_per_share"):
        record("x", "-1", date(2025, 1, 1))
    with pytest.raises(ValueError, match="event_id"):
        record("", "1", date(2025, 1, 1))
    with pytest.raises(ValueError, match="currency"):
        record("x", "1", date(2025, 1, 1), currency="idr")
    with pytest.raises(ValueError, match="ex_date"):
        record("x", "1", datetime(2025, 1, 1, tzinfo=None))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="finite"):
        record("x", "NaN", date(2025, 1, 1))


def test_net_dividend_requires_known_tax_treatment() -> None:
    assert net_dividend_amount(Decimal("1000"), None) is None
    assert net_dividend_amount(Decimal("1000"), Decimal("0.1")) == Decimal("900.0")
    with pytest.raises(ValueError, match="between zero and one"):
        net_dividend_amount(Decimal("1000"), Decimal("1.1"))


def test_dividend_yield_is_a_fraction_and_guards_price() -> None:
    assert dividend_yield(Decimal("5"), Decimal("100")) == Decimal("0.05")
    assert dividend_yield(Decimal("0"), Decimal("100")) == Decimal("0")
    assert dividend_yield(Decimal("5"), Decimal("0")) is None
    assert dividend_yield(Decimal("5"), Decimal("-100")) is None
    with pytest.raises(ValueError, match="decimal.Decimal"):
        dividend_yield(5, Decimal("100"))  # type: ignore[arg-type]


def test_trailing_and_forward_yields_are_labelled() -> None:
    records = [record("cash-1", "5", date(2025, 1, 1))]
    trailing = trailing_yield(records, as_of=AS_OF, currency="IDR", price=Decimal("100"))
    assert trailing is not None
    assert trailing.value == Decimal("0.05")
    assert trailing.basis == "TRAILING"
    assert trailing.is_estimate is False

    forward = forward_yield(Decimal("6"), Decimal("100"))
    assert forward.value == Decimal("0.06")
    assert forward.basis == "FORWARD"
    assert forward.is_estimate is True


def test_trailing_yield_without_eligible_evidence_is_none() -> None:
    assert trailing_yield([], as_of=AS_OF, currency="IDR", price=Decimal("100")) is None


def test_payout_and_coverage_ratios() -> None:
    assert payout_ratio(Decimal("5"), Decimal("10")) == Decimal("0.5")
    assert payout_ratio(Decimal("5"), Decimal("0")) is None
    assert payout_ratio(Decimal("5"), Decimal("-10")) is None
    assert earnings_coverage(Decimal("10"), Decimal("5")) == Decimal("2")
    assert earnings_coverage(Decimal("10"), Decimal("0")) is None
    assert free_cash_flow_coverage(Decimal("8"), Decimal("4")) == Decimal("2")
    assert free_cash_flow_coverage(Decimal("-8"), Decimal("4")) == Decimal("-2")
    assert free_cash_flow_coverage(Decimal("8"), Decimal("0")) is None


def test_growth_and_cagr() -> None:
    assert dividend_growth(Decimal("110"), Decimal("100")) == Decimal("0.1")
    assert dividend_growth(Decimal("100"), Decimal("0")) is None
    cagr = dividend_cagr(Decimal("100"), Decimal("121"), 2)
    assert cagr is not None
    assert abs(cagr - Decimal("0.1")) < Decimal("0.0000000001")
    assert dividend_cagr(Decimal("0"), Decimal("121"), 2) is None
    assert dividend_cagr(Decimal("100"), Decimal("121"), 0) is None
    with pytest.raises(ValueError, match="years"):
        dividend_cagr(Decimal("100"), Decimal("121"), 1.5)  # type: ignore[arg-type]


def test_consistency_handles_gaps_without_inventing_payments() -> None:
    annual = {2020: Decimal("5"), 2021: Decimal("6"), 2023: Decimal("7")}
    assert consecutive_distribution_years(annual) == 1
    assert dividend_consistency(annual) == DividendConsistency(
        years_observed=3,
        years_paid=3,
        consecutive_years=1,
        year_over_year_reductions=0,
    )


def test_consistency_counts_reductions_only_for_adjacent_years() -> None:
    annual = {2020: Decimal("6"), 2021: Decimal("5"), 2022: Decimal("0"), 2023: Decimal("5")}
    summary = dividend_consistency(annual)
    assert summary.years_paid == 3
    assert summary.consecutive_years == 1
    assert summary.year_over_year_reductions == 2
    assert dividend_consistency({}) == DividendConsistency(0, 0, 0, 0)


def test_projection_is_labelled_as_simulated() -> None:
    projection = project_dividend_cash(100, Decimal("10"), Decimal("0.1"))
    assert projection.gross_cash == Decimal("1000")
    assert projection.net_cash == Decimal("900.0")
    assert projection.is_simulated is True
    unknown_tax = project_dividend_cash(100, Decimal("10"), None)
    assert unknown_tax.net_cash is None
    assert unknown_tax.gross_cash == Decimal("1000")


def test_projection_rejects_fractional_quantity() -> None:
    with pytest.raises(ValueError, match="whole number"):
        project_dividend_cash(Decimal("10.5"), Decimal("1"), None)


def test_confirmed_dividend_allocation_reconciles_exactly() -> None:
    allocation = allocate_confirmed_dividend(
        Decimal("1000000.01"),
        reinvest=Decimal("0.5"),
        money_market=Decimal("0.3"),
        withdrawal=Decimal("0.2"),
    )
    assert allocation.reinvestment + allocation.money_market + allocation.withdrawal == (
        allocation.net_amount
    )


def test_confirmed_dividend_allocation_rejects_invalid_weights() -> None:
    with pytest.raises(ValueError, match="sum to one"):
        allocate_confirmed_dividend(
            Decimal("100"),
            reinvest=Decimal("0.5"),
            money_market=Decimal("0.3"),
            withdrawal=Decimal("0.3"),
        )
    with pytest.raises(ValueError, match="cannot be negative"):
        allocate_confirmed_dividend(
            Decimal("-1"),
            reinvest=Decimal("0.5"),
            money_market=Decimal("0.3"),
            withdrawal=Decimal("0.2"),
        )


@given(
    gross=st.decimals(min_value=0, max_value=1_000_000, places=2),
    rate=st.decimals(min_value=0, max_value=1, places=2),
)
def test_net_amount_never_exceeds_gross(gross: Decimal, rate: Decimal) -> None:
    net = net_dividend_amount(gross, rate)
    assert net is not None
    assert ZERO <= net <= gross


@given(
    amounts=st.lists(st.decimals(min_value=0, max_value=1000, places=2), max_size=8),
)
def test_trailing_sum_is_non_decreasing_with_window(amounts: list[Decimal]) -> None:
    records = [
        record(f"e{index}", str(value), date(2025, 1, 1)) for index, value in enumerate(amounts)
    ]
    short = trailing_dividend_per_share(records, as_of=AS_OF, currency="IDR", window_days=30)
    long = trailing_dividend_per_share(records, as_of=AS_OF, currency="IDR", window_days=365)
    assert short is None or long is not None
    if short is not None and long is not None:
        assert long >= short


@given(
    net=st.decimals(min_value=0, max_value=1_000_000, places=2),
)
def test_allocation_parts_sum_to_confirmed_net(net: Decimal) -> None:
    allocation = allocate_confirmed_dividend(
        net,
        reinvest=Decimal("0.5"),
        money_market=Decimal("0.3"),
        withdrawal=Decimal("0.2"),
    )
    assert allocation.reinvestment + allocation.money_market + allocation.withdrawal == net


@given(
    amounts=st.lists(st.decimals(min_value=0, max_value=1000, places=2), max_size=8),
)
def test_selection_never_includes_non_cash_or_unverified(amounts: list[Decimal]) -> None:
    records = [
        record(f"cash-{index}", str(value), date(2025, 1, 1)) for index, value in enumerate(amounts)
    ]
    records.append(record("stock", "10", date(2025, 1, 1), dividend_type=DividendType.STOCK))
    records.append(record("unverified", "10", date(2025, 1, 1), quality=DividendQuality.UNVERIFIED))
    selected = select_cash_dividends(records, as_of=AS_OF, currency="IDR")
    assert all(item.dividend_type in CASH_DIVIDEND_TYPES for item in selected)
    assert all(item.quality in VERIFIED_QUALITIES for item in selected)
