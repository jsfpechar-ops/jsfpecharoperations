# 0550: Go G5d-2: the database writes of a UbyPort submission, in Go, matching Python
Status: review
Depends on: 0482 (#642) | Base commit: main | Branch: claude/project-thread-4fdmo3
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 90k tokens
## 1. Objective
Plan v4 step 17 (G5), rule 1 (filing correctness). G5d-2 of 3: the four database writes of `reporting.submit_batch` in Go, plus the receipt lookup that `PlanOutcome` needs. Nothing calls the new code yet (G5d-3 wires it), nothing changes in Python or in production.
## 2. Context
- Python source of truth: `App/app/reporting.py` `submit_batch` (line 1541): the `db.insert("submission", ...)`, the `outcome_unknown` branch (`with db.immediate()`: submission update + every guest's `submission_id`), the transport branch (`db.update`, no transaction needed), and the final `with db.immediate()` (every `guest_writes` entry in order, then the submission update). `receipt_submission_id` (line 1151). Helpers: `db.utcnow`, `db.update_in`, `db._write_values`, `db.encrypt_field`.
- Go already has: `ubyport.PlanOutcome`, `OutcomePlan`, `GuestWrite`, `SubmitResult`, `*Error` (with `RequestXML`) in `go/internal/ubyport/`; the transaction pattern in `claim.go`; the test database helper `claimTestPool` in `claim_test.go` (same package, reuse it, do not copy it); `secure.NewMultiFernet` in `go/internal/secure/fernet.go`.
- **Traps:**
  - `submission.request_xml` is an encrypted field (`ENCRYPTED_COLUMNS` in `db.py`): Python stores the ciphertext in `request_xml_enc` and writes `request_xml = NULL`. `encrypt_field` turns `""`/None into NULL. Do the same through a passed-in encrypter; never store the envelope in plain text (it holds passport numbers).
  - Python `json.dumps` defaults: separators `", "` and `ensure_ascii=True` (`["á", "x"]`, lowercase hex, surrogate pairs above U+FFFF). `guest_ids` is `json.dumps(list of int)` (`[3, 4]`), `record_errors` is `json.dumps(list of str)` (`[]` when empty). Go's `encoding/json` differs (no space, no escaping, escapes `<>&`); write a small `pyJSONDumps` for these two shapes.
  - `receipt_pdf` and `error_pdf` are written `or None`: `""` becomes NULL. `header_errors` and `pseudo_stamp` are written as they are (`""` stays `""`). `request_xml` of the outcome-unknown branch is `exc.request_xml or None`.
  - `db.utcnow()` is `2026-11-01T10:00:00+00:00` (UTC, seconds, `+00:00`). The functions take the time string from the caller; add `UTCNow() string` producing that form.
  - A `GuestWrite` key absent from `Values` means "leave the column alone"; a nil value is SQL NULL. Build `SET` in sorted key order and refuse (return an error, write nothing) any key outside: `submit_state, submitted_at, submission_id, receipt_submission_id, last_errors, submit_attempts, updated_at`.
  - Both transactions are all or nothing: on any error roll back and return it.
## 3. Files
New: `go/internal/ubyport/store.go`, `go/internal/ubyport/store_test.go`. Write `docs/tasks/0550-report.md`. Nothing else.
## 4. Steps
1. `store.go`, package `ubyport`, comment at the top naming the Python lines it mirrors:
   - `type FieldEncrypter func(plain string) (string, error)` and `func encryptField(enc FieldEncrypter, plain string) (any, error)` (`""` gives nil, as `encrypt_field`).
   - `func UTCNow() string`.
   - `func InsertSubmission(ctx context.Context, pool *pgxpool.Pool, apartmentID int64, mode string, guestIDs []int64, endpoint, now string) (int64, error)`: columns `apartment_id, created_at, mode, state='running', guest_ids, endpoint`, `RETURNING id`.
   - `func RecordOutcomeUnknown(ctx, pool, enc FieldEncrypter, submissionID int64, guestIDs []int64, errText, requestXML, finished string) error`: one transaction, submission `state='outcome_unknown', finished_at, error_text, request_xml=NULL, request_xml_enc`, then `UPDATE guest SET submission_id` for each id in order.
   - `func RecordTransportError(ctx, pool, submissionID int64, errText, finished string) error`: `state='transport_error', finished_at, error_text`.
   - `func RecordOutcome(ctx, pool, enc FieldEncrypter, submissionID int64, plan OutcomePlan, res SubmitResult, now string) error`: one transaction; every `plan.GuestWrites` entry in order (`UPDATE guest SET ... WHERE id = $n`), then submission `state=plan.State, finished_at=now, header_errors, record_errors, pseudo_stamp, receipt_pdf, error_pdf, request_xml=NULL, request_xml_enc, response_xml`.
   - `func ReceiptLookup(ctx, pool, guests []OutcomeGuest) (func(id *int64) *int64, error)`: one query `SELECT id FROM submission WHERE id = ANY($1) AND receipt_pdf IS NOT NULL AND receipt_pdf <> ''` over the non-zero `SubmissionID`s, then a closure that returns the id when held, else nil (nil and 0 give nil), as `receipt_submission_id`.
   - `pyJSONDumps` (unexported) for `[]int64` and `[]string`.
2. `store_test.go` (skips without `UBYHOST_TEST_DATABASE_URL`, like `claim_test.go`; CI sets it). Insert an apartment and guests with the fewest columns the schema needs (read `App/migrations_pg/00001_baseline.sql` for NOT NULL columns of `user`, `entity`, `apartment`, `reservation`, `guest`; if those are many, copy the insert helper `claim_test.go` already uses). Use a real `secure.MultiFernet` with a fixed test key as the encrypter and decrypt `request_xml_enc` in the asserts. Cases:
   - Insert: row has `state='running'`, `guest_ids` exactly `[3, 4]` style, the given `created_at`.
   - Outcome unknown: submission fields, `request_xml` NULL, `request_xml_enc` decrypts to the envelope; every guest points at the submission. Empty envelope gives NULL in both columns.
   - Transport error: the three fields; guests untouched.
   - Outcome: a plan from `PlanOutcome` over two guests (one accepted, one `106;` refused) is written; guest columns equal the plan values, keys not in a write stay as they were; `record_errors` `["", "106;"]`; `receipt_pdf ""` gives NULL, `header_errors ""` stays `""`.
   - Rollback: a plan whose second write has a key outside the allowed list returns an error and leaves the first guest and the submission unchanged.
   - `ReceiptLookup`: held id returned, id without receipt gives nil, nil gives nil.
   - `pyJSONDumps` (no database): `[]int64{3,4}` → `[3, 4]`, empty → `[]`, `[]string{"á","<x>","😀"}` → `["á", "<x>", "😀"]`.
3. Commit: `0550: Go G5d-2 submission DB writes matching submit_batch`.
## 5. Do not touch
`App/` (all of it), every other file in `go/internal/ubyport/`, `go/cmd/`, `go/internal/jobs`, `go.mod`/`go.sum` (no new dependency), compose, CI.
## 6. Commands
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/ubyport/ -count=1 2>&1 | tail -30`. The database tests skip locally (no database); CI is the gate for them, say so in the report.
- From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
`git diff --stat origin/main` lists only the section 3 files and this brief. gofmt, vet and the non-database tests pass locally; every database test passes in CI with 0 skipped in the `go` job.
## 8. Stop and ask
Stop if the schema has no `submission.request_xml_enc` column, or if a Python write cannot be matched without a new dependency.
## 9. Report
`docs/tasks/0550-report.md`: command tails, the diff stat, anything beyond section 2 you had to decide.
