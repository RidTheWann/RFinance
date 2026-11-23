# Reporting

RFinance reports are local, user-controlled exports of records already stored
in the application. They never fetch market data and never present simulated
activity as actual brokerage performance.

## Simulated ledger CSV (`ledger-csv-v1`)

`LedgerReportService.ledger_csv()` renders the authoritative portfolio ledger
through `render_ledger_report()` in `src/rfinance/reporting/csv.py`. The
Portfolio Simulator's "Export simulated ledger (CSV)" button writes the report
to a user-selected path.

Every row carries:

- `sequence`, `event_id`, `occurred_at_utc` and `event_type` from the immutable
  ledger;
- explicit `instrument_id`, `quantity`, `unit_price`, `amount`, `fees`, `taxes`
  and `currency` cells;
- `source_reference` for provenance where the event requires it;
- `record_status = SIMULATED` and the `methodology_version` (`ledger-csv-v1`);
- the UTC `generated_at_utc` timestamp of the export.

Rules:

- Missing optional values are **empty cells**, never zero.
- Events are ordered by ledger sequence and duplicate sequences are rejected.
- An event whose currency differs from the ledger base currency is rejected
  rather than silently mixed into the report.
- CSV quoting is delegated to the standard library, so commas and quotes in
  source references are preserved.
- User-supplied text cells beginning with a spreadsheet formula prefix
  (`=`, `+`, `-`, `@`, tab or carriage return) are prefixed with an apostrophe
  so a spreadsheet application treats them as text rather than a formula.
- The export contains no recomputed totals: cash, positions and P/L must be
  reconstructed from the ledger by the deterministic replay engine.

The report is a record of the local simulation. It is not a tax document,
brokerage statement or evidence of executed trades.
