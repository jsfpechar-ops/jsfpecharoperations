# 2074 Report: Restart filing attempts when a guest corrects a record

Status: review

## Files changed

- `go/internal/ubyport/collect.go` — added `collectGuestError` and exported `BlockedAsDuplicate`, `FiledRecordChanged`, `EditKeepsDuplicateBlock`, and `GuestCorrectionResetsAttempts` using `GuestFields` and `IsDuplicate`.
- `go/internal/web/guest/form_save.go` — extended `guestSaveRow` with all 13 reportable fields and `ubyGuest()`; updated `loadGuestSaveRow` to select and decrypt all 6 encrypted fields (`birth_date`, `doc_number`, `visa_number`, `res_street`, `res_city`, `signature_png`); updated `buildSavePayload` to match `App/app/routes/guest.py:2579-2619`; fixed `updateGuestSaveRow` to subtract `ubyport.SubmissionClaimTTL.Seconds()` and propagate non-`pgx.ErrNoRows` errors.
- `go/internal/web/guest/form_save_test.go` — added `TestGuestSaveFilingCorrection` with 7 subtest groups (18 leaf cases) against live PostgreSQL.
- `docs/tasks/2074-go-guest-filing-correction.md` — committed updated brief and set `Status: review`.

## Commands

- `cd go && gofmt -l .` -> exit 0 (empty output)
- `cd go && go vet ./...` -> exit 0 (empty output)
- `cd go && UBYHOST_TEST_DATABASE_URL=... go test ./internal/web/guest/ -run 'GuestSaveFilingCorrection|FormSave|GuestWriteEncryption|GuestSaveChildSigner' -count=1 -v` -> exit 0, 0 skipped:
  ```
      --- PASS: TestGuestSaveFilingCorrection/sent_restricted_claimed_and_cas_protected/active_submission_claim_refused_403 (0.00s)
      --- PASS: TestGuestSaveFilingCorrection/sent_restricted_claimed_and_cas_protected/expired_submission_claim_allows_save (0.00s)
      --- PASS: TestGuestSaveFilingCorrection/sent_restricted_claimed_and_cas_protected/concurrent_cas_state_flip (0.00s)
  PASS
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/guest	0.857s
  ```
- `cd go && UBYHOST_TEST_DATABASE_URL=... go test ./internal/ubyport/ -run 'Collect|GoldenEnvelopes' -count=1 -v` -> exit 0, 0 skipped:
  ```
      --- PASS: TestGoldenEnvelopesMatchByteForByte/batch_three (0.00s)
      --- PASS: TestGoldenEnvelopesMatchByteForByte/wsa_header (0.00s)
  PASS
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport	2.288s
  ```
- `cd go && UBYHOST_TEST_DATABASE_URL=... go test ./... -count=1` -> exit 0, all packages passed:
  ```
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stays	2.888s
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/submissions	0.732s
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/webpush	0.008s
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/welcomeback	0.002s
  ```
- `python3 scripts/context_lint.py` -> exit 0 (`context lint: OK`).

## Acceptance (§7)

- [x] `ubyport.BlockedAsDuplicate`, `ubyport.FiledRecordChanged`, `ubyport.EditKeepsDuplicateBlock`, and `ubyport.GuestCorrectionResetsAttempts` share `ubyport.GuestFields` and `ubyport.IsDuplicate`; `Collect` and `GoldenEnvelopes` pass.
- [x] `loadGuestSaveRow` hydrates and decrypts all 13 reportable fields (`birth_date`, `doc_number`, `visa_number`, `res_street`, `res_city`, `signature_png`); `buildSavePayload` matches `App/app/routes/guest.py:2579-2619`.
- [x] Unchanged duplicate-blocked edits (case/whitespace normalization, fresh signature, `lang=de`, empty stay dates inheriting booking dates, Czech `duplic` and `150:` errors) stay `blocked` with `last_errors` and `submit_attempts` preserved while `notice_lang` updates; changing `doc_number`, `birth_date`, `surname`, or `note` resets to `pending`, `last_errors = NULL`, `submit_attempts = 0`.
- [x] Non-duplicate `error`/`blocked` edits reset `submit_attempts = 0`; `pending` edits preserve `submit_attempts`; `DEU <-> CZE` nationality transitions set `not_required`/`pending` and reset attempts on eligible rows.
- [x] `sent` (403), `restricted_at` (303 no-op), active `submission_claim` within 5 min TTL (403), and CAS-flipped rows (`updated=false, err=nil`) are refused untouched; expired `submission_claim` (past 5 min TTL) allows save and resets attempts.
- [x] `gofmt`, `go vet`, targeted guest + ubyport tests, full `go test ./... -count=1`, and `python3 scripts/context_lint.py` all pass with 0 skipped and 0 failures.

## Deviations

- In `TestGuestSaveFilingCorrection/blocked_duplicate_unchanged_fields_stays_blocked`, enabled `de` via `SetGuestLanguages("en,cs,de")` with `t.Cleanup` restoring `"en,cs"` because package default enables only `en,cs`.

## Questions

None.

## Owner steps

1. Open after 2073.
2. Verify unchanged duplicate preservation vs genuine UbyPort field correction and active vs expired `submission_claim` behavior in this report.
