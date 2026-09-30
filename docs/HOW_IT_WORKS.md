# How Lociqua works

```text
Authorized CSV data → validation → normalization → local database
                                                     ↓
Multi-location search → bounded async tasks → one result tab per location
```

Each locality is an independent search task. The browser starts those tasks at
the same time, so a fast locality can show results without waiting for a slower
one. The service limits concurrent work, caches equivalent requests briefly, and
coalesces identical in-flight requests to avoid unnecessary duplicate work.

The current local database provider uses SQLite, which is appropriate for a
single-machine demo or small team. Larger deployments should use PostgreSQL,
PostGIS, a worker queue, and a distributed cache.
