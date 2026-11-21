# ADR 0002: Decimal accounting and explicit observation quality

- Status: Accepted
- Date: 2026-11-21

## Context

Financial records can be corrupted by binary floating-point rounding, implicit unit conversions, or treating missing/unverified observations as actual values.

## Decision

Use Decimal for monetary and share-price calculations. Financial input contracts require explicit currency, timestamps, source identity, and quality state. Missing values remain absent; invalid denominators produce unavailable metrics.

## Consequences

- Statistical functions may later use NumPy floats where their domain supports it, but accounting totals and order/cash quantities remain Decimal-based.
- Provenance and quality checks become part of the data contract, not optional UI decoration.
- Formula conventions and quality eligibility must be versioned and tested before recommendations use them.
