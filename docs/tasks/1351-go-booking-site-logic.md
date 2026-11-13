# 1351: Go booking site logic and iCal routes (switched off)

Status: todo
Depends on: none | Base commit: a83df54 | Branch: task/1351-go-booking-site-logic
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier B (money: prices, refunds). Review: Opus orchestrator reads the risk-listed files.

## 1. Objective

First half of porting the public booking site (`/p/<slug>`, `App/app/routes/property_page.py`) to Go: a new package `go/internal/web/booking` with the logic layer (settings, price quote, refund amount, manage token and URL, history-slug redirect, month grid, pay rails, iCal) and the three routes that render no HTML page. Every result is pinned to the Python one by a golden file, so the later page brief can build on logic that already matches Python exactly.

Nothing goes live: Caddy sends a path to Go only after the owner adds it to `UBYHOST_GO_PATHS`.

## 2. Context

Split (brief writer's decision): this brief is site, calendar, rails, quotes, iCal, redirect and the no-HTML routes. Checkout (Stripe session + hold), direct request, guest cancel (refund call), manage page view data and the HTML pages are left for later briefs (1352 and the page brief). `RefundCZK` and `ManageToken` are already here because the stay-calendar route and the later cancel brief both need them.

Python sources ported (read-only, do not open unless a step fails): `App/app/booking_site.py` (settings 69-101, ical_token 140-150, earliest_check_in 156-163, quote 166-213, check_in_moment and refund_czk 219-244, token_hash, manage_token, token_ok, manage_url 250-279), `App/app/booking_calendar.py` (all), `App/app/booking_rails.py` (account_on_file, enabled, ready, pay_modes), `App/app/booking_ical.py` (all), `App/app/booking_manage.py` (calendar_ics), `App/app/property_page.py` (resolve 80-101, dates_available 333-349, photos_dir 217), `App/app/routes/stay_fees.py` (revolut_link_ok 270-280), `App/app/routes/property_page.py` (routes at 250, 394, 552; `_RATE_MAX = 120`, `_RATE_WINDOW = 3600`, `client_key(request, scope)` so the rate key is `<ip>:<scope>`).

Routes registered (new file `go/cmd/ubyhost-web/register_web_booking.go`, via `registerRoutes` in `registry.go`):

| Pattern | Python route | Notes |
|---|---|---|
| `GET /p/{slug}/{file}` | `/p/{slug}/{token}.ics` | `{token}.ics` is not a valid ServeMux wildcard. The handler cuts the `.ics` suffix; any other file name is 404 before any database call. Later briefs may add `GET /p/{slug}/thanks` (more specific, no conflict), `POST /p/{slug}/book` and `POST /p/{slug}/checkout` (other method, no overlap). No bare `GET /`, no `GET /p/{slug}`. |
| `GET /p/{slug}/b/{booking_id}/{token}/calendar.ics` | `booking_manage_calendar` | rate scope `booking_manage`; 200 only for a `paid` booking with a good HMAC token |
| `GET /photos/property/{name}` | `property_photo_file` | `[0-9a-f]{32}\.jpg` under `$UBYHOST_DATA_DIR/property_photos`, no rate limit |

The history-slug 301 is exposed as `booking.Resolve` + `booking.RedirectPath` for the page brief; `GET /p/{slug}` is not registered.

Python behaviour copied on purpose (the golden file proves it):
- `date.fromisoformat` in Python 3.13 also accepts `20261201`, `2026-W49-2`, `2026W49` and ignores trailing bytes in a 10-byte string (`2026120199`). `ParseISODate` does the same.
- `refund_czk` subtracts two datetimes that share the Prague tzinfo, which Python does by wall clock (DST ignored). `RefundCZK` compares Prague wall clocks too (golden cases around 28 Mar 2027 and 25 Oct 2026).
- `ical_token` mints and stores a token on the first check, even for a wrong token; stored JSON is `json.dumps(..., sort_keys=True)` text.
- Quotes check `dates_available` against all active reservations, archived or not; the iCal export skips archived ones.

Known differences (accepted, documented in code): a 404 is Go's plain `404 page not found`, not Python's 404 page; a non-numeric `booking_id` is 404 in Go (FastAPI answers 422); a settings value that is not a number is treated as absent (Python would raise; `save_settings` only writes whole numbers); a float `advance_notice_days` such as `7.0` is rewritten as `7` if Go mints the iCal token (Python keeps `7.0`); Go needs a secret key to exist (Python mints one) and answers 500 without it.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/booking/site.go` | create | Settings, quote, refund, tokens, manage URL, slug resolve |
| `go/internal/web/booking/isodate.go` | create | Python 3.13 date.fromisoformat |
| `go/internal/web/booking/calendar.go` | create | Month grid and taken nights |
| `go/internal/web/booking/rails.go` | create | Direct pay rails, Stripe mode, pay modes |
| `go/internal/web/booking/ical.go` | create | iCal export feed, stay calendar, feed token |
| `go/internal/web/booking/handlers.go` | create | The three HTTP handlers + rate limit |
| `go/internal/web/booking/golden_test.go` | create | Parity test against golden.json |
| `go/internal/web/booking/handlers_test.go` | create | Route tests |
| `go/cmd/ubyhost-web/register_web_booking.go` | create | Registers the three routes |
| `App/scripts/booking_site_golden.py` | create | Golden generator |
| `App/tests/test_go_booking_golden.py` | create | Fails when golden.json is stale |
| `go/internal/web/booking/testdata/golden.json` | create (generated by step 3) | Python outputs |
| `docs/tasks/1351-files/` | delete (step 4) | Carrier copies of the files above, removed once copied |
| `docs/tasks/1351-report.md` | create | Your report |

No other file may change. In particular not `go/internal/payments/`, `go/internal/hostweb/`, `go/internal/jobs/`, `go/internal/mail/`, `go/cmd/ubyhost-web/main.go`, `registry.go`, `register_web.go`, `App/tests/conftest.py`, `docs/ENVIRONMENT.md`, `docs/context/*`.

## 4. Steps

Start: `git switch task/1351-go-booking-site-logic` (the branch holds this brief) and check `git status --short | tail -5` shows no change to tracked files. Untracked files that are not in §3 are not yours: leave them, never `git add` them; add files only by their exact §3 path.

### Step 1: put the files in place

The exact file contents are in `docs/tasks/1351-files/` (one `.txt` per target path, so neither Go nor pytest picks them up there). From the repo root:

```bash
mkdir -p go/internal/web/booking && cp docs/tasks/1351-files/go/internal/web/booking/site.go.txt go/internal/web/booking/site.go
mkdir -p go/internal/web/booking && cp docs/tasks/1351-files/go/internal/web/booking/isodate.go.txt go/internal/web/booking/isodate.go
mkdir -p go/internal/web/booking && cp docs/tasks/1351-files/go/internal/web/booking/calendar.go.txt go/internal/web/booking/calendar.go
mkdir -p go/internal/web/booking && cp docs/tasks/1351-files/go/internal/web/booking/rails.go.txt go/internal/web/booking/rails.go
mkdir -p go/internal/web/booking && cp docs/tasks/1351-files/go/internal/web/booking/ical.go.txt go/internal/web/booking/ical.go
mkdir -p go/internal/web/booking && cp docs/tasks/1351-files/go/internal/web/booking/handlers.go.txt go/internal/web/booking/handlers.go
mkdir -p go/internal/web/booking && cp docs/tasks/1351-files/go/internal/web/booking/golden_test.go.txt go/internal/web/booking/golden_test.go
mkdir -p go/internal/web/booking && cp docs/tasks/1351-files/go/internal/web/booking/handlers_test.go.txt go/internal/web/booking/handlers_test.go
mkdir -p go/cmd/ubyhost-web && cp docs/tasks/1351-files/go/cmd/ubyhost-web/register_web_booking.go.txt go/cmd/ubyhost-web/register_web_booking.go
mkdir -p App/scripts && cp docs/tasks/1351-files/App/scripts/booking_site_golden.py.txt App/scripts/booking_site_golden.py
mkdir -p App/tests && cp docs/tasks/1351-files/App/tests/test_go_booking_golden.py.txt App/tests/test_go_booking_golden.py
```

Then check the hashes (the same list as §7):

```bash
sha256sum -c docs/tasks/1351-files/SHA256SUMS 2>&1 | tail -12
```

Expected: 11 lines ending `OK`. Any `FAILED`: copy that file again once; still failing: STOP (§8). Do not edit any of these files. Commit `1351 step 1` (add the 11 target paths by name).

### Step 2: build and vet

```bash
cd go && go build ./... 2>&1 | tail -5 && go vet ./internal/web/booking/ ./cmd/ubyhost-web/ 2>&1 | tail -5 && gofmt -l internal/web cmd 2>&1 | tail -5
```

Expected: no output. No commit (nothing changed).

### Step 3: generate the golden file

From `App/` (create the venv first if `App/.venv` is missing: `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -3`):

```bash
.venv/bin/python scripts/booking_site_golden.py 2>&1 | tail -3
cd .. && sha256sum go/internal/web/booking/testdata/golden.json 2>&1 | tail -1
```

Expected: `wrote .../golden.json` and hash `5fb4154237c9155eca42bbd51852323b88786bcfcf7fe85cea9d813e73b64541`. Different hash: STOP (§8), do not edit the JSON by hand. Commit `1351 step 3`.

### Step 4: remove the carrier copies

```bash
git rm -r -q docs/tasks/1351-files && git status --short | tail -5
```

Commit `1351 step 4`.

### Step 5: tests (§6), then the report (§9).

## 5. Do not touch

Everything not in §3. Hard rules: no new dependency (only the standard library, pgx and the repo's own `internal/secure`); never push to `main`; no secrets in the repo (the golden secret is a fixed test string); no tracking, no outbound request (this brief makes none).

## 6. Commands

```bash
cd go && go test -count=1 ./internal/web/booking/ ./cmd/ubyhost-web/ 2>&1 | tail -10
```

Expected: `ok` for both packages. With a local Postgres also run it with `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:<port>/postgres` set in front; without one the database tests skip locally and CI runs them (`.github/workflows/ci.yml` sets the variable). Write in the report which of the two you ran.

```bash
cd App && .venv/bin/python -m pytest tests/test_go_booking_golden.py tests/test_booking_site.py tests/test_property_page.py tests/test_stripe_connect.py -q --tb=short -x 2>&1 | tail -15
```

Expected: all pass (brief writer's dry run of `tests/test_booking*.py tests/test_property_page*.py tests/test_go_booking_golden.py`: 195 passed, 6 skipped).

## 7. Acceptance

- [ ] `sha256sum` of every §3 file matches this list:

```text
145ad7da372b7847521f2589aee90da259033d680ee96ecfd413aa0b6fdcd436  go/internal/web/booking/site.go
9fd092fc524655b6ca5fa784c239866fee579dddc42faa7a3056c624b5bb5236  go/internal/web/booking/isodate.go
f0b2fbe9e2a3ac4135d27ebe3e88706b1d635ee6212b39e4e655a644c78c5496  go/internal/web/booking/calendar.go
ab63c3487bafdd3e6aab382cd6936d14549229a36d12e2d9807d5b1b231806d6  go/internal/web/booking/rails.go
25feb316f07ad943bdf3b32add2a71f052ef33d589c5dae508cf39862c02396d  go/internal/web/booking/ical.go
e20ad4cd5969bba4dea78ff35f6740005c40cecc23b253d2f24768cf4ed7b672  go/internal/web/booking/handlers.go
fcb429874ffad1b7b256db91dd578e173c50c8fe10131d02e43870b7e5167fdb  go/internal/web/booking/golden_test.go
2ac7b3902e66e3aa7a86b1e3a13aa1e3d545c3da5600126076d30e17571193f1  go/internal/web/booking/handlers_test.go
5b6d54b4143d59ecc01e9ed90d246dd64c5e8087632fc2d94a3b51d4540b0a36  go/cmd/ubyhost-web/register_web_booking.go
eb3b704a627073cdc5e4da2bf894a40c01934fe954d9ab1de4015a855e2e7c4f  App/scripts/booking_site_golden.py
abd43f80969a34fd199834eb076b7d8380175fb494fd0373d7549568f572d125  App/tests/test_go_booking_golden.py
5fb4154237c9155eca42bbd51852323b88786bcfcf7fe85cea9d813e73b64541  go/internal/web/booking/testdata/golden.json
```

- [ ] `git diff --stat a83df54 -- . ':!docs/tasks' | tail -3` shows only the §3 paths, and `docs/tasks/1351-files` no longer exists.
- [ ] Both §6 commands pass.
- [ ] `grep -c 'registerRoutes' go/cmd/ubyhost-web/register_web_booking.go` prints 1.

## 8. Stop and ask

Stop, and write the report, if:

- a hash differs twice;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1351-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `go/internal/web/booking/site.go`: `LoadSettings`, `GetQuote`, `RefundCZK` (money), `ManageToken`.
- `go/internal/web/booking/handlers.go`: rate limit, token checks, the `/p/{slug}/{file}` suffix guard.
- `go/cmd/ubyhost-web/register_web_booking.go`: the three patterns.
- `App/scripts/booking_site_golden.py`: the cases and the clock patches (`db.utcnow`, `booking_site._now`, `datetime` in booking_ical and booking_manage).

## Owner steps

1. Review and merge the PR when CI is green (nothing changes in production: no path is routed to Go).
2. Later, to switch the routes to Go, add these paths to `UBYHOST_GO_PATHS` on the server (space separated, Caddy path matchers), then restart Caddy:

```text
/p/*/*.ics /p/*/b/*/*/calendar.ics /photos/property/*
```

3. Check one feed in the browser: open the iCal export link from the host's booking settings; it must download the same calendar as before.
