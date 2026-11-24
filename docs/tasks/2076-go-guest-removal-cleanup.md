# 2076: Clean up a removed guest and reassess filing

Status: review
Depends on: 2075 | Base commit: 76af25f60a9e770c258668ff608b24ebb4aeb549 | Branch: task/2076-go-guest-removal-cleanup
Executor: Gemini 4 Neon (medium) | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Complete Go guest-removal parity in `POST /l/{token}/{reservation_id}/remove/{guest_id}`:

1. Delete the removed guest's encrypted passport photo via `passportphotos.DeletePhoto(guestDataDir(d.getenv), guestID)` only after the authorized `DELETE FROM guest` commits (missing photo is success; I/O errors log safe diagnostics without failing the committed removal).
2. Fix the `guest_removed_by_guest` audit row `owner_user_id` (`apt.OwnerUserID` instead of `apt.ID`), fix the `SubmissionClaimTTL` nanoseconds-vs-seconds bug in the compare-and-set `DELETE`, and wire `formPagesSubmitStayIfComplete` to `ubyport.SubmitCompletedStay` after deletion and linked-child `signed_for_*` cleanup.
3. Prove allowed removal, missing-photo removal, photo I/O resilience, expired vs active lease behavior, and zero-side-effect refusals in `TestGuestRemovalCleanup`, plus capture and inspect a 390 px post-removal screenshot.

## 2. Context

Go first. UbyPort filing correctness and privacy take priority. Use synthetic data and an isolated local PostgreSQL database (`testPoolOptional(t)`) for tests.

Verified anchors at base commit `76af25f60a9e770c258668ff608b24ebb4aeb549`:

- `App/app/routes/guest.py:2250`

  ```text
  removed = db.execute(
  ```
- `App/app/routes/guest.py:2265`

  ```text
  passport_photos.delete_photo(guest_id)
  ```
- `App/app/routes/guest.py:2270`

  ```text
  owner_user_id=apartment["owner_user_id"],
  ```
- `App/app/routes/guest.py:2272`

  ```text
  await run_in_threadpool(reporting.submit_stay_if_complete, apartment["id"], reservation_id)
  ```
- `go/internal/web/guest/form_pages.go:350`

  ```text
  cutoff := float64(d.now().Unix()) - float64(ubyport.SubmissionClaimTTL)
  ```
- `go/internal/web/guest/form_pages.go:365`

  ```text
  if err := formPagesDeletePhoto(ctx, d.pool, guestID); err != nil {
  ```
- `go/internal/web/guest/form_pages.go:369`

  ```text
  d.now().UTC(), "guest", "guest_removed_by_guest", fmt.Sprintf("guest=%d reservation=%d", guestID, resID), apt.ID)
  ```
- `go/internal/web/guest/form_pages.go:370`

  ```text
  _ = formPagesSubmitStayIfComplete(ctx, d.pool, d.getenv, d.now, apt.ID, resID)
  ```
- `go/internal/web/guest/form_pages.go:942`

  ```text
  func formPagesDeletePhoto(ctx context.Context, pool *pgxpool.Pool, guestID int64) error { return nil }
  ```
- `go/internal/web/guest/form_pages.go:944`

  ```text
  func formPagesSubmitStayIfComplete(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, aptID, resID int64) error {
  ```
- `go/internal/web/guest/shared.go:165`

  ```text
  &a.PassportPhotoPolicy, &a.LockProvider, &a.DefaultPurpose, &a.OwnerUserID, &legal, &ctrl)
  ```
- `go/internal/web/guest/passport_required.go:87`

  ```text
  func guestDataDir(getenv func(string) string) string {
  ```
- `go/internal/passportphotos/save.go:131`

  ```text
  func DeletePhoto(dataDir string, guestID int64) error {
  ```
- `go/internal/ubyport/completion_submit.go:36`

  ```text
  func SubmitCompletedStay(
  ```

Key findings from inspection:

