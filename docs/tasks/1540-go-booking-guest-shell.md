# 1540: Go guest page shell, booking terms and thanks pages (switched off)

Status: review
Depends on: none | Base commit: none (one big PR) | Branch: the current branch
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier B (public guest pages). Review: Opus orchestrator reads the risk-listed files.

**One big PR mode.** Work on the current branch. Never create a branch, never push, never open a PR. Commit `1540 step k` after each step. Acceptance checks use `git log --oneline --grep='^1540 step'`, not a fixed base commit.

## 1. Objective

Add the Go shell every public booking page needs (the port of `base.html` with `show_nav = false`) and the two static pages that use it: `GET /terms/booking` and `GET /p/{slug}/thanks`. The thanks page closes the `/p/{slug}/thanks` path collision: today Go's wildcard `GET /p/{slug}/{file}` answers 404 for it.

## 2. Context

Python sources mirrored (read-only, do not open unless a step fails): `App/app/routes/property_page.py` `booking_terms_page` 31-35, `property_page_thanks` 570-577, `_page_lang` 90-95; `App/app/templates/base.html` (no-nav branch), `booking_terms.html`, `property_page_booked.html`, `_pp_booking_css.html`, `_booking_terms_cs.html`, `_booking_terms_en.html`.

Why a new shell: `go/internal/hostweb/layout` always wraps the body in the host page frame and is read-only for this thread. The shell lives in `go/internal/web/booking/shell.go`. Pages are template files that define `guest.content` (and optionally `guest.head`); they read `{{.Data}}` and translate with `{{.T "key"}}`. Later briefs (1541 to 1545) add pages with the same shell.

Parity notes (route, Python function and lines):

| Go route | Python | Lines | Notes |
|---|---|---|---|
| `GET /terms/booking` | `booking_terms_page` | 31-35 | language `?lang`, cookie `ubyhost_lang`, else cs; title, noindex, nav links and legal text copied byte for byte |
| `GET /p/{slug}/thanks` | `property_page_thanks` | 570-577 | `X-Robots-Tag: noindex`; shows no booking data |

Known differences (accepted): the shell sets no CSRF cookie and emits an empty `csrf-token` meta (no public booking form has a CSRF field, and `csrf.js` does nothing without a token), so Go sets fewer cookies than Python; a slug with unusual characters is URL-escaped by `html/template` in the back link; a 404 is Go's plain text.

Privacy and rules: no tracking cookies, no third-party script (the test checks that every script is from `/static/`), light mode only, no personal data stored, no outbound request. PostHog is not loaded (`App/app/analytics.py` does not list these templates).

**Goes live on deploy if its path is routed to Go:** `/terms/booking` and `/p/*/thanks`. Check `UBYHOST_GO_PATHS` on the server: a `/terms/*` or `/p/*` entry would send them to Go at once. Both are static and safe to serve from Go.

