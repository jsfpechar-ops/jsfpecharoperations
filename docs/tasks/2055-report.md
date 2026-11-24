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

## Chunk A (run 4)

Status: partial. Item (2) done; item (1) not started (executor tool cap reached).

- Commit `6399f9f` (step 2, completeness): `go/internal/web/guest/stay_view.go` `stayPeople` now selects `signature_png` and passes it as `SignaturePNG` to `validation.GuestIsComplete`. Python `guest_is_complete` = `guest_issues` (validate_guest + `guest_signature_issue`, allow_imported=True, under-15 exemption). Go `validation.GuestIssues` already implements that rule; the stay page was the only path that left the signature out. New DB test `go/internal/web/guest/stay_people_signature_test.go` (no signature = incomplete, signed = complete, filled = 1).
- Item (1) door-code card: NOT done. Remaining steps for the next run:
  1. Add `doorCodes` (interface with `ViewForStay(ctx, reservationID, apartmentID int64) (*doorcodes.Shown, error)`, as `staydetail/types.go` DoorCodeViewer) to `stayClaimDeps` in `go/internal/web/guest/stay_claim.go` (struct ~line 46). Constructor at `stay_claim.go:81`; second literal at `go/internal/web/guest/party.go:409`. Wire the `*doorcodes.Service` in `go/cmd/ubyhost-web/` the way `register_web_staydetail.go:32` builds it.
  2. In `stayOverview` (`stay_claim.go:152`) call `ViewForStay`, pass the result through `renderStayPage` (`stay_view.go:126`) into `stayView`, and render a `#door-code` card in `go/internal/web/guest/templates/stay.tmpl` after the people section.
  3. States, from Python `App/app/templates/guest/stay.html:67-83`: `issued` shows PIN, times, first-use deadline; `failed` shows the failed text; any other state shows the preparing text. Go `Shown` states are `issued`, `failed`, `preparing`, `waiting`, `delayed`; `waiting` and `delayed` map to the preparing text.
  4. One DB or render test per state.
- Verification run in this worktree:
  - `go build ./...`: passes.
  - `go test -v -count=1 ./internal/web/guest/... ./internal/doorcodes/...`: doorcodes, doorcodes/cleaning, doorcodes/wire pass. 0 skipped. `guest` package has 3 failing tests, all from the same cause: `apartment_owner_user_id_fkey`. `TestConfirmClaimAppliesDeclaredGuests`, `TestStayOverviewMailOnHonorsClaimCookie`, `TestConfirmClaimRace` insert apartments with owner_user_id 1, and `layout_test` has no `user_account` row 1. These tests used to skip because the schema was not migrated. Not caused by the step 2 change. Fix belongs to Chunk C item 8 (migrate `layout_test` via the Go helper and seed the owner).
- Deviations:
  - Item (1) not done (see above).
  - `layout_test` is partly migrated from my attempt to call `migrateGuestPool` in the new test. That helper is not idempotent (baseline re-run failed on `ubyhost_invoice_delete_guard`). I removed the call. The owner or Chunk C must reset or finish that DB.
  - Test fixtures follow the stored formats: `birth_date` is `DDMMYYYY` text, purpose code `03`.

## Chunk A2 (run 4, item 1: door-code card)

Status: done. Item (1) only; item (2) was already in commit `6399f9f`.

