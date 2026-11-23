# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Deterministic risk-policy engine tests (no Qt, database or network)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from rfinance.domain.risk.controls import (
    RiskPolicy,
    RiskRule,
    RiskSeverity,
    RiskSnapshot,
    evaluate_risk,
)

_AS_OF = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)


def _snapshot(**overrides: object) -> RiskSnapshot:
    values: dict[str, object] = {
        "as_of": _AS_OF,
        "peak_value": Decimal("1000000"),
        "current_value": Decimal("900000"),
        "valuation_methodology": "portfolio-valuation-v1",
        "valuation_is_complete": True,
        "instrument_weights": {},
        "sector_weights": {},
        "allocation_deviations": {},
        "last_reviewed_at": None,
    }
    values.update(overrides)
    return RiskSnapshot(**values)  # type: ignore[arg-type]


def test_ten_percent_drawdown_raises_elevated_event_and_suspends_buy_candidates() -> None:
    assessment = evaluate_risk(_snapshot())

    assert assessment.drawdown == Decimal("0.10")
    assert [finding.rule for finding in assessment.findings] == [RiskRule.ELEVATED_DRAWDOWN]
    assert assessment.findings[0].severity is RiskSeverity.WARNING
    assert assessment.buy_candidates_suspended is True
    assert assessment.allocation_changes_suspended is False
    assert assessment.review_required is True


@pytest.mark.parametrize(
    ("current", "expected_drawdown", "expected_rule"),
    [
        (Decimal("1000000"), Decimal("0"), None),
        (Decimal("1100000"), Decimal("0"), None),
        (Decimal("900001"), Decimal("0.099999"), None),
        (Decimal("900000"), Decimal("0.10"), RiskRule.ELEVATED_DRAWDOWN),
        (Decimal("850000"), Decimal("0.15"), RiskRule.CRITICAL_DRAWDOWN),
        (Decimal("800000"), Decimal("0.20"), RiskRule.CRITICAL_DRAWDOWN),
    ],
)
def test_drawdown_boundaries_select_the_expected_rule(
    current: Decimal,
    expected_drawdown: Decimal,
    expected_rule: RiskRule | None,
) -> None:
    assessment = evaluate_risk(_snapshot(current_value=current))

    assert assessment.drawdown == expected_drawdown
    assert [finding.rule for finding in assessment.findings] == (
        [] if expected_rule is None else [expected_rule]
    )


def test_critical_drawdown_suspends_allocation_changes_as_well_as_buys() -> None:
    assessment = evaluate_risk(_snapshot(current_value=Decimal("850000")))

    assert assessment.findings[0].severity is RiskSeverity.CRITICAL
    assert assessment.buy_candidates_suspended is True
    assert assessment.allocation_changes_suspended is True
    assert assessment.review_required is True


def test_incomplete_valuation_produces_no_drawdown_finding() -> None:
    assessment = evaluate_risk(
        _snapshot(
            valuation_is_complete=False,
            instrument_weights={"IDX:BBCA": Decimal("0.05")},
        )
    )

    assert assessment.drawdown is None
    assert [finding.rule for finding in assessment.findings] == [RiskRule.VALUATION_INCOMPLETE]
    assert assessment.buy_candidates_suspended is False


def test_missing_or_non_positive_peak_produces_no_drawdown_finding() -> None:
    without_peak = evaluate_risk(_snapshot(peak_value=None))
    zero_peak = evaluate_risk(_snapshot(peak_value=Decimal("0")))

    assert without_peak.drawdown is None
    assert zero_peak.drawdown is None
    assert [finding.rule for finding in without_peak.findings] == [RiskRule.VALUATION_INCOMPLETE]
    assert [finding.rule for finding in zero_peak.findings] == [RiskRule.VALUATION_INCOMPLETE]


def test_custom_policy_thresholds_are_applied() -> None:
    policy = RiskPolicy(elevated_drawdown=Decimal("0.05"), critical_drawdown=Decimal("0.25"))

    assert [f.rule for f in evaluate_risk(_snapshot(), policy=policy).findings] == [
        RiskRule.ELEVATED_DRAWDOWN
    ]
    assert [
        f.rule
        for f in evaluate_risk(_snapshot(current_value=Decimal("760000")), policy=policy).findings
    ] == [RiskRule.ELEVATED_DRAWDOWN]


