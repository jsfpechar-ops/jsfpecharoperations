# Architecture map

**Stack**

- Python 3.12, FastAPI, Jinja2 templates, plain JS/CSS (no framework).
- SQLite via `App/app/db.py`.
- APScheduler worker, reportlab PDFs, pyotp, boto3 (SES, S3), icalendar, cryptography (Fernet).
- Versions are in `App/requirements.txt`; the lock is `App/requirements.lock`.

**Production** (`deploy/lightsail/`)

- Lightsail 8 GB, Docker Compose (`deploy/lightsail/docker-compose.yml`) running:
  - `ubyhost`: web, uvicorn, 2 workers, port 8080.
  - `worker`: scheduler.
  - `litestream`: continuous SQLite replication to S3.
  - `caddy`.
  - `mock-ubyport`.
- Cloudflare proxy in front, with origin certs.
- Staging: Render `ubyhost-staging` with mock UbyPort (`render.yaml`).
- CI (`.github/workflows/ci.yml`) runs these jobs: test (ruff, pytest with coverage, dependency audit), smoke, guest-browser, shellcheck, docker, secrets (gitleaks), context.

**Code map** (`App/app/`)

| Area | Files |
|---|---|
| App + routes | `App/app/main.py` (routers), `App/app/routes/` (guest, admin, admin_accounts, invoices, stay_fees, exports, signup, legal, privacy_requests, onboarding, api, mail_unsubscribe) |
| Police filing | `App/app/ubyport/` (SOAP client, errors), `App/app/reporting.py` (batches, sweep, state), `App/app/deadlines.py`, `App/app/filing_watchdog.py` |
| Stays and guests | `App/app/icalsync.py` (feeds), `App/app/claim.py` (guest claim), `App/app/housebook.py`, `App/app/validation.py`, `App/app/passport_photos.py` |
| Auth and security | `App/app/auth.py` (passwords, sessions, TOTP), `App/app/security.py`, `App/app/access.py`, `App/app/rate_limit.py`, `App/app/turnstile.py`, `App/app/client_ip.py`, `App/app/env_guard.py` |
| Data | `App/app/db.py`, `App/app/migrations/`, `App/app/retention.py`, `App/app/dsr.py`, `App/app/workspace_export.py` |
| Money | `App/app/invoices.py`, `App/app/invoice_pdf.py`, `App/app/stay_fee.py`, `App/app/stay_fee_filing.py`, `App/app/stay_fee_remittance_pdf.py` |
| Mail | `App/app/mail.py` (SES and outbox), `App/app/mail_notify.py`, `App/app/lifecycle_mail.py` |
| Scheduler | `App/app/scheduler.py`, `App/app/worker.py`, `App/app/alerts.py` |
| Copy (i18n) | `App/app/i18n.py` (guest), `App/app/host_i18n.py` (host, 357 KB: grep it, never read it whole), `App/app/landing_i18n.py`, and the legal `*_i18n.py` files |
| UI | `App/app/templates/` (`guest/` = guest pages), `App/app/static/` (`app.css` 95 KB, `guest.css`, `tokens.css`) |

**Large files** (grep, then read ranges only): `App/app/routes/admin.py` (116 KB), `App/app/reporting.py` (100 KB), `App/app/db.py` (69 KB), `App/app/mail_notify.py` (69 KB), `App/app/routes/guest.py` (77 KB).

**Tests:** `App/tests/` (about 240 files). Key guards:

- `App/tests/test_privacy_first.py` (cookies)
- `App/tests/test_no_tracking.py` (CSP)
- `App/tests/test_auth_forms_no_js.py`
- `App/tests/test_guest_browser_e2e.py`
- `App/tests/test_host_geometry.py`

**Numbering**

- Tasks are `docs/tasks/NNNN-*.md`.
- Migrations are `App/app/migrations/NNNN_*.sql`; `0001` is the frozen `db.SCHEMA`.
- Run `python3 scripts/context_lint.py` to get the next free task and migration numbers.
- The historic WP/patch series (WP01–WP33, patches 0001–0034) is done and lives in `docs/archive/UbyHost_workplan/`.
