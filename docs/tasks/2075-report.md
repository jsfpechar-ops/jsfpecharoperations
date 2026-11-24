# 2075 Report: File the completed stay immediately

Status: review

## Files changed

- `go/internal/ubyport/completion_submit.go` (added): `SubmitCompletedStay` matching `App/app/reporting.py:1152-1197`.
- `go/internal/web/guest/form_save.go` (edited): `guestFormSubmitStayIfComplete` delegates to `ubyport.SubmitCompletedStay`; dropped `scheduler` import.
- `go/internal/web/stays/guest_edit.go` (edited): `guestSubmitStayIfComplete` delegates to `ubyport.SubmitCompletedStay`; dropped `scheduler` import; kept `guestSaveDecrypter`.
- `go/internal/web/stays/edit_posts.go` (edited): `editSubmitStayIfComplete` delegates to `ubyport.SubmitCompletedStay`; dropped `scheduler`, `secure`, and `editSaveDecrypter`.
- `go/internal/web/staydetail/filing.go` (edited): `submitStayIfComplete` delegates to `ubyport.SubmitCompletedStay` with `submitCompletedStayOpts`; dropped `enqueueJob` and `saveDecrypter`.
- `go/internal/web/staydetail/post_test.go` (edited): updated save filing tests to inject `submitCompletedStayOpts` and assert stay-scoped filing with 0 global submit jobs.
- `go/internal/ubyport/completion_submit_test.go` (added): `TestSubmitCompletedStay` covering two-stay isolation, empty-scope guard, all gates, receipt write, failure alert, auth-pause follow-up, and concurrent/repeat duplicate protection.

## Commands

- `rg -n 'scheduler\.Enqueue|enqueueJob' go/internal/web/guest/form_save.go go/internal/web/stays/guest_edit.go go/internal/web/stays/edit_posts.go go/internal/web/staydetail/filing.go` -> 0 matches.
- `cd go && test -z "$(gofmt -l .)"` -> exit 0 (clean).
- `cd go && go vet ./...` -> exit 0 (clean).
- `cd go && go test ./internal/ubyport/ -run 'TestSubmitCompletedStay|TestGoldenEnvelopes|TestPlanOutcome|TestSweep' -count=1 -v` -> `PASS`, 0 skipped (`ok ... 5.764s`).
- `cd go && go test ./internal/web/guest/ -run 'TestLead|TestAfterLeadChange|TestFormSave|TestGuestSave|TestGuestWriteEncryption' -count=1 -v` -> `PASS`, 0 skipped (`ok ... 2.417s`).
- `cd go && go test ./internal/web/stays/ -run 'TestEditPosts|TestQuickEdit|TestRegisterEditPosts|TestGuestWriteEncryption|TestGuestEditGoldenHTTP|TestGuestLifecycleGoldenHTTP' -count=1 -v` -> `PASS`, 0 skipped (`ok ... 0.561s`).
- `cd go && go test ./internal/web/staydetail/ -count=1 -v` -> `PASS`, 0 skipped (`ok ... 2.239s`).
- `cd go && go test ./... -count=1` -> `PASS`, all packages green.
- `python3 scripts/context_lint.py` -> `context lint: OK`.

## Acceptance (§7)

- [x] `ubyport.SubmitCompletedStay` matches `App/app/reporting.py:1152-1197`: refreshes completion before mode/auth gates, requires `immediate`, honors `ubyport_auth_failed:<apt>`, verifies active non-archived stay belonging to the apartment, guards empty `OnlyGuestIDs`, files via `NewSweepDeps` + `SubmitForApartment(..., "completion_immediate")` with `IgnoreSchedule=true`, and raises `submission_immediate` warning on failure without failing the write.
- [x] All four web wrappers (`guest/form_save.go`, `stays/guest_edit.go`, `stays/edit_posts.go`, `staydetail/filing.go`) call `ubyport.SubmitCompletedStay` with zero direct global `scheduler.Enqueue(..., "submit")` calls; hook order and redirects remain intact.
- [x] `TestSubmitCompletedStay` passes with 0 skipped: two-stay isolation (`cSurN == "StayA"`, Stay B stays `pending`, `submission.mode == "completion_immediate"`, `STAMP-2075`/`PDF-2075`), empty-scope guard (Stay B stays `pending`), all 7 gates, `submission_immediate` warning alert, `ubyport_auth_failed` follow-up block, and 2 concurrent + 1 sequential call sending 1 guest / 1 submission row.
- [x] Golden envelopes, `staydetail`, `guest`, `stays`, full `go test ./... -count=1`, `go vet ./...`, `gofmt`, and `python3 scripts/context_lint.py` all pass.

## Deviations

- In `TestSubmitCompletedStay`, checked guest map key `"cSurN"` (the `GuestFields` map key passed to `Sender.Submit` before XML serialization to `prijmeni`).
- Used a separate fixture apartment for the `ErrAuth` subcase in `failed send raises submission_immediate warning safely` so the preceding unexpected-error crash's unclosed submission did not mask the auth-error call.

## Questions

None.

## Owner steps

1. Open/review after 2074 is included.
2. Review fake-sender scope, empty-`OnlyGuestIDs` guard, and concurrent duplicate-protection evidence above.
