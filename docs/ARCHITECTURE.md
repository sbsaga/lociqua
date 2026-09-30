# Architecture

Lociqua is a modular Python application.

| Component | Purpose |
| --- | --- |
| Dashboard | Imports CSV files and shows location-specific results. |
| API | Provides local HTTP endpoints for import and search. |
| Importer | Validates bounded UTF-8 CSV input. |
| Store | Persists companies and source records in SQLite. |
| Provider interface | Lets the core search local data or future authorized providers. |
| Orchestrator | Applies bounded concurrency, retries, cache, coalescing, and failure isolation. |
| Normalizer | Canonicalizes fields and removes cautious duplicates. |

The default provider is `LocalDatabaseProvider`. It does not make remote network
requests. Future providers must declare their terms, limits, timeouts, cache
rules, and security requirements before being enabled.
