# 1381: Go layout shell data: alerts, billing banner, Havel, security prompt

Status: todo
Depends on: 1380 (draft PR #985, stacked) | Base commit: fe42cc4 | Branch: task/1381-go-layout-alerts
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: A (host alerts carry the filing warnings, Appendix 5 §10.4(2))

## 1. Objective

Finish `go/internal/hostweb/layout` so Go host pages can go live: port the host alert stack (`alerts.open_alerts`, `shell_slice`, `present_many`, `_host_alerts.html`), `_billing_banner.html`, `_havel_panel.html` with `havel_on` and the panel state, the security prompt and the celebration toast. Add the #985 review fixes (safe hrefs, slot order, CSRF cookie 30 days) and the small API items the page threads asked for.

## 2. Context

All code is pre-written and dry-run green: gofmt, go vet, `go test -race` for hostweb/... and calendar, the DB test against Postgres 16, both generator `--check`s, the two pytest files and the context lint. It is in `/home/user/1381-prewritten/` with the repo's relative paths and a `MANIFEST.sha256` (27 files). You copy it in and verify. Do not edit any file.

The 1380 API is unchanged. Additions (never rename):

```go
// Page, added in 1381
HideAlertStack, AlertsExpanded, PhHidePin bool  // hide_alert_stack, alerts_expanded, ph_hide_pin
CelebrationMilestone string; SentGuestCount int // routes fill these in Python; "" shows no toast
func Lang(r *http.Request, host *session.Host) string  // the language Render resolves (Page.Lang still wins in Render)
func ParseFuncs(cat hostweb.Catalog, funcs template.FuncMap, fsys fs.FS, patterns ...string) (*Templates, error) // page funcs; a layout name is an error
func MustParseFuncs(...) *Templates
// template funcs: seq n | seq a b (range), add, sub, default "d" .V (nil or "" -> d), billing_on
// calendar (new file): type AlertStay, AlertProgress; AlertProgresses(ctx, pool, getenv, stays, at); AlertProgressNoGuests(stay)
```

- Reads, all read-only and parameterised: `shellSQL` (one row: workspace, property count, account e-mail and prompt columns, both billing rows), `openAlertsSQL` (alerts LEFT JOIN the stay and the feed property, `ORDER BY created_at DESC, id DESC`, then a stable sort by level), one guest read for the alert stays (`calendar.loadGuests`, per stay only when one guest will not decrypt), and only while Havel is on one `rate_limit_event` count (no prune DELETE). At most 4 queries per page.
- Empty `Page.Title` with a `<name>.title` slot: `<title>` is the slot's text.
- `go_host_i18n.py` learns `prefix.*` lines; `i18n_keys.txt` lists `notification.*`, `billing.banner.*`, `security_prompt.*`, `havel.topic.*` and single keys.
- Golden: 9 cases. New: `alerts_dashboard_cs` (`/`: every alert, filing `submission_rejected`, overdue `deadline`, job_failed, trial banner with warning, celebration, Havel composer, security prompt), `alerts_invoices_en` (compact page, slice to criticals + 12, folded kinds, overdue banner, Havel `limit_week`), `alerts_reservations_scope` (`?apartment=` scope, `ph_hide_pin`, canceling banner), `property_err_minutes0` (`?sec=bank&err=E`, MinutesLeft 0, one inline alert with its action), `v2_alerts_hidden`, `visitor_cenik` (`/cenik?lang=vi&msg=x&toast_kind=error&fix=nope`). The golden page now calls every ported `ui_*` macro. The Go test also fails on a raw i18n key in the output.
- #985 fixes: `safeHref` on every macro-built href (non http/https/mailto schemes become `#ZgotmplZ`), slots rendered in a fixed order, package doc lines on `csrf` and `safe` (trusted HTML only), `csrfMaxAge` 30 days (`auth.SESSION_REMEMBER_MAX_AGE`).

## 3. Files

| Path | Action | What |
|---|---|---|
| go/internal/hostweb/layout/alerts.go | create (555 lines) | open_alerts SQL, shell_slice, present_many, _host_alerts logic |
| go/internal/hostweb/layout/shelldata.go | create (264) | billing banner, Havel gate/limits/topics, security prompt |
| go/internal/hostweb/layout/pagefuncs.go | create (88) | Lang, ParseFuncs, MustParseFuncs, seq/add/sub/default |
| go/internal/hostweb/layout/href.go | create (46) | safeHref |
| go/internal/hostweb/layout/shelldata_test.go | create (237) | unit tests for the above |
| go/internal/calendar/alert_progress.go | create (94) | exported reservation_progress for alert stays |
| go/internal/hostweb/layout/layout.go | edit (720) | Page fields, shell fields, shellSQL, loadShell, view, slot order, docs, CSRF age |
| go/internal/hostweb/layout/funcs.go | edit (161) | new funcs, getenv on reqCtx |
| go/internal/hostweb/layout/macros_ui.go | edit (595) | hrefs through safeHref |
| go/internal/hostweb/layout/macros_components.go | edit (612) | hrefs through safeHref |
| go/internal/hostweb/layout/shell.html | edit (553) | billing banner, alerts, celebration, Havel panel, security prompt |
| go/internal/hostweb/layout/i18n_keys.txt | edit (224) | 1381 keys |
| go/internal/hostweb/layout/i18n.json | edit (1181) | generated |
| go/internal/hostweb/layout/layout_test.go | edit (533) | golden inputs, raw-key check, DB test of the real queries |
| go/internal/hostweb/layout/testdata/golden_page.html | edit (35) | every ui_* macro |
| go/internal/hostweb/layout/testdata/golden_cases.json | edit (1852) | generated |
| go/internal/hostweb/layout/testdata/legacy_en.html | edit (513) | generated |
| go/internal/hostweb/layout/testdata/v2_cs_impersonating.html | edit (495) | generated |
| go/internal/hostweb/layout/testdata/nonav_vi.html | edit (308) | generated |
| go/internal/hostweb/layout/testdata/alerts_dashboard_cs.html | create (682) | generated |
| go/internal/hostweb/layout/testdata/alerts_invoices_en.html | create (613) | generated |
| go/internal/hostweb/layout/testdata/alerts_reservations_scope.html | create (613) | generated |
| go/internal/hostweb/layout/testdata/property_err_minutes0.html | create (549) | generated |
| go/internal/hostweb/layout/testdata/v2_alerts_hidden.html | create (470) | generated |
| go/internal/hostweb/layout/testdata/visitor_cenik.html | create (415) | generated |
| App/scripts/go_layout_golden.py | edit (374) | 1381 cases, alerts.db stand-in, pinned clock |
| App/scripts/go_host_i18n.py | edit (75) | `prefix.*` lines |
| docs/tasks/1381-report.md | create | your report |

No other file may change.

## 4. Steps

1. Verify the bundle: `cd /home/user/1381-prewritten && sha256sum -c MANIFEST.sha256 2>&1 | tail -30`. All 27 lines `OK`. A missing bundle or a FAILED line: STOP (§8).
2. Copy it in, from the repo root: `cp -r /home/user/1381-prewritten/go /home/user/1381-prewritten/App . && git status --short | tail -30`. It shows only the §3 paths (` M` for edits, `??` for new files). Then `sha256sum -c /home/user/1381-prewritten/MANIFEST.sha256 2>&1 | tail -30`: all 27 `OK`. Commit `1381 step 2`.
3. Generated files are current. From `App/` (venv if missing: `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt`): `.venv/bin/python scripts/go_host_i18n.py --check 2>&1 | tail -30; echo rc=$?` and `.venv/bin/python scripts/go_layout_golden.py --check 2>&1 | tail -30; echo rc=$?`. Both `rc=0`, no other output. No commit.
4. §6 command 1, then from `go/`: `go build ./cmd/ubyhost-web 2>&1 | tail -5; rm -f ubyhost-web` (no output).
5. §6 commands 3 and 4. Write the report (§9), commit `1381 step 5`.

## 5. Do not touch

Every other file in `go/internal/calendar/` (only the new `alert_progress.go`), `go/internal/hostweb/*.go`, `go/cmd/` (no routes), every Jinja template, `App/app/`. Hard rules: 1 (filing), 3 (no secrets; the golden and DB test keys are test strings), 4 (no new dependency: stdlib + pgx only), 8 (never push or merge).

## 6. Commands

1. `cd go && test -z "$(gofmt -l .)" && go vet ./internal/hostweb/... ./internal/calendar/ && go test -count=1 -race ./internal/hostweb/... ./internal/calendar/ 2>&1 | tail -30` → three `ok` lines (hostweb, hostweb/layout, calendar).
2. Optional DB test (the orchestrator ran it green on Postgres 16): `UBYHOST_TEST_DATABASE_URL=postgres://... go test -count=1 -run ShellQuery -v ./internal/hostweb/layout 2>&1 | tail -5` → `PASS`. Without the variable it skips; CI decides.
3. `cd App && .venv/bin/python -m pytest tests/test_go_layout_golden.py tests/test_go_host_i18n.py -q --tb=short -x 2>&1 | tail -30` → `3 passed`.
4. `python3 scripts/context_lint.py 2>&1 | tail -5` → `context lint: OK`.

No browser or screenshot tests: no page is served by Go yet (no route).

## 7. Acceptance

- [ ] `sha256sum -c` all 27 OK; `git diff --stat fe42cc4` lists only §3 files.
- [ ] Both generators `--check` exit 0.
- [ ] §6 commands 1, 3 and 4 as expected; `go build ./cmd/ubyhost-web` clean.

## 8. Stop and ask

Stop, and write the report, if:

- the bundle is missing or a checksum fails;
- a generator `--check` reports a stale file (main moved: the orchestrator regenerates and ports the change);
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1381-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risks

- **Deliberate deviations from Python** (documented in code): an unreadable guest on a `deadline`/`headcount_mismatch` stay makes Python raise (the page 500s and hides every filing warning); Go keeps the card with the stored English detail. A visitor on a fresh install without accounts gets no system alerts (Python shows them). An unparseable `trial_ends_at` or `signup_at` shows no banner/prompt (Python raises). `created_at` ties break by `id DESC` (Python: undefined). Havel counts skip the prune DELETE (same numbers).
- **Golden coverage gaps**: alert stays in the golden have no guests (`AlertProgressNoGuests`); progress with guests and the decryption fallback are covered by the DB test only. The passkey branch of the security prompt is unit-tested, not golden (golden base URL is an IP).
- `calendar/alert_progress.go` uses calendar's unexported `progress`, `anchorDate`, `loadGuests`; a later change there changes alert cards too (intended: one rule).
- Not ported, by design: `onboarding.progress` (no shell template reads it; pages pass their own), `open_alerts` for page bodies (dashboard ports call the package themselves later), `havel_on` override from a route context.
- Drift: any edit of `_host_alerts.html`, `alerts.py` presentation, `_havel_*.html`, `base.html` or a `notification.*` string fails `test_go_layout_golden.py` until regenerated and ported. Intended.
- `stored_params` values: JSON bool prints `True`/`False`, lists/dicts print Go-style (no stored kind uses them today).

### Risk list (for the reviewer)

All of `alerts.go`, `shelldata.go`, `calendar/alert_progress.go`, `href.go`, the `layout.go` diff (shellSQL, loadShell, buildView) and the new `shell.html` defines, against `App/app/alerts.py` (open_alerts, shell_slice, present_many, _present_*), `_host_alerts.html`, `billing_trial.banner`, `templating._havel_*`/`_security_prompt`, `havel.limit_state` and `base.html`.

## Owner steps

None for this PR beyond review and merge with `scripts/merge-pr-on-green.sh` after #985, once CI is green.
