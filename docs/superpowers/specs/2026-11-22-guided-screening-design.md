# Guided screening evaluation — design

Date: 2026-11-22. Size: small feature.

## Intent

The deterministic screening engine exists but no workflow assembles evidence
from persisted records. This slice adds an application service and a Research
Center form that evaluate one instrument from instrument status, the latest
review-adjusted price, verified dividend evidence, and explicitly supplied
fundamental inputs, then persist the recommendation.

## Goals / non-goals

- Goals: assemble only persisted/eligible evidence; never invent a metric;
  keep AI out; use `RecommendationService.evaluate` unchanged; show why a
  `BUY_CANDIDATE` was blocked.
- Non-goals: no financial-statement persistence yet, no price fetch, no
  automated evaluation schedule, no portfolio drawdown inference.

## Constraints

- `Decimal` inputs, IDR, `AGENTS.md` canonical, append-only recommendations.
- Fundamental values are supplied by the operator and labelled as such; the
  service does not claim they came from a verified filing.
- Drawdown, when supplied, must be a finite fraction between 0 and 1.

## Approaches

1. **Chosen — application service + opt-in form.** Reads instrument/price/
   dividend evidence, computes metrics from supplied inputs, delegates to the
   existing recommendation engine. Small and testable.
2. Persist financial statements first. Rejected: larger scope; belongs to a
   separate slice.
3. Let the UI build `ScreeningInput` directly. Rejected: puts domain assembly
   in the presentation layer.

## Design

`ScreeningEvaluationService.evaluate(instrument_id, *, fundamentals, as_of,
portfolio_drawdown=None, ...)`:
- load instrument registry; unresolved/unverified/inactive → emit candidate
  with unusable price evidence;
- load latest review-adjusted observation for the instrument via
  `ObservationReviewService.list_candidates`, map source policy from the
  source registry, compute age days from `observed_at_utc`;
- collect verified cash dividend event IDs for the instrument;
- compute `fundamental-metrics-v1` via `compute_fundamental_metrics`;
- build `EvidenceItem`s with explicit references and `VERIFIED`/`UNVERIFIED`
  quality, then call `RecommendationService.evaluate` and return its result.

UI: a form in the Research Center for instrument ID, five fundamental inputs,
optional drawdown, and an "Evaluate" button; results list stays as-is.
