# Documentation gap report

Generated from a read-only audit of the repository at the current revision.
Every `⚠️ UNKNOWN` marker in the docs is listed below, grouped by importance.
Each question is phrased to be answered by the owner (or by checking a named
location).

## Verification pass (what was confirmed and how)

Checked after the first draft. "Confirmed" means a repo, GitHub or public-source check was made. Production facts cannot be checked from here.

| Gap | Result | Evidence |
|---|---|---|
| Holiday list (Q5) | **Confirmed** against the statute: 13 days, identical set. Good Friday is in §2 "ostatní svátky", which §3 also makes days of rest, so the working-day rule matches. The "only from 2016" claim was not checked. | `App/app/deadlines.py:38-59`; [Act 245/2000 Sb. §1–§3, version 12 (valid from 13.05.2026)](https://www.zakonyprolidi.cz/cs/2000-245) |
| Deploy approval gate (Q9) | **Confirmed: none.** `production` environment has `protection_rules: []`. Auto-deploy ran successfully today (09:07, 09:38 UTC). | `gh api repos/.../environments/production`; `.github/workflows/deploy-production.yml:19-22, 55` |
| Restore drill (Q13) | Last visible run **success 2026-10-26**. Content of the restore is not visible. | `gh run list --workflow restore-drill.yml` |
| Backup cron (Q12) | **Scripted**: daily 03:00 UTC on-volume backup and Sunday 04:00 Google Drive backup. Live crontab not checked. | `deploy/lightsail/scripts/setup-server.sh:72-76`, `finish-bootstrap.sh:70` |
| Active Caddy file (Q15) | **Confirmed**: `CLOUDFLARE_PROXY=1` → `Caddyfile.cloudflare`; otherwise `Caddyfile.acme`. Live env value not checked. | `deploy/lightsail/scripts/deploy.sh:41-52` |
| Prod mock override (Q19) | Code exists: `UBYHOST_ALLOW_PROD_MOCK=1` lets production start with mock UbyPort. Production value unknown. | `App/app/env_guard.py:125-129` |
| Stripe webhook (Q21 part) | **Confirmed**: public `POST /webhooks/stripe`. Live Stripe mode still unknown. | `App/app/routes/stripe_connect.py:102-103` |
| ARES / VAT calls (Q33) | **Confirmed: no callers.** Modules exist but nothing imports them. Dead code. | grep for `import ares`, `vat_register` in `App/app` (only i18n strings) |
| Turnstile fail-open (new) | **Confirmed**: 5 attempts per 15 min per IP, then fail open. | `App/app/turnstile.py:19-20, 63-83` |
| CSRF on push/passkeys (Q36) | **Partly confirmed.** Neither router file references CSRF or a `protect_*` dependency. Whether JSON endpoints are protected another way is untested. | `App/app/routes/push.py`, `App/app/routes/passkeys.py` |
| Raw id lookups (Q3) | **Partly confirmed.** 64 raw `WHERE id = ?` lookups in routes; 10 carry an owner clause within two lines. The delete at `admin.py:4275` is guarded upstream. The rest are not each traced. | grep over `App/app/routes/*.py` |
| iCal providers (Q29) | **Confirmed** from the module docstring: Airbnb, Booking.com, Agoda, Vrbo. | `App/app/icalsync.py:1-20`, `:56-57` |
| Apify use (Q22) | **Confirmed**: guest guide import, billed per run, usage tracked under provider `apify`. Data sent and DPA still open. | `App/app/guest_guide_import.py:26, 124` |
| Undocumented env names (I-5) | `GOOGLE_EXPORT_DAYS`: in 2 code files, purpose not read. `UBYHOST_SIGNUP_ENABLED`: in 4 code files, not in `docs/ENVIRONMENT.md`. `UBYHOST_META_GRAPH_VERSION`: in code, not documented. `UBYHOST_LITESTREAM_ENABLED`: no hits in `App/app`; not checked in `deploy/`. `UBYHOST_ADMIN_PASSWORD`: documented, **no code hit** (drift confirmed). | grep over `App/app` and `docs/ENVIRONMENT.md` |

### Runtime verification (2026-10-31, scratch worktree, PR commit)

| Check | Result |
|---|---|
| `pip install -r requirements.txt -r requirements-dev.txt` (py3.12) | ok |
| `db.init_db()` on empty DB | 68 tables; `schema_migrations` 33 rows (baseline + 0002–0033) |
| `pytest tests/test_deadlines.py` | 25 passed |
| `UBYHOST_ROLE=web uvicorn app.main:app` | `/healthz` 200 |
| `./run.sh` (staging + no-login) | app `/healthz` 200; mock `/healthz` 200 |
| `POST /demo` with `x-csrf-token` | 303; 2 apartments, 18 reservations, 8 guests created |
| `UBYHOST_ROLE=worker python -m app.worker` | scheduler starts, jobs registered, clean stop on SIGTERM |
| Demo calendar feeds during `ical` job | 2 errors when `PUBLIC_BASE_URL` pointed at port 8080 while the app ran on 8095. Demo feeds are built from `PUBLIC_BASE_URL` (`App/app/demo.py:147-156`). With the matching URL: `sync_all` gives `errors=0`, both feeds fetched. |
| `POST /demo` without CSRF header | 303 to `/login?notice=form_expired` (CSRF enforced) |

**Still open (cannot be verified from the repo or public sources):** production env values (Q10, Q11, Q14, Q16, Q21), production NULL-owner rows (Q4), live Litestream bucket and region, server crontab state, the actual content of the last restore drill, the RETENTION/ROPA/vendor documents (Q20, Q24), and the erasure path (Q25). These need access to the Lightsail server, the AWS console, or the owner.

## A. Blocks the migration (answer before any port)

1. **Is the Go + River migration decided?** The brief says "being considered". The repo has no Go code and no decision record. Check `docs/plans/` and the owner. ([migration-to-go](migration-to-go.md))
2. **Is the Postgres move the next step, and who owns it?** The repo says "defer production migration" (commit `84763c6b`). Is that still true? ([architecture](architecture.md#postgres-connection-strategy))
3. **Is every route query owner-scoped?** Shared-schema tenancy with `owner_user_id` and no RLS (`App/app/access.py`, `App/app/db.py:1416`). Which routes use raw `WHERE id = ?` without an owner clause? A full route audit is needed. ([architecture](architecture.md#data-model-and-tenancy))
4. **Do NULL-owner rows exist in production?** `owner_user_id IS ?` matches NULL when owner is None (`App/app/db.py:1416`); backfill at `App/app/auth.py:779-782`. Run `SELECT count(*) FROM … WHERE owner_user_id IS NULL` on production.
5. **Is the holiday list correct for every year?** `App/app/deadlines.py:38-59` is hardcoded; tests cover 2024–2026 only. Compare against the official Czech calendar for 2027+.
6. **Which legal statute governs the three-working-day window?** `deadlines.py:3-4` cites §100(c) Act 326/1999; the statute text is not verified in code. Confirm with the lawyer (`docs/UbyHost_workplan/04_legal_positions.md`).
7. **Does the police service accept the production NTLM SOAP client?** Only the mock is exercised. Run the `test` environment with real credentials and record results. (`App/app/ubyport/client.py`)
8. **Is there a SOAP golden-file test suite for `ZapisUbytovane`, `TestDostupnosti`, `DejMiCiselnik`?** None was located. Confirm `App/tests/` contents. (required before the police-API port)

## B. Safety, privacy and operations (answer soon)

9. **Does production deploy run automatically on green `main`?** `.github/workflows/deploy-production.yml:19-22` (`workflow_run`) vs. `AGENTS.md` rule 8 ("production deploy is manual"). Does a GitHub Environment approval gate exist?
10. **What is the production value of `UBYHOST_RETENTION_AUTOPURGE`?** Default 0 (`App/app/config.py:221`). If 1, personal data is deleted by the daily job.
11. **What are the production values of `UBYHOST_DEPLOYMENT`, `UBYHOST_ENABLE_SCHEDULER` and `UBYHOST_ROLE` on the worker?** Not in repo. Check the server `.env`. Staging-only password and no-login paths are refused when `UBYHOST_DEPLOYMENT=production` (`App/app/env_guard.py`).
12. **Where is the cron or timer for `App/scripts/backup_data.sh`?** No schedule was found in the repo. Check the server crontab and `deploy/lightsail/scripts/`.
13. **When was the last successful restore drill, and what was its result?** `docs/context/status.md` lists "backup drill" as done; `.github/workflows/restore-drill.yml` runs weekly (Mon 03:30 UTC). The owner must give the date. ([runbook](runbook.md#backups))
14. **Is the S3 bucket for Litestream and off-site backups set, and what is its name and region?** Bucket name is an env value (`deploy/lightsail/litestream.yml:54-61`). Check the server `.env`, not the repo.
15. **Which is the active Caddy file in production?** `deploy/lightsail/caddy/Caddyfile.acme` vs. `Caddyfile.cloudflare`; `scripts/deploy.sh:49-52` chooses by `CLOUDFLARE_PROXY` (inferred). Check `Caddyfile.active` on the server.
16. **Is the Lightsail instance 8 GB / 2 vCPU, and in which AWS region?** `Dockerfile` comment and `docs/LIGHTSAIL.md` say so; confirm in the AWS console.
17. **Where do alerts go?** Better Stack, healthchecks.io and `uptime.yml` are named; the alert route is not in the repo. Who is paged, and how?
18. **What is the log retention and shipping target?** Grafana Alloy is in compose (`deploy/lightsail/docker-compose.yml`, profile `monitoring`); the destination and retention are not documented in the repo.
19. **Does `UBYHOST_ALLOW_PROD_MOCK` appear in production?** `env_guard.py` (~137) warns or refuses production + mock UbyPort.
20. **Which AI vendors receive guest or host data, and under which DPA?** Anthropic (`App/app/ai.py`) and optional Mistral (`App/app/config.py:355-359`). Check `App/app/subprocessors_i18n.py` and `docs/vendors/`.
21. **Is Stripe live in production?** `UBYHOST_STRIPE_MODE` (`App/app/config.py:176`) is not in the repo; `docs/context/status.md` says billing is ON.
22. **What does Apify do, and is it still used?** `UBYHOST_APIFY_TOKEN` (`App/app/config.py:183`) is used by `App/app/guest_guide_import.py`. Confirm the use case and its DPA status.
23. **Which data goes to Meta (Conversions API) and PostHog, and on what consent basis?** `App/app/meta_capi.py`, `App/app/posthog_sync.py`; cookie inventory `App/app/cookie_inventory.py`. Confirm against `docs/privacy/`.
24. **What is the processing basis per activity?** `docs/privacy/ROPA.md` was not read in this pass. Confirm it is current with the code (`UBYHOST_PRIVACY_VERSION` 1.7).
25. **How is erasure done, and can it reach backups?** `App/app/dsr.py` and `App/app/routes/privacy_requests.py` were not read for the delete path. Backup deletion is not described.
26. **Are the plaintext `doc_number` and `visa_number` columns still written, and can they be dropped?** `App/app/db.py:222-225`.
27. **Are invoice, remittance and photo files encrypted on the production volume?** Code paths show mixed encryption (`App/app/db.py:547`, `App/app/passport_photos.py:201`). Check the volume.

## C. Missing facts in code or docs (answer when convenient)

28. **Is there a maintainer, license file and contact?** `App/LICENSES/` exists; the top-level license and maintainer policy are not in the repo.
29. **Which iCal providers are supported?** The sample feed (`App/app/sample_calendar.py`) is Airbnb-shaped; `airbnb.com` and `booking.com` appear in code (`grep`). Confirm the supported list and whether any provider needs a token.
30. **What is the iCal internal retry policy?** `App/app/icalsync.py` was not read in full.
31. **What are the push and guide-import queue semantics?** `App/app/push.py` and `App/app/guest_guide_import.py` were not read in full.
32. **Does any UbyPort submission bypass the sweep (manual submit route)?** Not checked. `App/app/routes/` should be grepped for `reporting.submit` or equivalent.
33. **Do `ares.lookup` and `vat_register.lookup` have call sites?** Grep found none under those names; they may be imported under another alias.
34. **Which Stripe, TTLock and `mail.drain` paths run inside an HTTP request versus a job?** `door_codes.py` calls `mail.drain` inline; `routes/admin.py:3391` and `routes/guest.py:1222` call TTLock.
35. **What do `GOOGLE_EXPORT_DAYS` and `UBYHOST_LITESTREAM_ENABLED` control?** Read in code, not documented.
36. **Does the CSRF check cover `push.py` and `passkeys.py` JSON POSTs?** No `protect_*` dependency was found on those routers; the enforcement code path was not traced.
37. **Do the staging-only auth paths run in production?** `UBYHOST_STAGING_LOGIN_PASSWORD` and `UBYHOST_STAGING_NO_LOGIN` are gated on `DEPLOYMENT=="staging"` (`App/app/auth.py:283-301`, `:692-700`). Confirm no staging value is set in production.
38. **Are Stripe, TTLock and other vendor secrets encrypted at rest beyond the `_enc` columns?** Coverage of `db.encrypt*` was not traced.
39. **Which Caddy and Cloudflare settings are live?** `deploy/lightsail/caddy/Caddyfile.cloudflare` trusts Cloudflare ranges and aborts non-Cloudflare peers. Confirm `CLOUDFLARE_PROXY` in production.
40. **What is the Playwright browser install path outside CI?** Playwright is not in `App/requirements-dev.txt`; CI installs 1.63.0 in its image (`.github/workflows/ci.yml:151-193`).

## D. Inconsistencies found (code vs. docs, dead config, drift)

| # | Item | Where | Note |
|---|---|---|---|
| I-1 | Scheduler "in the web process" | `docs/OPERATIONS.md` § Scheduled jobs vs. `App/app/main.py:159`, `App/app/worker.py` | Docs stale for production; true only for `UBYHOST_ROLE=all`. |
| I-2 | Production deploy manual vs. automatic | `AGENTS.md` rule 8 vs. `.github/workflows/deploy-production.yml:19-22` | See Q9. |
| I-3 | boto3 version drift | `App/requirements.lock:31` (1.43.108) vs. `App/requirements.txt:15` (1.43.118) | Lock and source differ. |
| I-4 | `UBYHOST_ADMIN_PASSWORD` documented but unused | `docs/ENVIRONMENT.md` | Not in `App/app/`. |
| I-5 | Undocumented env names | `App/app/config.py`, `App/app/*.py` | `UBYHOST_SIGNUP_ENABLED`, `UBYHOST_SIGNUP_NOTIFY_EMAIL`, `UBYHOST_META_DATASET_ID`, `UBYHOST_META_ACCESS_TOKEN`, `UBYHOST_META_TEST_EVENT_CODE`, `UBYHOST_META_GRAPH_VERSION`, `UBYHOST_ADS_CONVERSION_NAME`, `POSTHOG_APP_URL`, `GOOGLE_EXPORT_DAYS`. |
| I-6 | Hostex and Search Console documented, not implemented | `docs/HOSTEX.md`, `docs/SEARCH_CONSOLE.md` | No code hits in `App/app/`. |
| I-7 | Google Ads described as an integration | `App/app/signup.py` | Actually a manual CSV export (gclid/gbraid/wbraid); no API. |
| I-8 | Plaintext and encrypted PII side by side | `App/app/db.py:222-225` | See Q26. |
| I-9 | SQLite-specific SQL despite the "Postgres-portable" rule | `App/app/db.py:96-97, 685-690, 1190, 1212, 1416` | `AGENTS.md` rule 5 vs. code. |
| I-10 | `.env.example` did not exist; `.env` names only | repo root | Created in this pass; no values. |
| I-11 | `README.md` pointed only at `App/`; `Dockerfile` comment mentions Fly.io and Railway | `README.md`, `Dockerfile` header | Stale host list; production is Lightsail. |
| I-12 | `App/requirements.txt` vs. `App/requirements.lock` for dev runs | `App/run.sh` installs `requirements.txt`; CI installs `requirements.lock` with hashes | Local and CI installs can differ. |
| I-13 | Local run enables private iCal URLs | `App/run.sh` sets `UBYHOST_ICAL_ALLOW_PRIVATE=1` | Off by default in code (`App/app/config.py:452`). |
| I-14 | `UBYHOST_WEB_WORKERS` default differs by comment | `Dockerfile` comment says 4 on the 8 GB server; `Dockerfile` ENV and CMD default 2 | Expected: production value lives on the server. |

## E. Files and topics not covered in depth in this pass

- `docs/UbyHost_workplan/` (9 files) and `docs/plans/` (194 files), `docs/tasks/` (2058 files): not read; the task series is historical.
- `App/app/routes/*.py`: sampled, not traced route by route.
- `App/app/*_i18n.py`: copy only; not reviewed.
- `docs/privacy/RETENTION.md`, `docs/privacy/ROPA.md`, `docs/vendors/`: not read in full.
- `deploy/lightsail/scripts/*.sh`: listed, not read.

## F. Migration-relevant decisions the owner should make

- Go + River versus staying in Python with PostgreSQL (see Q1–Q2).
- Whether production deploy stays manual (see Q9).
- Whether the scheduler moves to a database-backed queue or stays in APScheduler.
