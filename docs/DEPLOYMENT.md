# Deployment notes

Use `docker-compose.production.yml` for the operational profile. It starts the
application, worker, PostgreSQL/PostGIS, Redis, and Nginx reverse proxy.

```powershell
docker compose -f docker-compose.production.yml up --build -d --remove-orphans
docker compose -f docker-compose.production.yml ps
```

The production profile requires a private `.env` with unique database,
application, and bootstrap-user secrets. It enables application authentication;
the local development Compose file is not a substitute for a public deployment.

For public access, provide HTTPS, a network boundary, and external identity
policy. Cloudflare Tunnel with Cloudflare Access is one operator-managed option,
but it is not a replacement for Lociqua roles, backups, source permissions, or
incident response.

Before release, follow [production testing](PRODUCTION_TESTING.md),
[operations](OPERATIONS.md), and the [release checklist](RELEASE_CHECKLIST.md).
