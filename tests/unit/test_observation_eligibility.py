from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from rfinance.domain.eligibility.observation import (
    EligibilityPolicy,
    EligibilityReason,
    InstrumentState,
    InstrumentStatus,
    ObservationCandidate,
    ObservationQuality,
    SourcePolicyStatus,
    SourceState,
    evaluate_observation,
    select_eligible_observations,
)

AS_OF = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)
OBSERVED_AT = datetime(2026, 1, 9, 12, 0, tzinfo=UTC)
ACQUIRED_AT = datetime(2026, 1, 9, 18, 0, tzinfo=UTC)


def candidate(**overrides: object) -> ObservationCandidate:
    values: dict[str, object] = {
        "instrument_id": "IDX:BBCA",
        "observed_at": OBSERVED_AT,
        "acquired_at": ACQUIRED_AT,
        "close": Decimal("9500"),
        "currency": "IDR",
        "source_id": "source-1",
        "quality": ObservationQuality.VERIFIED,
    }
    values.update(overrides)
    return ObservationCandidate(**values)  # type: ignore[arg-type]


def instrument(**overrides: object) -> InstrumentState:
    values: dict[str, object] = {
        "instrument_id": "IDX:BBCA",
        "verification_status": InstrumentStatus.VERIFIED,
        "active": True,
        "currency": "IDR",
    }
    values.update(overrides)
    return InstrumentState(**values)  # type: ignore[arg-type]


def source(**overrides: object) -> SourceState:
    values: dict[str, object] = {
        "source_id": "source-1",
        "policy_status": SourcePolicyStatus.UNREVIEWED,
    }
    values.update(overrides)
    return SourceState(**values)  # type: ignore[arg-type]


def evaluate(
    item: ObservationCandidate,
    *,
    instrument_state: InstrumentState | None = None,
    source_state: SourceState | None = None,
    policy: EligibilityPolicy | None = None,
) -> tuple[EligibilityReason, ...]:
    decision = evaluate_observation(
        item,
        instrument=instrument() if instrument_state is None else instrument_state,
        source=source() if source_state is None else source_state,
        as_of=AS_OF,
        expected_currency="IDR",
        policy=policy,
    )
    return () if decision.eligible else decision.reasons


def test_verified_observation_from_unreviewed_user_import_is_eligible() -> None:
    assert evaluate(candidate()) == ()


def test_instrument_verification_does_not_promote_an_observation() -> None:
    reasons = evaluate(candidate(quality=ObservationQuality.UNVERIFIED))
    assert EligibilityReason.OBSERVATION_UNVERIFIED in reasons


def test_unverified_or_rejected_instrument_is_blocked() -> None:
    assert EligibilityReason.INSTRUMENT_UNVERIFIED in evaluate(
        candidate(), instrument_state=instrument(verification_status=InstrumentStatus.UNVERIFIED)
    )
    assert EligibilityReason.INSTRUMENT_REJECTED in evaluate(
        candidate(), instrument_state=instrument(verification_status=InstrumentStatus.REJECTED)
    )


def test_inactive_or_wrong_currency_instrument_is_blocked() -> None:
    assert EligibilityReason.INSTRUMENT_INACTIVE in evaluate(
        candidate(), instrument_state=instrument(active=False)
    )
    assert EligibilityReason.INSTRUMENT_CURRENCY_MISMATCH in evaluate(
        candidate(), instrument_state=instrument(currency="USD")
    )


def test_missing_instrument_or_source_is_blocked() -> None:
    missing_instrument = evaluate_observation(
        candidate(),
        instrument=None,
        source=source(),
        as_of=AS_OF,
        expected_currency="IDR",
    )
    missing_source = evaluate_observation(
        candidate(),
        instrument=instrument(),
        source=None,
        as_of=AS_OF,
        expected_currency="IDR",
    )
    assert EligibilityReason.INSTRUMENT_UNVERIFIED in missing_instrument.reasons
    assert EligibilityReason.UNKNOWN_SOURCE in missing_source.reasons


def test_source_policy_gates() -> None:
    assert EligibilityReason.SOURCE_BLOCKED in evaluate(
        candidate(), source_state=source(policy_status=SourcePolicyStatus.BLOCKED)
    )
    assert EligibilityReason.SOURCE_RESTRICTED in evaluate(
        candidate(), source_state=source(policy_status=SourcePolicyStatus.RESTRICTED)
    )
    assert (
        evaluate(candidate(), source_state=source(policy_status=SourcePolicyStatus.APPROVED)) == ()
    )


def test_unreviewed_source_can_be_disabled_by_policy() -> None:
    strict = EligibilityPolicy(allow_unreviewed_sources=False)
    assert EligibilityReason.SOURCE_UNREVIEWED in evaluate(candidate(), policy=strict)


