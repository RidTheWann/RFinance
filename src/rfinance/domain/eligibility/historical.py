"""Historical-observation eligibility, separate from current-price freshness."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from rfinance.domain.eligibility.observation import (
    InstrumentState,
    InstrumentStatus,
    ObservationCandidate,
    ObservationQuality,
    SourcePolicyStatus,
    SourceState,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


FORMULA_VERSION = "historical-price-eligibility-v1"


class HistoricalEligibilityReason(StrEnum):
    """Stable diagnostics for historical-price eligibility."""

    INVALID_AS_OF = "INVALID_AS_OF"
    INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
    FUTURE_OBSERVATION = "FUTURE_OBSERVATION"
    INVALID_ACQUISITION_TIME = "INVALID_ACQUISITION_TIME"
    INVALID_CLOSE = "INVALID_CLOSE"
    INSTRUMENT_UNVERIFIED = "INSTRUMENT_UNVERIFIED"
    INSTRUMENT_REJECTED = "INSTRUMENT_REJECTED"
    INSTRUMENT_INACTIVE = "INSTRUMENT_INACTIVE"
    INSTRUMENT_CURRENCY_MISMATCH = "INSTRUMENT_CURRENCY_MISMATCH"
    OBSERVATION_UNVERIFIED = "OBSERVATION_UNVERIFIED"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    UNKNOWN_SOURCE = "UNKNOWN_SOURCE"
    SOURCE_BLOCKED = "SOURCE_BLOCKED"
    SOURCE_RESTRICTED = "SOURCE_RESTRICTED"
    SOURCE_UNREVIEWED = "SOURCE_UNREVIEWED"


def historical_observation_reasons(
    candidate: ObservationCandidate,
    *,
    instruments: Mapping[str, InstrumentState],
    sources: Mapping[str, SourceState],
    as_of: datetime,
    expected_currency: str,
    allow_unreviewed_sources: bool = True,
) -> tuple[HistoricalEligibilityReason, ...]:
    """Return all failures without applying current-quote staleness rules.

    Historical bars are expected to be older than the current market session.
    This gate therefore checks look-ahead, evidence quality, identity, source
    policy, currency and timestamp integrity, but deliberately does not reject
    a bar merely because its observation date is old or it was imported later.
    """

    reasons: list[HistoricalEligibilityReason] = []
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        reasons.append(HistoricalEligibilityReason.INVALID_AS_OF)
        return tuple(reasons)

    observed_at = candidate.observed_at
    acquired_at = candidate.acquired_at
    if (
        observed_at.tzinfo is None
        or observed_at.utcoffset() is None
        or acquired_at.tzinfo is None
        or acquired_at.utcoffset() is None
    ):
        reasons.append(HistoricalEligibilityReason.INVALID_TIMESTAMP)
    else:
        observed_utc = observed_at.astimezone(UTC)
        acquired_utc = acquired_at.astimezone(UTC)
        if observed_utc > as_of.astimezone(UTC):
            reasons.append(HistoricalEligibilityReason.FUTURE_OBSERVATION)
        if acquired_utc < observed_utc:
            reasons.append(HistoricalEligibilityReason.INVALID_ACQUISITION_TIME)

    if candidate.quality is not ObservationQuality.VERIFIED:
        reasons.append(HistoricalEligibilityReason.OBSERVATION_UNVERIFIED)

    if not candidate.close.is_finite() or candidate.close <= 0:
        reasons.append(HistoricalEligibilityReason.INVALID_CLOSE)

    if (
        len(expected_currency) != 3
        or not expected_currency.isascii()
        or not expected_currency.isupper()
    ):
        raise ValueError("expected_currency must be a three-letter uppercase currency code")

    if candidate.currency != expected_currency:
        reasons.append(HistoricalEligibilityReason.CURRENCY_MISMATCH)

    instrument = instruments.get(candidate.instrument_id)
    if instrument is None or instrument.instrument_id != candidate.instrument_id:
        reasons.append(HistoricalEligibilityReason.INSTRUMENT_UNVERIFIED)
    else:
        if instrument.verification_status is InstrumentStatus.UNVERIFIED:
            reasons.append(HistoricalEligibilityReason.INSTRUMENT_UNVERIFIED)
        elif instrument.verification_status is InstrumentStatus.REJECTED:
            reasons.append(HistoricalEligibilityReason.INSTRUMENT_REJECTED)
        if not instrument.active:
            reasons.append(HistoricalEligibilityReason.INSTRUMENT_INACTIVE)
        if instrument.currency != expected_currency:
            reasons.append(HistoricalEligibilityReason.INSTRUMENT_CURRENCY_MISMATCH)

    source = sources.get(candidate.source_id)
    if source is None or source.source_id != candidate.source_id:
        reasons.append(HistoricalEligibilityReason.UNKNOWN_SOURCE)
    elif source.policy_status is SourcePolicyStatus.BLOCKED:
        reasons.append(HistoricalEligibilityReason.SOURCE_BLOCKED)
    elif source.policy_status is SourcePolicyStatus.RESTRICTED:
        reasons.append(HistoricalEligibilityReason.SOURCE_RESTRICTED)
    elif (
        source.policy_status is SourcePolicyStatus.UNREVIEWED
        and not allow_unreviewed_sources
    ):
        reasons.append(HistoricalEligibilityReason.SOURCE_UNREVIEWED)

    return tuple(reasons)
