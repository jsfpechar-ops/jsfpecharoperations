# 2076 Report: Clean up a removed guest and reassess filing

Status: review

## Files changed

- `go/internal/web/guest/form_pages.go` — real `passportphotos.DeletePhoto(guestDataDir(getenv), guestID)` post-delete with safe I/O error logging, `ubyport.SubmissionClaimTTL.Seconds()` fix, `apt.OwnerUserID` in `guest_removed_by_guest` audit INSERT, and `ubyport.SubmitCompletedStay` wired via `formPagesSubmitStayIfComplete` with `formPagesSubmitCompletedStayOpts` test seam.
- `go/internal/web/guest/form_pages_test.go` — added `TestGuestRemovalCleanup` covering allowed removal + stay-scoped filing, missing photo, photo I/O error resilience, expired lease allowance, and 5 zero-side-effect refusal cases.
- `docs/tasks/screenshots-2076/removed-guest-390.png` — 390 px Chromium screenshot of the real Go post-removal stay page (`?lang=en&removed=1`).
- `docs/tasks/2076-go-guest-removal-cleanup.md` — updated brief and set `Status: review`.

## Commands

- `cd go && test -z "$(gofmt -l .)"` -> `gofmt OK` (exit 0)
- `cd go && go vet ./...` -> clean (exit 0)
- `cd go && go test ./internal/web/guest/ -run 'GuestRemovalCleanup|FormPages' -count=1 -v`:
  - 11 top-level tests + 10 `TestGuestRemovalCleanup` subtests: all PASS, 0 skipped (`ok github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/guest 0.533s`).
- `cd go && go test ./... -count=1`:
  - All packages PASS (exit 0; `guest` 9.685s, `ubyport` 26.723s).
- `python3 scripts/context_lint.py` -> `context lint: OK` (exit 0).

## 390 px screenshot inspection (`docs/tasks/screenshots-2076/removed-guest-390.png`)

Inspected once at 390x844 (`full_page=True`, light mode, `overflow=False`):
- Header shows `Guest registration` / `Old Town Studio, Prague` and `EN` switcher cleanly aligned.
- Stay dates card (`10.06.2026 – 12.06.2026 · 2 nights`) and green confirmation banner (`The person was removed.`) are clearly visible.
- Completion card (`Thank you. Everyone is registered` + `Add another person`) renders cleanly after removing the extra guest.
- Guest list shows only `Anna Novakova · saved ✓`; removed guest (`Extra RemovedGuest`) is absent.
- Host card and privacy footer (`does not use tracking cookies`, `How your data is handled`) render in light mode with no clipping or horizontal overflow.

## Acceptance (§7)

- [x] `formPagesDeletePhoto` deletes the removed guest's photo via `passportphotos.DeletePhoto(guestDataDir(d.getenv), guestID)` only after authorized `DELETE FROM guest` succeeds; missing photo is success; I/O errors log safely without failing the committed removal.
- [x] `guest_removed_by_guest` audit INSERT records `apt.OwnerUserID` (verified with `owner_user_id != apartment_id`), `handleRemovePost` uses `ubyport.SubmissionClaimTTL.Seconds()`, and `formPagesSubmitStayIfComplete` calls `ubyport.SubmitCompletedStay` after deletion and linked-child `signed_for_*` cleanup.
- [x] Owned-cookie update, `303` redirect to `?lang=<lang>&removed=1`, and language cookie are preserved.
- [x] `TestGuestRemovalCleanup` passes with 0 skipped: allowed deletion, missing photo, photo I/O resilience, expired lease allowance, and zero-side-effect refusals (another stay, restricted, `sent`, active filing lease, unowned).
- [x] `docs/tasks/screenshots-2076/removed-guest-390.png` captured from the real Go post-removal page at 390 px and inspected above.
- [x] `gofmt`, `go vet ./...`, targeted `GuestRemovalCleanup|FormPages` tests, full `go test ./... -count=1`, and `python3 scripts/context_lint.py` all pass with 0 failures and 0 skipped DB cases.

## Deviations

- None. (Note: `apartment` column in PostgreSQL schema is `uby_idub`, used in `TestGuestRemovalCleanup` fixture.)

## Questions

- None.

## Owner steps left

1. Review `docs/tasks/screenshots-2076/removed-guest-390.png` and `docs/tasks/2076-report.md`.
2. Merge via orchestrator after 2075.
