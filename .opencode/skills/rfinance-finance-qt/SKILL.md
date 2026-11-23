---
name: RFinance Finance and Qt Patterns
description: Applied patterns for RFinance Decimal finance code, provenance, financial-sector handling, and PySide6 desktop layering. Use when implementing analysis engines, data ingestion, or desktop workflows.
---

# Finance and Qt patterns

## Decimal and units

- Use `Decimal` for money, prices, cash, fees, tax and ledger amounts. Reject non-finite values at boundaries.
- Ratios are fractions, not percentages, unless named otherwise. Store exact Decimal text in SQLite; replay converts back.
- Define numerator, denominator, units, sign convention, missing-data behaviour and formula version for every new metric.
- Guard zero/negative denominators explicitly. Return `None` with a reason; never substitute zero.

See `docs/FINANCIAL_METHODOLOGY.md` for `fundamental-metrics-v1`, `dividend-analytics-v1`, `portfolio-valuation-v1` and `screening-deterministic-v2`.

## Evidence and quality

- Ingest through frozen, `extra="forbid"` Pydantic contracts with provenance fields.
- Raw observations are append-only. Effective quality derives from the latest evidence-backed review, never by mutating the raw row.
- Promotion requires explicit reviewer, evidence reference, SHA-256 digest, notes, verified instrument identity, and allowed source policy.
- Instrument identity verification does not promote a price; verification does not certify licensing, adjustment or freshness.
- Separate reported, derived, forecast, analyst, AI-interpreted and simulated values in every result type.

## Banking exception

When `is_financial=True`, industrial leverage, cash-flow coverage and EV metrics are `NOT_APPLICABLE`. Do not inherit industrial assumptions for banks. Industry classification must come from verified metadata, never inferred from ticker or sector text.

## Screening

Confidence describes evidence quality/completeness only, never probability of profit. Hard-block `BUY_CANDIDATE` for stale/unverified price, missing fundamentals, or elevated/critical drawdown. Each recommendation carries evidence IDs, risk flags, explanation, invalidation conditions, data freshness and methodology version.

## Qt presentation layer

- Widgets only render application-service results. No formulas, SQL, or provider parsing in `ui/`.
- Long-running work runs on a `QThread` worker with `completed`/`failed` signals; expose progress and cancellation where applicable.
- Never close while a worker is running; pages expose `is_busy` and the main window checks it.
- Empty states explain what data is required. Data freshness, units, periods and simulation labels are visible.
- Monkeypatch-free tests use `pytest-qt`; Qt worker-thread tests can be timing-flaky on non-Windows/offscreen runners — verify against CI before calling a failure a product defect.

## Verification

```sh
ruff check . && ruff format --check . && mypy src && python -m pytest
```
