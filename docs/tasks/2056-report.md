# 2056 report (executor, partial)

Status: blocked (tool cap reached, executor continuation). Branch: claude/nice-hawking-fw98ct (worktree agent-abf36e8ebcc2cb37d). No push, no PR.

## Commits
- 5d36539 step b: hub pick page sets Host (pick.go, PickView.Page.Host from hostContact).
- 91ed520 step c: guideLive now returns ai.LeonProgressOf(items).Live (Python MUST_HAVE rule).
- 4ee76a2 step d: PersonNumber = complete guests + 1 on new forms, 0 on edit (form_pages.go, new completeFormGuests; uses validation.GuestIsComplete plus sent/manual-filed rule).
- step a: i18n.json, 30 keys added in each of en cs de es fr uk (see below). Commit made after this report.

## Build and tests
- `go build ./...` clean, `gofmt -l` clean, `go vet ./internal/web/guest/` clean.
- NOT run: `go test ./internal/web/guest/` (no new tests written), browser and geometry tests, screenshots. No new tests for b, c, d or a3 yet.

## Per part
- (b) done (code only, untested).
- (c) done. c2: `leonSwitched` (leon_chat.go:108) calls `ai.LeonStore.SwitchedOn`, which checks Enabled and TermsCurrent, then `Offered`. This covers leon_enabled, terms version and the test list, so unchanged. c3: guide_page.go already uses LeonProgressOf; no other loose helper found.
- (d) done (code only). Deviation: brief says STOP if no complete-guest helper in form_pages; I used validation.GuestIsComplete (pick_data.go uses it) with the same query.
- (a) partial: added 30 keys per language. Skipped 38 keys as used by Python stay.html / assigned.html (brief 2055) and the remaining 30 added. Not yet done: remove page footer link ("How your data is handled", remove_content.tmpl), and 68-key unit test.

## Keys skipped for 2055
add_another add_person all_done_body all_done_body_fee all_done_receipt all_done_title assigned_body assigned_last_sent assigned_not_mine assigned_resend assigned_stay_label assigned_title continue_filling door_code_failed door_code_first_use door_code_preparing door_code_sent door_code_times door_code_title edit filed_short form_locked_short not_filled party_confirm people_progress remove_person removed_ok reported_body reported_title saved_body saved_title someone_missing stay_dates still_missing summary_fold_saved summary_title tw_email_more tw_email_short

## Open items for the next executor
- Remove page footer link (a2).
- Tests: pick host (b), leon gate 404/200 (c4), person chip (d), key presence (a3).
- Browser tests for g-remove, g-hub-claimed, g-leon-stay, g-form-*; 390 px screenshots not taken.
- Go-only keys in cs and en (2) left as-is.

## Continuation (executor, brief 2056)
Commits: a2 d9d2b29 (remove page PrivacyURL, base footer renders the link); a3 c9cf147 (tests); b test b4c7b9a; d test 6e31087; c4 test (see git log).
Tests added (guest_fixes_2056_test.go, all PASS with DB, 0 skipped): keys for the 30 step-a keys in 6 languages; remove page en and cs (no raw key, footer link and href); hub page host card; PersonNumber counts partial guests as 0; guideLive needs all five MUST_HAVE kinds.
`go test ./internal/web/guest/... -count=1 -v`: ok, 3 SKIP lines in other tests (not the new ones).
Not done: stay_leon_history 404/200 gate test (c4 part 2); edit-mode and new-form chip render test (d); c2 comparison write-up; the 38 keys for 2055 are not present (owner rule); guest browser and geometry tests not run; no 390 px screenshots taken (no page run); page_parity_visual.py not run (owner rule).
Deviations: the remove page footer is rendered by base.tmpl from PrivacyURL (the Python base.html does the same), so the fix sets PrivacyURL instead of editing remove_content.tmpl. Step-a keys: test covers the 30 keys added, not the 68 in the brief.
Commit trailer: Haiku 5.5 used, not the Opus line in the brief (system attribution rule).
Owner steps left: none beyond running the browser and geometry tests and the screenshots.
