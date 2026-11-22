# Data Source Policy

## Preferred source order

1. Official, documented APIs.
2. Official downloadable datasets.
3. Licensed providers whose terms permit the intended use.
4. Listed-company investor-relations documents.
5. Other public sources only after legal/technical access review.
6. User-provided source files through an explicit import flow.

## Indonesia research targets

IDX, OJK, KSEI, and individual issuer investor-relations sites are research targets, not pre-approved adapters. Each source requires a documented review of terms, license, authentication, rate limits, retention, redistribution rights, permitted automation, and data fields before automated ingestion is enabled.

Public visibility alone does not grant permission to crawl, scrape, cache indefinitely, or redistribute data. Never bypass login, CAPTCHA, paywalls, anti-bot systems, or access controls.

## Provenance requirements

Store source identity, URL/document reference, acquisition timestamp, observation timestamp, reporting period, currency, unit, original value, normalized value, transformation version, data quality, and verification status where applicable.

## Fallback behavior

When no permitted machine-readable source exists, use user import or manual entry with UNVERIFIED status until independently validated. A provider outage must preserve last-known cache with a visible STALE state; stale values cannot silently qualify recommendations.
