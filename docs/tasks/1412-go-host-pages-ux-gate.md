# 1412: UX gate for the Go host pages added in PR #1003

Status: blocked — owner option B (2026-11-13): waiting for the owner's staging screenshots; the orchestrator reviews them, no executor run
Depends on: owner staging screenshots | Base commit: 3d75651dd | Branch: none (the report is written by the orchestrator in the PR that records it)
Executor: none (the orchestrator reviews; no Haiku run) | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Run the UX gate (AGENTS.md hard rule 10, [workflow](../context/workflow.md#ux-gate)) on the Go host pages that PR #1003 added, by looking at real screenshots from the Lightsail staging server, and record per page what the 390, 768 and 1280 px screenshots show. No code is fixed here: every finding becomes a later fix brief (1413 and up). The pages are dormant until their paths are added to `UBYHOST_GO_PATHS`, so the gate must pass before the owner does that in production.

## 2. Context

Go GET pages that need the gate (each verified in code: `grep -n 'GET ' <file>`), all rendered inside the layout shell `go/internal/hostweb/layout/`:

| Page | Registered in |
|---|---|
| `/entities` | `go/internal/web/properties/lists.go` (`RegisterLists`, line 41) |
| `/apartments` | `go/internal/web/properties/lists.go` (`RegisterLists`, line 42) |
| `/guide` | `go/internal/web/properties/pages.go` (`RegisterPages`, line 39) |
| `/guest-links` | `go/internal/web/properties/pages.go` (`RegisterPages`, line 40) |
| `/admin/customers` (operator admin) | `go/cmd/ubyhost-web/register_web_customers.go` line 19 |
| `/admin/customers/{user_id}` (operator admin) | `go/cmd/ubyhost-web/register_web_customers.go` line 20 |
| `/admin/funnel` (operator admin) | `go/cmd/ubyhost-web/register_web_customers.go` line 21 |

`register_web_customers.go` line 22 also registers `POST /admin/customers/{user_id}/aktivovat`; the Go service serves it when the path is routed to Go.

Why the automatic gate cannot run (checked by the brief writer):

1. `App/tests/test_layout_lint_browser.py` takes its server from `wide_host` and `wide_base` in `App/tests/test_host_wide_geometry_browser.py`: an in-process uvicorn of the Python app (`from app.main import app`) on SQLite.
2. Which paths go to Go is decided by Caddy through `UBYHOST_GO_PATHS` (`deploy/lightsail/caddy/Caddyfile.acme`, line 29: `@go path {$UBYHOST_GO_PATHS:/__go_off__}`). The Python app has no proxy to Go (`git grep -n 'UBYHOST_GO_PATHS' -- App` prints nothing), and the tests run no Caddy.
3. The Go binary needs `UBYHOST_DATABASE_URL` (Postgres). No script or CI job starts it with seeded host data and a login session for a browser run.

Owner decision 2026-11-13: option B. The owner publishes the seven pages on the Lightsail STAGING server only, takes the screenshots by hand and sends them. Production `.env` is not touched, so nothing ships to users. `layout_lint.js` is not run under option B: the review is visual only and the report says so.

Caddy's `path` matcher ignores the HTTP method and the query string. Three consequences for the staging test:

- `/entities` and `/apartments` are also the targets of the Python forms `POST /entities` and `POST /apartments` (`App/app/routes/admin.py` lines 1195 and 1801). While those paths are routed to Go, the "add" forms on these two pages fail (Go serves only GET there). The test does not need them: do not submit them.
- Detail pages such as `/apartments/<id>` and the POST actions under `/apartments/...` and `/entities/...` are not listed, so they stay on Python. The links `/apartments?view=bookings` and `/apartments?view=settings...` go to the Go list page. Stay on the pages of the table; ignore where those links lead.
- `/admin/customers/*` sends every customer sub-path to Go, including the POST `/admin/customers/{id}/aktivovat` that Go also serves.

## 3. Files

| Path | Action | What |
|---|---|---|
| `docs/tasks/1412-report.md` | create | per-page findings, written by the orchestrator from the 21 screenshots |

Nothing else may change. Fix briefs for the findings are separate files (1413 and up).

## 4. Steps

The orchestrator (not Haiku) does these once the owner has sent the screenshots:

1. Check the upload: 21 PNG files named `<page>-<width>.png`, i.e. `entities`, `apartments`, `guide`, `guest-links`, `admin-customers`, `admin-customer-detail`, `admin-funnel`, each at 390, 768 and 1280. A missing file: ask the owner for it in the chat.
2. Open each screenshot and check it against the checklist in [design-system](../design/design-system.md) (read the 390 px image first). Look for word-per-line wrapping, clipped or overlapping text, a horizontal scrollbar, buttons or boxes outside the viewport, a misplaced help "?", and a layout shell that differs from the Python host pages (sidebar, header, footer).
3. Write `docs/tasks/1412-report.md` with one line per page: `390: ...; 768: ...; 1280: ...`, plus the design-system checklist ticked. The report says in its first line: "Visual review only: `layout_lint.js` was not run (option B)."
4. Every finding becomes its own fix brief (1413 and up), named in the report. Fix nothing in this brief.
5. Set this brief's `Status:` to `review` when the report is written, and `done` when the fix briefs are merged or the owner accepts the findings.

## 5. Do not touch

- `App/`, `go/`, `deploy/`, `scripts/`, `tests/`, `.github/`.
- The production `.env` and the production `UBYHOST_GO_PATHS`.
- No new tooling: hard rule 4 and the "no invented tooling" instruction of this brief.

## 6. Commands

None for an executor. Re-check commands for §2:

- `grep -n 'GET ' go/internal/web/properties/lists.go go/internal/web/properties/pages.go go/cmd/ubyhost-web/register_web_customers.go | cut -c1-140 | tail -10`
- `git grep -n 'UBYHOST_GO_PATHS' -- App | wc -l` (expected `0`)

## 7. Acceptance

- [ ] 21 screenshots received, one per page and width of §2.
- [ ] `docs/tasks/1412-report.md` has one line `390: ...; 768: ...; 1280: ...` for each of the 7 pages and states that the lint was not run.
- [ ] Every finding is named as a fix brief (1413 and up) or marked "accepted" by the owner.
- [ ] `git diff --stat origin/main...HEAD | tail -5` lists only this brief, the report and the fix briefs.

## 8. Stop and ask

Stop, and write the report, if:

- `Status:` is `blocked` and no screenshots have arrived;
- a screenshot does not show the Go page (for example the Python page with the old layout): ask the owner to check that the paths are in `UBYHOST_GO_PATHS` on staging and that the `ubyhost-go` service runs;
- an excerpt is not found;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a file outside §3 needs a change;
- §5 would be touched.

## 9. Report

Write `docs/tasks/1412-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The 21 screenshots received (names).
2. Per page: `390: ...; 768: ...; 1280: ...`.
3. §7 ticked.
4. The fix briefs opened (1413 and up).
5. The note that `layout_lint.js` was not run.
6. Owner steps left.

## Risk list (for the reviewer)

The screenshots themselves, read at 390 px first. The staging data is mock data, so long real-world names and many rows are not covered: say so in the report.

## Owner steps

These are for the Lightsail STAGING server only (the second Lightsail instance, never the production server). Production is not touched and nothing ships to users. The `.env` file on staging is in `/opt/ubyhost/deploy/lightsail/` (see `docs/LIGHTSAIL.md`).

1. Open a terminal on your computer and connect to the staging server: `ssh ubuntu@<staging server address>`. Use the staging address, not the production one (the production address is `LIGHTSAIL_HOST` in GitHub secrets; do not use it).
2. Go to the server folder: `cd /opt/ubyhost/deploy/lightsail`. Check that the Go service runs: `docker compose ps | grep -i go`. If no `go` line shows up as running, stop and tell the orchestrator in the chat (the Go service must run on staging; `COMPOSE_PROFILES` in `.env` must contain `go`).
3. Write down the current setting. Run `grep -n '^UBYHOST_GO_PATHS' .env` and copy the whole line into a note on your computer. If it prints nothing, write down "not set".
4. Open the file: `nano .env`. Find the line starting with `UBYHOST_GO_PATHS=`. Keep what is already inside the double quotes and add a space and then these paths, still inside the quotes: `/entities /apartments /guide /guest-links /admin/customers /admin/customers/* /admin/funnel`. Example: `UBYHOST_GO_PATHS="<what was there> /entities /apartments /guide /guest-links /admin/customers /admin/customers/* /admin/funnel"`. If the line did not exist, add it with only the new paths. Never leave the value empty: Caddy will not start. Why these paths: they send only the seven pages to Go. The forms under `/apartments/...` and `/entities/...` stay on Python because those paths are not in the list. The two exceptions are `/admin/customers/<id>/aktivovat`, which Go also serves, and the "add" forms of the Entities and Apartments pages, which post to `/entities` and `/apartments` and will not work during the test: do not use them. Save with Ctrl+O, Enter, then leave with Ctrl+X.
5. Check the new setting and apply it. Run `./scripts/caddy-validate.sh`; it must end without an error. Then run `docker compose up -d caddy`. Then open the staging site in a browser and make sure the normal login page still loads. If the validate step prints an error, do step 9 (put the old line back) and tell the orchestrator.
6. Make sure the staging data has at least one property, one apartment and one customer (mock data is fine). If one is missing, create it through the normal pages: a property under Properties, an apartment under Apartments (use the Python page `/apartments/...` flow, not the Go list), and a customer by signing up a second test account. Do this before you take the pictures.
7. Take the host-page pictures in Chrome on a computer. Sign in to the staging site as a host. Press F12. Click the phone/tablet icon at the top left of the panel (Toggle device toolbar). In the bar above the page, click the width number and type `390`. Open each of these four pages by typing the address after the staging domain: `/entities`, `/apartments`, `/guide`, `/guest-links`. On each page, click the three dots at the right end of the device toolbar and choose "Capture full size screenshot". Chrome saves a PNG; rename it to `<page>-390.png`, for example `entities-390.png`, `apartments-390.png`, `guide-390.png`, `guest-links-390.png`. Repeat the same four pages at width `768` (`entities-768.png` and so on) and at width `1280`.
8. Take the admin pictures. Sign out, then sign in as the operator admin account. Repeat step 7 for `/admin/customers`, then `/admin/customers/<id>` (click any customer in the list and use its page; name the files `admin-customer-detail-<width>.png`), then `/admin/funnel`. File names: `admin-customers-390.png`, `admin-customer-detail-390.png`, `admin-funnel-390.png`, and the same three at 768 and 1280. You now have 21 pictures in total (7 pages times 3 widths). Send all 21 to the orchestrator in the chat. A page that shows an error or the old Python layout: send a picture of it anyway and say so.
9. Roll back as soon as the pictures are sent. On the staging server, in `/opt/ubyhost/deploy/lightsail`, run `nano .env`, put back the exact `UBYHOST_GO_PATHS` line you wrote down in step 3 (or delete the line if it was not set), save with Ctrl+O, Enter, Ctrl+X. Then run `./scripts/caddy-validate.sh` and `docker compose up -d caddy`. Open the staging site once more to check that it loads. The production `.env` was never opened or changed and nothing was shown to real users.
