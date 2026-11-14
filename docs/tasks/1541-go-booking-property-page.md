# 1541: Go public property page and booking quote step (switched off)

Status: review
Depends on: 1540 | Base commit: none (one big PR) | Branch: the current branch
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier B (guest-facing, shows prices from the quote code). Review: Opus orchestrator reads the risk-listed files.

**One big PR mode.** Work on the current branch. Never create a branch, never push, never open a PR. Commit `1541 step k` after each step. Acceptance checks use `git log --oneline --grep='^1541 step'`, not a fixed base commit.

## 1. Objective

Port the public booking page `GET /p/{slug}` (photos, text, guide cards, calendar, quote, guest form) and the no-JS quote step `POST /p/{slug}/book` to Go on the guest shell of 1540. Every amount comes from the existing, golden-tested `GetQuote` and `MonthGrid` of 1351; this brief adds no money rule.

## 2. Context

Python mirrored (read-only, open only if a step fails): `App/app/routes/property_page.py` `property_page_view` 38-53, `_render_page` 56-76, `_page_lang` 90-95, `_href` 98-107, `_month_param` 110-119, `_short_day` 122-126, `_booking_view` 129-166, `_noindex` 169-174, `_og` 177-188, `_page_context` 191-247, `BOOK_ERRORS` 265, `_bookable_apartment` 277-284, `_guests` 287-291, `property_page_book` 294-315, `_book_error` 318-324; `App/app/property_page.py` `widget_ready` 398-417, `nightly_price` 351-356; `App/app/booking_site.py` `site_allowed` 58-64; templates `property_page.html`, `property_page_book.html`.

Parity table (route, Python function, lines, what is pinned by tests):

| Go | Python | Lines | Test |
|---|---|---|---|
| `GET /p/{slug}` | `property_page_view` | 38-53 | 301 for a history slug to `/p/<live>`, 404 for unpublished and unknown, 120 per hour rate limit (scope `property_page`), 429 `slow down` |
| `PropertyPageHandler` quote block | `_booking_view` + `booking_site.quote` | 129-166 | fixed numbers below |
| `LoadPage` | `_page_context`, `_noindex`, `_og` | 169-247 | escaping, `splitlines`, 400-character split, noindex |
| `WidgetReady` | `widget_ready` | 398-417 | via the page test (the Book card shows) |
| `SiteAllowed` | `site_allowed` | 58-64 | plans test |
| `POST /p/{slug}/book` | `property_page_book` | 294-315 | quote page, 303 error redirects, 404 |

Money (nothing new is computed; the numbers are shown as the quote code returns them). Fixed test numbers, fixture apartment 1, clock 28 Nov 2026, 1 to 4 Dec, 2 guests: 3 nights x 2 000 = 6 000, cleaning 500, total 6 500 CZK, city tax on site 50 x 2 x 3 = 300 CZK, policy moderate. Thousands are separated by a no-break space, as the Python `money` macro does.

Behaviour copied on purpose: the quote page of `POST /book` is always rendered in English (`lang "en"`) and has no pay-mode list, so its hidden `pay_mode` is always `stripe` (Python passes the page dict without `pay_modes`); the page language is `?lang`, then cookie `ubyhost_lang`, then Czech; `?book=` shows only the twelve listed errors.

Known differences (accepted): a photos or amenities value that is not a JSON list of strings reads as empty (Python answers 500); `strip` and `splitlines` follow Go's Unicode whitespace for the few control characters that differ; a 404 is Go's plain text page; the shell sets no CSRF cookie (see 1540); a form body over 1 MiB is cut.

Rules: no tracking cookie, no third-party script, no analytics (the page is not in `PUBLIC_ANALYTICS_TEMPLATES`), light mode, the page works without JavaScript (links and plain forms). The guest e-mail typed after a field error is never put in a URL (that re-render is brief 1542).

**Paths fully served by Go after this brief:** `/p/{slug}` (GET) and `/p/{slug}/book` (POST). Collision check: `GET /p/{slug}/book` matches Go's wildcard `GET /p/{slug}/{file}` and answers 404, where Python answers 405; nothing links to it.

**Goes live on deploy:** nothing new unless `UBYHOST_GO_PATHS` already holds `/p/*`. If it does, `GET /p/{slug}` and the whole page go live at once, and `POST /p/*/checkout` (brief 1542) would still be Python only: the form on the page would post to a path that Caddy then sends to Go with no handler. Check the server value before merging; if `/p/*` is there, take it out until 1542 and 1543 are switched together (brief 1550 has the order).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/cmd/ubyhost-web/register_web_booking_property.go` | create (21 lines) | new file, copied from the sidecar |
| `go/internal/web/booking/pagectx.go` | create (288 lines) | new file, copied from the sidecar |
| `go/internal/web/booking/property.go` | create (263 lines) | new file, copied from the sidecar |
| `go/internal/web/booking/property_test.go` | create (224 lines) | new file, copied from the sidecar |
| `go/internal/web/booking/templates/book.tmpl` | create (46 lines) | new file, copied from the sidecar |
| `go/internal/web/booking/templates/property.tmpl` | create (154 lines) | new file, copied from the sidecar |
| `go/internal/web/booking/view.go` | create (181 lines) | new file, copied from the sidecar |

No other file may change. In particular not `go/internal/hostweb/`, `go/internal/session/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, `go/cmd/ubyhost-web/register_web_booking.go`, anything under `App/`.

