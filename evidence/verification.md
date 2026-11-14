# Local verification record

The local results below were observed on 8 November 2026 in Docker Desktop. The GitHub pipeline evidence was produced after the repository was published. A 3–5 minute demo video still needs to be recorded and linked in the submission form.

## GitHub pipeline and published image

The [verify and publish run](https://github.com/Hari-haran-22/hospital-appointment-devops-assessment/actions/runs/42524057659) completed successfully for commit `65974ff6c01d6c9860138840cefd7591fc2aba46`. Its verify job ran formatting, lint, PostgreSQL-backed API tests, an image build, and a high/critical vulnerability scan. Its publish job pushed the versioned image to GitHub Container Registry.

```text
Image tag: ghcr.io/hari-haran-22/hospital-appointment-devops-assessment:sha-65974ff6c01d6c9860138840cefd7591fc2aba46
Digest:    sha256:87edc5ad0aa514140e3a1df417faac23ec5e4d761a96388bf48e8586a76b651f
```

## Clean build and API rule

An isolated Compose project initialized a fresh PostgreSQL volume, created the application and test databases, and ran the test image. The same checks were then repeated against the separate test database in the main project. The test fixture refuses to run if `DATABASE_NAME` is not `appointments_test`.

```text
ruff format --check .      5 files already formatted
ruff check .               All checks passed!
pytest -q                  4 passed, 1 third-party deprecation warning
```

The concurrent booking test sent two patient requests for the same doctor and slot. It observed one HTTP 201, one HTTP 409, and exactly one confirmed database row. Other tests covered role and ownership checks, invalid references and time windows, rescheduling, cancellation, slot reuse, and audit events. The local deployment database is isolated from test cleanup.

## Deployment and security

`docker compose up --build -d --wait` started the database, app, and HTTPS proxy. The app and database ports were not published to the host; Caddy bound `127.0.0.1:8443`. HTTPS `/health/live` and `/health/ready` both returned HTTP 200. The app container reported `uid=10001(app) gid=10001(app)`.

The final local runtime image is `hospital-appointments:local`, image ID `sha256:9531786accd77e73c0b910d472bddca5e36f55c8f6432a8f1807af2ab718ceb2`. This is a local image ID, not a registry digest. The final base is pinned to `python:3.12-alpine@sha256:e064671ca452259bab50e8e2c7bd896e39e9a343bb06ca25234adf6fe18d0fc7`.

Trivy 0.76.2 scanned the final local image on 8 November 2026 using high and critical severity filters:

```text
Alpine OS packages: 0 HIGH/CRITICAL
Python packages:    0 HIGH/CRITICAL
```

The scan result is time-specific; CI repeats it for each build and blocks publication if high or critical findings are reported.

## Backup, restore, and failure recovery

The final Alpine deployment ran `scripts/verify-recovery.ps1` successfully. A synthetic appointment was created, backed up, cancelled, then restored. The appointment returned to `confirmed` and readiness was HTTP 200. Stopping PostgreSQL changed readiness to HTTP 503; restarting it returned readiness to HTTP 200.

```text
CREATE   status=confirmed id=c079d1a2-a805-4db3-ab66-be6dcfdaf983
BACKUP   backups/appointments-20261108-173518.dump
SHA-256  123DE6610E60869281CE4F2DB06A920C214A7E4D3B60395841215B5031DD971E
MUTATION status=cancelled
RESTORE  status=confirmed health=200
FAILURE  readiness_http=503
RECOVERY readiness_http=200
```

The backup dump is kept locally under ignored `backups/` and is excluded from the repository. The runbook describes how a reviewer can repeat the drill and verify the counts.

## Video rehearsal on 14 November 2026

The guided `scripts/demo-video.ps1 -Auto` run completed on the local deployment. It showed two simultaneous requests returning HTTP 201 and 409, exactly one confirmed database row, JSON request logs, readiness changing to HTTP 503 during a PostgreSQL outage, and recovery to HTTP 200. It created `backups/demo-20261114-182259.dump` with SHA-256 `F5D199C184629D90BD0B5BACE7A19CCC27FB0C151680F49C29A32DF8A311B0A4`. Final readiness was HTTP 200. This is rehearsal evidence; the required narrated video has not yet been recorded.

The 14 November CI scan detected a fixable high-severity issue in the pinned Alpine base image's `krb5-libs` package. The Dockerfile now upgrades it to `1.22.3-r0`. A fresh local Trivy scan of the rebuilt image reported zero high or critical OS and Python package findings, and all four API tests passed. The rebuilt local service returned HTTP 200 from readiness.
