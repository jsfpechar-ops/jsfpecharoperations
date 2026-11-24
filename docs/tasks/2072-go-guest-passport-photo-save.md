# 2072: Validate and store required guest passport photos

Status: todo
Depends on: 2071 | Base commit: f6be14e46b68677884e26533eef674b15cb89f6a | Branch: task/2072-go-guest-passport-photo-save
Executor: Luna | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Restore the apartment-specific passport photo requirement on guest save. Use the existing encrypted photo store and the Python upload policy.

## 2. Context

Go first. UbyPort filing correctness and privacy take priority. Use synthetic data and an isolated local PostgreSQL schema for tests. Review the named anchors against the approved base or its prerequisite tip.

- `App/app/reporting.py:409`

  ```text
  def guest_needs_passport_photo(guest, apartment) -> bool:
  ```
- `App/app/routes/guest.py:2483`

  ```text
  passport_upload = form.get("passport_photo")
  ```
- `go/internal/web/guest/form_save.go:113`

  ```text
  form := postForm(r)
  ```
- `go/internal/web/guest/draft_scan.go:379`

  ```text
  func readUploadLimited(f multipart.File) ([]byte, error) {
  ```
- `go/internal/passportphotos/save.go:47`

  ```text
  func Save(dataDir string, keys *secure.MultiFernet, guestID int64, content []byte, contentType string) error {
  ```

## 3. Files

| Path | Action | Purpose |
|---|---|---|
| `go/internal/web/guest/form_save.go` | edit | Handle the named upload and successful save timestamp. |
| `go/internal/passportphotos/save.go` | edit | Expose the existing prepare/validate path for pre-write validation. |
| `go/internal/web/guest/form_save_test.go` | edit | Cover multipart cases and encrypted storage. |

The executor report and brief status follow section 9.

## 4. Steps

1. In the photo package expose the existing upload preparation result to the caller so validation and the JPEG/PDF conversion happen before guest persistence and only once. Preserve the current size/type rules, Python allowance for stored PDFs, encrypted filename and file modes. Keep the old `Save` entry point usable by existing callers.
2. In `handleGuestFormSave`, after normalization and before 422 localization, evaluate `guest_needs_passport_photo` using the saved/proposed Python inputs and property setting. Use the exact Python field `passport_photo`, reuse `readUploadLimited`, and distinguish absent, rejected and valid uploads. An existing attachment satisfies the rule only when the timestamp and actual file agree, as in Python. Use the existing localized photo issue keys. Optional data follows the Python branch.
3. After the guest row succeeds, persist the prepared encrypted photo and stamp `passport_photo_at` only after the file write succeeds. Surface disk and timestamp errors using the existing error path, preserve the prior attachment on replacement failure, and invoke this request's completion hooks only after a required attachment is durable. Keep the background filing eligibility rules unchanged. Constrain any cleanup to this guest and keep the storage mode and data directory consistent with the host read path.
4. Add `TestGuestSavePassportPhoto` covering required foreign guest, optional/Czech guest, bad and oversized content, existing photo reuse, missing old file, valid encrypted upload and I/O failure. Assert that a refused or failed upload does not run this request's completion hook and capture the 390 px missing-photo state. Run section 6.

## 5. Do not touch

Keep upload limits, accepted media, host photo permissions, browser copy, and keys unchanged. Existing photo retention applies. Use synthetic photos only.

## 6. Commands

Run from the indicated directory with pipeline failure reporting on. Expect the listed cases to run and pass. Required database and browser cases must show zero skips.

```sh
cd go && go test ./internal/web/guest/ -run 'GuestSavePassportPhoto' -count=1 -v 2>&1 | tail -30
cd go && go test ./internal/passportphotos/ -count=1 -v 2>&1 | tail -30
```

For each changed guest-facing response, include a 390 px screenshot from the Go flow with synthetic data. For host page changes apply the 390/768/1280 host UX gate and report what you saw at each width.

