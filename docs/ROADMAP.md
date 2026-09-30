# Roadmap

## Available now

- Authorized CSV intake, source registry, normalization, provenance, audit
  history, quality information, and controlled CSV export.
- Concurrent multi-location search, Redis-backed queued search jobs, and a
  separate worker for the production profile.
- PostgreSQL/PostGIS persistence, application sign-in, workspace roles,
  review-only duplicate decisions, operational metrics/logs, and backup/restore
  helpers.

## Candidate future work

1. Import-column mapping and spreadsheet support.
2. Permitted open-data ingestion with source-specific attribution and license
   checks.
3. More search filters and a broader duplicate-review workflow.
4. Multi-workspace product design only after isolation, billing, support, and
   operational ownership are fully specified.
5. Expanded observability and performance measurement based on real authorized
   workloads.

No roadmap item authorizes restricted-source scraping, access-control bypass,
CAPTCHA solving, stealth collection, or use beyond a source's license or
contract.

Next: [feature guide](FEATURES.md) or [architecture](ARCHITECTURE.md).