def test_currency_is_never_silently_converted() -> None:
    assert EligibilityReason.CURRENCY_MISMATCH in evaluate(candidate(currency="USD"))


def test_future_and_stale_observations_are_blocked() -> None:
    future = candidate(observed_at=AS_OF + timedelta(minutes=1))
    assert EligibilityReason.FUTURE_OBSERVATION in evaluate(future)
    stale = candidate(observed_at=AS_OF - timedelta(days=30))
    assert EligibilityReason.STALE_OBSERVATION in evaluate(stale)


def test_acquisition_timing_gates() -> None:
    before_observation = candidate(acquired_at=OBSERVED_AT - timedelta(minutes=1))
    assert EligibilityReason.INVALID_ACQUISITION_TIME in evaluate(before_observation)
    very_late = candidate(acquired_at=OBSERVED_AT + timedelta(days=30))
    assert EligibilityReason.LATE_ACQUISITION in evaluate(very_late)


def test_non_positive_or_non_finite_close_is_blocked() -> None:
    assert EligibilityReason.INVALID_CLOSE in evaluate(candidate(close=Decimal("0")))
    assert EligibilityReason.INVALID_CLOSE in evaluate(candidate(close=Decimal("-1")))
    assert EligibilityReason.INVALID_CLOSE in evaluate(candidate(close=Decimal("NaN")))


def test_all_failed_gates_are_reported_together() -> None:
    reasons = evaluate(
        candidate(
            currency="USD",
            quality=ObservationQuality.SIMULATED,
            close=Decimal("0"),
            observed_at=AS_OF + timedelta(days=1),
        )
    )
    assert set(reasons) >= {
        EligibilityReason.CURRENCY_MISMATCH,
        EligibilityReason.OBSERVATION_UNVERIFIED,
        EligibilityReason.INVALID_CLOSE,
        EligibilityReason.FUTURE_OBSERVATION,
    }


def test_timezone_offsets_are_normalized_to_utc() -> None:
    offset = timezone(timedelta(hours=7))
    local = candidate(
        observed_at=OBSERVED_AT.astimezone(offset),
        acquired_at=ACQUIRED_AT.astimezone(offset),
    )
    assert evaluate(local) == ()


def test_report_partitions_without_mutating_inputs() -> None:
    good = candidate()
    bad = candidate(quality=ObservationQuality.ESTIMATED)
    report = select_eligible_observations(
        [good, bad],
        instruments={"IDX:BBCA": instrument()},
        sources={"source-1": source()},
        as_of=AS_OF,
        expected_currency="IDR",
    )
    assert report.eligible == (good,)
    assert [item for item, _ in report.rejected] == [bad]
    assert report.rejected[0][1].eligible is False


def test_invalid_inputs_are_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        candidate(observed_at=datetime(2026, 1, 9, 12, 0))
    with pytest.raises(ValueError, match="currency"):
        candidate(currency="idr")
    with pytest.raises(ValueError, match="positive integer"):
        EligibilityPolicy(max_observation_age_days=0)
    with pytest.raises(ValueError, match="allowed_qualities"):
        EligibilityPolicy(allowed_qualities=frozenset())
    with pytest.raises(ValueError, match="does not match"):
        evaluate(candidate(), instrument_state=instrument(instrument_id="IDX:OTHER"))
    with pytest.raises(ValueError, match="timezone-aware"):
        evaluate_observation(
            candidate(),
            instrument=instrument(),
            source=source(),
            as_of=datetime(2026, 1, 10, 12, 0),
            expected_currency="IDR",
        )


@given(
    age_days=st.integers(min_value=0, max_value=400),
    quality=st.sampled_from(list(ObservationQuality)),
)
def test_stale_or_unverified_observations_are_never_eligible(
    age_days: int, quality: ObservationQuality
) -> None:
    item = candidate(
        observed_at=AS_OF - timedelta(days=age_days),
        acquired_at=AS_OF - timedelta(days=age_days) + timedelta(hours=1),
        quality=quality,
    )
    decision = evaluate_observation(
        item,
        instrument=instrument(),
        source=source(),
        as_of=AS_OF,
        expected_currency="IDR",
    )
    if quality is not ObservationQuality.VERIFIED or age_days > 7:
        assert decision.eligible is False
        assert decision.reasons


@given(day=st.integers(min_value=-5, max_value=5))
def test_future_observations_are_never_eligible(day: int) -> None:
    item = candidate(
        observed_at=AS_OF + timedelta(days=day),
        acquired_at=AS_OF + timedelta(days=day, hours=1),
    )
    decision = evaluate_observation(
        item,
        instrument=instrument(),
        source=source(),
        as_of=AS_OF,
        expected_currency="IDR",
    )
    if day > 0:
        assert EligibilityReason.FUTURE_OBSERVATION in decision.reasons
        assert decision.eligible is False
