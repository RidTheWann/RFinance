# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Deterministic portfolio risk review triggers.

Formula version: ``risk-controls-v1``.

Drawdown is the peak-to-current decline of a consistently valued simulated
portfolio: ``(peak - current) / peak``. A new high produces zero drawdown.
Thresholds are review triggers, never loss limits or return guarantees. An
incomplete valuation produces no drawdown number at all; missing values are
not coerced to zero or to a verified figure.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

FORMULA_VERSION = "risk-controls-v1"
ZERO = Decimal("0")
ONE = Decimal("1")


class RiskRule(StrEnum):
    """Named, auditable rules that can be triggered by a review."""

    ELEVATED_DRAWDOWN = "ELEVATED_DRAWDOWN"
    CRITICAL_DRAWDOWN = "CRITICAL_DRAWDOWN"
    SINGLE_INSTRUMENT_CONCENTRATION = "SINGLE_INSTRUMENT_CONCENTRATION"
    SECTOR_CONCENTRATION = "SECTOR_CONCENTRATION"
    ALLOCATION_DEVIATION = "ALLOCATION_DEVIATION"
    REVIEW_OVERDUE = "REVIEW_OVERDUE"
    VALUATION_INCOMPLETE = "VALUATION_INCOMPLETE"
    PROHIBITED_ACTIVITY = "PROHIBITED_ACTIVITY"


class RiskSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True, slots=True)
class RiskPolicy:
    """Configurable review thresholds; these are triggers, not guarantees."""

    max_single_instrument_weight: Decimal = Decimal("0.10")
    max_sector_weight: Decimal = Decimal("0.20")
    review_interval_months: int = 6
    allocation_deviation_tolerance: Decimal = Decimal("0.05")
    elevated_drawdown: Decimal = Decimal("0.10")
    critical_drawdown: Decimal = Decimal("0.15")

    def __post_init__(self) -> None:
        if self.review_interval_months <= 0:
            raise ValueError("review_interval_months must be positive")
        for name in (
            "max_single_instrument_weight",
            "max_sector_weight",
            "allocation_deviation_tolerance",
            "elevated_drawdown",
            "critical_drawdown",
        ):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite() or not ZERO <= value <= ONE:
                raise ValueError(f"{name} must be a finite fraction between zero and one")
        if not ZERO <= self.elevated_drawdown <= self.critical_drawdown <= ONE:
            raise ValueError("elevated drawdown cannot exceed critical drawdown")


