# Hospital appointment operations runbook

This runbook is for the local Docker Compose deployment. Run commands from the repository root. The first setup is in the README. The service is healthy when `docker compose ps` shows all three long-running services healthy and the proxied readiness endpoint returns HTTP 200.

## Deploy and verify

```powershell
./scripts/setup-local.ps1
docker compose up --build -d --wait
docker compose ps
curl.exe -k -i https://localhost:8443/health/live
curl.exe -k -i https://localhost:8443/health/ready
docker compose logs --tail=50 app
```

The backend port is 8000 inside the Compose edge network, PostgreSQL listens only on the private backend network, and 8443 is bound to host loopback. Caddy uses a local internal CA, so `curl.exe -k` is appropriate only for this local demonstration.

## Diagnose and recover

| Symptom | Check | Action |
| --- | --- | --- |
| HTTPS request fails | `docker compose ps` and `docker compose logs proxy` | Restart proxy after app is healthy |
| HTTP 503 readiness | `docker compose ps db` and `docker compose logs db` | Restore database service; inspect volume and credentials |
| App exits on startup | `docker compose logs app` | Confirm secret files exist and are at least 32 characters |
| Booking returns 409 | Check slot listing and audit events | Choose a free slot; conflict is expected |
| Unexpected 401/403 | Confirm token role and patient ID | Use correct synthetic token; never paste tokens into logs or tickets |

```powershell
docker compose logs --tail=100 app db proxy
docker compose restart app
curl.exe -k -i https://localhost:8443/health/ready
```

For a recovery demonstration, run `docker compose stop db`, observe `docker compose ps` and a failing readiness check, then run `docker compose start db` and wait for readiness. The proxy may serve HTTP 502 while the app is unavailable; use `docker compose ps` to distinguish that from a database failure. Record timestamps, status codes, and the final healthy state. A restart does not delete the named PostgreSQL volume.

## Backup

Run the following PowerShell commands. They create a timestamped PostgreSQL custom-format dump on the host and print a SHA-256 checksum. Do not commit the dump; it may contain data even though this assessment uses synthetic records.

```powershell
New-Item -ItemType Directory -Force ./backups | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$file = "backups/appointments-$stamp.dump"
docker compose exec -T db pg_dump -U postgres -d appointments -Fc -f /tmp/appointments.dump
docker compose cp db:/tmp/appointments.dump $file
docker compose exec -T db rm -f /tmp/appointments.dump
Get-FileHash $file -Algorithm SHA256
```

Add `backups/` to `.gitignore` before storing local dumps. Keep a separate, access-controlled off-host copy for any real deployment. Verify a backup by restoring it to a disposable environment and checking appointment and audit counts.

## Restore

The following procedure replaces the current database state with the selected dump. Make a fresh backup first. Use a local file path that you have reviewed. Keep the app stopped while restoring so clients cannot write. The database must be healthy.

```powershell
$file = 'backups/appointments-YYYYMMDD-HHMMSS.dump'
docker compose stop app proxy
docker compose cp $file db:/tmp/restore.dump
docker compose exec -T db pg_restore -U postgres -d appointments --clean --if-exists /tmp/restore.dump
docker compose exec -T db rm -f /tmp/restore.dump
docker compose start app proxy
docker compose ps
curl.exe -k -i https://localhost:8443/health/ready
docker compose exec -T db psql -U postgres -d appointments -c 'SELECT count(*) FROM appointments;'
docker compose exec -T db psql -U postgres -d appointments -c 'SELECT count(*) FROM audit_events;'
```

If restore fails, leave the app stopped, inspect `pg_restore` output, and restore the fresh pre-restore backup. The database password files are outside the dump. Do not run `docker compose down -v` during recovery.

## Rollback

Use an immutable image tag or digest recorded in the successful pipeline, not the moving `main` tag. For a local rollback, set `APP_VERSION` in `.env` to the previous SHA tag, pull or load that image, and run `docker compose up -d --no-build app proxy`. Check health, logs, and a read-only API route. The Compose file includes a build context, so `--no-build` is essential when selecting a previously built image. Database schema compatibility must be checked before an application rollback; this MVP has one initial schema version and no later migrations.

```powershell
docker compose config --images
docker compose up -d --no-build app proxy
curl.exe -k -i https://localhost:8443/health/ready
docker compose logs --tail=50 app
```

For a registry release, pull the digest or `sha-<commit>` image and tag it locally as `hospital-appointments:<APP_VERSION>` before the `up` command. Keep the former immutable tag until verification passes. The pipeline digest, commit, test result, and deployment time belong in the release record.

## Incident notes

Record the first failing timestamp, request ID, affected endpoint, `docker compose ps`, relevant container logs, action taken, and recovery timestamp. Do not record bearer tokens, secret file contents, or actual patient information. This demo uses only synthetic patient records.
