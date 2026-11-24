# 2070: Encrypt personal fields on Go guest writes

Status: review
Depends on: 2069 | Base commit: f6be14e46b68677884e26533eef674b15cb89f6a | Branch: task/2070-go-guest-write-encryption
Executor: Luna | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Write the same protected guest fields as Python and clear legacy plaintext during the same database write. Apply this to host guest creation and edits and to the already encrypted guest self-save path.

## 2. Context

Go first. UbyPort filing correctness and privacy take priority. Use synthetic data and an isolated local PostgreSQL schema for tests. Review the named anchors against the approved base or its prerequisite tip.

- `App/app/db.py:2010`

  ```text
  def _write_values(table: str, values: Dict[str, Any]) -> Dict[str, Any]:
  ```
- `App/app/db.py:2027`

  ```text
  out[key] = None
  ```
- `go/internal/web/stays/guest_edit.go:665`

  ```text
  func guestUpdateIf(ctx context.Context, pool *pgxpool.Pool, guestID int64, expectState string, values map[string]any, at time.Time) bool {
  ```
- `go/internal/web/stays/guest_edit.go:687`

  ```text
  func insertHostGuest(ctx context.Context, c *guestEditCall, resID int64, payload hostGuest, signature, state string, isLead bool, stamp string) (int64, error) {
  ```
- `go/internal/web/guest/form_save.go:354`

  ```text
  func encryptSaveFields(getenv func(string) string, payload map[string]any) (map[string]any, error) {
  ```

## 3. Files

| Path | Action | Purpose |
|---|---|---|
| `go/internal/secure/guest_write.go` | add | Shared guest field mapping based on Python. |
| `go/internal/web/stays/guest_edit.go` | edit | Use the protected fields on host insert and compare-and-set update. |
| `go/internal/web/guest/form_save.go` | edit | Clear the touched legacy columns through the same mapping. |
| `go/internal/web/stays/guest_edit_test.go` | edit | Verify actual encrypted and legacy columns of host writes. |
| `go/internal/web/guest/form_save_test.go` | edit | Verify replacement and intentional clearing on guest self-save. |

The executor report and brief status follow section 9.

## 4. Steps

1. Add `secure.GuestWriteValues(keys *MultiFernet, values map[string]any) (map[string]any, error)`. Pass through unrelated keys. Do not change the fee-write route in this brief. For supplied `birth_date`, `doc_number`, `visa_number`, `res_street`, `res_city`, `signature_png` and `fee_host_reason`, set the legacy key to `nil` and the matching `_enc` key to Fernet ciphertext or `nil` when the value is nil or empty. Follow Python's actual empty string treatment in `App/app/db.py:encrypt_field`. Return an error for a supplied protected value of the wrong type. Build a fresh map and fail before writing on a key or encryption failure.
2. In `insertHostGuest`, replace the six plaintext INSERT targets with the six corresponding `_enc` targets, using values prepared through `GuestWriteValues`. In `guestUpdateIf`, convert the supplied updates before formatting the SET list. Return encryption or query errors via the normal host error path and preserve no-row compare-and-set behavior. Keep the state and active submission-claim checks, owner gate, and unchanged fields. Confirm the first `GuestWriteEncryption` command once the test is added.
3. In `encryptSaveFields`, replace the local switch with `secure.GuestWriteValues`. The insert already names only the `_enc` columns. Since update builds from the map, its SET clauses now clear each legacy field it touched. Run the second `GuestWriteEncryption` command after adding the fixture.
4. In each named test file, add `TestGuestWriteEncryption` using synthetic records and an isolated database. Cover a new write, an existing legacy plaintext value, ciphertext replacement, an explicitly cleared nullable field, a value left off the update, and encryption failure. Verify ciphertext in the raw row plus the effective value after application hydration or filing-data read.

## 5. Do not touch

Keep existing keys, schema, field classification, legacy read fallback, filing state transitions and receipt handling. Older rows are remediated on save only. A separate owner decision is needed for a bulk backfill.

## 6. Commands

Run from the indicated directory with pipeline failure reporting on. Expect the listed cases to run and pass. Required database and browser cases must show zero skips.

```sh
cd go && go test ./internal/web/stays/ -run 'GuestWriteEncryption|GuestEdit' -count=1 -v 2>&1 | tail -30
cd go && go test ./internal/web/guest/ -run 'GuestWriteEncryption|EncryptSaveFields|GuestSaveInsertCols' -count=1 -v 2>&1 | tail -30
```

Use fixture credentials and record only pass/fail, counts, and redacted diagnostics.

## 7. Acceptance

- [ ] Host create and edit write protected values only into `_enc`; guest self-save clears touched legacy columns.
- [ ] Hydration returns the replacement or explicit empty value, including on rows created before encryption.
- [ ] No sensitive field values appear in test output, audit detail or error logs.

## 8. Stop and ask

Stop and report if an anchor diverges after listed prerequisites, a required test fails twice, a dependency or file outside section 3 is needed, or the executor limit is reached. Escalate any need for live credentials, a real provider, a deployed server, or a product decision.

## 9. Report

Write `docs/tasks/2070-report.md` with the changed paths, command results, counts, acceptance evidence and owner steps. Set the brief to `Status: review` after completing the checks. Use `Status: blocked` in the report if stopped.

## Risk list (for the reviewer)

`go/internal/secure/guest_write.go`, `go/internal/web/stays/guest_edit.go`, `go/internal/web/guest/form_save.go`

## Owner steps

1. Start this after 2069 is in the executor base.
2. Review anonymized database evidence before releasing guest writes.