- Commit `1ca03e3` (step 1, wiring): `stayClaimDeps` gets `doorCodes DoorCodeViewer` (exported interface, `ViewForStay`); `RegisterStayClaim` takes it as a last argument; `go/cmd/ubyhost-web/register_web_guest_stay_claim.go` passes `stayDoorCodes(pool)` (the same service staydetail uses). `party.go` unchanged: its gate literal only calls `pinRedirect`.
- Commit `cf34b53` (step 2, render): `stayOverview` calls `ViewForStay` and passes `*doorcodes.Shown` to `renderStayPage` into `stayView.DoorCode` (`stay_view.go`, `doorCodeCardFrom`). `stay.tmpl` renders `#door-code` in the all-registered branch (remaining <= 0), after the big-ok card, as Python does (`stay.html:66-80`).
- States and Python conditions: `issued` shows PIN (`g-door-code`), times (`door_code_times`), first-use line only when `FirstUseBy` is set (not for custom codes), sent line only when `ClaimEmailMasked` is set. `failed` shows `door_code_failed`. Anything else (`preparing`, `waiting`, `delayed`) shows `door_code_preparing`. `nil` (Python `None`) hides the card.
- Tests: `go/internal/web/guest/stay_door_code_test.go` (`TestDoorCodeCardStates`, `TestDoorCodeCardRender` with 8 subtests, one per state plus hidden cases). These are unit tests that render `staySet`, with no DB.
- Test callers: `csrf_forms_test.go`, `party_claim_start_test.go`, `pick_http_test.go` pass `nil` for the new argument.
- Verification (fresh DB `guest_test`): `go build ./...` passes in `go/`. `go test ./internal/web/guest/... ./internal/doorcodes/... ./cmd/ubyhost-web/...` passes, including `TestConfirmClaimAppliesDeclaredGuests`, `TestStayOverviewMailOnHonorsClaimCookie` and `TestConfirmClaimRace`.
- Deviations: a `ViewForStay` error is logged and the card is hidden, so the page still renders (Python would return 500). The door-code CSS (`.g-door-code`) and the 390 px screenshot were not checked; they belong to Chunk C item 8.

## Chunk B (run 5)

Status: partial. Items (a), (c), (d), (e) done; (b) not done.

- `42fbebe` (a) Turnstile on the assigned resend form: `assigned.tmpl` draws the `cf-turnstile` widget and loads api.js only when `RequireTurnstile && TurnstileSiteKey`, as Python `require_turnstile and turnstile_site_key`. The server check on the resend POST already existed (`party.go`, guest_claim, `claim_error=bot`) and is unchanged. Without JS the form still posts its fields; the widget is inert, as in Python. Unconfigured or non-production: the widget is hidden and `turnstile.Verify` passes, as Python. Test: `go/internal/web/guest/assigned_turnstile_test.go`.
- `39b5be6` (e) birth date on stay rows: `validation.DisplayBirthDate` matches Python `display_birth_date` (normalise, DD.MM.YYYY, else stripped value). Test: `go/internal/validation/birth_display_test.go`.
- `4be9b9a` (c) guide link: `stay.tmpl` shows `g-guide-link` (`data-guide-link`) when `GuideLive`, set from `ai.LeonProgressOf(items).Live`. A store error hides the link only. Test: `go/internal/web/guest/stay_guide_link_test.go` (render only; the DB items path is not covered).
- `8d58337` (d) assigned last-sent line: `claimLastSent` takes MAX(sent_at) over `claim` and `claim_resend` in `email_outbox` and renders `assigned_last_sent`. Python applies `date_cz` to a datetime; Go uses the DB session date. Test: `go/internal/web/guest/assigned_last_sent_test.go`.
- (b) duplicate warnings: NOT done. `formPagesDupWarnings` (`form_pages.go`) is a stub returning nil, and the guest `i18n.json` has no `dup_what_doc` / `dup_what_person` keys (Python: `App/app/i18n.py`). Needs its own run.

Verification (`UBYHOST_TEST_DATABASE_URL` = guest_test):
- `go build ./...` passes. `go test ./internal/web/guest/... ./internal/turnstile/... ./cmd/ubyhost-web/...` and `./internal/validation/` pass.
- Skips, not caused by Chunk B: `TestConfirmClaimRace`, `TestConfirmClaimAppliesDeclaredGuests`, `TestStayOverviewMailOnHonorsClaimCookie`, `TestStayPeopleSignatureCompleteness` skip with "needs migrated Postgres schema" on guest_test. Belongs to Chunk C item 8.
- `TestDoorCodesJobIssuesCodeThroughHandler` failed once in a combined run, then passed alone. Probably DB sharing between packages; not investigated.
- No 390 px screenshots or layout lint in this chunk (Chunk C).