## 7. Acceptance

- [ ] Required-photo failures show the matching translated field issue.
- [ ] A valid upload is encrypted and the database stamp reflects the durable attachment.
- [ ] Failure handling preserves the last valid attachment and skips this request's completion hook.

## 8. Stop and ask

Stop and report if an anchor diverges after listed prerequisites, a required test fails twice, a dependency or file outside section 3 is needed, or the executor limit is reached. Escalate any need for live credentials, a real provider, a deployed server, or a product decision.

## 9. Report

Write `docs/tasks/2072-report.md` with the changed paths, command results, counts, acceptance evidence and owner steps. Set the brief to `Status: review` after completing the checks. Use `Status: blocked` in the report if stopped.

## Risk list (for the reviewer)

`go/internal/web/guest/form_save.go`, `go/internal/passportphotos/save.go`

## Owner steps

1. Open after 2071.
2. Review the missing-photo screenshot and encrypted-storage result.

## Continuation (orchestrator)

Step 1 is done (worktree commit 29791cf: `passportphotos.Prepare`, `SavePrepared`; `Save` unchanged in behaviour). The executor stopped at step 2 because it could not find the Python helpers in Go. Findings, then the replacement for steps 2-4. Anchors below are checked against the current tip; if one differs, stop.

### A. Python helpers and their Go status

Python rule (`App/app/reporting.py:409-427`, `guest_needs_passport_photo`): policy = `apartment.passport_photo_policy` trimmed, lowercased, empty = "off"; true only when policy == `required_foreign` AND `guest_is_reportable(nationality)` AND `_guest_entered_by(guest) != "host"` AND NOT `guest_identity_verified(guest)`.

| Python | Go | Difference |
|---|---|---|
| `validation.guest_is_reportable` | `validation.GuestIsReportable` at `go/internal/validation/validation.go:510` | none (empty nationality = false, Czech = false) |
| `reporting._guest_entered_by` (`reporting.py:387`) | none: port needed | trivial: `entered_by` empty means "guest" |
| `reporting.guest_identity_verified` (`reporting.py:380`) | none: port needed | trivial |
| `guest_needs_passport_photo` | none: port needed | `RequirePassport` at `go/internal/web/guest/form_pages.go:673` only does the policy half for page display |
| `passport_photos.has_photo` (`passport_photos.py:68`) | none (`passportphotos.Read` at `save.go:99` decrypts, too heavy) | add `Has` |

Port (new file `go/internal/web/guest/passport_required.go`, package `guest`; add it to the section 3 table):

```go
// passportRequired is reporting.guest_needs_passport_photo.
// enteredBy and identityVerifiedAt come from the stored row, or "guest" and ""
// for a new guest (guest.py:2486 passes exactly that stub).
func passportRequired(policy, nationality, enteredBy, identityVerifiedAt string) bool {
	if strings.ToLower(strings.TrimSpace(policy)) != "required_foreign" {
		return false
	}
	if !validation.GuestIsReportable(nationality) {
		return false
	}
	if enteredBy == "host" { // empty counts as "guest"
		return false
	}
	// guest_identity_verified: non-reportable is always verified (excluded above);
	// otherwise verified only when identity_verified_at is set.
	return identityVerifiedAt == ""
}
```

Python `bool(guest["identity_verified_at"])` is truthy for any non-empty string, so the exact test is `identityVerifiedAt == ""` (no trimming). The nationality is the NORMALISED `values.Nationality` for a new guest, as in Python (`values["nationality"]`); for an existing guest Python uses the STORED row's nationality (`existing`), not the posted one. Copy that.

Also add `func Has(dataDir string, guestID int64) bool` to `go/internal/passportphotos/save.go`: true when any of `<id><ext>` or `<id><ext>.enc` for ext in `AllExtensions` is a regular file (Python `_paths_for`, `path.is_file()`).

