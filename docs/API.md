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
