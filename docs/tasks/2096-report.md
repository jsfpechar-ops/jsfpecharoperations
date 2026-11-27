# Report 2096: Pre-submit guest review & confirm summary screen

- Updated `go/internal/ubyport/recover.go` so `RefreshRegistrationCompletedAt` auto-stamps only on 12h quiet (`formsSettled`), preserving already-confirmed stays while preventing premature bypass.
- Added `AlreadyAddedNames` (owned by current device cookie only) on `/new` when `PersonNumber > 1`.
- Deferred completion/submit from `form_save.go` and `/count` to new `POST /l/{token}/{reservation_id}/confirm-registration` (`confirm_registration.go`, CSRF-protected); cleared `registration_completed_at` on `/another`.
- Added Review & Confirm summary state (`NeedsConfirm`) in `stay_view.go` + `templates/stay.tmpl` (`<details open>`, top `DupWarnings`, no-JS Confirm POST button, deferred `DoorCode`/`FeePanel`) across all 6 guest languages.
- Verified green with Postgres 16: `go test ./internal/web/guest/... ./internal/ubyport/... ./cmd/ubyhost-web/... -count=1`.
- Owner/UX follow-up: spot-check 390 px mobile screenshot of Review & Confirm and Confirmed states before merging out of draft.
