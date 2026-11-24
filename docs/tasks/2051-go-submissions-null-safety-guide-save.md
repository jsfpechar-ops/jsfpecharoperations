# 2051: Go fixes (submissions NULL safety, guide card Save, Leon help placement)

Status: todo
Executor: Haiku 5.5, alone. Limits: 100k tokens, 30 tool calls. Read only AGENTS.md, docs/context/executor.md, this brief and the files named below.
Follows: 2041 classification (read-only). Branch: the branch you are on; do not push or merge.
Owner rules: UbyPort filing correctness first (rule 1: do not touch filing logic). Option 1: every Python function exists in Go and Go text equals Python text. The Go-only "External guide" card is ACCEPTED; do not touch it.

## 1. Objective

(a) CRITICAL: Go `/submissions` and `/submissions/{id}` answer HTTP 500 when a submission row has NULL `mode`, `guest_ids` or `record_errors`. Make them render like Python. (b) Port the secondary "Save" button on the guide card. (c) Put the Leon "?" help in the body like Python.

## 2. Context (verified in this checkout)

Schema (`App/migrations_pg/00001_baseline.sql`, `CREATE TABLE public.submission`): NULL-able text columns are finished_at, mode, guest_ids, header_errors, record_errors, pseudo_stamp, receipt_pdf, error_pdf, endpoint, request_xml, response_xml, error_text, retried_at, request_xml_enc. NOT NULL: id, apartment_id, created_at, state. Real filings always write mode, state, guest_ids, endpoint (`App/app/reporting.py` ~1815); older or hand-made rows can have NULL mode and guest_ids.

Unsafe scans (plain `string` receiving a possible NULL; pgx errors, handler answers 500), all in `go/internal/web/submissions/data.go`:
- `listSQL` (line 17) scanned at ~line 56: `s.mode` -> `&r.Mode`, `s.guest_ids` -> `&r.GuestIDs`.
- `detailSQL` (line 77) scanned at ~line 138: `s.mode` -> `&s.Mode`, `s.guest_ids` -> `&s.GuestIDs`, `s.record_errors` -> `&s.RecordErrors`.
Already safe in the same file: header_errors, pseudo_stamp, finished_at, error_text, endpoint, receipt_pdf, error_pdf (all `*string`); guest columns use COALESCE.

Python on NULL: `report_mode_label(None)` returns "" (`App/app/templating.py:413`); list guest count is `0` when guest_ids is NULL (`App/app/templates/submissions.html:56`); stamp shows an em dash. The Go helpers already handle empty strings: `reportModeLabel("")` returns "", `guestCountJSON("")` returns 0 (`go/internal/web/submissions/tpl.go:67,116`), and LoadDetail already skips empty `GuestIDs` and `RecordErrors`. So `COALESCE(x, '')` in SQL gives exactly Python's display.

Other Go readers of the same columns (audited; all NULL-safe except as noted, none changed here):
- Page paths, safe: `go/internal/web/exports/submissions.go` (pseudo_stamp, receipt_pdf, request_xml, response_xml all `*string`), `go/internal/web/staydetail/view.go:25` (COALESCE), `go/internal/palette/db.go:142` and `go/internal/web/auth/opspage/data.go:294` (only NOT NULL columns), `go/internal/web/exports/guest_json.go:118`, `go/internal/web/exports/housebook.go:290` (`*string`).
- Filing-job / ops paths, scan safely as `*string`: `go/internal/ubyport/notify.go:135` (NULL guest_ids returns no stays) and `go/internal/ops/reconcile.go:30-45` (NULL guest_ids makes `json.Unmarshal("")` fail and the row is skipped via `continue`). Report only; do not change (filing logic, rule 1).

Guide card (b): Python `App/app/templates/guest_guide_card.html:60-61` always renders two buttons: primary `guest_guide.save_next` with `name="then" value="next"`, then secondary `guest_guide.save` (plain submit, no `then`). Go `go/internal/web/ai/guide/templates/guide_card.tmpl:47` renders only one (`save_next` if `.HasNext`, else `save` as primary). The Go handler already supports save-without-advance: `go/internal/web/ai/guide_cards.go:155` reads `then`; it advances only when `then == "next"` (line 186) and otherwise redirects to the guide index with the saved flash (line 197). Both i18n keys exist in `go/internal/web/ai/guide/i18n.json` (`guest_guide.save`, `guest_guide.save_next`). No handler change is needed.

Leon help (c): Python (`App/app/templates/guest_guide.html:70-73`) opens the Leon section with title only and puts `help_tip('guide-leon-help', ...)` as the first line of the body. Go (`go/internal/web/ai/guide/templates/guide_index.tmpl:59`) passes the help_tip as the third argument of `guide_section_open` (next to the title).

## 3. Files (you may touch only these)

