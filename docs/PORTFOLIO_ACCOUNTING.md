# Portfolio Accounting Model (Initial Simulation Ledger)

## Scope

The first ledger is a pure deterministic domain component. It reconstructs the cash balance, quantities, cost basis, realized profit/loss, simulated dividend cash, and fee/tax totals from ordered immutable events. It is not yet persisted to SQLite or exposed through a complete UI workflow.

## Supported events

- `CAPITAL_INJECTION`: explicit funding event; no capital is assumed or automatically repeated.
- `BUY`: debits quantity × unit price plus purchase fees and taxes.
- `SELL`: credits quantity × unit price less sale fees and taxes.
- `CASH_WITHDRAWAL`: explicit cash outflow; cannot make cash negative.
- `SIMULATED_DIVIDEND`: explicit simulated net cash receipt tied to an existing position and unique source reference. It is not a confirmed real-world receipt or an announced/forecast dividend.

Every event has a unique event ID, strictly increasing sequence, timezone-aware event time, and a currency. The initial replay requires one portfolio currency (IDR by default); foreign exchange is not inferred.

## Cost basis and realized P/L

Weighted average cost is used.

- Buy cost basis addition = quantity × unit price + buy fees + buy taxes.
- Sale proceeds = quantity × unit price − sale fees − sale taxes.
- Cost basis removed on sale = current weighted average cost × sold quantity; a full position close removes the exact remaining basis to avoid residual rounding.
- Realized P/L = net sale proceeds − cost basis removed.

Unrealized P/L is intentionally not calculated here; it requires a timestamped, quality-qualified valuation observation.

## Instrument lot constraints

Every buy or sell requires a known positive lot size supplied by the instrument registry. A missing lot-size record blocks the event. Quantity must be an exact multiple of lot size. The current component does not itself verify an exchange lot-size source; the future registry/provider layer must mark that metadata with provenance and quality before it can be supplied.

## Integrity rules

- The event sequence must be strictly increasing.
- Event IDs must be unique.
- Currency must match the account base currency.
- Cash may never become negative.
- A sale cannot exceed the held quantity.
- A dividend cannot be credited without a holding at that point in the event sequence.
- A simulated dividend source reference cannot be credited twice per instrument.
- Forecasts and announcements do not create cash events.
- Replay does not create missing instruments, positions, or external capital.

## Current boundary

The event replay has no persistence or UI write path yet. The next increment is SQLAlchemy event storage, database migration, repository reconstruction, and integration tests proving that re-opening the database produces the same ledger balances.