### B. Existing multipart bug to fix first (same file)

The form posts `enctype="multipart/form-data"` (`go/internal/web/guest/templates/form_content.tmpl:46`, file input `name="passport_photo"` at :258). `handleGuestFormSave` (`go/internal/web/guest/form_save.go:87`) calls only `r.ParseForm()`, which does NOT read multipart bodies, so `postForm(r)` (:119, :309) would see no fields on a real browser post. Replace the `ParseForm` block at :87 with:

```go
if strings.HasPrefix(r.Header.Get("Content-Type"), "multipart/form-data") {
	if err := r.ParseMultipartForm(maxPDFBytes + 1024); err != nil {
		return err
	}
	defer r.MultipartForm.RemoveAll() //nolint:errcheck
} else if err := r.ParseForm(); err != nil {
	return err
}
```

`ParseMultipartForm` also fills `r.PostForm`, so `postForm` keeps working unchanged. Confirm `WithPOSTCSRF` (`form_save.go:35`) does not already consume the body; if it calls ParseForm first, that is fine for multipart (a no-op for the body). If the csrf token only exists in the multipart body, stop and report. `maxPDFBytes` is in `go/internal/passportphotos` (unexported) and `draft_scan.go` uses a package-level `maxPDFBytes`; reuse the guest package one.

### C. Replacement steps 2-4

2. Extend `guestSaveRow` (`form_save.go:49`) and the SELECT in `loadGuestSaveRow` (:354) with `nationality`, `entered_by`, `identity_verified_at`, `passport_photo_at` (all `COALESCE(...,'')`). Nationality is stored plain (check `insertGuestSaveRow` payload at :329; if it is only stored encrypted, stop). After the `guestcontract`/`legal_ack` issue (right after the `legal_ack_missing` block, before `issues = localizeIssues(...)` at ~:157) add:
   - `apt` is the `*Apartment` from `OpenLink`; policy is `apt.PassportPhotoPolicy`.
   - Build the inputs: existing != nil: `existing.nationality, existing.enteredBy, existing.identityVerifiedAt`; else `values.Nationality, "guest", ""`.
   - If `passportRequired(...)`: `file, hdr, ferr := r.FormFile("passport_photo")`. Treat `http.ErrMissingFile` or `hdr == nil` or `hdr.Size == 0 && hdr.Filename == ""` as absent (Python: an empty file part is falsy-ish; browsers send an empty part with empty filename when nothing is chosen). If present: `raw, err := readUploadLimited(file)` (`draft_scan.go:379`; close the file), then `body, ext, err := passportphotos.Prepare(raw, hdr.Header.Get("Content-Type"))`. On error append `validation.Issue{Field: "passport_photo", Message: msg, Severity: "error"}` where `msg` is the localized text (section D). If absent and not `hasExisting` append the `passport_photo_missing` issue. `hasExisting` = `existing != nil && existing.passportPhotoAt != "" && passportphotos.Has(dataDir, existing.id)`. Keep `body`, `ext` in locals.
   - When not required: do not read the file at all (Python ignores it). Do not store it.
   - `dataDir` comes from `getenv("UBYHOST_DATA_DIR")` exactly as `go/internal/web/stays/guest_privacy.go:37` (`privacyDataDir`), so the host read path agrees; copy that helper into the guest package rather than importing `stays`. Keys: `secure.LoadDataKeys(d.getenv)` as in `guestSaveDecrypter` (`go/internal/web/guest/stay_claim.go:654`).
