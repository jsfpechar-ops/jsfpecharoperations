# 2072 report: required guest passport photo save

Status: blocked
Executor: Haiku 5.5 (continuation) | Branch: worktree-agent-aa90d5d2cd22cdaf8 (no push, no PR)

## Done

- Step B (multipart parse): `handleGuestFormSave` parses multipart bodies with `ParseMultipartForm(maxPDFBytes + 1024)` only when `r.MultipartForm` is nil, else `ParseForm`.
- Step 1 (earlier commit 29791cf): `passportphotos.Prepare` and `SavePrepared`.
- Passport rule: `go/internal/web/guest/passport_required.go` has `passportRequired` (Python `guest_needs_passport_photo`), `passportUploadText` (cs, de, es, uk map) and `guestDataDir`. `passportphotos.Has` added.
- Step 2: the rule is evaluated after normalisation with stored nationality, entered_by and identity_verified_at for an existing guest. `passport_photo` is read via `r.FormFile`, `readUploadLimited`, then `Prepare` before any write. Absent with no existing stamped file gives `passport_photo_missing`.
- Step 3: after the row write and before audit, hook and redirect, `SavePrepared` runs and then `passport_photo_at` is stamped. `SavePrepared` now writes `<id><ext>.enc.tmp` and renames it, so a failed replacement keeps the old file.
- Step 4 (partial): `TestPassportRequired` (10 cases) and `TestGuestSavePassportPhoto` (encrypted storage, mode 0600, Has, failed replacement keeps prior photo).

## Not done (Left)

- HTTP-level `TestGuestSavePassportPhoto` cases: required+no file (422), bad content (422), valid upload (303 and hook 1), not required (ignored), existing stamped guest, and I/O failure through `handleGuestFormSave`.
- 390 px missing-photo screenshot. No browser work was done.
- Multipart upload tests.

## Test results

- `go build ./...`: pass.
- `go test ./internal/web/guest/... ./internal/passportphotos/... ./internal/web/stays/... -count=1`: pass (guest, passportphotos, stays all ok).
- `-v` run: 3 SKIP lines (`TestClaimOpsSignedOutRedirects`, `TestGuestEditSignedOutRedirects`, `TestGuestLifecycleSignedOutRedirects`). These are pre-existing tests this change does not touch; not checked against the base branch.

## Deviations

- Step 4 is partial (see Left). The brief asked for the HTTP cases; they were not written.
- The Prepare message map covers cs, de, es, uk as the brief says. Python's `PASSPORT_UPLOAD_MESSAGES` also has `fr`, so French guests get English refusals. Left as a parity gap.
- `ParseMultipartForm` is not wrapped in `http.MaxBytesReader` on the header-token path, matching `draft_scan.go`. The CSRF path already has a body limit.

## Owner steps left

1. Decide on the `fr` refusal text.
2. Review the next session's HTTP test results and the 390 px screenshot.
