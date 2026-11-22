# Indonesia Financial Data Access Review

- Review date: 2026-11-21
- Scope: public-market, listed-company, regulatory and central-depository data for the initial Indonesia/IDR market.
- Decision: no automated IDX or OJK provider is approved by this review.

## Executive decision

RFinance must not equate public visibility with a right to automate access, retain, or redistribute a financial dataset. The initial compliant ingestion route is a user-selected file or manually entered observation with explicit origin metadata. Imported observations remain `UNVERIFIED` until source, period, unit, and value checks have actually been completed.

An official provider adapter may be enabled only after its exact product, endpoint/download route, licence, retention, rate limit, redistribution terms, and automated-access permission have been reviewed and recorded.

## IDX / Indonesia Stock Exchange

### Market data and reference products

IDX's Data Services product information describes market data products that include real-time, delayed, end-of-day and historical market information, with licensed data distribution and display/non-display use categories. It also offers reference information related to issuers, financial statements, corporate actions and disclosures.

Official research entry points:
- IDX Data Services: https://www.idx.co.id/en/products/idx-data-services/
- IDX Terms of Use (Indonesian): https://www.idx.co.id/id/syarat-penggunaan/

The product catalogue and licensing terms are a commercial data access route, not evidence that an unlicensed application can consume or redistribute the same content. The current public product pages do not establish a generally available, unrestricted API for RFinance. No endpoint, API key flow, feed format, entitlement, rate limit, or licence price is assumed here.

### Website content

IDX website Terms of Use must be treated as the controlling access policy for website content. The indexed policy states limits on use and prohibits scraping/crawling; public access therefore must not be turned into an automated crawler. A user-visible web page is not an API contract.

**Decision:** no Playwright scraper, HTML crawler, hidden endpoint reverse engineering, paywall bypass, or data redistribution. Re-evaluate a direct feed only against a specific written product/contract and technical specification.

## OJK

OJK's integrated Data Portal is the official research entry point for financial-sector statistics and metadata:
- OJK Data Portal: https://data.ojk.go.id/
- OJK main site: https://www.ojk.go.id/

OJK statistical datasets are useful for sector context and regulatory aggregates. They should not be mistaken for a live exchange quote feed or a security-level corporate-action service. Availability of a downloadable report does not, by itself, establish permission for automated bulk retrieval, perpetual local caching, or redistribution.

**Decision:** treat the portal as a candidate source for explicitly downloaded official datasets and user-provided reports. Record the exact publication, period, file URL, retrieval date, unit, revision/provisional markers and relevant footnotes. Do not add automated requests until OJK documents an applicable access method and usage terms.

## KSEI and issuer disclosures

KSEI and issuer investor-relations documents remain source-research targets. No machine-readable KSEI integration, issuer API, terms approval, or data entitlement is verified in this review. Do not invent a provider adapter.

A user can select an issuer report or an official disclosure document for local ingestion when the document was lawfully obtained. The stored source reference must identify the actual document and publication/reporting period. Extracted values remain unverified until they pass explicit validation and cross-checks.

## Approved initial fallback: user-supplied import

The first import path should be a local, explicit user action:
1. The user selects a file through the desktop file picker.
2. RFinance stores the file in its local document area and records its checksum, filename, import timestamp, and user-provided source description.
3. The parser validates schema, dates, currency, units, duplicate rows, numeric precision, and instrument identity.
4. Original source values and normalized values are stored separately, with a transformation/version record.
5. Imported market observations are assigned `UNVERIFIED` by default. An import cannot promote itself to `VERIFIED`.
6. Invalid or ambiguous rows are rejected or quarantined with row-level diagnostics; they are never silently discarded or converted to zero.
7. Offline mode can use cached/imported data while showing acquisition and observation timestamps.

For any source without verified terms, mark automated acquisition and redistribution as not approved. An imported document must not authorize AI or a parser to access additional websites or local files.

## Evidence and outstanding research

This review establishes the integration boundary; it is not a legal opinion and does not approve any particular dataset for redistribution. Before an adapter is activated, add a dated source-specific review covering:
- Exact data product and source owner.
- Official documentation and legal terms URL/version.
- Authentication/entitlement and technical access method.
- Automated access permission, rate limits and fair-use limits.
- Local storage duration and historical/backfill limits.
- Display, non-display, export and redistribution permissions.
- Required attribution and user-visible source metadata.
- Fields, units, adjustment conventions, publication revisions and correction process.
- Adapter contract fixtures captured from permitted sample data.

No IDX, OJK, KSEI, or issuer API integration is enabled by this review.
