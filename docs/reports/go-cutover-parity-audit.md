# Go cutover parity audit — 2026-11-22

Read-only audit of the Python → Go move, asked by the owner: *is production fully on Go, is it
waiting for a switch, or is it still being tested in staging — and what are we missing?*

**Method.** Static reading of both stacks plus live probes of `ubyhost.com` and
`staging.ubyhost.com` (GET/HEAD/POST to public URLs only; no cookies, no guest data, nothing
written). The code tree audited is **`a0af257c9`**, the commit that staging serves
(`/healthz` reports it). `main` is 64 commits behind that tree — see §2.

**Short answer.** Production is **not** on Go. It runs Python with a handful of paths already
on Go. Staging is 100% Go. The full cutover is merged on `main` but has never been deployed to
production, and `main` does not yet contain the last parity round that staging runs.

---

## 1. What is actually running where

| Environment | Serves traffic | Evidence (live, 2026-11-22) |
|---|---|---|
| Production `ubyhost.com` | Python (FastAPI) for most paths; Go for a few | `GET /healthz` → `{"status":"ok","version":"1.1.0",…}` — `1.1.0` is `App/app/__init__.py`, not a git SHA. `POST /healthz` → `405 {"detail":"Method Not Allowed"}` (Starlette). `GET /login/__nope__`, `/invoices/__nope__`, `/p/__nope__`, `/dev/ui/__nope__` → `{"detail":"Not Found"}` (Python). `POST /cenik` → `404 page not found` and `GET /predplatne/__nope__` → same (Go) |
| Staging `staging.ubyhost.com` | Go only | `GET /healthz` → `{"version":"a0af257c95bf6fc85ea5260929d1005e9e56fb36"}` (the Go binary's `-X main.version`). `GET /apartments/abc` → Go 501 (see AUD-04). `GET /static/fonts/` → directory listing (Go) |
| `main` (`34da9985a`) | full cutover merged | `deploy/lightsail/docker-compose.yml` has **no** `ubyhost`/`worker` service (commit `95ee256b0`, "1782 step 1"); both Caddyfiles end in `handle { reverse_proxy ubyhost-go:8081 ubyhost-go-b:8081 }` — one target, no Python fallback |
| Deploy path to production | manual | `.github/workflows/deploy-production.yml` is `workflow_dispatch` and requires typing `DEPLOY` |

So the switch the code used to have (`UBYHOST_GO_PATHS` in Caddy) is **gone** — the routing
decision is no longer "which paths go to Go", it is "which commit production has deployed".

## 2. The two trees (this is the main process finding)

- `a0af257c9` = merge of PR #1254 into `vibe/go-parity-ux-fixes` = **what staging runs**.
- `34da9985a` = `main` = **what production would deploy**.
- `main` is missing **64 commits**, including the whole `2011`–`2018` page-parity series
  (`docs/tasks/2010-go-parity-fix-index.md` §10 records those rows going 49 → 0) and the
  `2019`–`2027` UX/evidence round.

Consequences:

1. Staging is not testing what production will run. A green staging says nothing about `main`.
2. Deploying `main` today would put production on a tree that still has the 49 failing parity
   rows — strictly worse than what staging shows.
3. The parity series has to reach `main` before any production deploy.

## 3. What is genuinely done

| Area | Evidence |
|---|---|
| Route coverage | `python3 scripts/go_parity_check.py --all` → **342/342** Python routes have a Go handler, method-aware |
| Job coverage | `python3 scripts/go_jobs_parity.py` → **15/15** kinds, identical intervals and cron times |
| Page inventory | 143 Jinja files / 115 page templates → every Python page has a Go page; the only genuinely missing fragment is `guest/_leon.html` (AUD-01) |
| Sessions | Go verifies Python's cookie signature, key order and lifetimes (12 h / 30 d / 90 d); no session is invalidated at cutover |
| CSRF, 2FA-pending, magic links, device cookie, impersonation | same salts, formats and lifetimes in both stacks |
| Secrets at rest | Fernet/MultiFernet incl. the legacy `sha256(SECRET_KEY)` key, TOTP, recovery codes and passkeys read Python's rows unchanged |
| Passwords | neither stack stores a password hash — login is link/passkey/TOTP, so there is nothing to migrate |
| PDFs | same DejaVu TTFs subset-embedded via gopdf; A4; invoice bytes deterministic; `pdf_sha256` hashes the stored blob in both stacks, so old download links stay valid |
| E-mails | every Python builder has a Go twin, same shell, same `List-Unsubscribe` headers; `guest_details_host` is dead in Python too |
| UbyPort (filing) | NTLM auth, 60 s timeout, fault/5xx classification, `submit_state` transitions, sweep backoff and the watchdog all match; nothing under `App/app/ubyport/` is unported |
| TTLock / door codes | `allowed_for` entitlement is compensated at all five call sites; claim confirmation is wired through `door_codes_wire.go` (the "not ported" comment in `wire/services.go` is stale) |

## 4. Why the green gates did not catch the gaps below

| Gate | What it really proves | Blind spot |
|---|---|---|
| `scripts/go_parity_check.py --all` (342/342) | a matching mux pattern is registered for each decorated Python route | reads only `routes/*.py` + `main.py` decorators: `app.mount("/static")`, the five `@app.exception_handler`s, trailing-slash redirects and handler *behaviour* are invisible |
| `scripts/e2e/page_parity_audit.py` (137 paths / 411 rows, fail 0) | same status + same **normalised text** | strips `<script>`/`<style>`, ignores every attribute, class, stylesheet, icon and layout; accepts "pass-soft" at <2 % length difference or 0.94 similarity; excludes `/healthz`, `/metrics`, `/sitemap.xml`, PDF/ZIP/CSV, `/stripe/webhook`. `docs/tasks/2026-report.md` states it outright: *"the DOM-text audit says 10851/10851 while the page still looks wrong"* |
| `scripts/e2e/diff_harness.py` (2733 cases, 0 hard) | status, `Location`, `Content-Type`, auth/CSRF outcome, cookie flags | body comparison is "soft"; still text, not markup |
| `App/scripts/go_page_parity_screenshots.py` (pixel diff) | real visual parity | run on two pages in the 2021 report; not part of any gate |
| Gate B — live staging vs prod | — | **never built**: `docs/tasks/2020-staging-prod-live-audit.md` is still `Status: todo` |

A one-page live diff (a handful of GETs, §7) would have caught AUD-01, AUD-07 and AUD-09.

## 5. Findings

Severity is "what a host, guest or operator sees **after** production moves to Go". ID prefix
`AUD-`; code references are to `a0af257c9`.

| ID | Sev | Gap | Where | What is seen |
|---|---|---|---|---|
| AUD-01 | high | Guest guide renders the "Ask Leon" jump link but never the chat panel | `App/app/templates/guest/guide.html:69` (`include "guest/_leon.html"`, 44 lines) → `go/internal/web/guest/templates/guide.tmpl:20`; no Leon template exists in the Go guest package | No AI chat on the guest guide; the anchor stays hidden; the chat API is unreachable from the UI |
| AUD-02 | high | Retention never deletes anything | `go/internal/retention/retention.go:67` `DryRun: !(AUTOPURGE && GO_RETENTION_APPLY)`; neither variable is passed by `deploy/lightsail/docker-compose.yml:111-201`; `App/app/retention.py` step is otherwise ported | Data promised to be deleted is kept forever; the Settings "purge" reports a dry run |
| AUD-03 | high | Workspace/account deletion step fails closed | `go/internal/retention/steps.go:22-25` `ErrWorkspacesNotPorted` vs `App/app/retention.py:291-326` | A terminated workspace keeps working past its date; the 7-day reminder mail never sends; the nightly job errors each run and raises `job_failed` |
| AUD-04 | high | Terminal 501s — the "Caddy falls back to Python" design is dead | `go/internal/web/properties/lists.go:47-51`, `apartment_small_posts.go:262,547`, `wizard.go:145-148`; `Caddyfile.cloudflare:85-87` has no fallback; `docs/ENVIRONMENT.md:190` still promises the re-send | Verified live: `GET https://staging.ubyhost.com/apartments/abc` → `501 not served by Go yet: a path id that is not a number`. Same for a mistyped/blocked iCal URL during setup (`add_feed` error re-render, `App/app/routes/admin.py:3329`) |
| AUD-05 | high | Booking-site invoice is never issued | `go/internal/payments/booking_webhook.go:13,324` (`booking_invoice.ensure` not ported) vs `App/app/booking_webhook.py:98-100` | A guest who paid on the booking site opens the invoice link → 404; the host has no invoice row |
| AUD-06 | medium | ~35 `UBYHOST_*` variables Go reads are never passed to the container | `deploy/lightsail/docker-compose.yml:111-201` vs `go/internal/web/guest/pick_data.go:204` (`UBYHOST_GUEST_PIN`), `lifecyclemail/config.go:54`, `retention.go:67`, `App/app/config.py:441` | Editing `.env` changes nothing: the guest PIN cannot be turned off, lifecycle mail never sends, the mail heartbeat never fires |
| AUD-07 | medium | Trailing slashes: Python 307s to the canonical path, Go 404s | Starlette `redirect_slashes` vs Go 1.22 mux + `go/cmd/ubyhost-web/main.go:240` catch-all | Verified: `ubyhost.com/cenik/` → `307 → /cenik`; `staging.ubyhost.com/cenik/` → `404 page not found`. Same for `/login/`, `/signup/`, `/jak-to-funguje/` |
| AUD-08 | medium | Dashboard calendar is a static grid | `go/internal/web/hostweb/templates/dashboard.tmpl` (150 lines, `/?cal_view=calendar` only swaps the H1) vs `App/app/templates/_dashboard_calendar.html` (175 lines + `dashboard-calendar.js`); that JS is only loaded on the cleaning page | No month navigation, no calendar↔gantt toggle, no drag-to-create, no refresh |
| AUD-09 | medium | 404/405 are no longer the product's page | `App/app/main.py:261-275` renders `error.html` (guest variant for `/l/`) vs `go/cmd/ubyhost-web/main.go:128-130`; `go/internal/web/auth/authpage/errorpage.go:27` rewrites only 500 | Verified: `ubyhost.com/this-page-does-not-exist` → `{"detail":"Not Found"}`; staging → `404 page not found`. Different shape, same absence of chrome |
| AUD-10 | medium | A queued job kind missing from `UBYHOST_GO_JOB_KINDS` never runs and never alerts | `go/internal/jobs/queue.go:60,196-230`; one open row per kind; the Python worker that filled the gap is retired (`docker-compose.yml` 1782) | A job silently stops; only a "late" badge on Operations |
| AUD-11 | medium | First admin is never created by Go; fresh DB / restore path is Python-only | `go/internal/web/auth/login.go:471` deletes `/data/initial_admin_login` but nothing writes it (`App/app/auth.py:864-899` did); `go/internal/schema/migrate.go:34-35` needs Python's legacy DDL; `deploy/lightsail/scripts/pg-cutover.sh:99-125` still `exec`s the removed `ubyhost` service | New host or restore: no way to log in; `rollback` says "no such service: ubyhost" |
| AUD-12 | medium | Startup guard reduced from 12 refusals to 1 | `App/app/env_guard.py:92-140` → `go/internal/envguard/staging_no_login.go:36` | Production can boot against mock UbyPort and file nothing to the police, silently |
| AUD-13 | medium | `/healthz` hard-codes `data_dir_writable`; `/metrics` lost the latency and DB families; no access log | `go/cmd/ubyhost-web/main.go:80-116` vs `App/app/main.py:360-363,448-471,603-613` | Caddy's `health_uri` keeps a full-disk slot healthy; latency/DB dashboards go blank; no per-request log line |
| AUD-14 | low | `/static/` serves directory listings | `go/internal/web/staticfiles/static.go:55` (Python `StaticFiles(html=False)` 404s) | Verified on staging: `GET /static/fonts/` lists the tree |
| AUD-15 | low | Operator AI-budget mail not sent (log only) | `go/internal/anthropic/ai.go:329-352` vs `App/app/ai.py:305-315` | The 80 % cap notice only reaches container logs |
| AUD-16 | low | Stripe Connect calls are not retried | `go/internal/payments/onboarder.go:7-11` vs the SDK's two retries in `App/app/stripe_connect.py` | A transient blip shows the host an error page instead of the Stripe link |
| AUD-17 | low | Case folding covers only `ß` | `go/internal/validation/validation.go:143`, `go/internal/stayfee/calc.go:15-21` vs `App/app/validation.py:396,1041` | Names/streets with other foldable letters are accepted by Python and rejected (or kept) by Go |

Open design items, both **shared with Python** (not Go regressions, but they still look wrong):

- `docs/tasks/2026-report.md` — `/guests/{id}`: `res_street` is labelled "(optional)" while the
  validator makes it an error (`App/app/validation.py:518-532`); five helper lines; a 12 × 12 input.
  Blocked on an owner decision (required vs conditional), then a copy fix.
- `docs/tasks/2027-report.md` — `--ink-faint` cannot reach WCAG AA on the canvas (2.92–3.13) and
  cannot be fixed by one token; needs a ramp or role split.

## 6. Checked and *not* a gap (so nobody re-opens them)

- TTLock `allowed_for` billing entitlement — compensated at `doorcodes/issue.go:49-63,382`,
  `reconcile.go:317`, `reconcile_alerts.go:95`, `lifecycle_clock.go:60`.
- Door-code claim confirmation — wired via `cmd/ubyhost-web/door_codes_wire.go:110`; the
  "not ported" comment at `wire/services.go:96-107` is stale.
- Fonts — Go serves `font/woff2` / `font/ttf`; **Python serves `application/octet-stream`**
  (verified live on both hosts). Go is the correct one; no action beyond ignoring the comment.
- `/entities?edit=N` — ported (`lists.go:219` 501s only for non-ASCII digits); verified 200 on staging.
- Wizard 501s — the four live steps all have templates; retired steps redirect
  (`onboarding/wizard_step.go:225`).
- Static assets — `go/Dockerfile:14` copies all of `App/app/static`; every `?v=` key in
  `base.html` matches `hostweb/layout/shell.html`.
- JS-called endpoints — every `fetch()` target in the shipped JS is registered in Go.
- PDFs, e-mails, UbyPort filing — see §3.
- `dev_ui` is intentionally deleted with Python (`docs/plans/go-full-move.md` §7), not ported.

## 7. Reproduce it

```bash
# which stack is live (version 1.1.0 = Python, a git SHA = Go)
curl -s https://ubyhost.com/healthz; echo
curl -s https://staging.ubyhost.com/healthz; echo

# the framework's own 405 shape: JSON = Starlette, text = Go
curl -s -X POST -o /dev/null -w '%{http_code} %{content_type}\n' https://ubyhost.com/healthz

# a path that is on Go in production vs one that is not
curl -s -X POST -o /dev/null -w '%{http_code}\n' https://ubyhost.com/cenik      # Go: 404 page not found
curl -s https://ubyhost.com/healthz -o /dev/null -w '%{http_code}\n'          # Python

# the terminal 501 (Go, no login needed)
curl -s -o /dev/null -w '%{http_code}\n' https://staging.ubyhost.com/apartments/abc

# trailing slash: 307 on Python, 404 on Go
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' https://ubyhost.com/cenik/
curl -s -o /dev/null -w '%{http_code}\n' https://staging.ubyhost.com/cenik/

# the static gates
python3 scripts/go_parity_check.py --all | tail -3
python3 scripts/go_jobs_parity.py | tail -3
```

## 8. Before production moves to Go

1. **Land the parity series on `main`** (`2010`…`2027`). Production deploys from `main`; today
   `main` is 64 commits behind staging and still carries the parity rows the series closed (49 at the 2026-11-21 audit).
2. **Close AUD-06** (`docker-compose.yml` env whitelist). It is the cheapest fix with the widest
   reach: retention, PIN, lifecycle mail and admin bootstrap all depend on it.
3. **Decide AUD-04.** With no Python fallback every remaining `notPorted` branch is a dead end:
   port them, or route them to the branded error page before the switch.
4. **Port or accept AUD-01, AUD-05, AUD-07, AUD-08, AUD-09** — the five a user actually sees.
5. **Build Gate B** (`docs/tasks/2020-staging-prod-live-audit.md`) and run it once on a handful
   of pages (login, `/`, `/reservations`, `/guests/{id}`, one `/l/…`); it would have caught
   AUD-01, AUD-07, AUD-09 on its own.
6. **Fix the docs that outlive the old topology**: `docs/ENVIRONMENT.md:190` (the Caddy re-send
   no longer exists), `docs/context/status.md` (rollback by trimming `UBYHOST_GO_PATHS` is not
   possible; "Python: mail, door_codes" is false since the worker was retired), and
   `docs/tasks/2019-staging-prod-identical-index.md` §1 step 3 (adds paths to prod `UBYHOST_GO_PATHS`).

## 9. Notes for whoever picks this up

- `docs/context/known-issues.md` is at **2477 / 2500 tokens** and `docs/context/status.md` at
  **696 / 700**, so the rows above are not filed as `K-*` entries: there is no headroom. A
  compaction pass (or replacing the retired-topology lines) has to come first, and the two
  findings in §5 marked "shared with Python" belong in that same pass.
- The audit is read-only; no code, config or server state was touched.
- The gate commands in §7 are the ones the CI already runs; the live probes are not automated
  anywhere yet — that is AUD-04/Gate B.
