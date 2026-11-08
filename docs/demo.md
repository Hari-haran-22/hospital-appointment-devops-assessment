# Four minute assessment demonstration plan

Record a 3–5 minute screen capture that proves the deployment and recovery path. Use synthetic data only. The reviewer should be able to see the command outputs and URLs without viewing secret values.

| Time | Show | Evidence |
| --- | --- | --- |
| 0:00–0:35 | Repository, architecture, Dockerfile, Compose | Focused service, non-root image, private database, HTTPS proxy |
| 0:35–1:10 | GitHub Actions run and published image | Green checks, scan step, SHA tag and digest |
| 1:10–2:00 | `docker compose ps`, HTTPS health, doctor/slot API | Running deployment and readiness |
| 2:00–2:45 | Concurrent booking test output and audit events | One success, one conflict, one confirmed row |
| 2:45–3:35 | Stop database, show failed health, restart, show recovery | Detection and recovery |
| 3:35–4:15 | Backup checksum, restore drill results, rollback runbook | Recoverability and documented rollback |

For a local-only submission, say clearly that port 8443 is bound to loopback and the certificate is issued by Caddy's local CA. Put the video URL in the submission form after uploading and verify reviewer access. Do not claim that the CI run, registry digest, or video exists until each has actually been produced.
