# Dividend Event Ledger and Calendar

Status: implemented local vertical slice (migration `0006_dividend_events`).
Methodology version for calculations: `dividend-analytics-v1` (see
[DIVIDEND_ANALYTICS.md](DIVIDEND_ANALYTICS.md)).

## Scope

This document describes how dividend **observations** enter RFinance, how they
are reviewed, and how the existing deterministic calculation layer is connected
to a calendar and a desktop view. It does not add a market-data provider, an
automatic dividend feed, or a broker integration.

## Data model

Two append-only SQLite tables are created by Alembic migration
`0006_dividend_events`:

- `dividend_events` — one raw observation per `(source_id, event_key)`, with
  instrument and source foreign keys, dividend type, lifecycle status, gross
  per-share amount (exact `Decimal` text), currency, ex/payment/record/cum
  dates, acquisition and announcement timestamps, reporting period, document
  reference, original value, unit, notes, and transformation version.
- `dividend_review_events` — an audit ledger of explicit `VERIFIED` / `REJECTED`
  decisions with reviewer, evidence reference, SHA-256 digest, notes, and a
  metadata snapshot.

Both tables have SQLite triggers that abort `UPDATE` and `DELETE`. A decision
never mutates the raw observation; the effective quality is the most recent
decision for the event, falling back to the ingested quality.

A `DividendEventContract` (Pydantic v2, frozen, `extra="forbid"`) validates
ingestion. It requires a timezone-aware acquisition timestamp, a three-letter
uppercase currency, a positive amount for cash types, no cash amount for
`STOCK`/`RIGHTS`, and an ordered reporting period when present. Ingested events
default to `UNVERIFIED`.

## Status versus quality

`event_status` and `quality_status` are independent:

- `event_status` describes the lifecycle: `ANNOUNCED`, `CONFIRMED`,
  `HISTORICAL`, `ESTIMATED`, `SIMULATED`, `CANCELLED`.
- `quality_status` (and the effective review decision) describes evidence
  quality using the shared `DataQualityStatus` values.

Only events that are **both** effectively `VERIFIED` **and** in an observed
status (`CONFIRMED` or `HISTORICAL`) with a cash type are eligible for trailing
analytics. Estimates, simulations, announcements and cancellations are never
counted as observed cash.

## Review gates

`DividendEventService.review_event_from_file` archives a user-selected document
under the per-user data directory (`Documents/DividendReviewEvidence`), hashes
it with SHA-256 using a bounded copy loop, then calls `review_event`. Promotion
to `VERIFIED` requires:

1. a raw `UNVERIFIED` event;
2. an instrument whose identity is already `VERIFIED` in the instrument master;
3. a source whose policy is neither `BLOCKED` nor `RESTRICTED`;
4. a lifecycle status that is not `ESTIMATED`, `SIMULATED` or `CANCELLED`;
5. a reviewer label, evidence reference, valid digest and non-empty notes.

There is no automatic promotion and no AI decision path. Verifying a dividend
does not verify prices, source licensing, or corporate-action adjustment.

## Calendar and analytics

- `calendar(start, end, instrument_id)` returns ex-dates and payment dates in a
  window. Each entry carries `is_confirmed_cash` and `is_estimate` flags, the
  effective quality and the source label. The same event can appear twice for
  different date kinds. An announced date is a planning item, not cash.
- `analytics(...)` maps eligible events into `DividendRecord` inputs for the
  pure calculation layer and returns trailing gross per-share amount, trailing
  yield (only when the caller supplies a price), an explicitly labelled forward
  yield (only when the caller supplies an estimate), net per-share amount (only
  when a withholding rate is known), and annual consistency. Missing inputs
  return `None`; they are never converted to zero.

The Dividend Center desktop page connects these services. It has no static demo
values: every row, date and figure is read from the local ledger or calculated
from verified events on a worker thread.

## Confirmed receipt posting (`dividend-receipt-v1`)

A Dividend Center workflow can post a net dividend that was **actually
received** into the simulated ledger. `DividendReceiptService.post_receipt`
requires an event whose effective quality is `VERIFIED`, whose status is
`CONFIRMED` or `HISTORICAL`, and whose type is cash; announcements, estimates,
simulations and unverified events are rejected. The caller supplies the net
amount explicitly — it is never derived from a forecast. The split uses the
configured 50% reinvest / 30% money market / 20% withdrawal preference via
`allocate_confirmed_dividend`, is stored in an append-only `dividend_receipts`
table unique on `dividend_event_id`, and is shown in the desktop. A duplicate
post is rejected by the service, the replay check and the database constraint.
The withdrawal leg leaves the simulation as a `CASH_WITHDRAWAL`; the other two
legs remain cash targets until a verified instrument is invested.

## Known boundaries

- Amounts are gross per share as supplied by the document. Currency conversion,
  withholding-tax rules and corporate-action adjustments are not inferred.
- Simulated dividend projections are never accepted as confirmed receipts.
- No provider adapter, scraping, or automated dividend calendar feed is enabled.