def test_instrument_and_sector_concentration_raise_review_findings() -> None:
    assessment = evaluate_risk(
        _snapshot(
            current_value=Decimal("1100000"),
            instrument_weights={"IDX:BBCA": Decimal("0.11")},
            sector_weights={"FINANCIALS": Decimal("0.21")},
        )
    )

    findings = {item.rule: item for item in assessment.findings}
    assert set(findings) == {
        RiskRule.SINGLE_INSTRUMENT_CONCENTRATION,
        RiskRule.SECTOR_CONCENTRATION,
    }
    assert findings[RiskRule.SINGLE_INSTRUMENT_CONCENTRATION].observed_value == Decimal("0.11")
    assert findings[RiskRule.SINGLE_INSTRUMENT_CONCENTRATION].threshold == Decimal("0.10")
    assert findings[RiskRule.SECTOR_CONCENTRATION].observed_value == Decimal("0.21")
    assert findings[RiskRule.SECTOR_CONCENTRATION].threshold == Decimal("0.20")
    assert assessment.buy_candidates_suspended is True
    assert assessment.allocation_changes_suspended is False


def test_concentration_at_the_limit_does_not_trigger() -> None:
    assessment = evaluate_risk(
        _snapshot(
            current_value=Decimal("1100000"),
            instrument_weights={"IDX:BBCA": Decimal("0.10")},
            sector_weights={"FINANCIALS": Decimal("0.20")},
        )
    )

    assert assessment.findings == ()
    assert assessment.review_required is False


def test_allocation_deviation_beyond_tolerance_requires_review() -> None:
    assessment = evaluate_risk(
        _snapshot(
            current_value=Decimal("1100000"),
            allocation_deviations={"EQUITY_INDEX": Decimal("0.06")},
        )
    )

    findings = {item.rule: item for item in assessment.findings}
    assert set(findings) == {RiskRule.ALLOCATION_DEVIATION}
    assert findings[RiskRule.ALLOCATION_DEVIATION].observed_value == Decimal("0.06")
    assert findings[RiskRule.ALLOCATION_DEVIATION].threshold == Decimal("0.05")
    assert assessment.buy_candidates_suspended is False


def test_review_is_overdue_after_six_calendar_months() -> None:
    just_due = evaluate_risk(_snapshot(last_reviewed_at=datetime(2026, 5, 23, 12, 0, tzinfo=UTC)))
    not_yet_due = evaluate_risk(
        _snapshot(last_reviewed_at=datetime(2026, 5, 24, 12, 0, tzinfo=UTC))
    )

    assert RiskRule.REVIEW_OVERDUE in {item.rule for item in just_due.findings}
    assert RiskRule.REVIEW_OVERDUE not in {item.rule for item in not_yet_due.findings}


def test_prohibited_activity_is_a_critical_blocking_finding() -> None:
    assessment = evaluate_risk(
        _snapshot(current_value=Decimal("1100000"), prohibited_activities=("LEVERAGE",))
    )

    assert len(assessment.findings) == 1
    finding = assessment.findings[0]
    assert finding.rule is RiskRule.PROHIBITED_ACTIVITY
    assert finding.severity is RiskSeverity.CRITICAL
    assert "LEVERAGE" in finding.explanation
    assert assessment.buy_candidates_suspended is True
    assert assessment.allocation_changes_suspended is True


def test_findings_have_a_deterministic_order() -> None:
    snapshot = _snapshot(
        current_value=Decimal("1100000"),
        prohibited_activities=("SHORT_SELLING", "LEVERAGE"),
        instrument_weights={"IDX:A": Decimal("0.12"), "IDX:B": Decimal("0.11")},
        sector_weights={"FINANCIALS": Decimal("0.22")},
        allocation_deviations={"EQUITY_INDEX": Decimal("0.06")},
        last_reviewed_at=_AS_OF - timedelta(days=200),
    )

    first = evaluate_risk(snapshot)
    second = evaluate_risk(snapshot)

    assert first == second
    assert [item.rule for item in first.findings] == [
        RiskRule.PROHIBITED_ACTIVITY,
        RiskRule.PROHIBITED_ACTIVITY,
        RiskRule.SINGLE_INSTRUMENT_CONCENTRATION,
        RiskRule.SINGLE_INSTRUMENT_CONCENTRATION,
        RiskRule.SECTOR_CONCENTRATION,
        RiskRule.ALLOCATION_DEVIATION,
        RiskRule.REVIEW_OVERDUE,
    ]


def test_policy_rejects_invalid_thresholds() -> None:
    with pytest.raises(ValueError, match="elevated drawdown"):
        RiskPolicy(elevated_drawdown=Decimal("0.20"), critical_drawdown=Decimal("0.15"))
    with pytest.raises(ValueError, match="between zero and one"):
        RiskPolicy(max_sector_weight=Decimal("1.5"))


def test_snapshot_rejects_naive_timestamps_and_negative_weights() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _snapshot(as_of=datetime(2026, 11, 23))
    with pytest.raises(ValueError, match="non-negative"):
        _snapshot(instrument_weights={"IDX:BBCA": Decimal("-0.1")})