- **`SubmissionClaimTTL` nanoseconds bug (`form_pages.go:350`)**: `ubyport.SubmissionClaimTTL` is `5 * time.Minute` (`300_000_000_000` ns), while `d.now().Unix()` is seconds (~`1.78e9`). `float64(d.now().Unix()) - float64(ubyport.SubmissionClaimTTL)` produced `-2.98e11`, causing any historical `submission_claim` row (even expired ones) to block removal forever. Use `ubyport.SubmissionClaimTTL.Seconds()`, matching `form_save.go:580`.
- **`apt.OwnerUserID` is already populated**: `removalGuard` calls `OpenLink` -> `loadApartmentDetail` (`shared.go:155-165`), which selects `owner_user_id` into `apt.OwnerUserID`.
- **Effective photo dir**: `guestDataDir(d.getenv)` (`passport_required.go:87`) reads `UBYHOST_DATA_DIR` with `"data"` fallback — identical to `form_save.go:220,294` and host photo access (`stays.privacyDataDir`).
- **Immediate filing test seam**: `ubyport.SubmitCompletedStay` accepts `*ubyport.SubmitCompletedStayOptions` (`completion_submit.go:21-25`), allowing tests to inject a recording `Submit` hook while exercising all real completion-refresh and stay-scoping gates inside `SubmitCompletedStay` (same pattern as `go/internal/web/staydetail/filing.go:14`).

## 3. Files

| Path | Action | Purpose |
|---|---|---|
| `go/internal/web/guest/form_pages.go` | edit | Real photo deletion, `SubmissionClaimTTL.Seconds()` fix, `apt.OwnerUserID` audit owner, shared `ubyport.SubmitCompletedStay` filing hook. |
| `go/internal/web/guest/form_pages_test.go` | edit | Add `TestGuestRemovalCleanup` proving post-removal effects, expired-lease allowance, and zero-side-effect refusals. |
| `docs/tasks/screenshots-2076/removed-guest-390.png` | create | 390 px Chromium screenshot of the post-removal guest stay page (`?lang=en&removed=1`). |

The executor report (`docs/tasks/2076-report.md`) and brief status follow section 9.

## 4. Steps

### Step 1: Real passport photo deletion in `go/internal/web/guest/form_pages.go`

Add the `passportphotos` import to `go/internal/web/guest/form_pages.go` (lines 25-30):

```go
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billingjob"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/headcount"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/passportphotos"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ruian"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
```

Replace the no-op `formPagesDeletePhoto` helper at `go/internal/web/guest/form_pages.go:942`:

```go
func formPagesDeletePhoto(getenv func(string) string, guestID int64) error {
	if getenv == nil {
		getenv = func(string) string { return "" }
	}
	return passportphotos.DeletePhoto(guestDataDir(getenv), guestID)
}
```

In `handleRemovePost`, invoke `formPagesDeletePhoto(d.getenv, guestID)` ONLY after `DELETE FROM guest` succeeds (`tag.RowsAffected() > 0`) and linked-child cleanup runs. Because `passportphotos.DeletePhoto` skips `os.IsNotExist`, a missing photo returns `nil`. On an I/O error, log safe diagnostics (guest ID + error only; no guest name, PII, or key material) and do **not** return 500 or abort the already-committed removal — the orphan photo sweeper (`go/internal/photosweep`) remains intact as fallback.

### Step 2: Fix `SubmissionClaimTTL.Seconds()`, audit `owner_user_id`, and wire `ubyport.SubmitCompletedStay`

In `go/internal/web/guest/form_pages.go`, update `handleRemovePost` lines `350-371`:

```go
	cutoff := float64(d.now().Unix()) - ubyport.SubmissionClaimTTL.Seconds()
	tag, err := d.pool.Exec(ctx, `DELETE FROM guest WHERE id = $1 AND reservation_id = $2
		AND COALESCE(submit_state,'') <> $3 AND restricted_at IS NULL
		AND NOT EXISTS (SELECT 1 FROM submission_claim WHERE guest_id = $1 AND claimed_at >= $4)`,
		guestID, resID, formSubmitSent, cutoff)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		d.formWriteUnavailable(w, r, lang, "already_filed", http.StatusForbidden, link, nil)
		return nil
	}
	if _, err := d.pool.Exec(ctx, `UPDATE guest SET signed_for_guest_id = NULL, signed_for_role = NULL,
		signed_for_at = NULL, signed_for_wording = NULL WHERE signed_for_guest_id = $1 AND reservation_id = $2`,
		guestID, resID); err != nil {
		log.Printf("guest remove: clear child signer guest=%d reservation=%d: %v", guestID, resID, err)
	}
	if err := formPagesDeletePhoto(d.getenv, guestID); err != nil {
		log.Printf("guest remove: delete photo guest=%d: %v", guestID, err)
	}
	if _, err := d.pool.Exec(ctx, `INSERT INTO audit (at, actor, action, detail, owner_user_id) VALUES ($1,$2,$3,$4,$5)`,
		d.now().UTC(), "guest", "guest_removed_by_guest", fmt.Sprintf("guest=%d reservation=%d", guestID, resID), apt.OwnerUserID); err != nil {
		log.Printf("guest remove: audit guest=%d reservation=%d: %v", guestID, resID, err)
	}
	if err := formPagesSubmitStayIfComplete(ctx, d.pool, d.getenv, d.now, apt.ID, resID); err != nil {
		log.Printf("guest remove: submit stay apartment=%d reservation=%d: %v", apt.ID, resID, err)
	}
```