`go/internal/web/submissions/data.go`, `go/internal/web/submissions/null_rows_test.go` (new), `go/internal/web/ai/guide/templates/guide_card.tmpl`, `go/internal/web/ai/guide/templates/guide_index.tmpl`, one new test file `go/internal/web/ai/guide_save_buttons_test.go`, `docs/tasks/2051-report.md`.

## 4. Steps (one commit each: `2051 step k`)

### Step 1: NULL-safe list query (`go/internal/web/submissions/data.go`)
`grep -nF 's.apartment_id, s.mode, s.guest_ids, s.state,' go/internal/web/submissions/data.go`. Replace that one line's content
`const listSQL = `SELECT s.id, s.created_at, s.apartment_id, s.mode, s.guest_ids, s.state,`
with
`const listSQL = `SELECT s.id, s.created_at, s.apartment_id, COALESCE(s.mode, ''), COALESCE(s.guest_ids, ''), s.state,`
Do not change the Go scan. Check: `cd go && /usr/local/go/bin/go build ./internal/web/submissions/ 2>&1 | tail -30` (no output).

### Step 2: NULL-safe detail query
Anchor: `const detailSQL = `SELECT s.id, s.apartment_id, s.created_at, s.mode, s.state, s.guest_ids,` and the next line `       s.header_errors, s.record_errors, s.pseudo_stamp, s.finished_at, s.error_text,`. Replace the two lines with:
```
const detailSQL = `SELECT s.id, s.apartment_id, s.created_at, COALESCE(s.mode, ''), s.state, COALESCE(s.guest_ids, ''),
       s.header_errors, COALESCE(s.record_errors, ''), s.pseudo_stamp, s.finished_at, s.error_text,
```
Keep `s.header_errors` raw (it scans into `*string`; ubyport.Classify needs nil vs value). Check: the same build command.

### Step 3: Go tests with NULL rows (new file `go/internal/web/submissions/null_rows_test.go`)
Package `submissions`. Use `dbPool(t)` from `db_test.go` (skips without `UBYHOST_TEST_DATABASE_URL`). To seed an owner and apartment, copy the INSERT statements for `user_account` and `apartment` from the existing seeding in `visible_text_test.go` (`grep -n "INSERT INTO apartment" go/internal/web/submissions/*_test.go`; if none, STOP and ask). Then insert two submission rows with raw SQL:
`INSERT INTO submission (id, apartment_id, created_at, state) VALUES (9101, <apt>, '2026-11-01T10:00:00+00:00', 'ok')` (mode, guest_ids, record_errors, everything else NULL) and a second row with `state = 'error'` and `mode = 'test'`, `guest_ids = '[]'`.
Tests:
- `TestLoadListNullRows`: `LoadList(ctx, pool, owner)` returns no error, 2 rows, the NULL row has `Mode == ""`, `GuestIDs == ""`, `GuestCount == 0`.
- `TestLoadDetailNullRow`: `LoadDetail(ctx, pool, owner, 9101, "en")` returns no error, `ok == true`, `Submission.Mode == ""`, `len(Guests) == 0`, `len(RecordErrors) == 0`, `Submission.HeaderErrors == nil`.
Run: `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/layout_test /usr/local/go/bin/go test ./internal/web/submissions/... 2>&1 | tail -30` Expect `ok`. Do not revert steps 1 and 2 to prove the tests fail. Also confirm the golden test still passes in the same run (it is in the package).

### Step 4: guide card Save buttons (`go/internal/web/ai/guide/templates/guide_card.tmpl`)
`grep -nF 'guest_guide.save_next' go/internal/web/ai/guide/templates/guide_card.tmpl` finds line 47. Replace that whole line
`{{if .HasNext}}{{ui_button (t "guest_guide.save_next") "primary" (kv "type" "submit" "attrs" (safe `name="then" value="next"`))}}{{else}}{{ui_button (t "guest_guide.save") "primary" (kv "type" "submit")}}{{end}}`
with these two lines:
```
{{ui_button (t "guest_guide.save_next") "primary" (kv "type" "submit" "attrs" (safe `name="then" value="next"`))}}
{{ui_button (t "guest_guide.save") "secondary" (kv "type" "submit")}}
```
(Python always shows both; `.HasNext` stays in the Go struct, unused by this template.)

### Step 5: Save-without-advance test (new file `go/internal/web/ai/guide_save_buttons_test.go`)
`grep -n "func Test" go/internal/web/ai/guide_cards_test.go | head` and copy the setup of the closest existing card-render test and the closest existing card-save POST test (same helpers, same package). Add two tests:
- `TestGuideCardRendersBothSaveButtons`: GET the card page; body contains `name="then" value="next"` once and the `Save`/`Uložit` secondary button (class contains `ui-btn-secondary` or the class `ui_button` emits for secondary; read it from the rendered output, do not guess).
- `TestGuideCardSaveWithoutThenStays`: POST the card form with valid fields and no `then`; expect the redirect target to be the guide index (`.../guide`), not `.../guide/<other id>`.
Run: `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/layout_test /usr/local/go/bin/go test ./internal/web/ai/... 2>&1 | tail -30` Expect `ok`. A failing golden that mentions the card page: STOP and ask.

