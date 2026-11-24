# 2055 report

Status: blocked (stay hub partly ported, see Deviations)
Branch: claude/nice-hawking-fw98ct (worktree agent-a9b76ed763c737e2e)
Commits: `9c5467e 2055 step 2` (i18n keys), `ecca932 2055 step 3` (stay.tmpl, assigned.tmpl), `d2ee36f 2055 step 4 to 6` (stay_view.go, stay_claim.go wiring, pages.go sets, stay_view_test.go).

## Step 1: diagnosis (partial)

- Confirmed by grep: the stay and assigned pages are stubs. `go/internal/web/guest/stay_claim.go:331` is `{{define "stay"}}...<body class="guest-stay"></body>...{{end}}`, and line 330 is the matching `assigned` stub. `renderGuestPage` (line 336) executes them, so the response is 200 with an empty body. This is the blank-page cause.
- The parity harness run (`page_parity_visual.py`, PARITY_ONLY=g-stay-claimed,g-stay-claimed-nocookie, 390) was denied by the auto-mode permission classifier. It was not run, so the harness row results are unknown.

## Step 2: text keys (done)

- 38 keys added to `go/internal/web/guest/i18n.json` for cs, de, en, es, fr, uk, with Python's exact strings (uk includes the `guest_uk_i18n` overrides). Keys added per language: 38. Totals after: cs 318, de 318, en 316, es 316, fr 316, uk 316. cs and de already held 2 extra keys before this step. File format kept (indent 1, sorted keys).

## Not done (steps 3 to 9)

- Step 3 (`templates/stay.tmpl`) is blocked by brief section 8. The Python stay page includes `guest/_fee_pay.html`. The guest Go package has no equivalent partial (grep for fee_pay/feePay finds only `go/internal/web/stayfees/pagetemplates/stay_fees.tmpl`, a different page). Decision needed from the owner or orchestrator: port the fee panel from stayfees, or write a new guest partial.
- Steps 4 to 5 (`stay_view.go`, `assigned.tmpl`): not started.
- Steps 6 to 8 (wiring, Go test `stay_page_test.go`, parity rerun, 390 screenshots, browser tests): not run.
- Step 9: this report only.

## Deviations

- The brief's step 1 harness command was denied, so the stub was proven by grep only.
- The committed i18n change does not cover the template keys I have not checked yet (for example `dup_warning_title`, `message_host`, `guide_title`). Check them in step 3.

## Owner or orchestrator steps left

- Decide the fee-panel port (see step 3).
- Allow the parity harness command, or run step 1 and step 8 manually.

## Steps 3 to 8 (run 2, per brief section 10)

