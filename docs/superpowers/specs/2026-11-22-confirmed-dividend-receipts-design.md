# Confirmed dividend receipts — design

Date: 2026-11-22. Size: small feature (one vertical slice).

## Intent and why

RFinance records dividend events with provenance and computes labelled
analytics, but a confirmed cash receipt has never been posted into the
simulated portfolio. Without it, cash balances cannot be reconciled to
actually received dividend income and the documented 50/30/20 distribution
preference is only text. This slice posts an explicitly confirmed net receipt
into the immutable ledger with duplicate protection and an auditable split.

## Goals

- A new ledger event `CONFIRMED_DIVIDEND` that credits a net cash amount and is
  unique per `(instrument_id, source_reference)`.
- A service that only posts from a dividend event whose effective quality is
  `VERIFIED`, whose status is `CONFIRMED`/`HISTORICAL`, and whose type is cash.
- Exact `Decimal` allocation using the configured 50% reinvest / 30% money
  market / 20% withdrawal preference, persisted for inspection.
- The withdrawal leg leaves the simulation as a separate `CASH_WITHDRAWAL`
  event so cash still reconciles; reinvest and money-market legs remain
  unallocated cash targets until a verified instrument is invested.
- A connected Dividend Center workflow and regression tests.

## Non-goals / anti-goals

- No broker login, real order, monthly contribution, or money movement.
- No inference of withholding tax, quantity held at ex-date, or a money-market
  instrument. Missing inputs are not converted to zero or guessed.
- No AI path may post a receipt; only an explicit user action.
- A simulated/projected dividend must never be posted as a confirmed receipt.

## Constraints

- All monetary values are `Decimal`; exact fixed-point text in SQLite.
- Base currency IDR; no currency conversion.
- Ledger is append-only; every balance must be reconstructable by replay.
- Duplicate receipts must be rejected by both replay and a database constraint.
- `AGENTS.md` remains canonical; skills do not override product invariants.

## Approaches

1. **Chosen — new ledger event type plus an explicit withdrawal leg.** Extends
   the canonical ledger, keeps cash reconciliation exact, and makes the source
   dividend event the deduplication key. Costs one SQLite table rebuild because
   the event-type CHECK constraint must change.
2. Reuse `SIMULATED_DIVIDEND` with a "confirmed" prefix. Rejected: it would
   label actual received cash as simulated, violating a core invariant.
3. Keep receipts in a separate ledger and display them alongside portfolio
   cash. Rejected: cash would not reconcile with recorded transactions.

## Design

- `LedgerEventType.CONFIRMED_DIVIDEND`: requires `instrument_id`, positive
  `amount` (net cash actually received), non-empty `source_reference`, zero
  fees/taxes, no trade fields. Replay credits cash, accumulates
  `confirmed_dividend_income`, and rejects a duplicate `(instrument, ref)`.
- `DividendReceiptService.post_receipt(dividend_event_id, net_amount, ...)`
  re-reads the dividend event and its effective quality, refuses estimates,
  simulations, announcements, cancellations and unverified events, computes
  the split with `allocate_confirmed_dividend`, then appends two ledger events
  (`CONFIRMED_DIVIDEND` net, `CASH_WITHDRAWAL` withdrawal leg) atomically and
  stores a `dividend_receipts` audit row unique on `dividend_event_id`.
- The caller supplies the confirmed net amount explicitly; it is never derived
  from a forecast. An optional `quantity`/`withholding_rate` is recorded as
  context only, not used to invent a cash figure.
- Migration `0008_confirmed_dividend_receipts` rebuilds
  `portfolio_ledger_events` with the extended CHECK constraint, recreates its
  indexes and append-only triggers, and adds `dividend_receipts`.
- UI: a "Confirmed receipt" form in the Dividend Center for a selected
  verified event; shows the computed allocation and the resulting ledger cash.

## Builder latitude

Choose column widths and index names consistent with existing migrations; keep
the exact event type name, source_reference convention
`DIVIDEND_RECEIPT:<event_id>` / `DIVIDEND_WITHDRAWAL:<event_id>`, and the
50/30/20 weights from the product specification.
