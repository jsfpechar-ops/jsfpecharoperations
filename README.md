# UbyHost

UbyHost automates the Czech Foreign Police (Policie ČR) guest-registration
reporting for short-term rental hosts: it reads booking calendars, collects
guest data, and files the reports through the UbyPort web service.

> Scope note: this README is the entry point. Depth lives in [`docs/`](docs/).
> Items marked `⚠️ UNKNOWN` could not be established from the repository; see
> [`docs/gap-report.md`](docs/gap-report.md).

## Key facts

- **Stack:** Python 3.12, FastAPI + Jinja2, SQLite (WAL), APScheduler, reportlab. Full list: [Tech stack](#tech-stack).
- **Production:** AWS Lightsail, Docker Compose, Caddy, Cloudflare in front, `ubyhost.com` ([`docs/LIGHTSAIL.md`](docs/LIGHTSAIL.md)).
- **Staging:** Render `ubyhost-staging`, mock UbyPort, ephemeral disk ([`render.yaml`](render.yaml), [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)).
- **Version:** `/healthz` reports `1.1.0` per [`docs/context/status.md`](docs/context/status.md); the code version source is `⚠️ UNKNOWN` (no version constant located in this pass).
- **Migration status:** the database is still SQLite. A Postgres move is planned and explicitly deferred (commit `84763c6b`, "defer production migration"). No Go code exists in the repo.

## Architecture (summary)

One Docker image (`Dockerfile`, `python:3.12-slim`, pinned by digest) runs as
three roles selected by `UBYHOST_ROLE`: `web` (uvicorn, 2–4 workers, no
scheduler), `worker` (`python -m app.worker`, runs all background jobs), and
`all` (local development only). Both share one SQLite file on a Docker volume,
replicated to S3 by Litestream. Background jobs (APScheduler) fill the mail
outbox, poll iCal feeds, and submit to UbyPort. Details and diagram:
[`docs/architecture.md`](docs/architecture.md).

## Quickstart (local)

Run from the repo root unless noted. **Executed on this commit in a scratch worktree** (2026-10-31): steps 2, 3, 4, 6 and 7 ran, and step 5 ran through the UI route. Local `run.sh` and the worker both start and stop cleanly. Steps 1 and 8 are from code reading.

1. Clone: `git clone https://github.com/jsfpechar-ops/jsfpecharoperations.git && cd jsfpecharoperations`
2. Create the environment: `cd App && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt`. `requirements-dev.txt` holds only test-time packages (`App/requirements-dev.txt`: pytest, httpx, pdfplumber); runtime deps are in `requirements.txt`. CI installs the hashed `requirements.lock` instead (`.github/workflows/ci.yml`); whether to do the same locally is `⚠️ UNKNOWN`.
3. Configure: copy [`.env.example`](.env.example) to `App/.env` (or export the variables). Local defaults are safe: `UBYHOST_UBYPORT_ENV=mock`, `UBYHOST_DEPLOYMENT=local`, `UBYHOST_MAIL_BACKEND=disabled`.
4. Migrate: migrations run automatically at start-up under a file lock (`App/app/db.py:1098`, `:1236`). There is no separate migrate command — `⚠️ UNKNOWN` whether one exists outside `db.py`.
5. Seed (optional demo data). There is no command. Sign in, then trigger the demo action, which is `POST /demo` (`App/app/routes/onboarding.py:22`). It seeds only when `UBYHOST_DEPLOYMENT=staging` (`App/app/demo.py:543`; otherwise the route shows `flash.error.demo_staging_only`). Verified: 2 apartments, 18 reservations and 8 guests were created. The request needs the page's `csrf-token` meta value sent as the `x-csrf-token` header.
6. Run the app (web + scheduler in one process): `cd App && ./run.sh` (sets `UBYHOST_ROLE=all`, `App/run.sh:31-40`). Verified: `/healthz` returns 200 on `PORT` (default 8080) and the mock UbyPort starts on 8081. `PUBLIC_BASE_URL` must match the port you use. Demo calendar feeds are built from it (`App/app/demo.py:147-156`), so a mismatch makes the feed fetch fail. For local sign-in without e-mail, set `UBYHOST_DEPLOYMENT=staging` and `UBYHOST_STAGING_NO_LOGIN=1` (`App/app/auth.py:283-301`). Staging mode does not apply to production.
7. Run the worker separately (production topology): `cd App && UBYHOST_ROLE=worker .venv/bin/python -m app.worker` (`App/app/worker.py`). Web and worker must not both hold the scheduler lock on the same `DATA_DIR`.

> ⚠️ UNKNOWN — needs human input: whether `App/run.sh` or `App/tools/smoke.py` is the owner-recommended local start path, and the minimum Python version tested (Dockerfile pins 3.12; `App/.venv` is 3.12).

## Running tests

Per `AGENTS.md` and `docs/context/test-map.md`, run only the files for your change:

```bash
cd App && .venv/bin/python -m pytest tests/test_deadlines.py -q --tb=short -x 2>&1 | tail -30
```

Full suite and browser shards run in CI (`.github/workflows/ci.yml`: ruff,
pytest with coverage, pip-audit, gitleaks, browser shards, shellcheck, Docker
build). Do not run the full suite locally unless asked — it is slow. Test
layout: [`docs/architecture.md#tests`](docs/architecture.md#tests).

## Tech stack

Versions from `App/requirements.txt` and `App/requirements.lock`:

| Area | Component | Version | Source |
|---|---|---|---|
| Runtime | Python | 3.12 (image `python:3.12-slim`) | `Dockerfile`, `render.yaml` |
| Web | FastAPI / Starlette / uvicorn | 0.162.0 / 1.10.0 / 0.54.0 | `App/requirements.txt` |
| Templates | Jinja2 | 3.1.6 | `App/requirements.txt` |
| Jobs | APScheduler (in-process) | 3.11.3 | `App/requirements.txt` |
| Database | SQLite (stdlib `sqlite3`, WAL) | `⚠️ UNKNOWN` (SQLite version in image unpinned; base image is Debian slim + `sqlite3` CLI) | `App/app/db.py:667-686`, `Dockerfile` |
| PDF | reportlab | 5.1.0 | `App/requirements.txt` |
| Calendars | icalendar | 7.3.0 | `App/requirements.txt` |
| Police client | requests, requests_ntlm | 2.34.2 / 1.3.0 | `App/requirements.txt`, `App/app/ubyport/client.py` |
| Crypto / auth | cryptography, pyotp, webauthn | 50.0.2 / 2.10.0 / 3.0.1 | `App/requirements.txt` |
| AI | anthropic SDK; Mistral is an alternative provider | 2.3.0 | `App/requirements.txt`, `App/app/config.py:355` |
| Payments | stripe | 16.0.1 | `App/requirements.txt` |
| Storage/mail | boto3 (SES only) | 1.43.118 | `App/requirements.txt`, `App/app/mail.py` |
| Backups | Litestream | 0.5.17 | `deploy/lightsail/docker-compose.yml` |
| Proxy | Caddy | 2 (alpine, digest-pinned) | `deploy/lightsail/docker-compose.yml` |
| Monitoring | Grafana Alloy, node-exporter, cAdvisor | v1.10.1 / v1.9.1 / v0.55.1 | `deploy/lightsail/docker-compose.yml` |
| Migrations | Custom SQL runner (not Alembic) | — | `App/app/db.py:1124-1260`, `App/app/migrations/` |

## Repository layout

```
.
├── AGENTS.md / CLAUDE.md / GEMINI.md   AI-agent entry points and rules
├── README.md                           this file
├── Dockerfile                          production image (root build context)
├── docker-entrypoint.sh                start-up guard, then exec "$@"
├── render.yaml / render_start.sh       Render staging blueprint (rootDir App)
├── requirements.txt                    Render entry; includes App/requirements.txt
├── deploy/lightsail/                   production compose, Caddy, Litestream, scripts
├── .github/workflows/                  CI, deploy, backup restore drill, security
├── scripts/                            repo-level tools (context lint, merge helper)
├── docs/                               documentation (see index below)
└── App/                                application
    ├── app/                            ~400 Python modules (FastAPI app, workers, PDFs)
    │   ├── main.py                     FastAPI app, role gate, lifespan
    │   ├── worker.py                   background worker process
    │   ├── scheduler.py                APScheduler job definitions
    │   ├── db.py                       SQLite access + migration runner
    │   ├── migrations/                 0002–0033 *.sql (0001 = frozen base schema)
    │   ├── ubyport/                    Police UbyPort SOAP client
    │   ├── routes/                     HTTP routers
    │   └── templates/, static/         Jinja2 templates; CSS/JS
    ├── tests/                          ~515 files (pytest; browser tests)
    ├── scripts/                        one-off ops/migration scripts
    ├── tools/                          smoke test, PWA icons, perf report
    ├── mock_ubyport/                   mock Police service (staging, dev)
    ├── requirements*.txt / .lock       dependencies
    └── run.sh / render_start.sh        start scripts
```

Source: `git ls-files` (3,511 tracked files at this revision).

## Documentation index

- [Architecture](docs/architecture.md) — topology, flows, data model, jobs, auth, deployment.
- [Runbook](docs/runbook.md) — deploy, rollback, migrations, backups, monitoring, failure modes.
- [Compliance](docs/compliance.md) — personal data, retention, deletion, residency, subprocessors.
- [Performance](docs/performance.md) — load, bottlenecks, scaling levers.
- [Limitations](docs/limitations.md) — technical debt, deferred work, fragile areas.
- [Migration to Go](docs/migration-to-go.md) — proposal only; not started.
- Official vendor links: [docs/integrations/REFERENCES.md](docs/integrations/REFERENCES.md). Integrations: [UbyPort (Police)](docs/integrations/ubyport-police-api.md), [iCal feeds](docs/integrations/ical-feeds.md), [Amazon SES](docs/integrations/ses-email.md), [Stripe](docs/integrations/stripe.md), [TTLock](docs/integrations/ttlock.md), [AI models](docs/integrations/ai-models.md).
- Gap report: [docs/gap-report.md](docs/gap-report.md) — every `⚠️ UNKNOWN`, grouped by importance.
- Existing repo docs (authoritative detail, kept in place): [OPERATIONS](docs/OPERATIONS.md), [LIGHTSAIL](docs/LIGHTSAIL.md), [DEPLOYMENT](docs/DEPLOYMENT.md), [ENVIRONMENT](docs/ENVIRONMENT.md), [SECURITY](docs/SECURITY.md), [UBYPORT_CORE](docs/UBYPORT_CORE.md), [SES](docs/SES.md), [TTLOCK](docs/TTLOCK.md), [privacy/RETENTION](docs/privacy/RETENTION.md), [privacy/ROPA](docs/privacy/ROPA.md).

## License and contact

- License: `App/LICENSES/` exists; the top-level license file is `⚠️ UNKNOWN` — check `App/LICENSES/` and the repo root.
- Maintainer / contact: `⚠️ UNKNOWN — needs human input`. The repo names `josef@ubyhost.com` (`render.yaml`, admin email) and `support@ubyhost.com` (`App/app/config.py:276`) but does not state a maintainer policy. See [`SECURITY.md`](SECURITY.md) for vulnerability reporting.
