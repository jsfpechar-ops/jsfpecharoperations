# 2072 report: Validate and store required guest passport photos

Status: blocked
Branch: claude/nice-hawking-fw98ct (fast-forwarded to origin, includes 2065, 2069, 2070, 2071)

## Commits

- `29791cf` 2072 step 1: exposes `passportphotos.Prepare` and `passportphotos.SavePrepared`. `Save` keeps its behaviour and calls both.

## Steps

1. Done. Photo package exposes prepare and save-prepared. Build passes.
2. Not done. `handleGuestFormSave` has no passport handling yet. Go has no equivalent of `guest_needs_passport_photo` (Python `reporting.py:409`), and no `passport_photo` multipart read or `passport_photo_missing` issue. Implementing it needs the Python helpers `guest_is_reportable`, `_guest_entered_by` and `guest_identity_verified`, which I did not read. Stopped at the tool-call cap rather than guess filing logic.
3. Not done. Depends on step 2.
4. Not done. `TestGuestSavePassportPhoto` not written.

## Command results

- `go build ./...` from `go/`: exit 0, no output.
- `go test ./internal/web/guest/... ./internal/web/stays/... -count=1` with `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/guest_test` (PostgreSQL accepting connections): `ok` for guest (4.98s) and stays (2.11s). Skips not counted; no new tests added.
- `go test ./internal/passportphotos/` and the `GuestSavePassportPhoto` run were not executed (no new tests exist).

## Deviations

Done: steps 1 to 1. Left: steps 2 to 4.

## Questions

- Step 2 needs the Go port of the Python passport-photo policy helpers (`guest_is_reportable`, `_guest_entered_by`, `guest_identity_verified`). Confirm the approach, or hand to a session with a larger budget.
- Brief anchor `form_save.go:113` (`form := postForm(r)`) is now at line 119. `postForm` takes `*http.Request` and returns a string map, so the file part needs `r.FormFile` or equivalent, not `postForm`.

## Owner steps left

None until steps 2 to 4 are done.
