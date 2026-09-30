# API reference

The reference server binds to `127.0.0.1` by default. Its API is intended for a
trusted local environment, not public internet use without TLS and authentication.

| Endpoint | Purpose |
| --- | --- |
| `POST /api/import/csv/preview` | Validate headers and return five non-persisted sample rows. |
| `POST /api/import/csv` | Import a bounded UTF-8 CSV into the local store. |
| `POST /api/search` | Search one or more authorized-provider queries. |
| `GET /api/companies/export` | Download search results as CSV. |
| `GET/POST /api/saved-searches` | List or save local searches. |
| `GET /api/providers` | List configured providers. |
| `GET/POST /api/sources` | List or register authorized data-source metadata. |
| `GET /api/companies/{id}` | Return a company, quality score, field provenance, and audit events. |
| `GET /api/companies?quality=low` | List low-quality records for review (PostgreSQL deployment). |
| `GET /api/duplicates?status=pending` | List scoped, explainable duplicate review candidates. |
| `POST /api/duplicates/{id}` | Editor/owner approves or rejects a duplicate review; never merges records. |
| `GET/POST /api/members` | Owner-only member list and user creation for the configured workspace. |
| `POST /api/members/{user_id}` | Owner-only role change or access revocation; protects the last owner. |

When `LOCIQUA_REQUIRE_AUTH=true`, every `/api/` route except login requires a
short-lived bearer token. Viewers are read-only, editors can manage data and
duplicate decisions, and owners can additionally manage workspace access.

## Search example

```json
{"queries":[
  {"keyword":"AI","location":"Baner","max_results":5,
   "provider_preference":["local_database"]},
  {"keyword":"AI","location":"Hinjewadi","max_results":5,
   "provider_preference":["local_database"]}
]}
```

The response includes task counts, de-duplicated results, provenance, errors,
and measured duration. Treat API responses as customer data: do not expose them
without access control.

See the [user guide](USER_GUIDE.md) for browser workflows and
[security and data rights](SECURITY_AND_DATA_RIGHTS.md) for operator obligations.