3. Order after the row is written (Python `guest.py:2709`): put the block after `savedID` is known and the `savedID == 0` redirect, BEFORE `auditGuestFormSaved` (:210), `guestFormSubmitStayIfComplete` (:209 region) and `runCompletion`. If `body != nil`: `passportphotos.SavePrepared(dataDir, keys, savedID, body, ext)`; on success `UPDATE guest SET passport_photo_at=$1, updated_at=$1 WHERE id=$2 AND reservation_id=$3` with `utcStamp`. On either error return it (existing 500 path) so no hook, submit-if-complete or redirect runs; the guest row stays saved, as in Python (Python has no transaction; do not add one). Change `SavePrepared` so a failed replacement keeps the old file: write `<id><ext>.enc.tmp` (0600) in the same dir, `os.Rename` onto the final name, then delete the OTHER extensions' files for this id (not the one just written); on a write error remove the tmp file and leave the prior files. Keep the existing `Save` tests green.
4. Tests in `go/internal/web/guest/form_save_test.go`, `TestGuestSavePassportPhoto`, same fixtures as `TestGuestSaveNoticeAndHeadcount` (:231; isolated rows, `UBYHOST_DATA_DIR` = `t.TempDir()`, `UBYHOST_DATA_KEYS` from `testDataEnv`). Set the apartment `passport_photo_policy` to `required_foreign`, post `multipart/form-data` built with `mime/multipart` (all normal required fields plus `legal_ack`, `party_size`, nationality `DEU`), file part `passport_photo`. Synthetic JPEG: `image/jpeg` encoded from a 64x64 `image.NewRGBA` (well over 64 bytes). Cases:
   - required + no file: 422, body contains the `passport_photo_missing` text, zero guest rows for the reservation, no file in the photos dir, hook counter 0.
   - required + bad content (`text/plain` and an over-5 MB JPEG): 422, translated message, nothing written, hook 0.
   - required + valid JPEG: 303, one guest row with `passport_photo_at` set, `<id>.jpg.enc` exists, mode 0600, content is not plaintext JPEG (`!bytes.HasPrefix(raw, {0xFF,0xD8,0xFF})`) and decrypts via `passportphotos.Read` to a JPEG, hook 1.
   - not required (policy `off`, or nationality `CZE`): file ignored, 303, no file, `passport_photo_at` empty.
   - existing guest with stamp and a real file, no new upload: 303, file untouched. Existing guest with stamp but file removed: 422 missing.
   - I/O failure: make the photos dir unwritable (parent dir read-only; skip when running as root) and assert error status, hook 0, row present, no stamp, prior file intact on replacement.
   - Unit tests for `passportRequired` over: policy off / `Required_Foreign ` (case/space) / Czech / empty nationality / host-entered / identity verified / new guest.
   Capture the 390 px missing-photo 422 screenshot as the brief says.

### D. Error message keys

Go `go/internal/web/guest/i18n.json` already has `passport_photo_missing` (cs line 218, de 577, en ~934, es ~1293) and `passport_photo_bad_type`, `passport_photo_too_large_image`, `passport_photo_too_large_pdf`. It has NO keys for the other `Prepare` errors (empty file, invalid PDF, invalid image, too many pixels) that Python maps in `PASSPORT_UPLOAD_MESSAGES` (`guest.py:57-105`, incl. uk via `guest_uk_i18n.PASSPORT_UPLOAD`). Add a small Go map in `passport_required.go` keyed by the English `Prepare` message, per language, copied verbatim from `PASSPORT_UPLOAD_MESSAGES` for `cs`, `de`, `es`, `uk`; English and unknown languages fall back to the English text, as Python (`PASSPORT_UPLOAD_MESSAGES.get(lang, {}).get(msg, msg)`). Do not add keys to `i18n.json` (translation file parity lint). Missing-photo uses `stringsCatalog.T(lang, "passport_photo_missing", nil)` like `legal_ack_missing` at `form_save.go:152`.

### E. Risks

- Multipart parsing (section B) is the highest risk: before this fix the real browser post carries no fields.
- Existing-row nationality and verification must come from the stored row, not the form.
- Photo file write is outside any DB transaction by design (Python parity); a crash between row insert and file write leaves a saved guest without a photo, and the guest is asked again on the next save because `passport_photo_at` is unset.
- Do not log file names or bytes.
