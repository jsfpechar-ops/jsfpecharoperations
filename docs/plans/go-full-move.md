# Plan: finish the move from Python to Go

Status: proposal, 2026-11-13. Nothing here starts until the owner approves it.
Extends [migration plan v4](postgresql/migration-plan-v4.md) steps G3 to G6.

## 1. Answer: no, production is not fully on Go

Go today is one service (`ubyhost-go`) that runs 8 of 15 queued job kinds and about 17 routes. Python still runs everything else, including the parts every Go job depends on.

| Area | On Go | Still on Python |
|---|---|---|
| Job kinds (`scheduler.JOB_KINDS`) | billing_snapshot, stripe_sweep, ical, push, submit, posthog, meta_capi, deadlines | mail, photo_sweep, retention, stay_fee_mail, billing, door_codes, guide_import |
| Scheduler (who enqueues) | nothing: Go only claims rows | APScheduler in the `worker` container enqueues **every** kind, Go ones included |
| Web routes | ~17: command palette, calendar, payments QR/connect/requests, Stripe webhook, push, pay PNGs, healthz, metrics | ~320 routes in 31 files under `App/app/routes/` plus 146 templates: login and sessions, passkeys, signup, onboarding, host dashboard and stays, guest registration, guest guide, cleaning, invoices and PDFs, stay fees, billing, exports, admin, legal pages, Havel and Leon AI, booking-site checkout |
| Filing (UbyPort) | the timed sweep (`submit`) | the immediate send when a guest finishes the last form, and the host "send" button: `reporting.submit_stay_if_complete` (14 call sites) and `routes/admin.py` |
| Schema | goose SQL files in `App/migrations_pg/` | applied only by `App/scripts/pg_schema.py` (Python); the app refuses to start while one is pending |
| Webhook | Go receives `/webhooks/stripe` | booking-site events are forwarded to Python (`UBYHOST_PY_WEBHOOK_URL`) |
| Compose | `ubyhost-go` | `ubyhost` (web) and `worker` (scheduler) both run the Python image |
| Scripts | none | `App/scripts/` ops scripts (backup, reencrypt, encrypt migrations, reconcile, exports) and the golden scripts used as parity fixtures |

Size: Python `App/app` is about 92,000 lines, Go about 18,000 (non-test). Most of the remaining work is G4 (host and guest web), which v4 already called "the bulk of the port".

## 2. How every step works

