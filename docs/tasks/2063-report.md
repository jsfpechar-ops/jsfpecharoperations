# 2063 report

Status: blocked (acceptance incomplete: DB render and key tests, browser tests, screenshot; commands green)
Done: steps 1 to 5 (step 5 partly). Left: step 5 DB render test and key test, step 6 PR and screenshots.

## Commits

- 57fdd05 2063 step 3: stay_fee_panel.go (buildFeePanel, loadFeePanel).
- 9305152 2063 step 4: stay_view.go (FeePanel field, loaded when Remaining <= 0, "not ported" comment removed), stay.tmpl (fee block after JustRemoved; all_done_body_fee), templates/_fee_pay.tmpl, pages.go.
- 2063 step 5: stay_fee_panel_test.go (TestBuildFeePanel, 7 subtests, pass); partial renamed to templates/fee_pay.tmpl.

## Commands (last lines)

- go build ./internal/web/guest/ and go vet: clean.
- go test -run TestBuildFeePanel: PASS, 7 subtests.
- go build ./...: build=0. go test guest, stayfee, ubyhost-web: test=0, SKIP lines=3.

## Not done

- DB render test (TestStayPageFeeBox) and key test (TestFeeKeysAllLanguages): not written (tool cap).
- Browser and geometry tests (section 6, line 67): not run. Screenshot: not taken. No PR opened.

## Deviations

- Partial named fee_pay.tmpl, not _fee_pay.tmpl: go:embed skips underscore-prefixed files, so pageSet panicked at init.
- Commit trailers: the brief asks for Claude Opus 5.5; the report's commit steps used the brief's trailers.

## Owner steps left

None yet. Brief 2063 needs the DB render test, key test, browser tests and screenshot before merge.

## Session 2 (step 5 tests)

Status: review (TestStayPageFeeBox/on_all_in fixed; all guest, stayfee and web packages green)

Session 3 (brief 2063 test fix, executor):
- Cause: the fee box fixture set declared_guests only on reservation_claim. The stay page reads it from the reservation row (pick_data.go), so the page stayed on the party step.
- Fix: stay_fee_box_test.go now also sets reservation.declared_guests. No product code changed.
- Commit: b52c13f (step fix: seed reservation.declared_guests in fee box fixture).
- Test run: go build ./... clean. TestStayPageFeeBox PASS (on_all_in, off, guest_missing). Packages guest, stayfee, cmd/ubyhost-web: ok.
- SKIP lines: TestJobRunProbe, TestRouteProbe, TestJobProbe (cmd/ubyhost-web, probe tests that skip without their env). No FAIL lines.
- Not done: browser and geometry tests, screenshot, PR (unchanged from session 2).
Done: steps 1 to 5 (step 5: TestBuildFeePanel passing; TestFeeKeysAllLanguages passing; TestStayPageFeeBox written in stay_fee_box_test.go). Left: fix on_all_in, browser and geometry tests, screenshot, PR.

- Test run: TestStayPageFeeBox/on_all_in FAIL ("fee box missing with guest pay on"); /off PASS; /guest_missing PASS. TestFeeKeysAllLanguages PASS.
- Diagnosis: LoadCompletionFee returns a non-nil fee for the fixture, so the loader is fine. The rendered page shows "Person 1 saved" and the party form, not the all-done state, so FeePanel is never loaded. Likely the headcount Expected/leadReduced rule or the guest fixture (is_lead) in renderFeeBox. Not resolved.
- Deviation: the new tests are in go/internal/web/guest/stay_fee_box_test.go, not stay_fee_panel_test.go.
- Owner steps left: none yet.
