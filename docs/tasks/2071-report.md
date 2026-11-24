# 2071 report

Status: blocked

Branch: claude/nice-hawking-fw98ct (fast-forwarded to origin, HEAD f1f0c10 before this work). Not pushed.

## Files changed

- `go/internal/web/guest/form_save.go`: new-guest save now refuses an empty `legal_ack` (`legal_ack` issue) and, when no expected total exists, a `party_size` outside 1–60 (`party_size` issue). Both are added before the existing localization and 422 branch. Two English message constants were added above `handleGuestFormSave`. The 2065 completion hooks, 2069 save gates and 2070 encryption are unchanged.

## Commands

- `gofmt -l internal/web/guest/form_save.go`: no output.
- `go vet ./internal/web/guest/`: no output.
- `go build ./...` (in `go/`): no output, clean.
- `go test ./internal/web/guest/ -run 'FormSave|Party' -count=1 -v` with `UBYHOST_TEST_DATABASE_URL` set: `ok ... 0.595s`. PASS: TestFormSaveGoldenShape, TestFormSaveRoutePattern, TestFormSaveAccess, TestPartyStartClaimMailOn, TestPartyMailEnabledConsoleBackend, TestPartyGoldenHTTP. Skips: 0.

## Steps

- Step 1 (notice and party size): done, commit `99911e1`. The new 422 checks have no test yet (step 4 not done).
- Step 2 (extract the `applyDeclared` transaction helper in `party.go`): not done.
- Step 3 (count and guest in one transaction in `insertGuestSaveRow`): not done.
- Step 4 (`TestGuestSaveNoticeAndHeadcount`): not done.

## Section 7 acceptance

- Missing notice returns the 422: implemented, untested.
- Count and guest share one transaction: not done.
- Two concurrent final-slot saves: not done.

## Deviations

- The brief's anchors were re-anchored on the current file. `legal_ack` and `party_size` checks are now in `handleGuestFormSave`, not `guest.py`-style lines.
- The English messages are duplicated from `go/internal/guestcontract/check.go`, because its constants are unexported. Exporting them would be a change outside brief section 3.
- The executor tool budget was reached after step 1. Done: steps 1 to 1. Left: steps 2 to 4.

## Questions

- Should the guestcontract messages be exported so `form_save.go` does not repeat them?

## Owner steps left

- None yet. A fresh session should continue from step 2.
