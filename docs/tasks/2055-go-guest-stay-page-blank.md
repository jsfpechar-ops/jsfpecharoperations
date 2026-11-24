# 2055: CRITICAL: the Go guest stay page renders blank (stub template); port guest/stay.html

Status: todo
Depends on: none | Base commit: HEAD | Branch: current
Executor: Haiku 5.5 | Fits one session: 30 tool calls (stop at 25; commit after every step)

## 1. Objective

`GET /l/{token}/{reservation_id}` on Go returns a white page for a claimed stay. Python (`stay_overview`, `App/app/routes/guest.py:1482`) shows the party stepper or the people rows ("Person 1 not filled in"), progress, host card and footer. Make Go identical in structure and text (Option 1: Go equals the Python function and text). Guest registration (police data) correctness first.

## 2. Context (orchestrator finding, verify in step 1)

- Route: `go/internal/web/guest/stay_claim.go:83` `GET /l/{token}/{rest...}` -> `dispatchGET` (line 86) -> `stayOverview` (line 152).
- Last line of `stayOverview` (about line 208): `renderGuestPage(w, "stay", lang, claimPage{...})`. `renderGuestPage` (line 336) executes the in-file `guestTemplates` (line 328), whose `stay` (and `assigned`, `confirm`, `unavailable`, `claim`) templates are PLACEHOLDERS: `<body class="guest-stay"></body>`. Status 200, empty body. This is the blank page. It is not the harness cookie.
- `assigned` at stay_claim.go:194 is the same stub (shown when mail is on and the device does not hold the claim). It is in scope: port `guest/assigned.html` too.
- Real pages use `guestAccess.renderPage(w, r, <set>, <view>, headers)` (`pages.go:101`) with `pageSet(...)` (pages.go:20) and a view embedding `Page` (see `claimView`, `claimSet`, `renderClaimPage` at stay_claim.go:350 for the pattern). Templates live in `go/internal/web/guest/templates/*.tmpl`; text keys come from `go/internal/web/guest/i18n.json`.
- Python template to port: `App/app/templates/guest/stay.html` (162 lines) and `assigned.html` (58 lines). Python view data: `_person_row` (guest.py:1153), `_duplicate_warnings` (1199), `_guide_is_live` (1473), `_fee_pay_panel` (2904), `door_codes.view`, `reporting.reservation_progress`.
- Go helpers that exist: `formPagesProgress`/`liveFormGuests`/`formPagesOwnedIDs` (form_pages.go:549/565/830), `headcount.Expected`, `validation.GuestIsComplete` (go/internal/validation/validation.go:497), `purposeLabel` (`go/internal/validationi18n/purpose.go:37`), `ubyport.CountryName` (go/internal/ubyport/request.go:289), `pickNightsLabel`, `mintGuestPageCSRF`, `hostMessageURL` (shared.go:78), `ai.LeonProgressOf(...).Live` (go/internal/web/ai/leon_facts.go:187) for guide_live, `doorcodes` (go/internal/doorcodes). Python `reporting.guest_is_complete`, `guest_form_locked`, `guest_filed_by_hand` must be matched: read the Go counterparts before writing (grep, step 3).
- Missing text keys: the 68 keys listed in 2056 section 4 are absent from `i18n.json`. 2056 adds them. THIS brief needs the stay and assigned keys: `add_another add_person all_done_body all_done_body_fee all_done_receipt all_done_title assigned_body assigned_last_sent assigned_not_mine assigned_resend assigned_stay_label assigned_title continue_filling door_code_failed door_code_first_use door_code_preparing door_code_sent door_code_times door_code_title edit filed_short form_locked_short not_filled party_confirm people_progress removed_ok remove_person reported_body reported_title saved_body saved_title someone_missing stay_dates still_missing summary_fold_saved summary_title tw_email_more tw_email_short`. Add them here for ALL six languages (en cs de es fr uk) by copying values from Python: `cd App && .venv/bin/python` -> `from app import i18n, guest_uk_i18n`; `i18n.STRINGS[lang][key]`, and for `uk` `guest_uk_i18n.STRINGS` overrides. Write them with a throwaway script OUTSIDE the repo (scratch dir) that loads `go/internal/web/guest/i18n.json`, inserts the keys, and dumps with `ensure_ascii=False, indent` matching the existing file (check `head -c 300` first and keep the same indentation/sort). Placeholders: Python `{n}` style equals what Go `stringsCatalog.T` expects (compare `person_progress` in both). 2056 skips keys already added.

