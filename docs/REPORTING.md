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

## Simulated portfolio PDF report (`portfolio-pdf-v1`)

`PortfolioReportService.build()` assembles an explicit `PortfolioReportData`
from the persisted ledger, `portfolio-valuation-v1`, persisted risk controls and
stored recommendations. `render_portfolio_report()` writes it to PDF with
PySide6's `QPdfWriter`; no new dependency is introduced and the renderer adds
no figures of its own. The Portfolio Simulator's "Export portfolio report
(PDF)" button writes the file to a user-chosen path.

The document includes:

- generation time (UTC), reporting period, currency and methodology versions;
- a `SIMULATED — not brokerage performance` status line on every report;
- cash, eligible market value, total simulated value, realized/unrealized P/L
  and valuation completeness;
- per-position valuation with explicit "not valued" diagnostics;
- category targets, current weights and deviations;
- active risk-control state and recent evidence-linked recommendations;
- unvalued-instrument warnings.

`as_text()` provides the same content as plain text for verification and
accessibility. Reports are point-in-time snapshots, not forecasts.