Keep lines `371-382` (owned-cookie update, `Cache-Control: no-store`, `WithLang`, and `303` redirect to `GuestLink(link, resID, LangQuery(lang, "&removed=1"))`) completely unchanged.

Replace the no-op `formPagesSubmitStayIfComplete` at `go/internal/web/guest/form_pages.go:944-946` with the 2075 helper and package-level test seam (matching `go/internal/web/staydetail/filing.go:14`):

```go
// formPagesSubmitCompletedStayOpts lets tests inject a fake submitter/sender
// without bypassing the gate logic inside ubyport.SubmitCompletedStay.
var formPagesSubmitCompletedStayOpts *ubyport.SubmitCompletedStayOptions

func formPagesSubmitStayIfComplete(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, aptID, resID int64) error {
	_, err := ubyport.SubmitCompletedStay(ctx, pool, getenv, now, aptID, resID, formPagesSubmitCompletedStayOpts)
	return err
}
```

### Step 3: Add `TestGuestRemovalCleanup` in `go/internal/web/guest/form_pages_test.go`

Add `TestGuestRemovalCleanup` in `go/internal/web/guest/form_pages_test.go` using `testPoolOptional(t)` (never silently skipped when `UBYHOST_TEST_DATABASE_URL` is set). Reuse package helpers (`mustExecGuest`, `rememberOwnedGuestIDs`, `ownedGuestIDs`, `mintGuestPageCSRF`, `csrfCookie`, `synthJPEG`, `testDataEnv` key format) with:

- **Distinct workspace owner vs apartment ID**: e.g. `ownerID = base`, `aptID = base + 100` (assert `ownerID != aptID`).
- **Environment**: `UBYHOST_SECRET_KEY` (32+ bytes), `UBYHOST_DATA_KEYS` (base64 32-byte Fernet key), `UBYHOST_DATA_KEY_LEGACY=0`, `UBYHOST_GUEST_PIN=0`, `UBYHOST_MAIL_BACKEND=disabled`, `UBYHOST_DATA_DIR=t.TempDir()`.
- **Apartment**: `active = 1`, `automation_mode = 'immediate'`, `permalink_token`, `owner_user_id = ownerID`, `uby_id = 'UBY123'`, `uby_name = 'Flat'`, `city_en = 'Prague'`.
- **Two stays in the same apartment**:
  - Target stay `resID` (`status = 'active'`, `source = 'manual'`, `date_from = '2026-06-10'`, `date_to = '2026-06-12'`, `declared_guests = 2`, `registration_completed_at = NULL`).
  - Second stay `otherResID` (`status = 'active'`, `source = 'manual'`, `declared_guests = 1`) holding an unrelated guest `otherGuestID` (proving stay-scoped filing never touches another stay, and proving cross-stay removal is refused).
- **Recording filing dependency**: save/restore `formPagesSubmitCompletedStayOpts` via `t.Cleanup`, injecting `Submit` on `&ubyport.SubmitCompletedStayOptions{SweepDeps: &ubyport.SweepDeps{...}, Submit: func(...) { ... }}` (or passing `Submit` alone so `SubmitCompletedStay` builds real `SweepDeps` with `UBYHOST_DATA_KEYS` and records `calls`, `aptID`, `opts`, `mode`).
- **Helper to POST removal**: mint valid CSRF token+cookie (`mintGuestPageCSRF` + `_csrf` form field), attach signed owned-guest cookie (`rememberOwnedGuestIDs`), send `POST /l/{token}/{resID}/remove/{guestID}?lang={lang}` through `RegisterFormPages`.

Required subtests inside `TestGuestRemovalCleanup`:

