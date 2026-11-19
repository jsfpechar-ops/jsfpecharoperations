# 1861: Port GET /reservations/{id} to Go, part 2: template, route, parity

Status: review
Depends on: 1860 | Base commit: the series branch after 1860's last commit | Branch: task/1860-1864-stay-page (series, see below)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (checkpoint at 60k)
Tier: A (guest data and filing status shown; the switch is 1864's owner steps)
1862 (owner's layout change) edits only `go/internal/web/staydetail/templates/stay_detail.tmpl` and waits for this brief.

> **Series mode (owner 2026-11-19).** One executor runs 1860, 1861, 1862, 1863, 1864 in that order on one branch, `task/1860-1864-stay-page` (created in 1860's series step 0), with no owner check in between. Commit each step as `1861 step k`, write `docs/tasks/1861-report.md`, set `Status: review`, then start 1862. Open no PR here (1864 opens the one PR). Never push to `main`, merge or deploy. Every command ends in `2>&1 | tail -30`. Anchors are quoted from the tip: if one is missing, STOP. At the cap: commit, write the report as `blocked`; a fresh session continues on the same branch. `git diff --stat origin/main` also lists the earlier series files: check that nothing outside the series' §3 tables changed.

## Open questions (orchestrator and owner; the executor does not decide these)

Questions 1 and 2 are resolved: kept below for the record. Only question 3 is open, and it does not block (step 6 already compares with live Python).

1. **Resolved by [1863](1863-go-stay-detail-post.md)** (Go serves the POST save; this brief still registers GET only). Original text: **POST /reservations/{id} (stay settings save) must be served by Go before the owner switch.** Decision, from the precedents: 1856 shipped `GET /reservations` with `POST /reservations` (`stays.CreateHandler`), and `GET /apartments/{id}` moved with `POST /apartments/{id}`. [ENVIRONMENT](../ENVIRONMENT.md) `UBYHOST_GO_PATHS`: Caddy sends every method of a listed path to Go and retries only GET/HEAD on 501, so a POST Go lacks answers 404 where Python would save; `scripts/go_parity_check.py` fails on it. Python `reservation_update` (`admin.py` ~4176-4223) ends with `reporting.submit_stay_if_complete(...)` (a filing trigger), `claim.expire_on_cancel(row)` and `alerts.resolve(...)`. No Go web equivalent of `submit_stay_if_complete` was found at the base commit (`go/internal/ubyport/sweep.go` has `SubmitForApartment`, the sweep job). That port is filing code (rule 1) and needs its own tier-A brief after a writer has read `reporting.submit_stay_if_complete`. **No number is free under this task's constraints (1860, 1861 used, 1862 reserved): the orchestrator assigns one (suggested 1863).** This brief registers GET only, which is safe while the path is off the list.
2. **Resolved by [1864](1864-go-stay-detail-switch.md)**: selector `/reservations/*[0-9]`; 1864 teaches both `caddy_match` functions Caddy's rule, tested against Go `path.Match`. Original text: **Caddy selector for "numeric id only".** Never `/reservations/*`: it is a prefix match and would send `POST /reservations/{id}/submit` and `POST /reservations/submit-ready` (filing) to Go. Caddy's `path` matcher uses Go `path.Match` for a pattern whose `*` is not at the end, so `/reservations/*[0-9]` would catch `/reservations/123` only (one segment ending in a digit). But the repo's tooling does not support `[...]`: `scripts/go_parity_check.py` and `App/tests/go_stack.py` (`caddy_match`: `re.escape(e).replace(r"\*", "[^/]*")`) treat it as literal text, and the runbook (wave P5) says "there is no Caddy token for numeric id only". Before the switch the owner must decide, and one tooling brief must teach both `caddy_match` functions character classes (verified against `caddy` itself). Until then the owner steps below are not run.
3. **Python goldens.** go-first allows Python golden output only for filing-data briefs. This page shows filing state, so this brief treats it as filing data and compares Go with live Python HTML (step 6). Confirm.

## 1. Objective

Serve `GET /reservations/{reservation_id}` from Go with HTML identical to Python's `reservation_detail.html` at every width (owner: the phone host app below 1024 px must look exactly as today). A live parity test and 390/768/1024/1280 screenshots prove it; the route stays dormant until the owner switch.

## 2. Context

Rules 1, 2, 6 (light only; every form works without JavaScript), 7, 9, 10. Python reference, READ-ONLY: `App/app/templates/reservation_detail.html` (407 lines; read with `sed -n 1,140p`, `141,280p`, `281,407p`). Anchors: line 1 `{% extends "host_page.html" %}`; `<div class="host-stay-detail">`; `<section class="stay-guests" id="guests">`; `<section class="stay-reports" id="reports">`; `<details class="card stay-filing ph-hide" id="file-by-hand">`; `<details class="card stay-settings ph-hide" id="stay-quick-edit">`. Page settings it sets: `v2 = true`, `nav = 'reservations'`, `how_key = 'stay'`, `body_kind = 'detail'`; title block `{{ reservation.internal_name }} · {{ reservation.date_from | date_cz }}`; blocks `page_title`, `back_url`, `back_label`, `meta`, `secondary_actions` are empty. It includes `_host_alerts.html` (Go: `layout.host_alerts` in `go/internal/hostweb/layout/shell.html`) and `partials/settings_back_header.html`, and uses from `_components.html`: `page_help, field_label, help_tip, progress_pill, submission_pill, row_menu_begin, row_menu_end, row_open, guest_count, deadline_badge, source_badge, v2_status_pill`; filters and globals: `date_cz, weekday, date_short, datetime_local, t, tp, nights, source_label, deadline_cell, link_window, identity_visible, display_birth_date, country_name, entered_by_label, validation_message, payments_hidden, havel_on, csrf_token, icon, urlencode`.

Go conventions to copy (read, never edit): `go/internal/web/stays/handlers.go` (`ListHandler` from `// ListHandler serves GET /reservations` to `func Register`; login guard, `layout.Render`, Nav), `go/internal/web/stays/tpl.go` (template funcs), `go/internal/web/stays/templates/stays_list.tmpl`, `go/internal/web/stays/i18n_test.go` (i18n key test). Registration file to copy exactly, `go/cmd/ubyhost-web/register_web_stays.go`:

```go
func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		stays.Register(mux, pool, os.Getenv, time.Now, m.wrap)
	})
}
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/staydetail/templates/stay_detail.tmpl` | new | block-by-block port of `reservation_detail.html`; file name fixed (1862 edits it) |
| `go/internal/web/staydetail/tpl.go` | new | parse with `layout.MustParse`, package-local funcs for any filter in §2 that `layout` lacks (ported verbatim from the Python filter) |
| `go/internal/web/staydetail/i18n.json`, `i18n_keys.txt`, `i18n_test.go` | new | every `t`/`tp` key the template uses, en/cs/vi copied from `App/app/host_i18n.py`; no new copy |
| `go/internal/web/staydetail/handlers.go` | new | `func Register(mux *http.ServeMux, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, wrap func(string, http.HandlerFunc) http.Handler, doorCodes ...DoorCodeViewer)` mounting only `GET /reservations/{reservation_id}` (1863 anchors on this signature's start and calls it with five arguments) |
| `go/internal/web/staydetail/handlers_test.go` | new | Go-only: no session redirects like Python; unknown or foreign id 404; fixed `View` renders the anchors in step 5 |
| `go/cmd/ubyhost-web/register_web_staydetail.go` | new | code in step 4 |
| `App/tests/test_1861_stay_detail_go_parity.py` | new | live Python-vs-Go HTML parity and screenshots. go-first exception 1 (parity test); no file under `App/app/` changes |

No other file may change. `docs/ENVIRONMENT.md` is not edited here (1864 documents the selector).

## 4. Steps

0. Anchors (one call): `ls go/internal/web/staydetail | tail -30` (expect the 1860 files, no `templates/`); `grep -nF 'func doorCodesSettings(getenv func(string) string) doorcodes.Settings' go/cmd/ubyhost-web/door_codes_wire.go; grep -nF 'func (systemClock) Now() time.Time' go/cmd/ubyhost-web/door_codes_wire.go; grep -nF 'type DoorCodeViewer interface' go/internal/web/staydetail/types.go` (one line each; the step 4 file needs them; the register file was vetted against a734a72f4 by the brief writer); `grep -rn 'web/staydetail\|"GET /reservations/{' go/cmd go/internal 2>&1 | tail -30` (expect none); `grep -n 'stay_detail\|stays' docs/context/test-map.md | tail -30` (the test-map rows used in §6); `grep -c 'settings_back_header\|v2_status_pill\|deadline_cell\|link_window\|row_menu_begin\|submission_pill\|help_tip\|field_label\|source_badge\|deadline_badge\|row_open\|page_help' go/internal/hostweb/layout/*.go go/internal/web/stays/tpl.go 2>&1 | tail -30`. Write in the report which §2 names `layout` or `stays` already provide.
1. Template: port the Python file block by block into `stay_detail.tmpl`, in the same order: phone back header and `sub-phone` lines, `card facts stay-dates`, `stay_cta` (exclusive branches, `data-fix-rejection`, `/submit` form with `_csrf` and `return_to`), `head`/`stay-head-actions`/row menu, status banners, demo banner, guests (desktop `guest-table` and phone `list guests guest-list`, placeholder rows), payments (renders nothing: `money_panels` is always empty), police card, `filed-by-hand`, `file-by-hand`, submissions table, door code, payment link, `stay-quick-edit` form posting to `/reservations/{{id}}`. Keep every class, id, `data-*` attribute, form action, hidden input and `ph-hide`/`ph-only`/`sub-phone` byte for byte; whitespace may differ. A `_components.html` macro or filter that `layout` lacks: port it verbatim into `tpl.go` or a `{{define "staydetail.*"}}` in the template. Command: `cd go && go vet ./internal/web/staydetail/... 2>&1 | tail -30`.
2. i18n: list the keys with `grep -o "t('[^']*'\|tp('[^']*'" App/app/templates/reservation_detail.html | sort -u | tail -80`, plus the dynamic ones (`stays.filter.state.<status>`, `guest.doc_type.<doc_type>`, `stay.detail.settings.state.<status>`, `send_controls.send_hint_key` values, `validation_message` keys). Copy en/cs/vi from `App/app/host_i18n.py`. `i18n_test.go` like `stays/i18n_test.go`. Command: `cd go && go test ./internal/web/staydetail/... 2>&1 | tail -30`.
3. `handlers.go`: copy the login guard, account lookup and `layout.Render` call from `stays.ListHandler`; Nav `reservations`, V2 on, title as §2. Parse `{reservation_id}` with `strconv.ParseInt`; bad or unknown id: 404 (Python `HTTPException(404)`). Build `Deps{Pool: pool, Getenv: getenv}` once in `Register`, with `DoorCodes: doorCodes[0]` when `len(doorCodes) > 0`. In the handler call `Build(r.Context(), deps, <owner id as stays.ListHandler gets it>, id, r.URL.Query().Get("return_to"), now())` (1860, `view.go`); `ok == false` answers 404. Register only `mux.Handle("GET /reservations/{reservation_id}", wrap("/reservations/{reservation_id}", ...))`. Never register POST here (1863 adds it).
4. `go/cmd/ubyhost-web/register_web_staydetail.go`, whole file:

```go
package main

// Brief 1861: the stay page (GET /reservations/{id}). It stays off until the
// owner adds a selector to UBYHOST_GO_PATHS; POST /reservations/{id} must be
// served by Go first (see docs/tasks/1861-go-stay-detail-page.md).

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/doorcodes"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/staydetail"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		staydetail.Register(mux, pool, os.Getenv, time.Now, m.wrap, stayDoorCodes(pool))
	})
}

// stayDoorCodes is the door-code service the stay page reads (door_codes.view),
// built like the door-code job's (door_codes_wire.go). It does not use the pool here.
func stayDoorCodes(pool *pgxpool.Pool) staydetail.DoorCodeViewer {
	keys, err := secure.LoadDataKeys(os.Getenv)
	if err != nil {
		return nil
	}
	return &doorcodes.Service{Pool: pool, Keys: keys, Settings: doorCodesSettings(os.Getenv), Clock: systemClock{}}
}
```

   Command: `cd go && go vet ./internal/web/staydetail/... ./cmd/ubyhost-web/... 2>&1 | tail -30; go test ./internal/web/staydetail/... ./cmd/ubyhost-web/... 2>&1 | tail -30`.
5. `handlers_test.go`: a fixed `View` (no DB) renders: `id="now"`, `id="guests"`, `id="reports"`, `id="stay-quick-edit"`, `action="/reservations/7"`, `action="/reservations/7/submit"` only when `SendControls.SendEnabled`, `id="file-by-hand"` only when `HandFiling.Candidates > 0` and the stay is active, `id="filed-by-hand"` only when `HandFiling.Count > 0`, no `<script src=` other than what `layout` adds. Same command as step 4.
6. Parity test `App/tests/test_1861_stay_detail_go_parity.py`: copy the skip marker, fixtures and login from `App/tests/test_1857_stays_go_append.py` and the seed helpers of `App/tests/test_0525_stay_detail.py`. Seed six stays: (a) active, 3 expected, one guest sent, one incomplete (placeholder row); (b) a guest `submit_state='error'` (fix CTA, send-again menu); (c) cancelled and archived; (d) the demo stay; (e) filed by hand inside the undo window; (f) door code issued. For each stay set `UBYHOST_GO_PATHS` (monkeypatch) to the exact path `/reservations/<id>` (exact entries match identically in Caddy and `go_stack.caddy_match`), fetch it once through Python and once through Go with the same session, take the inner HTML of `<div class="host-stay-detail">` and the `<title>`, normalise with `re.sub(r"\s+", " ", s).strip()` and replace the `_csrf` value with `X`, and assert equality. On failure print only the first differing 200 characters with guest names replaced by `<name>` (rule 3). Command from `App/`: `UBYHOST_GO_PATHS=/__go_test__ .venv/bin/python -m pytest tests/test_1861_stay_detail_go_parity.py -q --tb=short -x -rs 2>&1 | tail -30`, 0 skipped.
7. Screenshots, in the same test file: for stay (a) and (b) at widths 390, 768, 1024 and 1280, save Python and Go shots to `$UBYHOST_SHOTS_DIR/stay-detail/{py,go}-<stay>-<w>.png`. Open each Go shot once next to its Python shot; they must look the same (below 1024 px above all).
8. UX gate and test-map rows (§6), 0 skipped.

Hand-over point if capped: steps 0 to 5 are the Go side; 6 to 8 may continue in a fresh session on the same branch.

## 5. Do not touch

Every file under `App/app/` (templates included); every POST route, above all `POST /reservations/{id}/submit` and `POST /reservations/submit-ready` (never registered in Go by this brief); `go/internal/web/stays/`; `go/internal/ubyport/`; `go/internal/hostweb/layout/`; the 1860 files except to call them; Caddy files; `docs/ENVIRONMENT.md`; `UBYHOST_GO_PATHS` on any server. No new dependency, no new copy, no third-party script.

## 6. Commands

From `go/`: `go vet ./internal/web/staydetail/... ./cmd/ubyhost-web/... 2>&1 | tail -30`; `go test ./internal/web/staydetail/... ./cmd/ubyhost-web/... 2>&1 | tail -30`; `gofmt -l internal/web/staydetail cmd/ubyhost-web 2>&1 | tail -30` (empty).
From `App/`: step 6 command; the stay-detail and host-UI rows of the test-map found in step 0, at least `.venv/bin/python -m pytest tests/test_0525_stay_detail.py tests/test_0912_stay_detail.py tests/test_design_stay_detail.py -q --tb=short -x 2>&1 | tail -30` and `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_host_stay_detail_layout_browser.py tests/test_host_geometry.py tests/test_layout_lint_browser.py -q --tb=short -x -rs 2>&1 | tail -30` (0 skipped).
Root: `python3 scripts/go_parity_check.py --paths "/reservations/1" 2>&1 | tail -30` (expected to FAIL on `POST /reservations/{reservation_id}` until 1863: copy the line into the report). `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] Go vet, test and gofmt clean.
- [ ] Parity test: all six stays equal, 0 skipped.
- [ ] Python and Go screenshots of stays (a) and (b) at 390, 768, 1024, 1280 look the same; the report says per width what you saw (rule 10; 1864 copies it into the PR body) and ticks the [design-system checklist](../design/design-system.md).
- [ ] Browser rows: 0 skipped; layout lint: zero findings.
- [ ] `go_parity_check.py` output shows GET served and POST missing (expected until 1863).
- [ ] `git diff --stat origin/main` shows only §3 files, this brief's status line and the report.

## 8. Stop and ask

As [TEMPLATE](TEMPLATE.md) §8, plus: a `_components.html` macro needs a change in `go/internal/hostweb/layout`; the parity test differs in anything but whitespace and you cannot fix it inside `stay_detail.tmpl` or `tpl.go`; a step would register any POST.

## 9. Report

`docs/tasks/1861-report.md`, 600 tokens at most: files, each command's last 5 lines, §7 ticked, which §2 helpers came from `layout` and which were ported, the `go_parity_check.py` line, screenshot paths, deviations, questions.

## Risk list (for the reviewer)

`stay_detail.tmpl` (the `stay_cta` branches, `/submit` and `filed-by-hand` forms, `ph-hide`/`ph-only`), `handlers.go` (GET only, owner scope), `register_web_staydetail.go`, the parity test's normalisation (it must not hide real differences).

## Owner steps

None for this brief. The switch (with the before/after `curl` checks and the rollback that were here) is the owner steps of [1864](1864-go-stay-detail-switch.md), run once after the series PR is merged and deployed.
