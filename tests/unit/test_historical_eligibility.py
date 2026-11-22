# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from rfinance.domain.eligibility.historical import (
    HistoricalEligibilityReason,
    historical_observation_reasons,
)
from rfinance.domain.eligibility.observation import (
    InstrumentState,
    InstrumentStatus,
    ObservationCandidate,
    ObservationQuality,
    SourcePolicyStatus,
    SourceState,
)

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


def make_candidate(
    *,
    observed_at: datetime | None = None,
    acquired_at: datetime | None = None,
    quality: ObservationQuality = ObservationQuality.VERIFIED,
    currency: str = "IDR",
) -> ObservationCandidate:
    observed = observed_at or datetime(2010, 1, 4, 9, 0, tzinfo=UTC)
    acquired = acquired_at or NOW
    return ObservationCandidate(
        instrument_id="IDX:BBCA",
        observed_at=observed,
        acquired_at=acquired,
        close=Decimal("9000"),
        currency=currency,
        source_id="source-bbca",
        quality=quality,
    )


def instrument(
    status: InstrumentStatus = InstrumentStatus.VERIFIED,
    *,
    active: bool = True,
    currency: str = "IDR",
) -> InstrumentState:
    return InstrumentState(
        instrument_id="IDX:BBCA",
        verification_status=status,
        active=active,
        currency=currency,
    )


def source(
    status: SourcePolicyStatus = SourcePolicyStatus.UNREVIEWED,
) -> SourceState:
    return SourceState(source_id="source-bbca", policy_status=status)


def evaluate(
    candidate: ObservationCandidate,
    *,
    identity: InstrumentState | None = None,
    provider: SourceState | None = None,
    allow_unreviewed_sources: bool = True,
):
    return historical_observation_reasons(
        candidate,
        instruments={} if identity is None else {candidate.instrument_id: identity},
        sources={} if provider is None else {candidate.source_id: provider},
        as_of=NOW,
        expected_currency="IDR",
        allow_unreviewed_sources=allow_unreviewed_sources,
    )


def test_old_historical_bar_and_late_user_import_remain_eligible() -> None:
    candidate = make_candidate(
        observed_at=datetime(2010, 1, 4, 9, 0, tzinfo=UTC),
        acquired_at=NOW,
    )

    assert evaluate(candidate, identity=instrument(), provider=source()) == ()


def test_historical_eligibility_does_not_allow_lookahead() -> None:
    candidate = make_candidate(observed_at=NOW + timedelta(seconds=1))

    reasons = evaluate(candidate, identity=instrument(), provider=source())

    assert HistoricalEligibilityReason.FUTURE_OBSERVATION in reasons


def test_only_verified_prices_and_verified_active_instruments_are_allowed() -> None:
    candidate = make_candidate(quality=ObservationQuality.UNVERIFIED)

    reasons = evaluate(
        candidate,
        identity=instrument(InstrumentStatus.UNVERIFIED, active=False),
        provider=source(),
    )

    assert HistoricalEligibilityReason.OBSERVATION_UNVERIFIED in reasons
    assert HistoricalEligibilityReason.INSTRUMENT_UNVERIFIED in reasons
    assert HistoricalEligibilityReason.INSTRUMENT_INACTIVE in reasons


def test_blocked_restricted_and_unknown_sources_are_rejected() -> None:
    candidate = make_candidate()

    assert HistoricalEligibilityReason.SOURCE_BLOCKED in evaluate(
        candidate,
        identity=instrument(),
        provider=source(SourcePolicyStatus.BLOCKED),
    )
    assert HistoricalEligibilityReason.SOURCE_RESTRICTED in evaluate(
        candidate,
        identity=instrument(),
        provider=source(SourcePolicyStatus.RESTRICTED),
    )
    assert HistoricalEligibilityReason.UNKNOWN_SOURCE in evaluate(
        candidate,
        identity=instrument(),
    )


def test_unreviewed_source_policy_is_explicitly_configurable() -> None:
    candidate = make_candidate()

    reasons = evaluate(
        candidate,
        identity=instrument(),
        provider=source(),
        allow_unreviewed_sources=False,
    )

    assert HistoricalEligibilityReason.SOURCE_UNREVIEWED in reasons


def test_wrong_currency_and_acquisition_before_observation_are_rejected() -> None:
    observed = NOW - timedelta(days=2)
    candidate = make_candidate(
        observed_at=observed,
        acquired_at=observed - timedelta(minutes=1),
        currency="USD",
    )

    reasons = evaluate(candidate, identity=instrument(), provider=source())

    assert HistoricalEligibilityReason.CURRENCY_MISMATCH in reasons
    assert HistoricalEligibilityReason.INVALID_ACQUISITION_TIME in reasons


def test_invalid_or_inactive_instrument_currency_is_rejected() -> None:
    candidate = make_candidate()

    reasons = evaluate(
        candidate,
        identity=instrument(active=False, currency="USD"),
        provider=source(),
    )

    assert HistoricalEligibilityReason.INSTRUMENT_INACTIVE in reasons
    assert HistoricalEligibilityReason.INSTRUMENT_CURRENCY_MISMATCH in reasons
