# Hospital appointment deployment assessment

This repository delivers the doctor appointment API requested in the ALGIONS AI LABS PRIVATE LIMITED DevOps and Cloud Engineering assessment. It is intentionally small: the focus is a reproducible build, safe concurrent booking, a private database, HTTPS ingress, CI, recovery, and evidence. All patients and doctors are synthetic.

**Assigned project:** Cloud Deployment & CI/CD – Hospital Management Platform.

## What runs

| Component | Purpose | Host exposure |
| --- | --- | --- |
| Caddy | HTTPS reverse proxy with a local internal certificate | `127.0.0.1:8443` |
| FastAPI | Doctor catalog, slots, appointments, health, audit API | None |
| PostgreSQL | Persistent appointment and audit data | None |

See [architecture](docs/architecture.md), [operations runbook](docs/runbook.md), and [demo plan](docs/demo.md). Docker Compose creates a private database network. The app runs as UID 10001 with a read-only filesystem, dropped Linux capabilities, and no published port. PostgreSQL uses a dedicated non-superuser application role. Secret files live in ignored `secrets/`; `.env` contains only nonsecret settings.

## Requirements and clean start

- Docker Engine or Docker Desktop with Compose v2 or later.
- PowerShell 7 for the Windows helper, or a POSIX shell and OpenSSL for the Unix helper.
- Free host port 8443.

From the repository root:

```powershell
./scripts/setup-local.ps1
docker compose up --build -d --wait
curl.exe -k https://localhost:8443/health/live
curl.exe -k https://localhost:8443/health/ready
docker compose ps
```

On Linux/macOS, run `sh scripts/setup-local.sh` in place of the PowerShell command. `-k` accepts Caddy's local development certificate. For a public hostname, replace `localhost` in `infra/Caddyfile` with the hostname and publish ports 80/443 in Compose; Caddy can then obtain a trusted certificate. Do not expose this synthetic demo without reviewing token management, rate limits, and backup retention.

The setup script creates five cryptographically random, local-only secrets and a nonsecret `.env`. It preserves existing files. The database schema and seed records are installed only when the PostgreSQL volume is first created. Do not use `docker compose down -v` on data you need to keep.

## API workflow

The API uses bearer tokens stored in `secrets/patient_one_token`, `secrets/patient_two_token`, and `secrets/staff_token`. Patient tokens are scoped to P001 and P002. Staff can operate on either synthetic patient and read audit events. Doctor and slot listings are public. OpenAPI documentation is at `https://localhost:8443/docs`.

PowerShell example:

```powershell
$token = Get-Content -Raw ./secrets/patient_one_token
$token = $token.Trim()
$date = (Get-Date).AddDays(1)
while ($date.DayOfWeek -in @('Saturday','Sunday')) { $date = $date.AddDays(1) }
$start = '{0}T09:00:00+05:30' -f $date.ToString('yyyy-MM-dd')
$body = @{ patient_id='P001'; doctor_id='D001'; start_at=$start } | ConvertTo-Json
Invoke-RestMethod -Uri 'https://localhost:8443/v1/appointments' -Method Post `
  -SkipCertificateCheck -Headers @{ Authorization = "Bearer $token" } `
  -ContentType 'application/json' -Body $body
```

The booking endpoint returns `201` for success and `409` when the confirmed slot is taken. PostgreSQL's partial unique index protects that rule even when requests arrive concurrently. A cancelled booking releases the slot. Appointment times must carry a UTC offset, fall on a weekday from 09:00 to 16:30 in Asia/Kolkata, align to a 30-minute boundary, and be within the next 30 days. The API provides:

