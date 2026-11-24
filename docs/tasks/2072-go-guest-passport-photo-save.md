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