@dataclass(frozen=True, slots=True)
class RiskSnapshot:
    """Explicit evidence for one risk review; no implicit data fetching."""

    as_of: datetime
    peak_value: Decimal | None
    current_value: Decimal | None
    valuation_methodology: str
    valuation_is_complete: bool
    instrument_weights: Mapping[str, Decimal]
    sector_weights: Mapping[str, Decimal]
    allocation_deviations: Mapping[str, Decimal]
    last_reviewed_at: datetime | None
    prohibited_activities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        if not self.valuation_methodology.strip():
            raise ValueError("valuation_methodology must not be empty")
        for value in (self.peak_value, self.current_value):
            if value is not None and (not value.is_finite() or value < ZERO):
                raise ValueError("portfolio values must be finite and non-negative")
        for name in ("instrument_weights", "sector_weights", "allocation_deviations"):
            mapping: Mapping[str, Decimal] = getattr(self, name)
            for key, value in mapping.items():
                if not isinstance(key, str) or not key.strip():
                    raise ValueError(f"{name} keys must be non-empty labels")
                if not isinstance(value, Decimal) or not value.is_finite() or value < ZERO:
                    raise ValueError(f"{name} values must be finite and non-negative")
        if self.last_reviewed_at is not None and (
            self.last_reviewed_at.tzinfo is None or self.last_reviewed_at.utcoffset() is None
        ):
            raise ValueError("last_reviewed_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class RiskFinding:
    """A triggered rule with its observed value and the threshold it breached."""

    rule: RiskRule
    severity: RiskSeverity
    observed_value: Decimal | None
    threshold: Decimal | None
    explanation: str
    evidence_reference: str


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    """Deterministic outcome of one review, including active suspensions."""

    as_of: datetime
    drawdown: Decimal | None
    findings: tuple[RiskFinding, ...]
    review_required: bool
    buy_candidates_suspended: bool
    allocation_changes_suspended: bool
    valuation_methodology: str
    methodology_version: str = FORMULA_VERSION


def _add_months(value: datetime, months: int) -> datetime:
    """Shift a timezone-aware instant by calendar months, clamping the day."""

    index = value.month - 1 + months
    year = value.year + index // 12
    month = index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def evaluate_risk(
    snapshot: RiskSnapshot,
    *,
    policy: RiskPolicy | None = None,
) -> RiskAssessment:
    """Evaluate the configured review triggers against one explicit snapshot."""

    applied = RiskPolicy() if policy is None else policy
    findings: list[RiskFinding] = []
    drawdown: Decimal | None = None

    valuation_usable = (
        snapshot.valuation_is_complete
        and snapshot.peak_value is not None
        and snapshot.current_value is not None
        and snapshot.peak_value > ZERO
    )
    if valuation_usable:
        peak = snapshot.peak_value
        current = snapshot.current_value
        assert peak is not None and current is not None
        drawdown = max(ZERO, (peak - current) / peak)
        if drawdown >= applied.critical_drawdown:
            findings.append(
                RiskFinding(
                    rule=RiskRule.CRITICAL_DRAWDOWN,
                    severity=RiskSeverity.CRITICAL,
                    observed_value=drawdown,
                    threshold=applied.critical_drawdown,
                    explanation=(
                        f"Peak-to-current drawdown {drawdown} reached the critical "
                        f"review threshold {applied.critical_drawdown}."
                    ),
                    evidence_reference=snapshot.valuation_methodology,
                )
            )
        elif drawdown >= applied.elevated_drawdown:
            findings.append(
                RiskFinding(
                    rule=RiskRule.ELEVATED_DRAWDOWN,
                    severity=RiskSeverity.WARNING,
                    observed_value=drawdown,
                    threshold=applied.elevated_drawdown,
                    explanation=(
                        f"Peak-to-current drawdown {drawdown} reached the elevated "
                        f"review threshold {applied.elevated_drawdown}."
                    ),
                    evidence_reference=snapshot.valuation_methodology,
                )
            )
    else:
        findings.append(
            RiskFinding(
                rule=RiskRule.VALUATION_INCOMPLETE,
                severity=RiskSeverity.WARNING,
                observed_value=None,
                threshold=None,
                explanation=(
                    "No complete valuation series is available; drawdown is unknown "
                    "and no drawdown-based suspension is inferred."
                ),
                evidence_reference=snapshot.valuation_methodology,
            )
        )

    for activity in sorted(set(snapshot.prohibited_activities)):
        findings.append(
            RiskFinding(
                rule=RiskRule.PROHIBITED_ACTIVITY,
                severity=RiskSeverity.CRITICAL,
                observed_value=None,
                threshold=None,
                explanation=(
                    f"Prohibited activity '{activity}' is present; new buy candidates and "
                    "simulated allocation changes are suspended."
                ),
                evidence_reference=snapshot.valuation_methodology,
            )
        )

    for label in sorted(snapshot.instrument_weights):
        weight = snapshot.instrument_weights[label]
        if weight > applied.max_single_instrument_weight:
            findings.append(
                RiskFinding(
                    rule=RiskRule.SINGLE_INSTRUMENT_CONCENTRATION,
                    severity=RiskSeverity.WARNING,
                    observed_value=weight,
                    threshold=applied.max_single_instrument_weight,
                    explanation=(
                        f"{label} weight {weight} exceeds the "
                        f"{applied.max_single_instrument_weight} single-instrument limit."
                    ),
                    evidence_reference=label,
                )
            )

    for label in sorted(snapshot.sector_weights):
        weight = snapshot.sector_weights[label]
        if weight > applied.max_sector_weight:
            findings.append(
                RiskFinding(
                    rule=RiskRule.SECTOR_CONCENTRATION,
                    severity=RiskSeverity.WARNING,
                    observed_value=weight,
                    threshold=applied.max_sector_weight,
                    explanation=(
                        f"{label} sector weight {weight} exceeds the "
                        f"{applied.max_sector_weight} sector limit."
                    ),
                    evidence_reference=label,
                )
            )

    for label in sorted(snapshot.allocation_deviations):
        deviation = snapshot.allocation_deviations[label]
        if deviation > applied.allocation_deviation_tolerance:
            findings.append(
                RiskFinding(
                    rule=RiskRule.ALLOCATION_DEVIATION,
                    severity=RiskSeverity.INFO,
                    observed_value=deviation,
                    threshold=applied.allocation_deviation_tolerance,
                    explanation=(
                        f"{label} deviates {deviation} from target, beyond the "
                        f"{applied.allocation_deviation_tolerance} review tolerance."
                    ),
                    evidence_reference=label,
                )
            )

    if snapshot.last_reviewed_at is not None and snapshot.as_of >= _add_months(
        snapshot.last_reviewed_at.astimezone(snapshot.as_of.tzinfo),
        applied.review_interval_months,
    ):
        findings.append(
            RiskFinding(
                rule=RiskRule.REVIEW_OVERDUE,
                severity=RiskSeverity.INFO,
                observed_value=None,
                threshold=Decimal(applied.review_interval_months),
                explanation=(
                    f"The last recorded portfolio review predates the "
                    f"{applied.review_interval_months}-month review interval."
                ),
                evidence_reference=snapshot.last_reviewed_at.isoformat(),
            )
        )

    critical = any(
        item.rule in (RiskRule.CRITICAL_DRAWDOWN, RiskRule.PROHIBITED_ACTIVITY) for item in findings
    )
    elevated = any(
        item.rule
        in (
            RiskRule.ELEVATED_DRAWDOWN,
            RiskRule.SINGLE_INSTRUMENT_CONCENTRATION,
            RiskRule.SECTOR_CONCENTRATION,
        )
        for item in findings
    )
    return RiskAssessment(
        as_of=snapshot.as_of,
        drawdown=drawdown,
        findings=tuple(findings),
        review_required=bool(findings),
        buy_candidates_suspended=critical or elevated,
        allocation_changes_suspended=critical,
        valuation_methodology=snapshot.valuation_methodology,
    )