1. **`allowed removal cleans photo, clears child signer, audits owner, updates cookie, redirects, and triggers stay-scoped filing`**:
   - Seed on `resID`:
     - `stayAdultID`: complete foreign/Czech adult (all required fields + valid PNG data-URL signature) so `validation.GuestIsComplete` is true.
     - `childID`: complete under-15 child (`birth_date = '2016-05-10'`, `signed_for_guest_id = removedID`, `signed_for_role = 'parent'`, `signed_for_at = '2026-06-15T11:00:00Z'`, `signed_for_wording = 'u15-2026-11-10'`).
     - `removedID`: incomplete extra adult (so `registration_completed_at` starts NULL) with a synthetic encrypted photo written via `passportphotos.Save(dataDir, keys, removedID, synthJPEG(t), "image/jpeg")`. Assert `passportphotos.Has(dataDir, removedID)` is `true` before POST.
   - Owned cookie contains `[stayAdultID, removedID]`. POST removal of `removedID` with `lang=cs`.
   - Assert:
     - HTTP `303`, `Location == fmt.Sprintf("/l/%s/%d?lang=cs&removed=1", tok, resID)`, `ubyhost_lang=cs` cookie set.
     - Updated owned cookie contains `stayAdultID` and does NOT contain `removedID`.
     - `removedID` row deleted from `guest`; `stayAdultID` and `childID` still exist.
     - Encrypted photo file deleted (`!passportphotos.Has(dataDir, removedID)`).
     - `childID` has `signed_for_guest_id IS NULL`, `signed_for_role IS NULL`, `signed_for_at IS NULL`, `signed_for_wording IS NULL`.
     - Exactly 1 `audit` row with `action = 'guest_removed_by_guest'`, `actor = 'guest'`, `detail = fmt.Sprintf("guest=%d reservation=%d", removedID, resID)`, and `owner_user_id == ownerID` (and `!= aptID`).
     - `calls == 1`, `gotApt == aptID`, `gotMode == "completion_immediate"`, `gotOpts.IgnoreSchedule != nil && *gotOpts.IgnoreSchedule`, and `gotOpts.OnlyGuestIDs` equals `[stayAdultID, childID]` (excludes `removedID` and `otherGuestID`).
     - `reservation.registration_completed_at` on `resID` is now non-empty.
2. **`missing photo file succeeds cleanly`**:
   - Seed an owned removable guest with NO photo file on disk.
   - POST removal -> `303`, row deleted, `guest_removed_by_guest` audit row written with `owner_user_id == ownerID`, filing check runs cleanly.
3. **`photo delete io error logs safely without failing committed removal`**:
   - Point `UBYHOST_DATA_DIR` at a regular file inside `t.TempDir()` (so `os.Stat` inside `DeletePhoto` returns `ENOTDIR` reliably even under root).
   - POST removal -> `303` (not 500), row deleted, audit row written with `owner_user_id == ownerID`, owned cookie updated.
4. **`expired filing lease allows removal`** (proves `SubmissionClaimTTL.Seconds()` fix):
   - Seed an owned removable guest with a `submission_claim` row whose `claimed_at = float64(now().Unix()) - 360` (6 minutes old, past the 5-minute `SubmissionClaimTTL`).
   - POST removal -> `303`, row deleted, photo deleted, audit row written with `owner_user_id == ownerID`.
