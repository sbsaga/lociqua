# Production verification

Run these checks only against an environment you control. Never place database passwords or bearer tokens in source control.

1. Copy `.env.example` to `.env` and replace every example secret.
2. Run `docker compose -f docker-compose.production.yml up --build -d`.
3. Run `python tests/production_smoke.py` and `python tests/security_smoke.py`.
4. With a disposable test account token in `LOCIQUA_TEST_TOKEN`, run `python tests/load_smoke.py` for `search`, then set `LOCIQUA_LOAD_MODE=import` and `job` for the write/queue checks.
5. Run `tests/backup_restore_test.ps1` and each selected component in `tests/recovery_smoke.ps1` during a maintenance window.
6. Run `docker compose -f docker-compose.production.yml ps`; every required service must be healthy or running.

## Backup and restore

Create a backup with `./infra/postgres/backup.ps1 -Destination ./backups/lociqua.dump`. The supplied restore helper defaults to the separate `lociqua_restore_test` database and refuses to overwrite `lociqua` unless explicitly confirmed. A backup is not verified until a restore succeeds and a sample search returns expected data.

## TLS

`infra/nginx/tls.conf.template` is ready for a domain and valid certificate. Do not enable it until DNS, certificate issuance, renewal, and HTTPS health checks are under your control.

## Release gate

Do not claim production readiness until smoke, authorization, background-job, backup-restore, load, and security tests have passed in the target environment.

Return to the [documentation index](README.md) for deployment and operations guidance.
