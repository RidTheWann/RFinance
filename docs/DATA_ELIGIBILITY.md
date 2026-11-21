# Observation Eligibility Policy

Formula version: `eligibility-observation-v1`.

This policy is implemented in
`src/rfinance/domain/eligibility/observation.py`. It is a pure, dependency-free
gate that decides whether a normalized market observation may be used by
downstream analysis (portfolio valuation, screening, or recommendations). It
does not fetch data, mutate records, promote quality states, or generate a
recommendation.

## Why a separate gate exists

Instrument identity verification and market-observation verification are
independent facts. Verifying that a ticker maps to a real issuer does not
certify a price, its source licence, its adjustment history, or its freshness.
The gate therefore requires both to be verified before an observation is
eligible. Missing or unverified values are never silently converted to verified
ones.

## Inputs

`ObservationCandidate` carries the instrument id, timezone-aware `observed_at`
and `acquired_at`, a positive finite `close`, a three-letter `currency`, a
`source_id`, and an `ObservationQuality`. `ObservationQuality` values mirror
`DataQualityStatus` so an application-layer mapper can convert persisted
contracts without letting the domain depend on storage.

`InstrumentState` carries the instrument id, verification status, active flag,
and currency. `SourceState` carries the source id and `SourcePolicyStatus`
(`APPROVED`, `UNREVIEWED`, `RESTRICTED`, `BLOCKED`), mirroring the source
registry.

## Gates and reasons

`evaluate_observation` returns every failed gate as an `EligibilityReason`, so
users can see why a value is unusable instead of receiving a silent omission.
An empty reason tuple means eligible.

| Reason | Condition |
|---|---|
| `INSTRUMENT_UNVERIFIED` | No instrument state, or status not in the allowed set |
| `INSTRUMENT_REJECTED` | Instrument-master status is `REJECTED` |
| `INSTRUMENT_INACTIVE` | Instrument is not active |
| `INSTRUMENT_CURRENCY_MISMATCH` | Instrument currency differs from the expected currency |
| `OBSERVATION_UNVERIFIED` | Observation quality is not in the allowed set (default: only `VERIFIED`) |
| `CURRENCY_MISMATCH` | Observation currency differs from the expected currency; no conversion is attempted |
| `FUTURE_OBSERVATION` | `observed_at` is after the evaluation time; blocks look-ahead |
| `STALE_OBSERVATION` | Observation is older than `max_observation_age_days` (default 7) |
| `LATE_ACQUISITION` | `acquired_at - observed_at` exceeds `max_acquisition_lag_days` (default 7) |
| `INVALID_ACQUISITION_TIME` | `acquired_at` precedes `observed_at` |
| `INVALID_CLOSE` | Close is non-finite or non-positive |
| `UNKNOWN_SOURCE` | No source state is available |
| `SOURCE_BLOCKED` | Source policy status is `BLOCKED` |
| `SOURCE_RESTRICTED` | Source policy status is `RESTRICTED` |
| `SOURCE_UNREVIEWED` | Source is `UNREVIEWED` and `allow_unreviewed_sources` is disabled |

All timestamps are normalized to UTC before comparison. Timezone-naive values
are rejected as malformed input rather than assumed to be local time.

## Source-policy interpretation

`allow_unreviewed_sources` defaults to `True`: a user's own imported document
may be used for local analysis even though it has not been approved for
automated access or redistribution. That flag never authorizes fetching,
crawling, or redistribution. `BLOCKED` and `RESTRICTED` sources always fail,
and `APPROVED` sources pass this particular gate.

## Selection

`select_eligible_observations` partitions a sequence into eligible observations
and `(candidate, decision)` rejections without mutating inputs or collapsing
duplicates. Downstream code must consume only the eligible partition. The gate
is a necessary precondition, not a sufficient one: it does not assert that
prices are corporate-action adjusted or that a provider entitlements check has
passed.
