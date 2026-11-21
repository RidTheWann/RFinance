# User-Supplied Market CSV Import

## Purpose and trust status

This workflow imports a local CSV selected by the user. It does not scrape websites, contact IDX/OJK/KSEI, download external datasets, or authenticate to a provider.

Every imported market observation is assigned `UNVERIFIED`. A successful parse means only that the row meets the application's structural and numeric checks. It does not verify the instrument, the origin or licence of the file, whether prices are adjusted, or whether the observation is true.

Do not use imported observations as evidence for a BUY_CANDIDATE until a separate review/verification workflow has been implemented and the required evidence has been captured.

## CSV schema

Encoding: UTF-8 or UTF-8 with BOM. Delimiter: comma. The first line is the header. Header names are case-sensitive canonical names; unknown columns and repeated/blank header names are rejected.

Required columns:

| Column | Meaning | Validation |
|---|---|---|
| `instrument_id` | User-supplied instrument identifier, e.g. `IDX:BBCA` | Non-empty string |
| `observed_at` | Time the observation represents | ISO-8601 timestamp with explicit UTC offset |
| `currency` | Currency of price fields | Three-letter uppercase code, e.g. `IDR` |
| `close` | Closing price | Finite positive decimal |

Optional columns:

| Column | Meaning | Validation |
|---|---|---|
| `open` | Opening price | Finite decimal greater than or equal to zero |
| `high` | High price | Finite decimal greater than or equal to zero |
| `low` | Low price | Finite decimal greater than or equal to zero |
| `volume` | Reported volume | Finite decimal greater than or equal to zero |

Do not include thousands separators, currency symbols, percent signs, or localized decimal commas in numeric fields. Use a period as the decimal separator. Do not put lots in the `volume` field unless the file's source definition makes the intended unit clear; the first import version preserves the reported quantity without converting between lots and shares.

When `high` and/or `low` are provided, the parser checks OHLC consistency. It does not infer missing OHLC values.

## Example

```csv
instrument_id,observed_at,currency,open,high,low,close,volume
IDX:BBCA,2026-11-20T09:00:00+07:00,IDR,9000,9200,8900,9100,1000
IDX:BBRI,2026-11-20T09:00:00+07:00,IDR,4000,4100,3900,4050,2500
```

The example is a schema illustration only. Its identifiers, prices, timestamps, and volumes are not an endorsed or verified market dataset.

## Import behavior

1. The user selects a local `.csv` file using the application file picker and supplies a source label.
2. RFinance copies the selected file into the local `Documents/MarketImports` directory. The original local file is not modified.
3. The application computes SHA-256 from the copied bytes and parses the archived copy.
4. It checks the required schema, timestamps, currency codes, finite numeric values, close price, and OHLC consistency.
5. Valid rows are persisted with their raw input row, normalized values, source ID, acquisition timestamp, observation timestamp, and transformation version.
6. Invalid rows are persisted as row-level issues with their original cells and error messages.
7. The batch records total, accepted, and rejected row counts. The database enforces that these counts reconcile.
8. The application reports the accepted/rejected totals and the `UNVERIFIED` status.

Limits in this version: maximum file size 50 MiB; maximum 500,000 data rows. Parsing and persistence run in a Qt worker thread, so the main UI thread remains responsive. The application prevents closing the window while the import worker is still active.

## Duplicate handling

An observation is considered a duplicate when the same source label has already imported the same `instrument_id` and UTC-normalized `observed_at`. Duplicate rows are rejected and recorded as issues. Existing observations are never overwritten.

A different source label is a separate source identity and may contain a separate observation record for the same instrument and timestamp. The source/provenance remains visible, and no implicit reconciliation or source precedence is applied.

## Local storage and integrity

- Source registry row: `source_registry`
- Import batch metadata: `data_import_batches`
- Parsed observations: `market_observations`
- Rejected row diagnostics: `data_import_issues`
- Archived CSV: path recorded relative to the RFinance data directory, under `Documents/MarketImports`

User-import sources are created as `USER_IMPORT` / `UNREVIEWED` with automated access and redistribution disabled. Database constraints prevent a user-import source from enabling those permissions. Import batches, observations, and issues are append-only through SQLite triggers.

The import workflow does not certify the legal right to use or redistribute the file. The user is responsible for selecting a file obtained lawfully and respecting its provider's licence and permitted-use terms.

## Current limitations

- There is no master instrument registry yet; the parser does not prove that a ticker or instrument ID exists on IDX or another exchange.
- No automatic provider or web crawler is configured.
- The importer does not infer whether prices are raw, split-adjusted, or dividend-adjusted.
- Volume is preserved as reported; no automatic lot/share conversion is performed.
- Imported values are not promoted to `VERIFIED`.
- CSV import alone does not make a security eligible for deterministic investment recommendations.
