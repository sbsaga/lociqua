# Architecture

Lociqua is a modular Python application with separate HTTP, search, persistence,
queue, and operational responsibilities.

| Component | Responsibility |
| --- | --- |
| Dashboard and API | Browser workflow, authenticated API routes, CSV import, search, export, company details, and administration actions. |
| Authentication and roles | Short-lived signed tokens; viewer read access, editor data/review access, owner member administration. |
| Orchestrator | Bounded concurrent searches, cache/single-flight behavior, rate policy, retries, circuit breaking, and structured errors. |
| Provider interface | Local database search today; future adapters must be explicitly authorized and configured. |
| PostgreSQL/PostGIS | Production companies, sources, provenance, reviews, memberships, and audit data. |
| Redis and worker | Durable queued search batches and a separate worker process. |
| Trust controls | Source registry, normalization, field provenance, quality information, explainable duplicate review, and audit events. |
| Operations | Docker Compose, Nginx, health/readiness endpoints, Prometheus-format metrics, JSON logs, backup/restore helpers, and optional webhook alerts. |

The production profile is a single configured workspace. Workspace information
inside a token must match the configured workspace before access is allowed.
Lociqua does not claim multi-tenant hosted isolation or a replacement for an
operator's network, identity, backup, and monitoring responsibilities.

Next: [how it works](HOW_IT_WORKS.md), [API reference](API.md), or
[operations](OPERATIONS.md).
