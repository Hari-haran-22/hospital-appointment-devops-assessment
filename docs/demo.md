# Four minute hospital appointment DevOps demonstration

Record a single 3–5 minute screen capture with your own narration. Show the browser and a readable PowerShell terminal. Use only synthetic records. Keep the `secrets/` directory, token values, unrelated windows, and notifications off screen.

## Prepare before recording

1. Start Docker Desktop. From the repository root run `docker compose up -d --wait` and `docker compose --profile test build tests`. Confirm `curl.exe -k https://localhost:8443/health/ready` returns `{"status":"ready"}`.
2. Open the [public repository](https://github.com/Hari-haran-22/hospital-appointment-devops-assessment) and its [Actions page](https://github.com/Hari-haran-22/hospital-appointment-devops-assessment/actions) in your browser. Open the latest successful `verify-and-publish` run. Keep the architecture diagram and `evidence/verification.md` available in tabs.
3. Use a large terminal font. Start screen and microphone recording with your preferred recorder, then run `./scripts/demo-video.ps1` in Windows PowerShell or PowerShell 7. The script pauses at each chapter so you can switch windows and narrate. `./scripts/demo-video.ps1 -Auto` performs a dry run without pauses; it deliberately stops and restarts the database and creates a local ignored backup.

## Recording sequence and suggested narration

| Time | On screen | Say in your own words |
| --- | --- | --- |
| 0:00–0:35 | Public repository and `docs/architecture.md` | “This is my DevOps and Cloud Engineering assessment for a doctor appointment API. Caddy is the only exposed service. The app and PostgreSQL communicate on private Compose networks, and the database uses a persistent volume.” |
| 0:35–1:10 | Latest green GitHub Actions run; expand verify and publish jobs | “A push to main starts formatting, linting, PostgreSQL-backed API tests, an image build, and a high or critical vulnerability scan. After those checks pass, the workflow publishes a commit-tagged image and prints its digest.” |
| 1:10–1:50 | Script chapter 2: `docker compose ps`, health, doctor list | “This deployment is local-only, bound to loopback port 8443 with Caddy's internal HTTPS certificate. Liveness confirms the process responds; readiness checks PostgreSQL and the appointment schema. The doctor records are synthetic.” |
| 1:50–2:25 | Script chapter 3: concurrency test output | “Two patient requests attempt the same doctor and half-hour slot simultaneously. The test expects one 201, one 409, and exactly one confirmed row. PostgreSQL's partial unique index enforces that rule even under concurrency.” |
| 2:25–3:20 | Script chapters 4 and 5: JSON logs, stop database, HTTP 503, restart, HTTP 200 | “Request logs include a request ID, path, status, and duration without tokens or bodies. When PostgreSQL stops, readiness becomes 503. After restarting it, readiness returns to 200 and the persistent data remains.” |
| 3:20–4:05 | Script chapter 6: new backup checksum; show `evidence/verification.md` and `docs/runbook.md` | “The backup is a PostgreSQL custom-format dump kept outside the container. The evidence file records a completed restore drill, and the runbook has deploy, restart, log, restore, incident, and rollback steps. Rollback uses an immutable image tag or digest.” |

Finish by showing the GitHub repository URL and the final healthy status. If the recording is shorter than three minutes, explain the secret mounts and non-root application role. If it runs longer than five minutes, trim waiting time between chapters rather than removing evidence.

The project is a focused local MVP: it has fixed synthetic patients and doctors, static demo tokens, and no public cloud endpoint. Say this clearly. The local certificate is not publicly trusted, so use terminal health output instead of a browser certificate warning as the deployment proof.

## After recording

Watch the full export once. Confirm that the CI run is green, the concurrency output shows `201` and `409`, the outage shows `503` then `200`, the backup hash is visible, and no secret value appears. Upload the video, test its link while signed out, and put the link plus the repository, pipeline run, final commit, and image digest into the submission form.
