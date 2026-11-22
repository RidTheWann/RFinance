from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from rfinance.analysis.fundamental.metrics import (
    CASH_FLOW_QUALITY,
    DEBT_TO_EQUITY,
    EARNINGS_QUALITY,
    EV_TO_EBITDA,
    FORMULA_VERSION,
    FREE_CASH_FLOW,
    GROSS_MARGIN,
    INTEREST_COVERAGE,
    NET_MARGIN,
    OPERATING_MARGIN,
    PRICE_TO_BOOK,
    PRICE_TO_EARNINGS,
    RETURN_ON_EQUITY,
    RETURN_ON_INVESTED_CAPITAL,
    REVENUE_GROWTH,
    MetricStatus,
    cash_flow_quality,
    compute_fundamental_metrics,
    debt_to_equity,
    earnings_quality,
    ev_to_ebitda,
    free_cash_flow,
    growth_rate,
    margin_ratio,
    metric_by_name,
    price_to_book,
    price_to_earnings,
    ratio,
    return_on_assets,
    return_on_equity,
    return_on_invested_capital,
)


def test_margin_is_a_fraction() -> None:
    assert margin_ratio(Decimal("25"), Decimal("100")) == Decimal("0.25")


def test_negative_profit_is_preserved() -> None:
    assert margin_ratio(Decimal("-5"), Decimal("100")) == Decimal("-0.05")


def test_zero_or_negative_denominator_returns_none() -> None:
    assert ratio(Decimal("10"), Decimal("0")) is None
    assert return_on_equity(Decimal("10"), Decimal("-2")) is None


def test_debt_to_equity_rejects_negative_debt() -> None:
    assert debt_to_equity(Decimal("-1"), Decimal("10")) is None
    assert debt_to_equity(Decimal("20"), Decimal("10")) == Decimal("2")


def test_valid_zero_profit_is_not_missing_data() -> None:
    assert margin_ratio(Decimal("0"), Decimal("100")) == Decimal("0")


def _sample_inputs() -> dict[str, Decimal | None]:
    return {
        "revenue": Decimal("1000"),
        "revenue_previous": Decimal("800"),
        "earnings_per_share": Decimal("5"),
        "earnings_per_share_previous": Decimal("4"),
        "gross_profit": Decimal("400"),
        "operating_income": Decimal("200"),
        "net_income": Decimal("150"),
        "average_equity": Decimal("750"),
        "average_total_assets": Decimal("2000"),
        "effective_tax_rate": Decimal("0.20"),
        "total_debt": Decimal("500"),
        "total_equity": Decimal("750"),
        "cash_and_equivalents": Decimal("100"),
        "interest_expense": Decimal("20"),
        "operating_cash_flow": Decimal("240"),
        "capital_expenditure": Decimal("90"),
        "price": Decimal("50"),
        "book_value_per_share": Decimal("25"),
        "enterprise_value": Decimal("5000"),
        "ebitda": Decimal("250"),
    }


def test_compute_all_metrics_with_full_inputs() -> None:
    metrics = compute_fundamental_metrics(_sample_inputs())
    by_name = {metric.name: metric for metric in metrics}
    assert len(metrics) == 17
    assert all(metric.status is MetricStatus.OK for metric in metrics)
    assert all(metric.formula_version == FORMULA_VERSION for metric in metrics)
    assert by_name[REVENUE_GROWTH].value == Decimal("0.25")
    assert by_name[GROSS_MARGIN].value == Decimal("0.4")
    assert by_name[OPERATING_MARGIN].value == Decimal("0.2")
    assert by_name[NET_MARGIN].value == Decimal("0.15")
    assert by_name[RETURN_ON_EQUITY].value == Decimal("0.2")
    assert by_name[RETURN_ON_INVESTED_CAPITAL].value == Decimal("160") / Decimal("1150")
    assert by_name[DEBT_TO_EQUITY].value == Decimal("500") / Decimal("750")
    assert by_name[INTEREST_COVERAGE].value == Decimal("10")
    assert by_name[FREE_CASH_FLOW].value == Decimal("150")
    assert by_name[EARNINGS_QUALITY].value == Decimal("1.6")
    assert by_name[CASH_FLOW_QUALITY].value == Decimal("0.625")
    assert by_name[PRICE_TO_EARNINGS].value == Decimal("10")
    assert by_name[PRICE_TO_BOOK].value == Decimal("2")
    assert by_name[EV_TO_EBITDA].value == Decimal("20")


def test_metrics_record_inputs_and_formula_for_reproducibility() -> None:
    metrics = compute_fundamental_metrics(_sample_inputs())
    metric = metric_by_name(metrics, RETURN_ON_EQUITY)
    assert metric is not None
    assert metric.formula == "net_income/average_equity"
    assert ("net_income", "150") in metric.inputs
    assert ("average_equity", "750") in metric.inputs
    assert metric.value == Decimal("150") / Decimal("750")


