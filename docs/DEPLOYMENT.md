# Deployment

## Local Docker run

```powershell
docker compose up --build
```

Open `http://127.0.0.1:8000/`. The supplied Compose file is a convenient local
container workflow; it does not add authentication or TLS.

## Before an internet-facing deployment

- Terminate TLS at a trusted reverse proxy.
- Add authenticated users, authorization, and tenant isolation.
- Use PostgreSQL/PostGIS instead of the default SQLite database.
- Use Redis/a worker service for large imports, scheduled refreshes, and queues.
- Put secrets in a secret manager; never in repository files or client code.
- Configure backups, retention periods, monitoring, and an incident process.

## Scaling direction

Keep API requests stateless, store durable jobs/results in PostgreSQL, and move
large imports/enrichment to bounded workers. Horizontal scale is appropriate
only after measurements show that a single instance is insufficient.
