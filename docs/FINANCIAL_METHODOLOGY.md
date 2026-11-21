# Financial Methodology

## General rules

- Monetary and share-level calculations use Decimal; floating point is reserved for explicitly non-accounting statistical work.
- Every metric must declare its unit, currency, period, source inputs, formula version, and missing-data behavior.
- Never replace missing observations with zero.
- A zero or negative denominator is invalid for metrics whose denominator represents revenue, equity, assets, or capital base; return an unavailable result with a reason rather than infinity.
- Reported metrics, derived metrics, analyst estimates, forward estimates, AI interpretations, and simulations must be separately labelled.
- Financial statements must be period-aligned and use a declared reporting basis (annual, quarterly, trailing twelve months, etc.).

## Current deterministic primitives

The initial implementation exposes:
- Margin fraction = profit / revenue, only when revenue > 0.
- ROE fraction = net income / average equity, only when average equity > 0.
- Debt-to-equity = total debt / total equity, only when debt >= 0 and equity > 0.

The functions return a fraction (for example, 0.25 = 25%), not a percentage-point value. Presentation formatting is a separate concern. Industry context and source-data requirements are not inferred by these low-level primitives.

## Planned metric conventions

Before release, document and test period alignment, treatment of negative earnings/equity, leases, minority interests, preferred equity, financial-sector exceptions, corporate actions, split adjustments, and restatements for every supported formula. Do not publish EV/EBITDA, yield, payout, coverage, or valuation outputs until their required inputs and conventions are defined.
