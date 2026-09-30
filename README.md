# Lociqua

> Self-hosted business discovery from data you are allowed to use.

![Lociqua: multiple location datasets become an organized business database](assets/lociqua-readme-hero.png)

Lociqua helps teams turn authorized company data into a clean, searchable local
directory. It deliberately contains no Google Maps scraper, browser automation,
stealthing, CAPTCHA handling, or provider-bypass logic.

New here? Start with [What problem Lociqua solves](docs/WHAT_PROBLEM.md), then
follow [Getting started](docs/GETTING_STARTED.md). See [Documentation](#documentation)
for architecture, data rights, and security guidance.

## Verified starting point

The supplied repository was empty: no `scripts/`, source files, license, scraper
engine, dependencies, or external endpoint configuration existed. Consequently,
there was no legacy request flow or performance baseline to measure, no local
scraper to optimize, and no backward-compatible CLI to preserve. Any claim about
a `localhost:8080` service or its geocoding/polling/enrichment behavior would be
an assumption, so none is made.

## Architecture

`API / CLI -> SearchOrchestrator -> bounded task workers -> provider adapters -> normalization -> cautious deduplication -> result response`

The orchestrator has a process-local TTL cache and single-flight map, a global
worker semaphore, provider-specific semaphore/rate gate, retry with jitter and
`Retry-After`, plus a CLOSED/OPEN/HALF_OPEN circuit breaker. Independent queries
run concurrently and `stream()` yields task results as they complete. A failed
task becomes a structured task error; it does not fail its batch.

`BusinessDiscoveryProvider` is the stable adapter contract. `LocalDatabaseProvider`
searches the included durable SQLite store, populated from customer-owned CSV
data. `FixtureProvider` remains only for deterministic tests and benchmarks.
Add only official, licensed, or expressly authorized adapters. Put
credentials in deployment secrets, enforce each provider's terms and quotas, and
do not enable caching where provider terms disallow it.

## Quick start

Requires Python 3.11+; runtime dependencies are standard library only.

```powershell
python -m pip install -e .
search-businesses import-csv examples/companies.csv
search-businesses search --keyword "AI" --location "Baner"
python -m unittest discover -s tests -v
python -m benchmarks.synthetic
```

## Documentation

- [What problem Lociqua solves](docs/WHAT_PROBLEM.md) — plain-language purpose and examples.
- [Getting started](docs/GETTING_STARTED.md) — first import and multi-location search.
- [How it works](docs/HOW_IT_WORKS.md) — request flow and why tabs load independently.
- [Data sources and rights](docs/DATA_RIGHTS.md) — what is allowed and what is not.
- [Architecture](docs/ARCHITECTURE.md) — components, limits, and extension points.
- [API reference](docs/API.md) — supported local endpoints and examples.
- [Deployment](docs/DEPLOYMENT.md) — Docker and production hardening direction.
- [Roadmap](docs/ROADMAP.md) — shipped scope and next milestones.
- [Security](SECURITY.md) — reporting and safe deployment expectations.
- [Contributing](CONTRIBUTING.md) — how to propose changes.
- [Release checklist](docs/RELEASE_CHECKLIST.md) — checks before publishing.

Import a UTF-8 CSV containing a `name` column through `POST /api/import/csv`; a
sample is at `examples/companies.csv`. Then use this payload for `POST /api/search`:

```json
{"queries":[{"keyword":"dentists","location":"Kothrud","provider_preference":["local_database"]}]}
```

Run the reference API with `python -c "from business_discovery.api import serve; serve()"`.
It exposes `POST /api/import/csv`, `POST /api/search`, and `GET /api/providers`. The reference server is
for a trusted deployment boundary; production must add TLS, authentication,
tenant/request rate limits, durable storage, and a real authorized provider.

Open `http://127.0.0.1:8000/` after starting the server for the included
local-first dashboard. It imports CSV records and searches the local database;
it makes no calls to third-party APIs or analytics services.

Enter one locality per line in the multi-location form. Each locality launches
an independent bounded search and receives its own result tab, with the chosen
maximum number of matching imported records.

## Configuration and deployment

Copy `.env.example` into environment-specific secret/configuration management.
Its limits define batch size, result count, total/provider concurrency, provider
rate, timeout policy, retry attempts, cache TTL, and enrichment policy. The core
currently reads constructor configuration, making configuration loading explicit
for an integrating service. For one-server deployment, run API and workers in one
process. At higher scale, replace the in-memory cache/single-flight state with
Redis and durable requests/tasks/results with a relational DB; workers remain
stateless and scale horizontally. Do not introduce distributed components until
that workload requires them.

## Data quality, enrichment, and security

Records retain provider provenance; canonical identity preference is source ID,
then canonical domain, phone, then normalized name plus locality. Fuzzy matching
is intentionally absent. Missing fields remain null. Enrichment is intentionally
not implemented: it must be a separate authorized stage. `validate_public_url`
rejects non-HTTP(S), credentialed, loopback, private, link-local, and reserved
resolved targets; an enrichment adapter must additionally enforce robots/terms,
redirect count, content type, response size, DNS-rebinding-aware validation, and
timeouts.

Inputs are bounded and validated; API payloads are capped at 1 MB. Never log
credentials or request headers. Use parameterized queries in any added store,
safe CSV writer settings for spreadsheet formula injection, pagination, and
authentication before exposing the service publicly.

## Tests and benchmark

Unit tests use no live provider. `python -m benchmarks.synthetic` is reproducible and
reports actual local timing for 1/3/10/50/100 deterministic fixture tasks. It is
not a live-provider benchmark and cannot quantify provider latency, CPU/memory,
or network calls. There is no pre-change benchmark because no prior executable
implementation existed. Before production, instrument provider latency, cache
hits, retry/circuit events, queue depth, p50/p95/p99, task throughput, memory,
and time-to-first/final result against authorized realistic workloads.

## Licensing and migration

The software is Apache-2.0; see `LICENSE` and `THIRD_PARTY_NOTICES.md`. This
license does not grant data collection, retention, or redistribution rights.
Because there is no legacy code to migrate, install this alongside any external
client and implement a `BusinessDiscoveryProvider` adapter only if that service
is authorized and its source/contract is known. Keep the legacy client separate
until side-by-side output, latency, and compliance validation is complete.

## Known limitations

This initial modular monolith has SQLite persistence for imported data but no
durable background jobs, distributed queue, SSE endpoint, geocoder adapter,
authentication, spreadsheet (.xlsx) importer, or self-hosted OpenStreetMap
importer. Those are deliberate next integration points, not claimed features.
The built-in fixture only demonstrates the contract and must not be represented
as business data.