### Step 6: Leon help in the body (`go/internal/web/ai/guide/templates/guide_index.tmpl`)
`grep -nF 'guide_section_open "leon"' go/internal/web/ai/guide/templates/guide_index.tmpl`. Replace the line
`{{guide_section_open "leon" (t "guest_guide.leon.title") (help_tip "guide-leon-help" (t "guest_guide.leon.help"))}}`
with two lines:
```
{{guide_section_open "leon" (t "guest_guide.leon.title") ""}}
{{help_tip "guide-leon-help" (t "guest_guide.leon.help")}}
```
Change nothing else, in particular not the `external` section. Check: `cd go && /usr/local/go/bin/go test ./internal/web/ai/... 2>&1 | tail -30` (same env var as step 5).

### Step 7: rule 7 and 10 (template change)
From `App/` (env: `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/layout_test`, Go on `PATH=/usr/local/go/bin:$PATH`):
1. `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_go_pages_layout_lint_browser.py tests/test_layout_lint_browser.py -q -x -rs 2>&1 | tail -30` Expect passed, 0 skipped, zero findings. Known pre-existing failure to ignore: `test_design_guardrails_browser` tap-target-small on Python guest-new (do not run it unless it is in your output by accident).
2. Parity shots: `PARITY_GROUP=F PARITY_ONLY=guide-item-cs,guide-item-en,apt-guide-full-cs,apt-guide-full-en .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -30`. Expect guide-item rows `identical` (both buttons now present); apt-guide-full rows `accepted` or at most differing only by the accepted External card.
3. View the side PNGs: guide-item and apt-guide-full at 390, 768 and 1280 (max 6 reads; paths are listed at the end of the parity output). Write per page, in the report, one or two plain sentences of what you saw (both buttons side by side or stacked at 390? the Leon "?" is next to the help text, not the title?).

## 5. Do not touch

Anything under `App/`, filing code (`go/internal/ubyport/`, `go/internal/ops/`), `go/internal/web/exports/`, `go/internal/web/staydetail/`, the External guide card, i18n files, goldens, dependencies, secrets. No push, no merge.

## 6. Commands

Every step ends with its own command above. Never run the full Go suite or pytest suite.

## 7. Acceptance

- [ ] `data.go`: mode, guest_ids (list and detail) and record_errors (detail) wrapped in COALESCE; no other change
- [ ] new NULL-row tests pass (list and detail); the existing submissions golden test still passes
- [ ] guide card renders primary "Save and next card" plus secondary "Save"; POST without `then` stays on the guide index (tested)
- [ ] Leon "?" is the first line of the Leon section body
- [ ] layout lint browser tests green, 0 skipped
- [ ] 390/768/1280 PNGs of guide-item and apt-guide-full viewed; one description per page in the report

## 8. Stop and ask

Anchor not found; the apartment/user seeding helper is missing (step 3); a golden diff; a test fails twice; any NULL-unsafe scan you find outside the list in section 2 that sits on a filing-job path (report it, do not fix); a parity row other than the ones named is `visible`.

## 9. Report

`docs/tasks/2051-report.md`, 600 tokens at most: files changed, each command with its last 5 lines, section 7 ticked, per-page screenshot descriptions, Deviations, Questions, `Status: review`.

OWNER PRODUCTION CHECK (read-only, for the owner's server prompt; paste each into the production database prompt ; the Go fix is safe whatever the counts are):
```
SELECT count(*) FROM submission WHERE mode IS NULL OR guest_ids IS NULL;
SELECT count(*) FROM submission WHERE record_errors IS NULL;
```
Include both numbers in the report line "Owner production check" once the owner has them (the executor cannot run them).

Commit trailers:
```
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014N5J8NCpdqN2TbR61gYRQf
```

## 10. Orchestrator decision (after part 1, Option 1)

- **Step 4 (guide card Save buttons): do it.** Go renders one button chosen by HasNext, so a host on a card with a next card cannot save without advancing: a lost Python function. You may update `go/internal/web/ai/guide_cards_test.go` `TestGuideCardFormSaveButtons` (~line 217) so it asserts Python's behaviour (both buttons always, exact Python markup/classes/text) instead of the old single button. Then write the step 5 redirect test and run step 7 (layout lint browser test, screenshots of the guide card page at 390/768/1280, viewed).
- **Step 6 (Leon help placement): do NOT do it.** `TestGuideIndexLeonHelpInSectionHeading` shows Go's placement is deliberate and no function is lost; record it in the report as ACCEPTED (Option 1, look-only).