- Step 3 done: `templates/stay.tmpl` and `templates/assigned.tmpl`. Fee panel not ported (decision 10).
- Step 4 done: `stay_view.go` (`renderStayPage`, `stayPeople`, `renderAssignedPage`). Keys checked: all 38 template keys present in all six languages (cs 318, de 316, en 318, es 316, fr 316, uk 316 after step 2 numbers as recorded; the 2 extra cs/en keys predate this brief).
- Step 6 done: `stayOverview` calls the new renderers; `stay` and `assigned` stubs removed from `guestTemplates`. `go build ./...` clean.
- Step 7: the DB test `stay_page_test.go` was not written. Replaced by `stay_view_test.go` `TestStayTemplatesRender` (no DB): renders stay (claimed, stepper, all done) and assigned, asserts stepper, progress bar, still-missing, person rows, edit link, resend form.
- Step 8: parity harness not run (decision 10). Go guest package with DB: `ok`, but 3 tests SKIP (`TestStayOverviewMailOnHonorsClaimCookie`, `TestConfirmClaimRace`, `TestConfirmClaimAppliesDeclaredGuests`) because layout_test has no migrated `apartment` table. These skips are environmental, not from this change.
- `test_go_pages_layout_lint_browser.py`: 6 passed, 0 skipped.
- Screenshots (390 px, rendered by the test to HTML, opened as file://, so NO CSS): `/tmp/claude-0/-home-user-jsfpecharoperations/fddd852d-eb27-56de-8c5b-4ff23a59b41e/scratchpad/2055-shots/stay-claimed-390.png` (heading, "Registered: 1 of 2", "Still to register: 1", "Add a person", "Anna Test - saved", "Person 2 - not filled in"; text order matches Python) and `.../assigned-390.png` (kicker and property, dates, "This reservation is already assigned", masked e-mail, e-mail field, resend button, host footer). Layout geometry is not verified because of the missing CSS.

## Not ported (stay.html / assigned.html)

- Python `dup_warnings` block: not ported.
- `door_code` card (`#door-code`): not ported; stayDoorCodes not called.
- `guide_live` link: not ported.
- Fee panel: not ported (decision 10).
- assigned: `claim_last_sent_at` line, turnstile widget and script not rendered; property name uses Page.Facility; city from apartment.CityEn.
- `icon('check')` replaced by `&#10003;` (approximation).

## Deviations

- Done: steps 1 to 6 and the browser test. Left: door-code card, duplicate warnings, guide link, DB-backed stay test (`stay_page_test.go`), 390 px screenshots with CSS, parity rerun.
- birth date shown as stored (no display formatting); residence is a plain join; completeness uses validation.GuestIsComplete with the fields the query loads (signature not loaded), so `complete` may differ from Python's `guest_is_complete` for some guests. Needs a check before merge.
- Filled count = complete or filed (Python `filled` also counts filed-by-hand; approximated by submit_state).
- Stay status is not `Locked` from `guest_form_locked` beyond sent or restricted.

## Owner or orchestrator steps left

- Decide whether door-code, dup-warning and guide-link ports go to a follow-up brief.
- Confirm the three skipped Go tests run on the migrated DB.

## Follow-up 2 (run 3, brief section 11)

- Merge of `origin/claude/nice-hawking-fw98ct`: commit `4f52d54`. Conflicts in `go/internal/web/guest/i18n.json` resolved by keeping both sides' keys. JSON valid, no duplicate keys in any object.
- Item 6 (completeness and parity): commit `d27fb41`. Go `validateResidence` now emits the non-Latin message when the raw street or city was typed but cleaned to nothing, as Python `validate_residence` does. Test `residence_raw_test.go` passes. `go test ./internal/validation/` ok.
  - Python `validate_guest` checks: surname, first_name (incl. warning), birth_date, nationality, doc_number (note when INPASS, czech child rule), visa_number, residence (street, city, country), purpose, forbidden characters in 7 fields, note length, stay_to after stay_from; plus signature via `guest_signature_issue`.
  - Go `validateGuest` checks: the same list. Only the residence raw-input message differed (fixed).
  - Not ported: Python's "Home address is too long" branch. It is unreachable because the composed value is cut to 255.
  - Still open: the Go stay page builds `complete` from the fields the query loads (signature not loaded). Python `guest_is_complete` may differ for some guests. Birth-date display formatting vs Python filter not checked.
- Item 1 (door-code card): NOT DONE. Findings: Go `doorcodes.Service.ViewForStay` (`go/internal/doorcodes/view_stay.go`) exists and is used by `go/internal/web/staydetail`. The guest `stayClaimDeps` (`go/internal/web/guest/stay_claim.go:46`, constructed at `stay_claim.go:81` and `party.go:409`) has no door-code dependency. Wiring needs a DoorCodes field and a constructor parameter from `go/cmd/ubyhost-web`. `stay.tmpl` has no `#door-code` block. Needs its own run.
- Items 2, 3, 4, 5, 7, 8: NOT DONE (budget). Not started.
- Tests run: `go test ./internal/validation/` ok. Guest DB tests and layout lint not re-run in this run. The 3 skipped guest DB tests from run 2 are still open.
- Screenshots: none taken in this run.
