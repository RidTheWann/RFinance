# Observation Review Workflow

Market observations are immutable: SQLite append-only triggers block updates and
deletes on `market_observations`. A price is never silently relabelled. Instead,
an explicit operator decision appends an event to `observation_review_events`,
and the *effective* quality is the most recent decision for that observation.

This workflow is implemented in `src/rfinance/application/observation_review.py`
with persistence from Alembic migration `0005_observation_review`. It deliberately
has no AI decision path and no automatic promotion.

## Gates for promotion to `VERIFIED`

All of the following must hold. Any failure raises an error and writes no event:

1. The observation exists.
2. Its raw quality is exactly `UNVERIFIED`. `SIMULATED`, `ESTIMATED`, `STALE`,
   `INCOMPLETE`, and `REJECTED` observations cannot be promoted.
3. Its effective quality is not already `VERIFIED`.
4. The instrument master status is `VERIFIED`. Instrument identity verification
   is a prerequisite, not a substitute, for price verification.
5. The source exists in the registry and its policy status is neither `BLOCKED`
   nor `RESTRICTED`.
6. A reviewer label, evidence reference, SHA-256 digest, and notes are supplied.

A `REJECTED` decision is always recordable with the same evidence requirements,
and a later `VERIFIED` decision can supersede it. Each event stores the previous
effective quality, the decision, the reviewer, the archived evidence reference,
the digest, the timestamp, and a JSON snapshot of the original observation
provenance.

## Evidence handling

`review_observation_from_file` copies a user-selected file into
`Documents/ObservationReviewEvidence` under the configured per-user data
directory, computes its SHA-256 digest, and links the archived relative path to
the audit event. Archive paths are checked to remain inside the data directory.
If the database write fails, the just-archived copy is removed. The caller may
instead supply an evidence reference and digest directly via `review_observation`.

## Connection to the eligibility gate

`effective_quality` returns the quality currently visible to downstream gates.
`list_candidates` shows raw and effective quality side by side so a reviewer can
see what will change. `candidates_for_eligibility` builds domain
`ObservationCandidate` values using the effective quality, ready for
`select_eligible_observations` from `eligibility-observation-v1`.

Verification here certifies only this explicit review decision. It does not
prove licensing, corporate-action adjustment, or that the observation is still
fresh; the eligibility gate checks those separately at use time.