## 4. Steps

### Step 1: copy the files

From the repo root:

```bash
mkdir -p go/cmd/ubyhost-web && cp docs/tasks/1541-files/go/cmd/ubyhost-web/register_web_booking_property.go.txt go/cmd/ubyhost-web/register_web_booking_property.go
mkdir -p go/internal/web/booking && cp docs/tasks/1541-files/go/internal/web/booking/pagectx.go.txt go/internal/web/booking/pagectx.go
mkdir -p go/internal/web/booking && cp docs/tasks/1541-files/go/internal/web/booking/property.go.txt go/internal/web/booking/property.go
mkdir -p go/internal/web/booking && cp docs/tasks/1541-files/go/internal/web/booking/property_test.go.txt go/internal/web/booking/property_test.go
mkdir -p go/internal/web/booking/templates && cp docs/tasks/1541-files/go/internal/web/booking/templates/book.tmpl.txt go/internal/web/booking/templates/book.tmpl
mkdir -p go/internal/web/booking/templates && cp docs/tasks/1541-files/go/internal/web/booking/templates/property.tmpl.txt go/internal/web/booking/templates/property.tmpl
mkdir -p go/internal/web/booking && cp docs/tasks/1541-files/go/internal/web/booking/view.go.txt go/internal/web/booking/view.go
```

Expected: no output. Commit `1541 step 1`.

### Step 2: check the files

```bash
sha256sum -c <<'EOT' 2>&1 | tail -15
8819de0265ea712b7d8084aed4b3051ab6e0f9806f62a59115045b02781a3f3a  go/cmd/ubyhost-web/register_web_booking_property.go
9b110007d5844f5f75c08033c51a18df5da1ab64e3cb73bc8ef28931689e3eb9  go/internal/web/booking/pagectx.go
e4747fd90fdf295d309c878d55cd737408d141f6c9195b61ea8663970143dd3b  go/internal/web/booking/property.go
15c43bd1272bd60bb68d1c0e7aa3f2d7e5db33c8122aae9b3a53fef2eb3a14e8  go/internal/web/booking/property_test.go
fe50b3f49ef180c02258b9c7ecb21d017f972cda6329faaeea2e4279aec0288e  go/internal/web/booking/templates/book.tmpl
4097d7d0e20588caff77007bcae54567fae17ca994e139d6af3df7fcf726f28c  go/internal/web/booking/templates/property.tmpl
f49fc75639bce570c5e8a7a7b015538e65e41b0eaa67c877fc0747e4acad7a3c  go/internal/web/booking/view.go
EOT
```

Expected: every line `OK`. `FAILED`: copy that file again once; still failing: STOP.

### Step 3: build, vet, format

```bash
cd go && go build ./... 2>&1 | tail -10 && go vet ./internal/web/booking/ ./cmd/ubyhost-web/ 2>&1 | tail -10 && gofmt -l internal/web cmd 2>&1 | tail -5
```

Expected: no output.

### Step 4: string catalog check

This brief adds no keys (1540 lists `pp.*`). `cd App && .venv/bin/python scripts/go_host_i18n.py --check 2>&1 | tail -3` prints nothing. Stale: STOP.

### Step 5: tests (section 6), then the report (section 9).

## 5. Do not touch

Everything outside section 3. Hard rules: no new dependency; never push to `main`; no secrets; no tracking cookie; the page must keep working without JavaScript.

## 6. Commands

```bash
cd go && go test -count=1 ./internal/web/booking/ ./cmd/ubyhost-web/ 2>&1 | tail -10
```

Expected: `ok` for both. The new tests need PostgreSQL: run them with `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:<port>/postgres` set (CI sets it); without it they skip. Say in the report which you ran.

## 7. Acceptance

- [ ] `sha256sum -c` of step 2 printed only `OK`.
- [ ] `git log --oneline --grep='^1541 step' | tail -5` shows step 1; `git show --stat --format=%s $(git log --grep='^1541 step 1' --format=%h -1) | tail -15` lists only section 3 paths.
- [ ] Both section 6 packages print `ok`, with the database variable set.
- [ ] `grep -c 'registerRoutes' go/cmd/ubyhost-web/register_web_booking_property.go` prints 1.
- [ ] Screenshots (rules 7 and 10) are taken in brief 1550 before any switch; this brief changes no served page.

## 8. Stop and ask

Stop, and write the report, if: a hash differs twice; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a new dependency seems needed; a file outside section 3 needs a change; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1541-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

- `go/internal/web/booking/pagectx.go`: `WidgetReady` and `SiteAllowed` decide whether the Book card (a payment entry point) shows; `LoadPage` (what a guest sees of the host's data: town and district only, never the street).
- `go/internal/web/booking/view.go`: `BuildBookingView`, `PageHref` (dates, guests in links), `monthParam`.
- `go/internal/web/booking/property.go`: `BookHandler` (404 unless bookable; the quote that the next step trusts), `Money`.
- `go/internal/web/booking/templates/property.tmpl`: the checkout form fields (`terms_version`, `pay_mode`).

## Owner steps

1. Nothing changes in production when this merges (no path is routed to Go by this brief).
