# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Deterministic eligibility gates for using market observations in analysis.

Formula version: ``eligibility-observation-v1``.

This is a pure policy layer. It does not fetch data, mutate records, change
quality states, or decide recommendations. It reports every failed gate so a
user can see why an observation cannot be used.
"""

from __future__ import annotations

import decimal
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

FORMULA_VERSION = "eligibility-observation-v1"


class ObservationQuality(StrEnum):
    """Observation qualities mirroring ``DataQualityStatus`` values."""

    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    ESTIMATED = "ESTIMATED"
    STALE = "STALE"
    INCOMPLETE = "INCOMPLETE"
    REJECTED = "REJECTED"
    SIMULATED = "SIMULATED"


class InstrumentStatus(StrEnum):
    """Instrument-master verification states."""

    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    REJECTED = "REJECTED"


class SourcePolicyStatus(StrEnum):
    """Source-registry policy states mirroring persisted values."""

    APPROVED = "APPROVED"
    UNREVIEWED = "UNREVIEWED"
    RESTRICTED = "RESTRICTED"
    BLOCKED = "BLOCKED"


class EligibilityReason(StrEnum):
    """Machine-readable reasons an observation cannot be used."""

    INSTRUMENT_UNVERIFIED = "INSTRUMENT_UNVERIFIED"
    INSTRUMENT_REJECTED = "INSTRUMENT_REJECTED"
    INSTRUMENT_INACTIVE = "INSTRUMENT_INACTIVE"
    INSTRUMENT_CURRENCY_MISMATCH = "INSTRUMENT_CURRENCY_MISMATCH"
    OBSERVATION_UNVERIFIED = "OBSERVATION_UNVERIFIED"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    FUTURE_OBSERVATION = "FUTURE_OBSERVATION"
    STALE_OBSERVATION = "STALE_OBSERVATION"
    LATE_ACQUISITION = "LATE_ACQUISITION"
    INVALID_ACQUISITION_TIME = "INVALID_ACQUISITION_TIME"
    INVALID_CLOSE = "INVALID_CLOSE"
    UNKNOWN_SOURCE = "UNKNOWN_SOURCE"
    SOURCE_BLOCKED = "SOURCE_BLOCKED"
    SOURCE_RESTRICTED = "SOURCE_RESTRICTED"
    SOURCE_UNREVIEWED = "SOURCE_UNREVIEWED"


DEFAULT_ALLOWED_QUALITIES = frozenset({ObservationQuality.VERIFIED})
DEFAULT_ALLOWED_INSTRUMENT_STATUSES = frozenset({InstrumentStatus.VERIFIED})


@dataclass(frozen=True, slots=True)
class ObservationCandidate:
    """A normalized observation with the provenance needed for a gate decision."""

    instrument_id: str
    observed_at: datetime
    acquired_at: datetime
    close: decimal.Decimal
    currency: str
    source_id: str
    quality: ObservationQuality

    def __post_init__(self) -> None:
        _timezone_aware(self.observed_at, "observed_at")
        _timezone_aware(self.acquired_at, "acquired_at")
        _text(self.instrument_id, "instrument_id")
        _text(self.source_id, "source_id")
        _currency(self.currency, "currency")
        if not isinstance(self.quality, ObservationQuality):
            raise ValueError("quality must be an ObservationQuality")
        if not isinstance(self.close, decimal.Decimal):
            raise ValueError("close must be a decimal.Decimal")


@dataclass(frozen=True, slots=True)
class InstrumentState:
    """The instrument-master state relevant to observation eligibility."""

    instrument_id: str
    verification_status: InstrumentStatus
    active: bool
    currency: str

    def __post_init__(self) -> None:
        _text(self.instrument_id, "instrument_id")
        _currency(self.currency, "currency")
        if not isinstance(self.verification_status, InstrumentStatus):
            raise ValueError("verification_status must be an InstrumentStatus")


@dataclass(frozen=True, slots=True)
class SourceState:
    """The source-registry policy state relevant to observation eligibility."""

    source_id: str
    policy_status: SourcePolicyStatus

    def __post_init__(self) -> None:
        _text(self.source_id, "source_id")
        if not isinstance(self.policy_status, SourcePolicyStatus):
            raise ValueError("policy_status must be a SourcePolicyStatus")


@dataclass(frozen=True, slots=True)
class EligibilityPolicy:
    """Configurable thresholds for observation usability."""

    max_observation_age_days: int = 7
    max_acquisition_lag_days: int = 7
    allow_unreviewed_sources: bool = True
    allowed_qualities: frozenset[ObservationQuality] = DEFAULT_ALLOWED_QUALITIES
    allowed_instrument_statuses: frozenset[InstrumentStatus] = DEFAULT_ALLOWED_INSTRUMENT_STATUSES

    def __post_init__(self) -> None:
        _positive_int(self.max_observation_age_days, "max_observation_age_days")
        _positive_int(self.max_acquisition_lag_days, "max_acquisition_lag_days")
        if not self.allowed_qualities:
            raise ValueError("allowed_qualities cannot be empty")
        if not self.allowed_instrument_statuses:
            raise ValueError("allowed_instrument_statuses cannot be empty")
        if not all(isinstance(item, ObservationQuality) for item in self.allowed_qualities):
            raise ValueError("allowed_qualities must contain ObservationQuality values")
        if not all(isinstance(item, InstrumentStatus) for item in self.allowed_instrument_statuses):
            raise ValueError("allowed_instrument_statuses must contain InstrumentStatus values")


@dataclass(frozen=True, slots=True)
class EligibilityDecision:
    """All failed gates for one observation; empty reasons means eligible."""

    eligible: bool
    reasons: tuple[EligibilityReason, ...]
    evaluated_at: datetime
    methodology_version: str = FORMULA_VERSION


@dataclass(frozen=True, slots=True)
class EligibilityReport:
    """Eligible observations and the rejection diagnostics for the rest."""

    eligible: tuple[ObservationCandidate, ...]
    rejected: tuple[tuple[ObservationCandidate, EligibilityDecision], ...]


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _currency(value: object, name: str) -> str:
    result = _text(value, name)
    if len(result) != 3 or not result.isascii() or not result.isupper():
        raise ValueError(f"{name} must be a three-letter uppercase currency code")
    return result


def _timezone_aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _source_reason(
    source: SourceState | None,
    policy: EligibilityPolicy,
) -> EligibilityReason | None:
    if source is None:
        return EligibilityReason.UNKNOWN_SOURCE
    if source.policy_status is SourcePolicyStatus.BLOCKED:
        return EligibilityReason.SOURCE_BLOCKED
    if source.policy_status is SourcePolicyStatus.RESTRICTED:
        return EligibilityReason.SOURCE_RESTRICTED
    if (
        source.policy_status is SourcePolicyStatus.UNREVIEWED
        and not policy.allow_unreviewed_sources
    ):
        return EligibilityReason.SOURCE_UNREVIEWED
    return None


def evaluate_observation(
    candidate: ObservationCandidate,
    *,
    instrument: InstrumentState | None,
    source: SourceState | None,
    as_of: datetime,
    expected_currency: str,
    policy: EligibilityPolicy | None = None,
) -> EligibilityDecision:
    """Evaluate one observation against every configured gate.

    Instrument identity verification and price observation verification are
    separate gates. Verifying an instrument never promotes an observation.
    """

    applied = EligibilityPolicy() if policy is None else policy
    evaluated_at = _timezone_aware(as_of, "as_of")
    expected = _currency(expected_currency, "expected_currency")
    reasons: list[EligibilityReason] = []

    if instrument is None:
        reasons.append(EligibilityReason.INSTRUMENT_UNVERIFIED)
    else:
        if instrument.instrument_id != candidate.instrument_id:
            raise ValueError("instrument.instrument_id does not match the observation")
        if instrument.verification_status not in applied.allowed_instrument_statuses:
            if instrument.verification_status is InstrumentStatus.REJECTED:
                reasons.append(EligibilityReason.INSTRUMENT_REJECTED)
            else:
                reasons.append(EligibilityReason.INSTRUMENT_UNVERIFIED)
        if not instrument.active:
            reasons.append(EligibilityReason.INSTRUMENT_INACTIVE)
        if instrument.currency != expected:
            reasons.append(EligibilityReason.INSTRUMENT_CURRENCY_MISMATCH)

    if candidate.quality not in applied.allowed_qualities:
        reasons.append(EligibilityReason.OBSERVATION_UNVERIFIED)
    if candidate.currency != expected:
        reasons.append(EligibilityReason.CURRENCY_MISMATCH)

    observed_at = candidate.observed_at.astimezone(UTC)
    acquired_at = candidate.acquired_at.astimezone(UTC)
    reference = evaluated_at.astimezone(UTC)
    if observed_at > reference:
        reasons.append(EligibilityReason.FUTURE_OBSERVATION)
    elif reference - observed_at > timedelta(days=applied.max_observation_age_days):
        reasons.append(EligibilityReason.STALE_OBSERVATION)

    if acquired_at < observed_at:
        reasons.append(EligibilityReason.INVALID_ACQUISITION_TIME)
    elif acquired_at - observed_at > timedelta(days=applied.max_acquisition_lag_days):
        reasons.append(EligibilityReason.LATE_ACQUISITION)

    if not candidate.close.is_finite() or candidate.close <= decimal.Decimal(0):
        reasons.append(EligibilityReason.INVALID_CLOSE)

    source_reason = _source_reason(source, applied)
    if source_reason is not None:
        reasons.append(source_reason)

    return EligibilityDecision(
        eligible=not reasons,
        reasons=tuple(reasons),
        evaluated_at=evaluated_at,
    )


def select_eligible_observations(
    candidates: Sequence[ObservationCandidate],
    *,
    instruments: Mapping[str, InstrumentState],
    sources: Mapping[str, SourceState],
    as_of: datetime,
    expected_currency: str,
    policy: EligibilityPolicy | None = None,
) -> EligibilityReport:
    """Partition observations into usable and rejected without mutating them."""

    eligible: list[ObservationCandidate] = []
    rejected: list[tuple[ObservationCandidate, EligibilityDecision]] = []
    for candidate in candidates:
        instrument = instruments.get(candidate.instrument_id)
        source = sources.get(candidate.source_id)
        decision = evaluate_observation(
            candidate,
            instrument=instrument,
            source=source,
            as_of=as_of,
            expected_currency=expected_currency,
            policy=policy,
        )
        if decision.eligible:
            eligible.append(candidate)
        else:
            rejected.append((candidate, decision))
    return EligibilityReport(eligible=tuple(eligible), rejected=tuple(rejected))