**Paths fully served by Go after this brief:** `/terms/booking` (GET only, Python has no other method) and `/p/{slug}/thanks`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/cmd/ubyhost-web/register_web_booking_pages.go` | create (20 lines) | new file, copied from the sidecar |
| `go/internal/web/booking/i18n.json` | create (366 lines) | new file, copied from the sidecar |
| `go/internal/web/booking/i18n_keys.txt` | create (36 lines) | new file, copied from the sidecar |
| `go/internal/web/booking/pages.go` | create (31 lines) | new file, copied from the sidecar |
| `go/internal/web/booking/pages_test.go` | create (113 lines) | new file, copied from the sidecar |
| `go/internal/web/booking/shell.go` | create (122 lines) | new file, copied from the sidecar |
| `go/internal/web/booking/templates/pp_booking_css.html` | create (50 lines) | new file, copied from the sidecar |
| `go/internal/web/booking/templates/shell.tmpl` | create (93 lines) | new file, copied from the sidecar |
| `go/internal/web/booking/templates/skeleton_detail.html` | create (8 lines) | new file, copied from the sidecar |
| `go/internal/web/booking/templates/terms.tmpl` | create (15 lines) | new file, copied from the sidecar |
| `go/internal/web/booking/templates/terms_cs.html` | create (16 lines) | new file, copied from the sidecar |
| `go/internal/web/booking/templates/terms_en.html` | create (16 lines) | new file, copied from the sidecar |
| `go/internal/web/booking/templates/thanks.tmpl` | create (7 lines) | new file, copied from the sidecar |

No other file may change. Never touch `go/internal/hostweb/`, `go/internal/session/`, `go/internal/jobs/`, `go/cmd/ubyhost-web/main.go`, `App/`.

## 4. Steps

### Step 1: copy the files

From the repo root:

```bash
mkdir -p go/cmd/ubyhost-web && cp docs/tasks/1540-files/go/cmd/ubyhost-web/register_web_booking_pages.go.txt go/cmd/ubyhost-web/register_web_booking_pages.go
mkdir -p go/internal/web/booking && cp docs/tasks/1540-files/go/internal/web/booking/i18n.json.txt go/internal/web/booking/i18n.json
mkdir -p go/internal/web/booking && cp docs/tasks/1540-files/go/internal/web/booking/i18n_keys.txt.txt go/internal/web/booking/i18n_keys.txt
mkdir -p go/internal/web/booking && cp docs/tasks/1540-files/go/internal/web/booking/pages.go.txt go/internal/web/booking/pages.go
mkdir -p go/internal/web/booking && cp docs/tasks/1540-files/go/internal/web/booking/pages_test.go.txt go/internal/web/booking/pages_test.go
mkdir -p go/internal/web/booking && cp docs/tasks/1540-files/go/internal/web/booking/shell.go.txt go/internal/web/booking/shell.go
mkdir -p go/internal/web/booking/templates && cp docs/tasks/1540-files/go/internal/web/booking/templates/pp_booking_css.html.txt go/internal/web/booking/templates/pp_booking_css.html
mkdir -p go/internal/web/booking/templates && cp docs/tasks/1540-files/go/internal/web/booking/templates/shell.tmpl.txt go/internal/web/booking/templates/shell.tmpl
mkdir -p go/internal/web/booking/templates && cp docs/tasks/1540-files/go/internal/web/booking/templates/skeleton_detail.html.txt go/internal/web/booking/templates/skeleton_detail.html
mkdir -p go/internal/web/booking/templates && cp docs/tasks/1540-files/go/internal/web/booking/templates/terms.tmpl.txt go/internal/web/booking/templates/terms.tmpl
mkdir -p go/internal/web/booking/templates && cp docs/tasks/1540-files/go/internal/web/booking/templates/terms_cs.html.txt go/internal/web/booking/templates/terms_cs.html
mkdir -p go/internal/web/booking/templates && cp docs/tasks/1540-files/go/internal/web/booking/templates/terms_en.html.txt go/internal/web/booking/templates/terms_en.html
mkdir -p go/internal/web/booking/templates && cp docs/tasks/1540-files/go/internal/web/booking/templates/thanks.tmpl.txt go/internal/web/booking/templates/thanks.tmpl
```

Expected: no output. Commit `1540 step 1`.

### Step 2: check the files

```bash
sha256sum -c <<'EOT' 2>&1 | tail -15
880383ab2b22ccc88182b795adfb826e6699572842bddb119c1d18095a7a9f8d  go/cmd/ubyhost-web/register_web_booking_pages.go
c886bae9aa4af1cf6146d58677d75e8ab016dea4f93a80fb5dff574b5a178939  go/internal/web/booking/i18n.json
6ad2e2d048d567bd7034a1234af8bd6b9604b0535f15b6bc725d5ab7f076103f  go/internal/web/booking/i18n_keys.txt
f589ca5abf490ce2f7ce7f0bc68cb141098a9b96a7580a13f20e098294c7034b  go/internal/web/booking/pages.go
bf36b1e1967488147ca157fdeae6f56049a8f0a6f6133d79153007fb952df383  go/internal/web/booking/pages_test.go
c519323e5cbab24cbcaa56248903bd43f1f434f8c74bfd0b5c5c7ee9fc34985d  go/internal/web/booking/shell.go
271c98bbf92314bea02acec78ae7aeebcc85036e071fe8d2f69805542d5b411c  go/internal/web/booking/templates/pp_booking_css.html
1af5389071e13ae7129fd3e002e69488923161dddd583e13da153bec07647cc0  go/internal/web/booking/templates/shell.tmpl
eed5a2fbe3e4cf9f0d51ac51a0c88000ac226db3bc745276e8f47d4ab65d1ad4  go/internal/web/booking/templates/skeleton_detail.html
c3aefdc91bb80083bed19cc35c2ece9e38ee09b60dd8ccdd73d5b0f56d15700c  go/internal/web/booking/templates/terms.tmpl
a751fc2a295a458a3fe9bfbea7de14eaf539f0a2d53517f67b3a2ff39a810c8d  go/internal/web/booking/templates/terms_cs.html
4dab2d6e507477a977f008b7a37f9f6ff346651803f18fd9d3385c3bc508b7cd  go/internal/web/booking/templates/terms_en.html
4c9e5218110862a24607ef4740fdf904162eefc6698bb464b8025664c974f014  go/internal/web/booking/templates/thanks.tmpl
EOT
```

Expected: every line `OK`. A `FAILED`: copy that file again once; still failing: STOP (section 8). No commit.

### Step 3: write the string catalog

`i18n.json` is generated from `host_i18n.py`. Check it is current:

```bash
cd App && .venv/bin/python scripts/go_host_i18n.py --check 2>&1 | tail -5
```

Expected: no output. If it prints `stale: ...booking/i18n.json`, run `.venv/bin/python scripts/go_host_i18n.py 2>&1 | tail -3`, then `cd .. && git diff --stat | tail -3` must show only that file; commit `1540 step 3`. Anything else stale: STOP.

### Step 4: build, vet, format

```bash
cd go && go build ./... 2>&1 | tail -10 && go vet ./internal/web/booking/ ./cmd/ubyhost-web/ 2>&1 | tail -10 && gofmt -l internal/web cmd 2>&1 | tail -5
```

Expected: no output. No commit.

### Step 5: tests (section 6), then the report (section 9).

## 5. Do not touch

Everything not in section 3. Hard rules: no new dependency (standard library and the repo's own packages); never push to `main`; no secrets; no tracking cookie; light mode only.

## 6. Commands

```bash
cd go && go test -count=1 ./internal/web/booking/ ./cmd/ubyhost-web/ 2>&1 | tail -10
```

Expected: `ok` for both. With `UBYHOST_TEST_DATABASE_URL` set the existing booking database tests also run; without it they skip (these new tests need no database). Say in the report which you ran.

## 7. Acceptance

- [ ] `sha256sum -c` in step 2 printed only `OK`.
- [ ] `git log --oneline --grep='^1540 step' | tail -5` lists steps 1 (and 3 if it ran); `git show --stat --format=%s $(git log --grep='^1540 step 1' --format=%h -1) | tail -15` lists only section 3 paths.
- [ ] Both section 6 packages print `ok`.
- [ ] `grep -c 'registerRoutes' go/cmd/ubyhost-web/register_web_booking_pages.go` prints 1.
- [ ] Screenshots (rule 7): none taken by the executor; the page is checked in the pre-switch brief 1550.

## 8. Stop and ask

Stop, and write the report, if: a hash differs twice; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a new dependency seems needed; a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1540-report.md` (600 tokens at most) and set `Status: review`. The report has: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

- `go/internal/web/booking/shell.go`: `pageLang`, `writeGuest` (no cookie, buffered render), `newSet` (templates parsed per handler factory).
- `go/internal/web/booking/templates/shell.tmpl`: the markup must match `base.html` (scripts only from `/static/`).
- `go/cmd/ubyhost-web/register_web_booking_pages.go`: the two patterns.

## Owner steps

1. Nothing changes in production until paths are routed to Go. Do not add `/terms/booking` or `/p/*/thanks` to `UBYHOST_GO_PATHS` yet: brief 1550 lists the order for the whole booking site.
