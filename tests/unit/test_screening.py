from datetime import UTC, datetime
from decimal import Decimal

import pytest

from rfinance.analysis.fundamental.metrics import (
    DEBT_TO_EQUITY,
    NET_MARGIN,
    PRICE_TO_EARNINGS,
    RETURN_ON_EQUITY,
    REVENUE_GROWTH,
    ComputedMetric,
    MetricStatus,
)
from rfinance.domain.recommendations.screening import (
    EvidenceItem,
    EvidenceKind,
    RecommendationAction,
    RiskFlag,
    ScreeningInput,
    ScreeningPolicy,
    evaluate_candidate,
)

AS_OF = datetime(2026, 11, 22, 10, tzinfo=UTC)


def healthy_metrics() -> tuple[ComputedMetric, ...]:
    return tuple(
        ComputedMetric(
            name=name,
            value=value,
            status=MetricStatus.OK,
            formula="test",
            inputs=(("input", "1"),),
        )
        for name, value in (
            (REVENUE_GROWTH, Decimal("0.20")),
            (NET_MARGIN, Decimal("0.15")),
            (RETURN_ON_EQUITY, Decimal("0.18")),
            (DEBT_TO_EQUITY, Decimal("0.40")),
            (PRICE_TO_EARNINGS, Decimal("12")),
        )
    )


def evidence() -> tuple[EvidenceItem, ...]:
    return (
        EvidenceItem(
            evidence_id="fin-1",
            kind=EvidenceKind.FUNDAMENTAL_METRIC,
            reference="annual-report-2025.pdf",
            quality="VERIFIED",
            observed_at=AS_OF,
            summary="Audited annual report",
        ),
        EvidenceItem(
            evidence_id="div-1",
            kind=EvidenceKind.DIVIDEND_EVENT,
            reference="dividend-event-1",
            quality="VERIFIED",
            observed_at=AS_OF,
            summary="Confirmed cash dividend",
        ),
    )


def candidate(**overrides: object) -> ScreeningInput:
    values = {
        "instrument_id": "IDX:BBCA",
        "as_of": AS_OF,
        "currency": "IDR",
        "metrics": healthy_metrics(),
        "price_observation_age_days": 2,
        "price_quality": "VERIFIED",
        "price_evidence_id": "price-1",
        "dividend_evidence_ids": ("div-1",),
        "evidence": evidence(),
    }
    values.update(overrides)
    return ScreeningInput(**values)  # type: ignore[arg-type]


def test_healthy_verified_candidate_can_be_a_buy_candidate() -> None:
    result = evaluate_candidate(candidate())
    assert result.action is RecommendationAction.BUY_CANDIDATE
    assert result.risk_flags == ()
    assert "not the probability" in result.explanation
    assert "BUY_CANDIDATE" in result.action.value
    assert result.evidence_ids == ("fin-1", "div-1", "price-1")
    assert result.data_freshness == AS_OF
    assert result.confidence_level > 0


def test_stale_price_blocks_buy_candidate() -> None:
    result = evaluate_candidate(candidate(price_observation_age_days=30))
    assert result.action is RecommendationAction.WATCH
    assert RiskFlag.STALE_PRICE in result.risk_flags
    assert "blocked" in result.explanation


def test_unverified_price_blocks_buy_candidate() -> None:
    result = evaluate_candidate(candidate(price_quality="UNVERIFIED"))
    assert result.action is RecommendationAction.WATCH
    assert RiskFlag.UNVERIFIED_PRICE in result.risk_flags


def test_missing_required_metric_blocks_buy_candidate() -> None:
    metrics = tuple(item for item in healthy_metrics() if item.name != PRICE_TO_EARNINGS)
    result = evaluate_candidate(candidate(metrics=metrics))
    assert result.action is RecommendationAction.WATCH
    assert RiskFlag.MISSING_FUNDAMENTALS in result.risk_flags
    assert "PRICE_TO_EARNINGS" in result.explanation


def test_missing_inputs_never_become_zero_metrics() -> None:
    metrics = tuple(
        ComputedMetric(
            name=item.name,
            value=None,
            status=MetricStatus.MISSING_INPUT,
            formula="test",
            inputs=(("input", "MISSING"),),
        )
        for item in healthy_metrics()
    )
    result = evaluate_candidate(candidate(metrics=metrics))
    assert result.action is RecommendationAction.INSUFFICIENT_DATA
    assert result.confidence_level == Decimal("0")
    assert result.evidence_ids == ("fin-1", "div-1")


def test_insufficient_data_when_no_metrics_supplied() -> None:
    result = evaluate_candidate(candidate(metrics=()))
    assert result.action is RecommendationAction.INSUFFICIENT_DATA


@pytest.mark.parametrize(
    ("drawdown", "flag", "action"),
    [
        (Decimal("0.12"), RiskFlag.ELEVATED_DRAWDOWN, RecommendationAction.WATCH),
        (Decimal("0.20"), RiskFlag.CRITICAL_DRAWDOWN, RecommendationAction.AVOID),
    ],
)
def test_drawdown_controls_block_new_buy_candidates(
    drawdown: Decimal, flag: RiskFlag, action: RecommendationAction
) -> None:
    result = evaluate_candidate(candidate(portfolio_drawdown=drawdown))
    assert flag in result.risk_flags
    assert result.action is action


def test_negative_earnings_with_high_leverage_is_avoided() -> None:
    metrics = tuple(
        ComputedMetric(
            name=item.name,
            value=(
                Decimal("-0.05")
                if item.name == NET_MARGIN
                else Decimal("2.5")
                if item.name == DEBT_TO_EQUITY
                else item.value
            ),
            status=MetricStatus.OK,
            formula="test",
            inputs=(("input", "1"),),
        )
        for item in healthy_metrics()
    )
    result = evaluate_candidate(candidate(metrics=metrics))
    assert RiskFlag.NEGATIVE_EARNINGS in result.risk_flags
    assert RiskFlag.HIGH_LEVERAGE in result.risk_flags
    assert result.action is RecommendationAction.AVOID


def test_confidence_measures_evidence_not_profit_probability() -> None:
    low = evaluate_candidate(candidate(evidence=()))
    high = evaluate_candidate(candidate())
    assert low.confidence_level < high.confidence_level
    assert high.confidence_level <= Decimal("1")
    assert "Confidence reflects evidence quality" in high.explanation


def test_no_dividend_evidence_is_a_transparent_flag() -> None:
    result = evaluate_candidate(candidate(dividend_evidence_ids=()))
    assert RiskFlag.NO_DIVIDEND_EVIDENCE in result.risk_flags
    assert "No verified dividend evidence" in result.dividend_assessment


def test_invalid_inputs_are_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        candidate(as_of=datetime(2026, 11, 22, 10))
    with pytest.raises(ValueError, match="fraction between"):
        candidate(portfolio_drawdown=Decimal("1.5"))
    with pytest.raises(ValueError, match="drawdown thresholds must be ordered"):
        ScreeningPolicy(elevated_drawdown=Decimal("0.2"), critical_drawdown=Decimal("0.1"))