Deviations:
- Commit trailers use Co-Authored-By Claude Haiku 5.5, the attribution given by the harness, not Opus 5.5 as the brief text said.
- `gofmt` realigned struct and literal fields in `stay_view.go`.

## Chunk B2 (duplicate warnings)

Status: review. Item (b) done in Go; browser and geometry checks for the stay page not run (see below).

- `35302fe` detection: `go/internal/web/guest/dup_warnings.go` ports `guest.py _duplicate_warnings`. A guest is flagged when it is owned by this device and another live guest in the stay has the same document number (`_doc_key`: upper case, A-Z and 0-9 only, INPASS and empty never match) or the same first name, surname and birth date (`_person_key`). Output is `Name: what`, with `what` = "document number" and/or "name and date of birth", joined by ", " in that order. `formPagesDupWarnings` (was a nil stub) now loads the stay's guests. Test: `dup_warnings_test.go` (TestDupWarningsFor: doc-only, person-only, both, other person's duplicate not shown, non-duplicate, INPASS).
- `8c9798f` stay page: `stayView.DupWarnings` is set in `renderStayPage`; `templates/stay.tmpl` draws the `data-dup-warning` block before the person summaries, as stay.html. Form page (`form_content.tmpl`) already drew the block for mode "new", as form.html. Test: TestStayDupWarningRender.
- `(step 3)` i18n: added `dup_what_doc` and `dup_what_person` to cs, de, en, es, fr, uk with Python's strings. `dup_warning_title` and `dup_warning_body` were already present and identical to Python in all six.

Pages that show the block: stay.html (new in Go), form.html new-guest form (existing Go call, now real detection).

Verification (`UBYHOST_TEST_DATABASE_URL` = guest_test): `go build ./...` passes. `go test ./internal/web/guest/... -v` passes. Skips: 4, the same as before (TestConfirmClaimRace, TestConfirmClaimAppliesDeclaredGuests, TestStayOverviewMailOnHonorsClaimCookie, TestStayPeopleSignatureCompleteness). No new skips.

Owner or orchestrator steps left:
- Rule 7/10 for the stay.tmpl change: run `test_layout_lint_browser.py` for the stay page, take a 390 px screenshot, and write what was seen in the PR. Not done in this chunk.

Deviations:
- Commit trailer: Co-Authored-By Claude Haiku 5.5, the attribution given by the harness, not Opus 5.5 as the brief text said.
- Title-casing of names uses a letter-boundary rule that matches Python's str.title() for ordinary names; exotic Unicode case edge cases were not checked.

## Chunk C (run 6)

Status: blocked (tool-call cap reached at 25; steps for layout lint, server and screenshots not run).

- Done: `go/internal/web/guest/stay_page_test.go` (DB-backed, claimed stay, 2 declared, 1 signed, shared doc number). Migrated `guest_test` with `App/scripts/pg_schema.py apply --expect-database guest_test` (76 tables, goose 24) and seeded `user_account` id 1 in `guest_test`.
- Test result: `TestStayPageClaimedDeclaredTwoOneDone` FAILS on `data-dup-warning` not found. Not diagnosed. Stepper, "saved", "not filled in" and the hidden door-code card passed.
- Guest package with DB: 0 skipped. 4 failures: the new test plus `TestConfirmClaimAppliesDeclaredGuests`, `TestConfirmClaimRace`, `TestStayOverviewMailOnHonorsClaimCookie`. The three older tests were skipped before the migration and now run. They insert `reservation` without `uid` (NOT NULL), so they fail against the real schema. Fix belongs in those tests (not edited per brief).
- `TestDoorCodesJobIssuesCodeThroughHandler` (in `./cmd/ubyhost-web`): 5 of 5 alone pass; 2 of 2 in the full run pass.
- Left: layout lint (item 8), Go server start, 390/768/1280 screenshots of stay and assigned pages, guide link assertion (not in test), door-code issued state test, owner steps: fix the three `uid` tests and the dup-warning assertion.
