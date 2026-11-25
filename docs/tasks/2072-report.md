# 2072 report: required guest passport photo save

Status: review
Executor: Gemini 4 Neon (continuation 2072-cont-1) | Branch: `wt-2072` (no push, no PR)

## Files changed

- `go/internal/web/guest/form_save.go` (edited) — resolved merge with `claude/nice-hawking-fw98ct` keeping 2084's `guestSaveValidateIssues(...)` alongside 2072's passport photo validation/storage path.
- `go/internal/web/guest/form_save_test.go` (edited) — resolved merge conflict, restored original direct-insert payloads (`1990-01-02`, `CZ`, `tourism`) in `TestGuestWriteEncryption` and `TestGuestSaveNoticeAndHeadcount`, added `testPoolOptional` guard in `TestGuestSavePassportPhotoHTTP`, split `passportHookCount` into `onComplete` and `notify`, tightened mode `0600` / ciphertext / 422 message / 200-char body-snippet assertions, and added `TestGuestSavePassportPhotoExistingGuestHTTP` (4 subtests) and `TestGuestSavePassportPhotoIOFailure` (2 subtests).
- `docs/tasks/screenshots-2072/missing-photo-390.png` (created) — 390 px full-page screenshot of the Go `422` missing-passport-photo refusal page.
- `docs/tasks/2072-wip-patches/` (deleted) — removed all 11 parked WIP patch/diff files via `git rm -r`.
- `docs/tasks/2072-report.md` (edited) — finalized report.
- `docs/tasks/2072-go-guest-passport-photo-save.md` (edited) — set `Status: review`.
- `docs/tasks/2072-cont-1.md` (edited) — set `Status: review`.

## Verification commands and results

- `gofmt -l .` (in `go/`): empty output, exit 0.
- `go vet ./...` (in `go/`): empty output, exit 0.
- `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/guest_test go test ./internal/passportphotos/... ./internal/web/guest/... -v -run 'TestPassport|TestGuestSavePassportPhoto|TestGuestWriteEncryption|TestGuestSaveNoticeAndHeadcount|TestGuestSaveValidateIssues' -count=1`:
  - `ok github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/guest 0.942s`
  - Targeted counts: `PASS=27 SKIP=0 FAIL=0` (including all 6 `TestGuestSavePassportPhotoHTTP`, 4 `TestGuestSavePassportPhotoExistingGuestHTTP`, 2 `TestGuestSavePassportPhotoIOFailure`, `TestGuestWriteEncryption`, 5 `TestGuestSaveNoticeAndHeadcount`, `TestGuestSaveValidateIssuesLegalAckOnEdit`, `TestGuestSaveValidateIssuesPartySizeOnNew`, `TestPassportRequired`, `TestGuestSavePassportPhoto`).
- `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/guest_test go test ./internal/passportphotos/... -v -count=1`:
  - `ok github.com/jsfpechar-ops/jsfpecharoperations/go/internal/passportphotos 0.004s` (PASS, 0 skipped).
- `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/guest_test go test ./... -count=1`:
  - All packages `ok`, exit 0, 0 failures.
- `python3 scripts/context_lint.py`: `context lint: OK`.

## Birth-date parity confirmation

Confirmed: both Python (`App/app/validation.py`) and Go (`go/internal/validation`) normalize and store `birth_date` as `DDMMYYYY`. The two direct-insert tests (`TestGuestWriteEncryption` and `TestGuestSaveNoticeAndHeadcount`) bypass `NormaliseGuest` and have been restored to their original ISO fixtures (`1990-01-02`, `CZ`, `tourism`), while HTTP save tests (`TestGuestSavePassportPhoto*`) post `"02.01.1990"`, `"CZE"`, `"99"` through `NormaliseGuest`.

## 390 px screenshot inspection

Inspected `docs/tasks/screenshots-2072/missing-photo-390.png` (captured from the real Go `422` HTML response of `POST /l/{token}/{reservation_id}/save?lang=en` with `/static/` served from `App/app/static` at 390 px width):
- Light-mode CSS loaded cleanly with no horizontal overflow or clipping.
- Top red error summary banner displays `Please correct the following:` and underlined `Please upload a photo of your passport or ID card.`.
- `Step 3 of 4 · Passport or ID document` card shows side-by-side `Take photo` and `Choose file` buttons, the format/size note (`JPEG, PNG or WebP photo up to 5 MB, or a PDF up to 15 MB`), bold red inline refusal `Please upload a photo of your passport or ID card.`, and `Back` / `Continue` buttons.
- Footer shows privacy notice (`does not use tracking cookies`) and `How your data is handled`.

## Acceptance checklist (2072-cont-1 §7)

- [x] Merge with `claude/nice-hawking-fw98ct` committed cleanly with zero conflict markers; `guestSaveValidateIssues` and 2072 passport check both run.
- [x] `TestGuestWriteEncryption` and `TestGuestSaveNoticeAndHeadcount` restored to original direct-insert payloads and pass; 2084 validation tests pass.
- [x] Existing-guest HTTP cases pass (stamped + file present, stamped + file deleted with `nationality=CZE`, replacement JPEG, host-verified `identity_verified_at`).
- [x] I/O-failure HTTP cases (0500 photos dir) pass (new guest 500 without stamps; replacement 500 preserves prior file and timestamp).
- [x] Valid-upload HTTP test checks mode `0600`, non-plaintext ciphertext prefix, decrypt-to-JPEG, exact hook counts `(1, 1)` vs `(0, 0)`, and 200-char body snippet on mismatch.
- [x] `docs/tasks/screenshots-2072/missing-photo-390.png` captured and visually verified at 390 px.
- [x] `docs/tasks/2072-wip-patches/` removed; `gofmt`, `go vet`, targeted + full `go test`, and `context_lint.py` green; report and both briefs set to `Status: review`.

## Deviations

- Full `go test ./... -count=1` was run with `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/guest_test` because `internal/web/settings` requires a test database URL (without it, `internal/web/guest` tests skip cleanly via `testPoolOptional`, while `settings_test.go` fails).

## Owner steps left

1. Review `wt-2072` diff, `docs/tasks/2072-report.md`, and `docs/tasks/screenshots-2072/missing-photo-390.png`.
2. Push/open PR and merge on green via `scripts/merge-pr-on-green.sh`.
