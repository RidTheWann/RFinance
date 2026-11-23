# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Deterministic, evidence-linked investment screening.

Formula version: ``screening-deterministic-v2``.

This module is a pure policy layer. It does not fetch data, mutate records,
produce numerical truths from AI output, or claim that an action will be
profitable. Confidence measures evidence quality and analytical completeness
only. A BUY_CANDIDATE is blocked whenever required evidence is stale,
unverified or materially incomplete.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from rfinance.analysis.fundamental.metrics import (
    DEBT_TO_EQUITY,
    NET_MARGIN,
    PRICE_TO_EARNINGS,
    RETURN_ON_EQUITY,
    REVENUE_GROWTH,
    ComputedMetric,
    MetricStatus,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from datetime import datetime

FORMULA_VERSION = "screening-deterministic-v2"
ZERO = Decimal("0")
ONE = Decimal("1")


class RecommendationAction(StrEnum):
    BUY_CANDIDATE = "BUY_CANDIDATE"
    HOLD = "HOLD"
    WATCH = "WATCH"
    AVOID = "AVOID"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class RiskFlag(StrEnum):
    STALE_PRICE = "STALE_PRICE"
    UNVERIFIED_PRICE = "UNVERIFIED_PRICE"
    MISSING_FUNDAMENTALS = "MISSING_FUNDAMENTALS"
    UNVERIFIED_FUNDAMENTALS = "UNVERIFIED_FUNDAMENTALS"
    ELEVATED_DRAWDOWN = "ELEVATED_DRAWDOWN"
    CRITICAL_DRAWDOWN = "CRITICAL_DRAWDOWN"
    RISK_REVIEW_REQUIRED = "RISK_REVIEW_REQUIRED"
    NEGATIVE_EARNINGS = "NEGATIVE_EARNINGS"
    HIGH_LEVERAGE = "HIGH_LEVERAGE"
    NO_DIVIDEND_EVIDENCE = "NO_DIVIDEND_EVIDENCE"


class EvidenceKind(StrEnum):
    FUNDAMENTAL_METRIC = "FUNDAMENTAL_METRIC"
    PRICE_OBSERVATION = "PRICE_OBSERVATION"
    DIVIDEND_EVENT = "DIVIDEND_EVENT"


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """A reference to information that supports or blocks a recommendation."""

    evidence_id: str
    kind: EvidenceKind
    reference: str
    quality: str
    observed_at: datetime | None = None
    summary: str = ""


@dataclass(frozen=True, slots=True)
class RiskControlEvidence:
    """Persisted risk-control state that constrains one screening result.

    This is a policy input assembled by the application layer from append-only
    risk events and the stored valuation series. It never replaces explicit
    portfolio drawdown supplied by the caller and never turns an unknown
    drawdown into zero.
    """

    review_required: bool = False
    buy_candidates_suspended: bool = False
    allocation_changes_suspended: bool = False
    critical: bool = False
    drawdown: Decimal | None = None
    active_event_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.drawdown is not None and (
            not self.drawdown.is_finite() or not ZERO <= self.drawdown <= ONE
        ):
            raise ValueError("drawdown must be a finite fraction between zero and one")


@dataclass(frozen=True, slots=True)
class ScreeningPolicy:
    """Configurable review thresholds; these are review triggers, not guarantees."""

    required_metrics: tuple[str, ...] = (
        REVENUE_GROWTH,
        NET_MARGIN,
        RETURN_ON_EQUITY,
        DEBT_TO_EQUITY,
        PRICE_TO_EARNINGS,
    )
    max_observation_age_days: int = 7
    min_positive_signals_for_buy: int = 4
    min_positive_signals_for_hold: int = 3
    max_debt_to_equity: Decimal = ONE
    min_return_on_equity: Decimal = Decimal("0.08")
    min_revenue_growth: Decimal = ZERO
    elevated_drawdown: Decimal = Decimal("0.10")
    critical_drawdown: Decimal = Decimal("0.15")
    expected_evidence_count: int = 8

    def __post_init__(self) -> None:
        if self.max_observation_age_days <= 0:
            raise ValueError("max_observation_age_days must be positive")
        if not 1 <= self.min_positive_signals_for_buy <= len(self.required_metrics) + 2:
            raise ValueError("min_positive_signals_for_buy is outside the signal range")
        if self.min_positive_signals_for_hold > self.min_positive_signals_for_buy:
            raise ValueError("hold threshold cannot exceed the buy threshold")
        if not ZERO <= self.elevated_drawdown <= self.critical_drawdown <= ONE:
            raise ValueError("drawdown thresholds must be ordered between zero and one")
        if self.max_debt_to_equity < ZERO or self.min_return_on_equity < ZERO:
            raise ValueError("fundamental thresholds cannot be negative")
        if self.expected_evidence_count <= 0:
            raise ValueError("expected_evidence_count must be positive")


@dataclass(frozen=True, slots=True)
class ScreeningInput:
    """All evidence needed for one deterministic decision."""

    instrument_id: str
    as_of: datetime
    currency: str
    metrics: tuple[ComputedMetric, ...]
    price_observation_age_days: int | None
    price_quality: str | None
    price_evidence_id: str | None = None
    dividend_evidence_ids: tuple[str, ...] = ()
    portfolio_drawdown: Decimal | None = None
    risk_controls: RiskControlEvidence | None = None
    evidence: tuple[EvidenceItem, ...] = ()

    def __post_init__(self) -> None:
        if not self.instrument_id.strip():
            raise ValueError("instrument_id must not be empty")
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        if len(self.currency) != 3 or not self.currency.isascii() or not self.currency.isupper():
            raise ValueError("currency must be a three-letter uppercase code")
        if self.price_observation_age_days is not None and self.price_observation_age_days < 0:
            raise ValueError("price_observation_age_days cannot be negative")
        if self.portfolio_drawdown is not None and (
            not self.portfolio_drawdown.is_finite() or not ZERO <= self.portfolio_drawdown <= ONE
        ):
            raise ValueError("portfolio_drawdown must be a finite fraction between 0 and 1")


@dataclass(frozen=True, slots=True)
class Recommendation:
    """An auditable research result, never a trade instruction or profit claim."""

    instrument_id: str
    action: RecommendationAction
    generated_at: datetime
    evidence_ids: tuple[str, ...]
    risk_flags: tuple[RiskFlag, ...]
    confidence_level: Decimal
    explanation: str
    invalidation_conditions: tuple[str, ...]
    data_freshness: datetime | None
    methodology_version: str = FORMULA_VERSION
    fundamental_assessment: str = ""
    price_assessment: str = ""
    dividend_assessment: str = ""

    def __post_init__(self) -> None:
        if not ZERO <= self.confidence_level <= ONE:
            raise ValueError("confidence_level must be a fraction between 0 and 1")


def _metric_map(metrics: Sequence[ComputedMetric]) -> Mapping[str, ComputedMetric]:
    return {item.name: item for item in metrics}


def _drawdown_flag(value: Decimal | None, policy: ScreeningPolicy) -> RiskFlag | None:
    if value is None:
        return None
    if value >= policy.critical_drawdown:
        return RiskFlag.CRITICAL_DRAWDOWN
    if value >= policy.elevated_drawdown:
        return RiskFlag.ELEVATED_DRAWDOWN
    return None


def evaluate_candidate(
    candidate: ScreeningInput,
    *,
    policy: ScreeningPolicy | None = None,
) -> Recommendation:
    """Produce a recommendation from verified evidence and deterministic rules."""

    applied = ScreeningPolicy() if policy is None else policy
    by_name = _metric_map(candidate.metrics)
    flags: list[RiskFlag] = []
    reasons: list[str] = []

    # Required fundamentals must exist and be computed from usable inputs.
    missing: list[str] = []
    unusable: list[str] = []
    for name in applied.required_metrics:
        metric = by_name.get(name)
        if metric is None or metric.status is MetricStatus.MISSING_INPUT:
            missing.append(name)
        elif metric.value is None or metric.status is not MetricStatus.OK:
            unusable.append(name)
    if missing:
        flags.append(RiskFlag.MISSING_FUNDAMENTALS)
        reasons.append(f"Missing required financial inputs: {', '.join(missing)}.")
    if unusable:
        flags.append(RiskFlag.MISSING_FUNDAMENTALS)
        reasons.append(f"Required metrics have unusable denominators: {', '.join(unusable)}.")

    verified_fundamentals = sum(
        1 for item in candidate.metrics if item.status is MetricStatus.OK and item.value is not None
    )
    if verified_fundamentals == 0:
        return Recommendation(
            instrument_id=candidate.instrument_id,
            action=RecommendationAction.INSUFFICIENT_DATA,
            generated_at=candidate.as_of,
            evidence_ids=tuple(item.evidence_id for item in candidate.evidence),
            risk_flags=tuple(flags),
            confidence_level=ZERO,
            explanation="No usable fundamental metrics are available; no conclusion is drawn.",
            invalidation_conditions=("Add verified financial statement inputs before screening.",),
            data_freshness=None,
            fundamental_assessment="No verified fundamental evidence.",
            price_assessment="Not evaluated.",
            dividend_assessment="Not evaluated.",
        )

    # Price evidence is required and must be fresh and verified.
    if candidate.price_observation_age_days is None or candidate.price_quality != "VERIFIED":
        flags.append(RiskFlag.UNVERIFIED_PRICE)
        reasons.append("No verified price observation is available.")
    elif candidate.price_observation_age_days > applied.max_observation_age_days:
        flags.append(RiskFlag.STALE_PRICE)
        reasons.append(
            f"Price is {candidate.price_observation_age_days} days old; "
            f"limit is {applied.max_observation_age_days}."
        )

    controls = candidate.risk_controls
    drawdown = candidate.portfolio_drawdown
    if drawdown is None and controls is not None:
        drawdown = controls.drawdown
    drawdown_flag = _drawdown_flag(drawdown, applied)
    if drawdown_flag is not None:
        flags.append(drawdown_flag)
        reasons.append(
            f"Portfolio drawdown reached {drawdown}; "
            "new buy candidates are suspended pending review."
        )
    if controls is not None:
        if controls.buy_candidates_suspended or controls.critical:
            flags.append(RiskFlag.RISK_REVIEW_REQUIRED)
            reasons.append(
                "An active risk-control event requires an explicit review before new "
                "BUY_CANDIDATE recommendations can be promoted."
            )
        elif controls.review_required:
            reasons.append(
                "A risk-control review is recorded; it does not suspend new buy candidates."
            )

    # Signal evaluation uses only verified, usable metric values.
    def signal(name: str, predicate: Callable[[Decimal], bool]) -> bool | None:
        metric = by_name.get(name)
        if metric is None or metric.status is not MetricStatus.OK or metric.value is None:
            return None
        return predicate(metric.value)

    growth = signal(REVENUE_GROWTH, lambda value: value >= applied.min_revenue_growth)
    margin = signal(NET_MARGIN, lambda value: value > ZERO)
    roe = signal(RETURN_ON_EQUITY, lambda value: value >= applied.min_return_on_equity)
    leverage = signal(DEBT_TO_EQUITY, lambda value: value <= applied.max_debt_to_equity)
    pe = signal(PRICE_TO_EARNINGS, lambda value: value > ZERO)

    net_income_metric = by_name.get(NET_MARGIN)
    if (
        net_income_metric is not None
        and net_income_metric.value is not None
        and net_income_metric.value <= ZERO
    ):
        flags.append(RiskFlag.NEGATIVE_EARNINGS)
    debt_metric = by_name.get(DEBT_TO_EQUITY)
    if (
        debt_metric is not None
        and debt_metric.value is not None
        and debt_metric.value > applied.max_debt_to_equity
    ):
        flags.append(RiskFlag.HIGH_LEVERAGE)
    if candidate.dividend_evidence_ids:
        dividend_assessment = (
            f"{len(candidate.dividend_evidence_ids)} verified dividend event reference(s)."
        )
    else:
        dividend_assessment = "No verified dividend evidence; income quality not assessed."
        flags.append(RiskFlag.NO_DIVIDEND_EVIDENCE)

    signals = [growth, margin, roe, leverage, pe]
    positive = sum(1 for item in signals if item is True)
    failures = [
        name for name, item in zip(applied.required_metrics, signals, strict=False) if item is False
    ]

    blocking = {
        RiskFlag.STALE_PRICE,
        RiskFlag.UNVERIFIED_PRICE,
        RiskFlag.MISSING_FUNDAMENTALS,
        RiskFlag.CRITICAL_DRAWDOWN,
        RiskFlag.ELEVATED_DRAWDOWN,
        RiskFlag.RISK_REVIEW_REQUIRED,
    }
    has_blocking = any(flag in blocking for flag in flags)

    if (
        RiskFlag.CRITICAL_DRAWDOWN in flags
        or (controls is not None and controls.critical)
        or (RiskFlag.NEGATIVE_EARNINGS in flags and RiskFlag.HIGH_LEVERAGE in flags)
    ):
        action = RecommendationAction.AVOID
    elif has_blocking:
        action = RecommendationAction.WATCH
    elif positive >= applied.min_positive_signals_for_buy:
        action = RecommendationAction.BUY_CANDIDATE
    elif positive >= applied.min_positive_signals_for_hold:
        action = RecommendationAction.HOLD
    else:
        action = RecommendationAction.WATCH

    if failures and action is RecommendationAction.BUY_CANDIDATE:
        reasons.append(f"Unmet fundamental signals: {', '.join(failures)}.")

    verified_evidence = sum(1 for item in candidate.evidence if item.quality == "VERIFIED")
    if candidate.price_quality == "VERIFIED":
        verified_evidence += 1
    verified_evidence += verified_fundamentals
    confidence = min(ONE, Decimal(verified_evidence) / Decimal(applied.expected_evidence_count))

    freshness = next(
        (item.observed_at for item in candidate.evidence if item.observed_at is not None),
        None,
    )
    for item in candidate.evidence:
        if item.observed_at is not None and (freshness is None or item.observed_at > freshness):
            freshness = item.observed_at

    invalidation: tuple[str, ...] = (
        "A required input becomes stale, unverified or materially incomplete.",
        "Portfolio drawdown reaches the elevated or critical review threshold.",
        "Verified fundamentals materially change from the values used here.",
    )
    if RiskFlag.RISK_REVIEW_REQUIRED in flags:
        invalidation += (
            "The active risk-control event must be explicitly reviewed before a "
            "BUY_CANDIDATE can be promoted.",
        )
    explanation_parts = [
        f"{action.value}: {positive} of {len(signals)} fundamental signals passed.",
        *reasons,
    ]
    if has_blocking:
        explanation_parts.append(
            "BUY_CANDIDATE is blocked until the stale, unverified or incomplete evidence "
            "is resolved and any required portfolio review is completed."
        )
    explanation_parts.append(
        "Confidence reflects evidence quality and completeness only, not the probability of profit."
    )

    evidence_ids: list[str] = [item.evidence_id for item in candidate.evidence]
    if candidate.price_evidence_id:
        evidence_ids.append(candidate.price_evidence_id)
    evidence_ids.extend(candidate.dividend_evidence_ids)
    if controls is not None:
        evidence_ids.extend(f"risk:{event_id}" for event_id in controls.active_event_ids)

    return Recommendation(
        instrument_id=candidate.instrument_id,
        action=action,
        generated_at=candidate.as_of,
        evidence_ids=tuple(dict.fromkeys(evidence_ids)),
        risk_flags=tuple(flags),
        confidence_level=confidence,
        explanation=" ".join(explanation_parts),
        invalidation_conditions=invalidation,
        data_freshness=freshness,
        fundamental_assessment=(
            f"{verified_fundamentals} usable metric(s); "
            f"{positive} of {len(signals)} signals passed."
        ),
        price_assessment=(
            "Verified price available."
            if candidate.price_quality == "VERIFIED"
            else "No verified price observation."
        ),
        dividend_assessment=dividend_assessment,
    )
