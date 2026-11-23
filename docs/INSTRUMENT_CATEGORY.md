# Instrument Category Evidence

Formula version: `instrument-category-v1`. Migration:
`0012_instrument_category`.

RFinance must never invent an investable product. Category membership and lot
size are therefore recorded only through an explicit, evidence-backed review,
not inferred from a ticker, sector label or asset-class name.

## Gates

A category decision is accepted only when:

- the instrument exists in the local registry and is active with
  `verification_status = VERIFIED`;
- the category is one of `EQUITY_INDEX`, `DIVIDEND_EQUITY` or `MONEY_MARKET`;
- the lot size is a positive finite `Decimal`;
- a reviewer label, notes, an evidence reference and a 64-character SHA-256
  digest are supplied;
- the evidence file has been archived under the local data directory when the
  file-based form is used.

Instrument identity verification and category evidence are separate from price
verification. A verified category with a lot size still has no eligible price,
so `allocation-plan-v1` reports `UNFILLED_TARGET` with the reason "no eligible
price" until a verified observation is available. No price is inferred from the
evidence file.

## Ledger semantics

Decisions are append-only. A new decision supersedes earlier ones when deriving
the latest state; a `REJECTED` decision removes the instrument from
`verified_investables()`. `AllocationPlanningService` uses those investables
automatically when no explicit instruments are supplied, so the desktop plan
reflects only evidence the operator has actually reviewed.

The desktop form lives in the Portfolio Simulator's Allocation plan panel. It
lets the operator select an evidence file, choose a category and lot size, and
record either `VERIFIED` or `REJECTED` with reviewer details. The evidence
archive is kept inside the per-user data directory; the original file is never
modified.
