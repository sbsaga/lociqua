# Lociqua operations runbook

This runbook is for the PostgreSQL/Redis production Compose deployment. It does
not make a laptop or a public tunnel highly available; use a managed host,
off-host backups, and an incident owner before relying on it for critical work.

## Startup and deployment

1. Keep a private `.env` beside `docker-compose.production.yml`. It must contain
   unique `POSTGRES_PASSWORD`, `LOCIQUA_AUTH_SECRET`, bootstrap email/password,
   and optionally `LOCIQUA_ALERT_WEBHOOK_URL`.
2. Confirm `.env`, `*.db`, `backups/`, and tunnel credentials are ignored by Git.
3. Start only from the repository directory:

   ```powershell
   docker compose -f docker-compose.production.yml up --build -d --remove-orphans
   docker compose -f docker-compose.production.yml ps
   Invoke-WebRequest http://127.0.0.1/healthz
   Invoke-WebRequest http://127.0.0.1/readyz
   ```

4. Put the Nginx port behind Cloudflare Tunnel. Protect the public hostname with
   Cloudflare Access and an allow policy before sharing it. Cloudflare provides
   public HTTPS; it does not replace application users/roles or backups.
5. Roll forward with a fresh image after backing up the database. Roll back only
   to the previously verified image after confirming database migrations are
   compatible. Never roll back a destructive migration without a tested restore.

## Health, logs, and alerts

`/healthz` means the HTTP process is alive. `/readyz` additionally confirms its
database path. `/metrics` exposes Prometheus-format process and HTTP counters.
Use Docker health status, structured JSON logs, Postgres/Redis metrics, and
Cloudflare availability monitoring as the source of truth.

Set `LOCIQUA_ALERT_WEBHOOK_URL` only to an operator-controlled HTTPS endpoint.
It emits throttled JSON alerts for HTTP 5xx responses and failed worker jobs.
Configure infrastructure monitoring separately for failed health probes, worker
restarts, Redis queue depth, Postgres errors, disk space, and failed backups.
The webhook is intentionally disabled when the variable is blank and it must
never contain credentials in the URL.

For an incident, preserve container logs and relevant audit events, limit access
through Cloudflare Access if needed, identify the affected workspace records,
and record the recovery decision. Do not send company data or tokens to an alert
endpoint.

## Backup and restore

Create a versioned custom-format backup:

```powershell
.\infra\postgres\backup.ps1 -Destination .\backups\lociqua-$(Get-Date -Format yyyyMMdd-HHmmss).dump
```

Run the restore drill regularly. It restores only to `lociqua_restore_test` by
default and verifies the company table is queryable:

```powershell
.\tests\backup_restore_test.ps1 -BackupDirectory .\backups
```

Keep encrypted copies off the host and test recovery before depending on any
backup. `restore.ps1` refuses the live `lociqua` database unless an operator
explicitly supplies `-AllowActiveDatabaseOverwrite`; that action requires an
approved maintenance window and a verified rollback backup.

## Recovery checks

During a maintenance window, test one component at a time:

```powershell
.\tests\recovery_smoke.ps1 -Service app
.\tests\recovery_smoke.ps1 -Service worker
.\tests\recovery_smoke.ps1 -Service redis
.\tests\recovery_smoke.ps1 -Service postgres
```

After each test, check `docker compose ... ps`, `/readyz`, an authenticated
search, and queued-job completion. Redis queue entries have a finite retention
period; investigate work that was running when a worker was terminated.

## Verification and release gate

From a clean disposable Compose volume, run unit tests, `tests/production_smoke.py`,
`tests/security_smoke.py`, `tests/load_smoke.py`, the backup/restore drill, and
the four recovery checks. Verify import, search, export, duplicate review,
quality details, role denial, Cloudflare Tunnel, HTTPS, Cloudflare Access OTP,
Lociqua sign-in, and alert delivery (when configured).

Rotate every password, token, webhook URL, Cloudflare tunnel token, and
`LOCIQUA_AUTH_SECRET` that was exposed in chat, logs, screenshots, source
control, or a shared terminal. Recreate `.env`, restart the stack, invalidate
old browser sessions, and re-run the smoke checks. Do not commit or paste the
new values.

Return to the [documentation index](README.md) for product and user guidance.
