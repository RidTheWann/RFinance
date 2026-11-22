# Portfolio Accounting Model — Local Simulation Ledger

## Scope

The portfolio ledger is an append-only, deterministic record of explicit simulated portfolio events. Its domain replay engine reconstructs cash, holdings, weighted-average cost, realized profit/loss, simulated dividend cash, fees, and taxes. A SQLAlchemy repository persists these events in SQLite, and an application service validates the full proposed ledger before committing a new event.

The ledger is not yet connected to a complete first-run wizard or portfolio UI. No default capital or position is injected automatically.

## Supported events

- `CAPITAL_INJECTION`: explicit funding event; no capital is assumed or automatically repeated.
- `BUY`: debits quantity × unit price plus purchase fees and taxes.
- `SELL`: credits quantity × unit price less sale fees and taxes.
- `CASH_WITHDRAWAL`: explicit cash outflow; cannot make cash negative.
- `SIMULATED_DIVIDEND`: explicit simulated net cash receipt tied to an existing position and unique source reference. It is not a confirmed real-world receipt or an announced/forecast dividend.
- `CONFIRMED_DIVIDEND`: net cash actually received for a verified, observed cash dividend event. Its `source_reference` is `DIVIDEND_RECEIPT:<event_id>` and is unique per instrument; replay accumulates `confirmed_dividend_income` separately from simulated dividends. The 20% withdrawal leg is booked as a separate `CASH_WITHDRAWAL` so cash reconciles.

Every event has a unique event ID, strictly increasing sequence, timezone-aware event time, and one account currency. The default replay currency is IDR; foreign exchange is not inferred.

## Cost basis and realized P/L

Weighted average cost is used.

- Buy cost basis addition = quantity × unit price + buy fees + buy taxes.
- Sale proceeds = quantity × unit price − sale fees − sale taxes.
- Cost basis removed on sale = current weighted average cost × sold quantity; a full position close removes the exact remaining basis to avoid residual rounding.
- Realized P/L = net sale proceeds − cost basis removed.

Unrealized P/L is intentionally not calculated here; it requires a timestamped, quality-qualified market valuation.

## Instrument lot constraints

Every buy or sell requires a `VerifiedLotSize` value containing a positive lot size, source reference, and timezone-aware verification timestamp. A missing or untyped lot-size value blocks the trade. Quantity must be an exact multiple of lot size.

The current repository does not yet have a production instrument registry/provider that issues verified lot-size records. Test fixtures use clearly marked synthetic evidence. Production UI must not permit users or AI to assert verification manually; the future source-registry flow must construct `VerifiedLotSize` only from validated market-rule evidence.

## Persistence and append-only behavior

- Ledger events are stored in `portfolio_ledger_events`.
- Monetary and quantity Decimals are stored as fixed-point text rather than SQLite NUMERIC, preserving exact decimal representation through close/reopen.
- Event timestamps are normalized to UTC ISO-8601 strings.
- The database enforces unique event IDs, unique sequence numbers, unique per-instrument dividend source references, allowed event types, and positive sequence numbers.
- SQLite triggers reject direct UPDATE and DELETE operations on ledger rows.
- Repository insertion requires the next contiguous sequence. The application service replays the proposed event set before persistence.
- Re-opening the database reloads events in sequence order and reconstructs the snapshot; summary totals are never treated as the source of truth.

The SQLite append-only triggers protect against ordinary accidental mutations through the database connection. They are not a cryptographic tamper-proof mechanism against an owner who can modify or replace the database file.

## Integrity rules

- Cash may never become negative.
- A sale cannot exceed the held quantity.
- A dividend cannot be credited without a holding at that point in the event sequence.
- A simulated dividend source reference cannot be credited twice per instrument.
- Forecasts and announcements do not create cash events.
- Replay does not create missing instruments, positions, or external capital.
- Currency mismatch is rejected; no implicit FX conversion is performed.

## Remaining portfolio work

The ledger still needs UI workflows, configurable initial-capital setup, verified instrument/lot-size registry integration, corporate-action handling, market valuation history, allocation/rebalancing, backup/restore tests, and end-user reconciliation/reporting.
