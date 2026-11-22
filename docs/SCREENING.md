# Deterministic Screening and Recommendations

Formula version: `screening-deterministic-v1`.
Persistence: Alembic migration `0007_recommendations` (append-only table).

## Scope and authority

RFinance generates **research results**, never trade instructions. The engine
is deterministic: AI output cannot override a risk flag, change a threshold,
or supply a missing figure. Confidence measures evidence quality and
analytical completeness only — it is explicitly not the probability that an
investment will be profitable.

A persisted recommendation is an audit record. The `recommendations` table and
its database triggers prevent updates and deletes; a new evaluation appends a
new row.

## Inputs

`ScreeningInput` requires:

- instrument ID, as-of time (timezone-aware) and expected currency;
- computed fundamental metrics from `fundamental-metrics-v1`
  (`src/rfinance/analysis/fundamental/metrics.py`);
- price observation age in days and its quality, with an evidence reference;
- optional dividend evidence references;
- optional portfolio drawdown under the documented valuation methodology;
- an evidence list, each item carrying an ID, kind, reference, quality,
  timestamp and summary.

The application layer is responsible for assembling these inputs from the
eligibility gates and persisted records. The domain engine never fetches data
or infers a prior period.

## Rules

Required metrics are revenue growth, net margin, ROE, debt-to-equity and P/E.
A missing required input produces `MISSING_FUNDAMENTALS`; a metric with an
unusable denominator or missing source values is never converted to zero. If
no metric is usable, the result is `INSUFFICIENT_DATA` with zero confidence.

Price evidence must be `VERIFIED` and within the configured age limit
(default 7 days). Otherwise `UNVERIFIED_PRICE` or `STALE_PRICE` is raised.

Drawdown uses the configured review triggers (10% elevated, 15% critical). A
critical drawdown, or negative earnings combined with excessive leverage,
produces `AVOID`. Any blocking flag — stale/unverified price, missing
fundamentals, elevated or critical drawdown — prevents a `BUY_CANDIDATE`.
With all evidence in order, the action is based on how many of the five
fundamental signals pass: at least four gives `BUY_CANDIDATE`, three gives
`HOLD`, fewer gives `WATCH`.

The result records the action, evidence IDs (deduplicated and deterministic),
risk flags, confidence fraction, explanation, invalidation conditions, newest
evidence timestamp, methodology version, and separate fundamental/price/
dividend assessments.

## Interpretation boundaries

- A `BUY_CANDIDATE` means "eligible for further research", not "buy now".
- `NO_DIVIDEND_EVIDENCE` is a transparency flag, not a penalty that fabricates
  a dividend figure.
- Thresholds are configurable review triggers, not guaranteed loss limits.
- Technical indicators are not yet an input to the action decision; they are
  reported separately by the Technical Analysis workflow.

## Guided evaluation workflow (`screening-evaluation-v1`)

`ScreeningEvaluationService.evaluate(instrument_id, fundamentals, ...)` assembles
evidence from persisted records only:

- instrument identity/status/currency from the instrument master;
- the latest review-adjusted price from the observation ledger, with age in
  days and source policy from the source registry;
- verified cash dividend event IDs for the instrument;
- metrics computed from operator-supplied fundamental inputs via
  `fundamental-metrics-v1`.

Fundamental inputs are explicitly labelled as operator-supplied, not verified
filings. No price is fetched and no metric is inferred. The assembled
`ScreeningInput` is passed unchanged to `RecommendationService.evaluate`, so
the same blocking rules and evidence requirements apply.

## Desktop view

The Research Center tab lists stored recommendations and exposes each result's
explanation, evidence IDs, risk flags and invalidation conditions. Its
"Evaluate from local evidence" form runs the assembly workflow on a Qt worker
thread and displays the resulting action and evidence.
