# 0490: cAdvisor v0.55.1 for Docker 29 (containerd image store)
Status: review
Depends on: none | Base commit: main | Branch: claude/project-thread-gksvyw
Executor: Haiku 5.5 | Fits one session: 10 tool calls, 20k tokens
## 1. Objective
Production runs Docker 29.8.0, which stores images in containerd. cAdvisor v0.52.1 cannot find container layers there and logs about 8 lines a minute like `Failed to create existing container: ... failed to identify the read-write layer ID` (seen 2026-11-01, survives a restart). Upstream fixed this in v0.54.0 ("add containerd-snapshotter support", google/cadvisor#3643). Bump to v0.55.1, pinned by digest. No App/ change, no new dependency (same image, newer tag).
## 2. Context
- `deploy/lightsail/docker-compose.yml` line 320: `image: gcr.io/cadvisor/cadvisor:v0.52.1@sha256:f40e6587...`.
- `README.md` line 76: monitoring versions row `v1.10.1 / v1.9.1 / v0.52.1`.
- v0.55.1 manifest-list digest (read from gcr.io 2026-11-01, has linux/amd64): `sha256:3de2bd5203120b866d74a9b283b2ffb8ec382fbf9dc321814700c6ea6f44ec57`.
- `deploy.sh` runs `docker compose up -d`, which pulls the new image and recreates only cadvisor. App, worker and database are untouched.
## 3. Files
Edit the two lines above. Write `docs/tasks/0490-report.md`.
## 4. Steps
1. Line 320 becomes `image: gcr.io/cadvisor/cadvisor:v0.55.1@sha256:3de2bd5203120b866d74a9b283b2ffb8ec382fbf9dc321814700c6ea6f44ec57`. Keep the `# Pinned by digest.` comment, flags and mounts.
2. README row: `v0.52.1` becomes `v0.55.1`.
## 5. Do not touch
Anything else in compose, Alloy config, the watchdog, App/.
## 6. Commands
- From `deploy/lightsail/`: `docker compose --profile monitoring config -q 2>&1 | tail -5` (if docker is missing, say so in the report).
- From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.
## 7. Acceptance
Compose config parses, lint passes. Owner check after deploy: `cd /opt/ubyhost/deploy/lightsail && sudo docker logs --since 1m ubyhost-cadvisor-1 2>&1 | grep -c '^E'` prints 0.
## 8. Stop and ask
If the digest or tag does not resolve, or compose config fails.
## 9. Report
`docs/tasks/0490-report.md`: diff summary, command tails, owner step.