5. **`refusals have zero side effects`** (table-driven subtests; each seeds a synthetic encrypted photo via `passportphotos.Save` and a child linked to the target guest where applicable, resets `calls = 0`, records prior audit count, and asserts after POST: target guest row intact, encrypted photo file still exists via `passportphotos.Has`, child's `signed_for_guest_id` unchanged, 0 new `guest_removed_by_guest` audit rows, `calls == 0`):
   - **another stay's guest**: target is `otherGuestID` (on `otherResID`), owned cookie includes `otherGuestID`, request path uses `resID` -> `404`.
   - **restricted guest**: `restricted_at = '2026-06-15T10:00:00Z'`, owned -> `403`.
   - **filed (`sent`) guest**: `submit_state = 'sent'`, owned -> `403`.
   - **active filing lease**: `submission_claim` row with `claimed_at = float64(now().Unix()) - 60` (within 5-minute TTL), owned -> `403`.
   - **unowned guest**: target on `resID` is removable, owned cookie does NOT contain target ID -> `403`.

### Step 4: Capture and inspect 390 px post-removal screenshot

Serve a local Go `httptest.Server` (or short-lived Go test/script) registering `RegisterStayClaim`, `RegisterFormPages`, and `/static/` from `App/app/static`, seeded with synthetic data against the local PostgreSQL test DB. Execute the real `POST /l/{token}/{reservation_id}/remove/{guest_id}?lang=en` flow and load the resulting 303 target `/l/{token}/{reservation_id}?lang=en&removed=1` in Playwright Chromium (`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`, viewport `390x844`, `full_page=True`), saving to `docs/tasks/screenshots-2076/removed-guest-390.png`.

Open `docs/tasks/screenshots-2076/removed-guest-390.png` once to visually inspect it (confirming light mode, no horizontal overflow, `"The person was removed."` status card visible, removed guest absent, remaining guest/stay summary clean) and record what you saw in `docs/tasks/2076-report.md`.

### Step 5: Verification and report

Run all commands in section 6, verify 0 skipped tests and 0 lint errors, write `docs/tasks/2076-report.md`, and set this brief's `Status:` to `review`.

## 5. Do not touch

Preserve route patterns, CSRF/PIN/claim/owned-cookie/lease guards, 2073 child-signer semantics, `go/internal/photosweep` orphan sweeper fallback, `go/internal/ubyport/completion_submit.go`, templates, and `i18n.json`. Use no real guest files, no real guest PII, and no live UbyPort filing.

## 6. Commands

Run from the repo root (or `go/` as shown) with `set -o pipefail`. Ensure `UBYHOST_TEST_DATABASE_URL` points to local PostgreSQL so DB tests run with 0 skipped.

```sh
cd go && test -z "$(gofmt -l .)"
cd go && go vet ./... 2>&1 | tail -30
cd go && go test ./internal/web/guest/ -run 'GuestRemovalCleanup|FormPages' -count=1 -v 2>&1 | tail -30
cd go && go test ./... -count=1 2>&1 | tail -30
python3 scripts/context_lint.py 2>&1 | tail -30
```

For the 390 px screenshot, use `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers` with Chromium and inspect `docs/tasks/screenshots-2076/removed-guest-390.png`.

## 7. Acceptance

- [ ] `formPagesDeletePhoto` deletes the removed guest's photo via `passportphotos.DeletePhoto(guestDataDir(d.getenv), guestID)` only after authorized `DELETE FROM guest` succeeds; missing photo is success; I/O errors log safely without failing the committed removal.
- [ ] `guest_removed_by_guest` audit INSERT records `apt.OwnerUserID` (verified with `owner_user_id != apartment_id`), `handleRemovePost` uses `ubyport.SubmissionClaimTTL.Seconds()`, and `formPagesSubmitStayIfComplete` calls `ubyport.SubmitCompletedStay` after deletion and linked-child `signed_for_*` cleanup.
- [ ] Owned-cookie update, `303` redirect to `?lang=<lang>&removed=1`, and language cookie are preserved.
- [ ] `TestGuestRemovalCleanup` passes with 0 skipped: allowed deletion, missing photo, photo I/O resilience, expired lease allowance, and zero-side-effect refusals (another stay, restricted, `sent`, active filing lease, unowned).
- [ ] `docs/tasks/screenshots-2076/removed-guest-390.png` is captured from the real Go post-removal page at 390 px and inspected in the report.
- [ ] `gofmt`, `go vet ./...`, targeted `GuestRemovalCleanup|FormPages` tests, full `go test ./... -count=1`, and `python3 scripts/context_lint.py` all pass with 0 failures and 0 skipped DB cases.

## 8. Stop and ask

Stop and report if an anchor diverges after listed prerequisites, a required test fails twice, a dependency or file outside section 3 is needed, or the executor limit is reached. Escalate any need for live credentials, a real provider, a deployed server, or a product decision.

## 9. Report

Write `docs/tasks/2076-report.md` with the changed paths, command results, test counts, 390 px screenshot inspection notes, acceptance evidence, and owner steps. Set this brief to `Status: review` after completing all checks. Use `Status: blocked` in the report if stopped.

## Risk list (for the reviewer)

`go/internal/web/guest/form_pages.go`

## Owner steps

1. Open after 2075.
2. Review the 390 px post-removal screenshot (`docs/tasks/screenshots-2076/removed-guest-390.png`) and removal/refusal test evidence in `docs/tasks/2076-report.md`.