## 3. Files

| Path | Action |
|---|---|
| `go/internal/web/guest/templates/stay.tmpl` | new (port of stay.html) |
| `go/internal/web/guest/templates/assigned.tmpl` | new (port of assigned.html) |
| `go/internal/web/guest/stay_claim.go` | edit `stayOverview` tail + the assigned call; remove the two stub `{{define}}` lines only when no caller is left (`grep -n 'renderGuestPage' go/internal/web/guest/*.go`; remove any stub whose name has no caller) |
| `go/internal/web/guest/pages.go` | add `staySet`, `assignedSet` next to `claimSet` |
| `go/internal/web/guest/stay_view.go` | new: `stayView`, person rows, duplicate warnings |
| `go/internal/web/guest/i18n.json` | add the keys above, six languages |
| `go/internal/web/guest/stay_page_test.go` | new DB-backed test |
| `docs/tasks/2055-report.md` | report |

## 4. Steps

1. DIAGNOSE (one command, 3 calls max; no repo change). The harness records status but discards the Go log (`scripts/e2e/page_parity_audit.py:243` `stdout=DEVNULL`). Run the one case at 390, then fetch the Go response yourself:
```
cd /home/user/jsfpecharoperations && source scripts/e2e/parity_env.sh && cd App && PARITY_GROUP=H PARITY_ONLY=g-stay-claimed,g-stay-claimed-nocookie PARITY_WIDTHS=390 .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -15
```
Expected: rows `g-stay-claimed-cs 390 visible`. Then prove the cause without servers: `grep -n 'guest-stay' go/internal/web/guest/stay_claim.go | tail -3` must print the stub line (`<body class="guest-stay"></body>`). That equals "Go writes status 200 with an empty body": harness cookie is NOT the cause. How to tell: the `nocookie` case is blank too and the stub body has no content for any cookie. If instead the grep finds NO stub, STOP and report (the cause is elsewhere: then run a scratch Go binary outside the repo: `go build -o /var/tmp/ubyhost-web-scratch ./cmd/ubyhost-web` from `go/`, start it with the env that `start_go` builds at page_parity_audit.py:229-243 plus `> /var/tmp/go-scratch.log 2>&1`, request the URL with `curl -s -D - -o /var/tmp/body.html <url>` and read `tail -30 /var/tmp/go-scratch.log`; do not start Python servers). Write the finding in the report.
2. Add the i18n keys (section 2). Verify: `python3 -c "import json;d=json.load(open('go/internal/web/guest/i18n.json'));print([len(d[l]) for l in sorted(d)])" 2>&1 | tail -3` increases by the same number in all six languages.
3. Read `App/app/templates/guest/stay.html` in two ranges of 90 lines and write `templates/stay.tmpl` as `{{define "content"}}`-style per `claim.tmpl` (read `claim.tmpl` header and `base.tmpl` first: `grep -n 'define\|block\|template' templates/claim.tmpl templates/base.tmpl | head -20`). Every Jinja branch becomes the same Go branch, same classes, same order, same text keys. Ported pieces: back link (`can_pick_other`), dates + `nights_label`, `party_error`, `just_removed`, fee panel (`_fee_pay.html`: if Go has no equivalent partial, STOP and ask: do not drop it silently), party question stepper (`expected is none`: input `party_size`, `data-guest-stepper`, hidden `_csrf`), all-done block with `another` form and door code card, saved card, progress bar (`(100*filled/expected)` rounded), still-missing, add-person link, duplicate warnings, mine-people `<details>` rows, others rows, guide link when live.
4. Write `stay_view.go`: build the view in `stayOverview` exactly like Python lines 1531-1585: guests ordered `is_lead DESC, id`; people index from 1; `mine` = id in `formPagesOwnedIDs`; `complete` via the Go complete check used by form_pages (find it: `grep -n 'GuestIsComplete\|guestComplete' go/internal/web/guest/*.go | head`); `locked`, `sent` (`submit_state = 'sent'`), `removable = mine && !sent && restricted_at empty`; summary fields as `_person_row` (birth date display, nationality via CountryName, doc_number blank when `INPASS`, purpose label, residence). `remaining = expected - filled` (filled = count of complete or filed-by-hand guests, NOT row count). Keep the existing redirect to `/new` when there are no people (stay_claim.go:202-206, Python 1544-1549). `guide_live` from `ai.LeonProgressOf` over the guide items (same query `guide_page.go` uses). `host_message_url` via `hostMessageURL`. `door_code`: use the same Go source the host stay-detail uses (`go/cmd/ubyhost-web/register_web_staydetail.go:27 stayDoorCodes`); if it cannot be called from package guest without an import cycle, STOP and ask.
5. Port `assigned.html` to `assigned.tmpl` (kicker, property name, city, dates, `claim_error` text via existing `claimErrorText`, resend form with hidden `resend=1`, `party_size`, email field, tw hints, privacy link, turnstile as in `claim.tmpl`, not-mine link) and render it from stay_claim.go:194 through `renderPage` with `assignedSet`. Reuse `renderClaimPage`'s view building (copy, do not refactor).
6. Replace both `renderGuestPage(...)` calls with `d.access().renderPage(...)` and header `Cache-Control: no-store` (as renderClaimPage). Then `cd go && go build ./... 2>&1 | tail -30`.
7. Test (new file `stay_page_test.go`, package guest): copy `testPool`/`mustExec` usage from `stay_claim_test.go:132-150` and the seeding from `csrf_forms_test.go:95` (apartment + active reservation). Seed a claimed claim row with `declared_guests = 2` and ONE complete-or-partial guest owned by the cookie (use the same cookie helper as `stay_claim_cookie_test.go`), request `GET /l/{token}/{id}` through the registered mux. Assert: status 200; body contains the people progress text for en (`people_progress` with done/total), `Person 1` row text, the `still_missing` text for 1, `data-guide-link` absent when the guide is not live, host card id `host-contact`, and the `g-btn` add-person link. Second test: reservation with NO declared count and one guest -> body contains `data-guest-stepper` and `name="party_size"`. Third: zero guests -> 303 to `/new`. Run:
```
cd /home/user/jsfpecharoperations/go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/layout_test go test ./internal/web/guest/ -run 'Stay|Claim|Assigned' -count=1 2>&1 | tail -30
```
Expected: `ok`, no `SKIP`.
8. Parity rerun and screenshots (rule 7): `cd App && PARITY_GROUP=H PARITY_ONLY=g-stay-claimed,g-stay-claimed-nocookie,g-stay-provisional PARITY_WIDTHS=390,768,1280 .venv/bin/python ../scripts/e2e/page_parity_visual.py 2>&1 | tail -15` (after `source scripts/e2e/parity_env.sh`). Expected: `invisible` or `identical`. Open the 390 side PNG of `g-stay-claimed-cs` once. Also run `cd App && .venv/bin/python -m pytest tests/test_guest_*.py tests/test_guest_browser_e2e.py -q -rs --tb=short -x 2>&1 | tail -30` ONLY if Python files changed: they must not, so skip it; run the Go browser/geometry tests for guest pages named in `docs/context/test-map.md` row "Go page ports" (`grep -n 'Go page' docs/context/test-map.md`) with 0 skipped.
9. Commit per step (`2055 step k`), trailer lines per executor rule. Report: include the step-1 evidence line, the Go test output, the 390 screenshot path.

## 5. Do not touch

`App/app/**`, `scripts/e2e/**` (unless step 1 proves the harness is the cause: then fix only the harness cookie code and say so), `go/internal/web/guest/form_*.go`, `leon_*.go`, other pages. Fee and door-code logic must reuse existing Go code, not reimplement.

## 6. Commands

The commands in steps 1, 6, 7, 8. Never the full Go or Python suite.

## 7. Acceptance

- [ ] Step-1 evidence recorded (stub proven or cause named).
- [ ] The Go test passes with 0 skips and asserts stepper and person rows.
- [ ] `g-stay-claimed` and `-nocookie` rows are not `visible` at 390/768/1280, cs and en.
- [ ] One 390 px screenshot of the page in the report.

## 8. Stop and ask

An anchor not found; no Go fee partial; door code not callable; more than 25 tool calls (commit, report `Done: steps 1 to k`).

## 9. Report

`docs/tasks/2055-report.md`, 600 tokens at most.