def test_missing_input_is_never_converted_to_zero() -> None:
    inputs = _sample_inputs()
    inputs["revenue"] = None
    metrics = compute_fundamental_metrics(inputs)
    gross = metric_by_name(metrics, GROSS_MARGIN)
    assert gross is not None
    assert gross.value is None
    assert gross.status is MetricStatus.MISSING_INPUT
    assert ("revenue", "MISSING") in gross.inputs
    net = metric_by_name(metrics, NET_MARGIN)
    assert net is not None
    assert net.status is MetricStatus.MISSING_INPUT


def test_unusable_denominators_have_explicit_status() -> None:
    inputs = _sample_inputs()
    inputs["revenue_previous"] = Decimal("0")
    inputs["earnings_per_share"] = Decimal("-1")
    metrics = compute_fundamental_metrics(inputs)
    growth = metric_by_name(metrics, REVENUE_GROWTH)
    pe = metric_by_name(metrics, PRICE_TO_EARNINGS)
    assert growth is not None and growth.status is MetricStatus.UNUSABLE_DENOMINATOR
    assert pe is not None and pe.status is MetricStatus.UNUSABLE_DENOMINATOR
    assert growth.value is None and pe.value is None


def test_financial_companies_exclude_industrial_leverage_and_cashflow_metrics() -> None:
    metrics = compute_fundamental_metrics(_sample_inputs(), is_financial=True)
    excluded = {
        DEBT_TO_EQUITY,
        INTEREST_COVERAGE,
        FREE_CASH_FLOW,
        EARNINGS_QUALITY,
        CASH_FLOW_QUALITY,
        RETURN_ON_INVESTED_CAPITAL,
        EV_TO_EBITDA,
    }
    for metric in metrics:
        if metric.name in excluded:
            assert metric.status is MetricStatus.NOT_APPLICABLE
            assert metric.value is None
            assert "financial institutions" in metric.note
        else:
            assert metric.status is not MetricStatus.NOT_APPLICABLE
    roe = metric_by_name(metrics, RETURN_ON_EQUITY)
    assert roe is not None and roe.value == Decimal("0.2")


def test_non_finite_inputs_are_rejected() -> None:
    inputs = _sample_inputs()
    inputs["revenue"] = Decimal("NaN")
    try:
        compute_fundamental_metrics(inputs)
    except ValueError:
        pass
    else:
        raise AssertionError("non-finite input must be rejected")


def test_primitives_cover_additional_metrics() -> None:
    assert return_on_assets(Decimal("100"), Decimal("1000")) == Decimal("0.1")
    assert growth_rate(Decimal("120"), Decimal("100")) == Decimal("0.2")
    assert growth_rate(Decimal("120"), Decimal("0")) is None
    assert free_cash_flow(Decimal("100"), Decimal("40")) == Decimal("60")
    assert free_cash_flow(Decimal("100"), Decimal("-1")) is None
    assert earnings_quality(Decimal("100"), Decimal("80")) == Decimal("0.8")
    assert cash_flow_quality(Decimal("100"), Decimal("60")) == Decimal("0.6")
    assert price_to_earnings(Decimal("100"), Decimal("5")) == Decimal("20")
    assert price_to_book(Decimal("100"), Decimal("200")) == Decimal("0.5")
    assert ev_to_ebitda(Decimal("1000"), Decimal("100")) == Decimal("10")
    assert ev_to_ebitda(Decimal("-1"), Decimal("100")) is None
    assert return_on_invested_capital(
        Decimal("100"), Decimal("0.25"), Decimal("300"), Decimal("700"), Decimal("100")
    ) == Decimal("75") / Decimal("900")
    assert (
        return_on_invested_capital(
            Decimal("100"), Decimal("1.5"), Decimal("300"), Decimal("700"), Decimal("100")
        )
        is None
    )


@given(
    numerator=st.decimals(min_value=Decimal("0"), max_value=Decimal("100000"), places=2),
    denominator=st.decimals(min_value=Decimal("1"), max_value=Decimal("100000"), places=2),
)
def test_ratio_invariant(numerator: Decimal, denominator: Decimal) -> None:
    value = ratio(numerator, denominator)
    assert value is not None
    assert value >= 0
    larger_denominator = ratio(numerator, denominator * 2)
    assert larger_denominator is not None
    assert larger_denominator <= value


@given(
    revenue=st.decimals(min_value=Decimal("1"), max_value=Decimal("10000"), places=2),
    previous=st.decimals(min_value=Decimal("1"), max_value=Decimal("10000"), places=2),
)
def test_growth_invariant(revenue: Decimal, previous: Decimal) -> None:
    value = growth_rate(revenue, previous)
    assert value is not None
    assert (value >= 0) is (revenue >= previous)


@given(
    profit=st.decimals(min_value=Decimal("-1000"), max_value=Decimal("1000"), places=2),
    revenue=st.decimals(min_value=Decimal("1"), max_value=Decimal("10000"), places=2),
)
def test_margin_is_bounded_when_profit_does_not_exceed_revenue(
    profit: Decimal, revenue: Decimal
) -> None:
    value = margin_ratio(profit, revenue)
    assert value is not None
    if profit <= revenue:
        assert value <= 1