- One brief per step, own branch, draft PR, the owner merges. Tiers and models as in the owner's playbook; reviews use Opus.
- Parity first: a Python golden script writes fixtures (like `App/scripts/*_golden.py`), the Go code must reproduce them, and the PR shows both.
- Switch: a job moves by adding its kind to `UBYHOST_GO_JOB_KINDS` (both containers' env, checked with `docker inspect`); a page moves by adding its path to `UBYHOST_GO_PATHS`. Rollback is removing it again and `docker compose up -d`.
- Python code for a step is deleted only in a later PR, after one clean production week on Go.
- No new dependency without a decision line (rule 4). Steps that need one say so.

## 3. Lanes (in order inside a lane; lanes run in parallel, max 3 threads)

### Lane J: remaining jobs, then the scheduler
| # | Step | Tier | Notes |
|---|---|---|---|
| J1 | `photo_sweep` to Go | A (guest data, deletion) | Parity: list of photos deleted on a fixture DB |
| J2 | `retention` to Go | A (deletion) | Every rule in `App/app/retention.py`; dry-run mode first, compare counts with Python for 3 nights before it deletes |
| J3 | `billing` to Go | B (payments) | Invoice numbers and amounts golden; PDF needs a Go PDF library (decision line) or stays on Python until W5 |
| J4 | Mail plan, then `mail` and `stay_fee_mail` | B | Playbook says mail needs its own plan first. Reuse `go/internal/mail`; golden of every template's subject and body |
| J5 | `guide_import` to Go | B (AI outbound) | Needs the Anthropic Go SDK or plain HTTP (decision line); PR states the request reason |
| J6 | `door_codes` | B | Still blocked on TTLock plan §11/§12 |
| J7 | Go scheduler: Go enqueues all kinds, Python `worker` stops | A (filing, deadlines) | Same intervals and cron times as `scheduler.py`; a switch `UBYHOST_SCHEDULER=go`; rollback is the switch back. Then the `worker` service leaves compose |

### Lane F: filing paths left in Python (highest risk, owner sign-off per step)
| # | Step | Tier | Notes |
|---|---|---|---|
| F1 | Go endpoint for "send this stay now" used by the Python web | A | Python calls Go instead of `reporting.submit_stay_if_complete`; one place files. Golden: request XML from the mock for every send mode |
| F2 | Host "send" and "re-file" buttons call F1 | A | Stops the lane on any mismatch with the mock |

### Lane D: schema authority
| # | Step | Tier | Notes |
|---|---|---|---|
| D1 | `ubyhost-go migrate plan/check/apply` with the same goose files and the `--expect-database` guard | A (migrations) | Run both for two migrations; Python `pg_schema.py` then removed |

### Lane W: web (G4), lowest risk first
| # | Step | Tier | Routes |
|---|---|---|---|
| W1 | Public read-only pages | C | `legal`, `mail_unsubscribe`, `property_page`, `guest_guide_view` |
| W2 | Auth: login link, sessions, passkeys, signup | A | `signup`, `passkeys`, login and 2FA in `admin_accounts.py`; needs a WebAuthn library (decision line); cookie and Fernet conformance fixtures from G1 |
| W3 | Guest registration and questions | A (guest data, filing trigger) | `guest`, `guest_questions`, `guest_leon`; after F1 so the save calls Go filing |
| W4 | Host daily work | B | dashboard and stays in `admin.py` (split into several briefs), `cleaning`, `exports`, `onboarding`, `onboarding_wizard` |
| W5 | Money pages | B | `invoices` (PDF), `stay_fees`, `billing`, rest of `payments`, `stripe_connect`, booking site and booking webhook (Go stops forwarding) |
| W6 | AI pages | B | `havel`, `leon_setup`, `guest_guide` editor |
| W7 | Admin | B | rest of `admin_accounts`, `admin_customers`, `admin_billing`, `privacy_requests`, rest of `admin.py` |

Each W step: Go renders the same templates' content (content tests, not byte parity), browser and layout tests pass for the moved pages (rules 7 and 10), then the paths go into `UBYHOST_GO_PATHS`.

### Lane X: retire Python (G6, last)
| # | Step | Tier |
|---|---|---|
| X1 | Port the ops scripts still used (`backup_data.sh` stays shell; reencrypt, reconcile, exports) to `ubyhost-go` subcommands | B |
| X2 | Caddy sends everything to Go; `ubyhost` and `worker` leave compose; Dockerfile and `requirements*` removed | A |
| X3 | Delete `App/`, SQLite paths, golden scripts; move the parity fixtures to `go/testdata`; CI runs Go only; docs | B |

## 4. Order and first three threads

1. Start now, in parallel: **J1** (photo_sweep), **D1** (migrate command), **W1** (public pages). No shared files.
2. Then J2, F1, W2. F1 and J7 are the riskiest; each stops for the owner before its switch.
3. Rough size: lanes J, F, D are about 12 briefs; lane W is 25 to 35 briefs because of `admin.py` (5,463 lines) and `guest.py` (3,060 lines); lane X about 4.

## 5. Owner decisions needed

1. Approve this plan and the first three threads.
2. Dependencies (one line each when its step starts): Go PDF library, WebAuthn library, Anthropic Go SDK or plain HTTP.
3. Whether billing PDFs wait for W5 (recommended) or move with J3.

## 6. Lane threads and Files lists (owner approved all steps, 2026-11-13)

Order changed by the owner's rule "filing last": lane F runs after J7, and W3 (guest pages) plus the stay "send" parts of `admin.py` run after F2.

`go/cmd/ubyhost-web/main.go` is the one file every lane needs, so **P0 goes first**, alone: it moves route and job registration out of `main.go` into one file per lane, each starting empty. After P0 no lane edits `main.go`.

| Thread | Steps | Files it may touch (nothing else) |
|---|---|---|
| P0 "Split Go registration per lane" (Tier B, short) | P0 | `go/cmd/ubyhost-web/main.go`, `main_test.go`, new `register_jobs.go`, `register_schema.go`, `register_web.go`, `register_filing.go`; `go/internal/jobs/queue.go` (`jobNames` for all 15 kinds) |
| J "Port remaining jobs and scheduler to Go" | J1-J5, J7 (J6 when TTLock unblocks) | new `go/internal/{photosweep,retention,billingjob,lifecyclemail,guideimport,scheduler}/`; `go/internal/mail/` (J owns it; other lanes add new files only); `register_jobs.go`; new `App/scripts/*_golden.py` for its jobs; J7 only: `App/app/scheduler.py`, `App/app/worker.py`, `deploy/lightsail/docker-compose.yml`; `docs/ENVIRONMENT.md` (J only) |
| D "Move database changes to Go" | D1 | `go/internal/schema/`, `register_schema.go`, `deploy/lightsail/scripts/deploy.sh`, `deploy/lightsail/scripts/pg-cutover.sh`, `docs/LIGHTSAIL.md`; removal PR: `App/scripts/pg_schema.py` |
| W "Port web pages to Go" | W1, W2, W4, W5, W6, W7, then W3 after F2 | new `go/internal/web/<area>/`, `go/internal/hostweb/`, `go/internal/session/`, `register_web.go`, new `go/internal/mail/<auth>_*.go` files; Python route files only in their removal PRs |
| F "Move police filing to Go" (last, highest risk) | F1, F2 | `go/internal/ubyport/`, `go/internal/statemachine/`, `register_filing.go`, `App/app/reporting.py` (`submit_stay_if_complete` body only), the send/re-file handlers in `App/app/routes/admin.py` |
| X "Retire Python" | X1-X3 | after all lanes; touches everything, so runs alone |

Shared files nobody but the coordinator edits: `docs/context/status.md`, `docs/context/test-map.md`, `docs/context/decisions.md`. A lane that needs a line there sends it to the coordinator. `deploy/lightsail/docker-compose.yml` belongs to J until J7 merges.

Start order (max 3): P0 alone, then J, D, W together; F when D finishes and J7 has merged; X last.

## 7. Fine split: one thread per job and per web area (owner lifted the 3-thread cap, 2026-11-13)

**P0 must add one thing before it merges (#965):** per-thread registration files. `register_jobs.go` and `register_web.go` are single lists, so two job threads or two web threads would edit the same file. Add `registerJob(kind string, minutes int, h func(*pgxpool.Pool) jobs.Handler)` and `registerRoutes(func(*http.ServeMux, *metrics, *pgxpool.Pool))`, both called from `init()` in a file of the thread's own (`register_job_<kind>.go`, `register_web_<area>.go`), plus a test that no kind or route pattern is registered twice. Existing entries stay where they are.

Rules for every thread below: `go/internal/hostweb/` (layout, `i18n.json`), `go/internal/session/` read side, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go` and `App/tests/conftest.py` are read-only. Each web area keeps its templates and its i18n file in its own package. Each thread adds new test files only (`App/tests/test_go_<area>*.py`, Go tests in its package) and new golden scripts only (`App/scripts/<name>_golden.py`). `docs/ENVIRONMENT.md`, `status.md`, `test-map.md`, `decisions.md` and `known-issues.md` are coordinator-only: threads send their lines. A shared package is edited only by the thread named as its owner; other threads add new files in it at most.

### Start when P0 merges (all at once)
| Thread | Steps | Tier | Files (own; plus its `register_*` file) |
|---|---|---|---|
| Port photo sweep job | J1 | A | `go/internal/photosweep/` |
| Port retention job | J2 (dry-run 3 nights, then delete) | A | `go/internal/retention/` |
| Port billing job and PDFs | J3; owns the PDF library (decision line) | B | `go/internal/billingjob/`, `go/internal/pdf/` |
| Plan and port mail job | J4 plan, then `mail` | B | `go/internal/mail/` (owner), `go/internal/lifecyclemail/` |
| Port stay fee mail job | `stay_fee_mail` | B | `go/internal/stayfeemail/`; new files only in `mail/` |
| Port guide import job | J5; owns the Anthropic client (decision line) | B | `go/internal/guideimport/`, `go/internal/anthropic/` |
| Move database changes to Go | D1 | A | `go/internal/schema/`, `deploy/lightsail/scripts/deploy.sh`, `pg-cutover.sh`, `docs/LIGHTSAIL.md` |
| Port public legal pages | `legal`, `mail_unsubscribe`, `guest_guide_view` | C | `go/internal/web/public/` |
| Port login and accounts | `admin_accounts` (`/login`, `/logout`, `/account`, `/admin`), `signup`, `passkeys`; WebAuthn library (decision line) | A | `go/internal/web/auth/`, `go/internal/session/` (owner) |
| Port onboarding pages | `onboarding`, `onboarding_wizard` (checks UbyPort login) | A | `go/internal/web/onboarding/` |
| Port property settings pages | `admin.py`: `/apartments/*` (not `/page`, `/booking-site`), `/entities`, `/feeds`, `/sync`, `/settings`, `/menu`, `/housebook`, `/guide`, `/guest-links`, `/alerts`, `/smart-locks` | B | `go/internal/web/properties/` |
| Port cleaning pages | `cleaning` | B | `go/internal/web/cleaning/` |
| Port data exports | `exports` (guest data) | A | `go/internal/web/exports/` |
| Port stay fee pages | `stay_fees` | B | `go/internal/web/stayfees/` |
| Port subscription billing pages | `billing`, `admin_billing` | B | `go/internal/web/billing/` |
| Port payments and booking site | rest of `payments`, `stripe_connect`, `property_page` (booking site `/p/*`), booking webhook (Go stops forwarding) | B | `go/internal/payments/` (owner), `go/internal/web/booking/` |
| Port customer admin pages | `admin_customers`, admin funnel | B | `go/internal/web/customers/` |
| Port privacy request pages | `privacy_requests` | A | `go/internal/web/privacy/` |

### Start when a dependency merges
| Thread | Waits for | Tier | Files |
|---|---|---|---|
| Port invoice pages | billing job (uses `pdf/`) | B | `go/internal/web/invoices/` |
| Port AI assistant pages | guide import (uses `anthropic/`) | B | `go/internal/web/ai/` (`havel`, `leon_setup`, `guest_guide` editor) |
| Move scheduler to Go | every job thread above | A | `go/internal/scheduler/`, `App/app/scheduler.py`, `App/app/worker.py`, `deploy/lightsail/docker-compose.yml` |
| Move police filing to Go (F1, F2) | scheduler and database threads | A, owner sign-off per switch | `go/internal/ubyport/`, `go/internal/statemachine/`, `App/app/reporting.py`, send handlers in `App/app/routes/admin.py` |
| Port stays and submissions pages | filing | A | `go/internal/web/stays/` (`/reservations/*`, `/submissions/*`) |
| Port host guest editing | filing | A | `go/internal/web/guestadmin/` (`/guests/*`) |
| Port guest registration pages | filing | A | `go/internal/web/guest/` (`guest`, `guest_questions`, `guest_leon`) |
| Retire Python (X1-X3) | everything | A | runs alone |

`dev_ui` is not ported; it is deleted with Python. Python files are edited only in each thread's later removal PR, after a clean production week.