| Method | Path | Access |
| --- | --- | --- |
| GET | `/health/live`, `/health/ready` | Public |
| GET | `/v1/doctors` | Public |
| GET | `/v1/doctors/{id}/slots?date=YYYY-MM-DD` | Public |
| POST | `/v1/appointments` | Patient owner or staff |
| GET | `/v1/appointments/{id}` | Patient owner or staff |
| PATCH | `/v1/appointments/{id}` | Patient owner or staff |
| POST | `/v1/appointments/{id}/cancel` | Patient owner or staff |
| GET | `/v1/audit-events` | Staff only |

## Checks and release

```powershell
docker compose --profile test run --build --rm tests sh -c 'ruff format --check . && ruff check . && pytest -q'
docker compose build app
docker image inspect hospital-appointments:local --format '{{.Id}}'
```

The [GitHub Actions workflow](.github/workflows/ci.yml) runs formatting, linting, database-backed API tests, and an image build on pull requests and pushes. A Trivy scan blocks publication if it finds high or critical vulnerabilities. A successful push to `main` publishes `ghcr.io/<owner>/<repo>:sha-<commit>` and `:main`; the build step prints the immutable registry digest. The immutable SHA tag or digest should be used for deployment and rollback. CI uses disposable generated secrets and GitHub's scoped `GITHUB_TOKEN` for the package registry.

## Configuration

| Setting | Default | Meaning |
| --- | --- | --- |
| `APP_VERSION` | `local` | Image tag and health version |
| `HTTPS_PORT` | `8443` | Loopback HTTPS port |
| `HOST_GID` | `10001` | Group allowed to read app secret files on Linux |
| `DATABASE_HOST` | `db` | Internal PostgreSQL hostname |
| `DATABASE_NAME` | `appointments` | Database name |
| `DATABASE_USER` | `appointment_app` | Least-privilege application role |
| `DATABASE_PASSWORD_FILE` | mounted secret | Application database password |
| `PATIENT_ONE_TOKEN_FILE`, `PATIENT_TWO_TOKEN_FILE`, `STAFF_TOKEN_FILE` | mounted secrets | Demo bearer tokens |

The role and schema are initialized by `infra/init-db.sh` and `infra/schema.sql`. Tests use a separate `appointments_test` database, so their cleanup fixture never touches the live demo database. On Linux, `secrets/` is owner-only on the host; the mounted app password is readable by the database initializer and app, while patient and staff tokens are readable by the app's host group. CI sets the matching host group ID automatically. App containers receive no PostgreSQL administrator password. Changing the secret file after first database initialization does not rotate the PostgreSQL role; perform a coordinated password rotation in PostgreSQL before updating that file.

## Operations and recovery

The [runbook](docs/runbook.md) contains restart, logs, failure diagnosis, backup/restore, rollback, and verification commands. At minimum:

```powershell
docker compose ps
docker compose logs --tail=100 app db proxy
docker compose restart app
```

Backups use PostgreSQL's custom format and are copied outside the container. Restore is a deliberate maintenance operation: stop the app, restore into PostgreSQL, restart, and verify the booking and audit counts. The runbook includes exact commands and cautions.

## Assessment evidence and limits

`evidence/verification.md` records local command results. Add the GitHub Actions run URL, published image digest, demo video link, final commit ID, and (if private) reviewer access to the submission form after publishing. The [demo plan](docs/demo.md) fits the required 3–5 minutes. The submission deadline is determined by the individualized invitation, which is not present in this repository.

This MVP has two synthetic patients and two doctors, a fixed weekday schedule, static local tokens, and one app instance in Compose. It does not include patient registration, real patient data, notifications, rate limiting, externally trusted TLS for a public hostname, or automated production deployment. Token rotation, schema migrations after initial deployment, and off-host backup retention would need a production process.

## AI use and attribution

The implementation was developed with AI coding assistance for architecture, code, tests, and documentation. The candidate should review and be able to explain every component before submitting. Synthetic names and records are invented for this assessment. The service uses FastAPI, Uvicorn, Psycopg, PostgreSQL, Caddy, Ruff, Pytest, Docker, and Trivy under their respective open-source licenses.
