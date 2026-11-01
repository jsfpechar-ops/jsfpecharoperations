# 0551: Go G5d-3a: data keys, alerts and audit, in Go, matching Python
Status: todo
Depends on: 0550 (#644) | Base commit: main | Branch: claude/project-thread-4e8qj2
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 90k tokens
## 1. Objective
Plan v4 step 17 (G5), rule 1. G5d-3 is split: **3a** (this brief) gives Go the side effects `submit_batch` needs besides mail and push: the data-key loader (for `request_xml_enc`), alert raise/resolve, the audit row, and the two read helpers. 3b is mail, 3c push, 3d the `SubmitBatch` flow and its job kind. Nothing calls the new code yet; nothing changes in Python or in production.
## 2. Context
- Python source of truth:
  - Keys: `App/app/db.py` `_key_material` and `_fernet` (line 2221-2260), `App/app/config.py` `data_keys` (269), `legacy_data_key_enabled` (283), `_load_secret` (210: env `UBYHOST_SECRET_KEY`, at least 32 chars, else file `$UBYHOST_DATA_DIR/secret_key`, default dir `data`, stripped, at least 32 chars).
  - Alerts: `App/app/alerts.py` `raise_alert` (439) and `resolve` (534). Audit: `db.audit` (db.py 2138).
  - `App/app/reporting.py` `apartment_in_doubt` (1522) and `clear_stuck_alert_if_recovered` (1195).
- Go already has: `secure.NewFernet`, `secure.NewMultiFernet`, `secure.LegacyKey` in `go/internal/secure/fernet.go`; `ubyport.UTCNow`, `ubyport.FieldEncrypter`, `pyJSONDumps` in `go/internal/ubyport/store.go`; `ubyport.SubmissionMaxAutoAttempts`; the test pool helper `claimTestPool` and guest/apartment insert helpers in `go/internal/ubyport/claim_test.go` and `store_test.go` (same package: reuse them).
- **Traps:**
  - **Go must never create a secret file.** Python `secret_key()` mints one when absent; Go returns an error instead (like `require_secret_key`). Never put a key or the secret in an error message or log.
  - Legacy flag: `UBYHOST_DATA_KEY_LEGACY` default `"1"`; off only for `0,false,no,off` after trim+lowercase. No keys and legacy off is an error. The secret is read only when legacy is on or there are no keys. Order: data keys in list order, legacy key last. A malformed key gives `UBYHOST_DATA_KEYS entry N is not a valid Fernet key` (1-based, no value).
  - Alert `params` is `json.dumps(params, ensure_ascii=False, sort_keys=True)`: separators `", "` and `": "`, keys sorted, non-ASCII kept as is, `<>&` not escaped; nil or empty map stores NULL. Values used by `submit_batch` are strings and ints only: support those two and return an error for any other type.
  - Raise: owner from `apartment_id`, else from `reservation_id` (join apartment), when the caller gives none; key = `dedupe_key` or `kind:apartmentID:reservationID:message` where a missing id prints `None` (Python f-string of None). Open alert with that key (`resolved_at IS NULL`) is updated (`level, message, detail, params, created_at`), else inserted; on unique violation (`23505`, index `idx_alert_dedupe`) update the open one instead.
  - Audit: `at, actor, action, detail, owner_user_id`, `actor_user_id` and `impersonator_user_id` NULL (a background send has no signed-in actor), actor `"host"` default.
  - In doubt and stuck: copy the SQL exactly; stuck uses state `error` and `SubmissionMaxAutoAttempts`.
## 3. Files
New: `go/internal/secure/datakeys.go`, `go/internal/secure/datakeys_test.go`, `go/internal/ubyport/effects.go`, `go/internal/ubyport/effects_test.go`. Write `docs/tasks/0551-report.md`. Nothing else.
## 4. Steps
1. `datakeys.go`: `func LoadDataKeys(getenv func(string) string) (*MultiFernet, error)` following section 2 exactly (use the concrete MultiFernet type the package already has; read the file with `os.ReadFile`, never create it). Add `func (m *MultiFernet) EncryptString(plain string) (string, error)` only if no such method exists, so `m.EncryptString` fits `ubyport.FieldEncrypter`.
2. `datakeys_test.go` (no database): keys only, legacy off; keys + legacy from env secret (decrypts a token made with `LegacyKey`); no keys, secret from a temp `UBYHOST_DATA_DIR/secret_key` with surrounding whitespace; no keys + legacy off gives error; short secret gives error; missing file gives error and the file still does not exist after; malformed second key gives the entry-2 message and the message does not contain the bad value; `"OFF "` counts as off.
3. `effects.go`, package `ubyport`, top comment naming the Python lines:
   - `type AlertParams map[string]any`, unexported `pyJSONParams(AlertParams) (*string, error)`.
   - `func RaiseAlert(ctx context.Context, pool *pgxpool.Pool, level, kind, message, detail, dedupeKey string, apartmentID, reservationID, ownerUserID *int64, params AlertParams) error` (empty `dedupeKey` means none).
   - `func ResolveAlert(ctx, pool, dedupeKey string) error`.
   - `func Audit(ctx, pool, action, detail string, ownerUserID *int64) error` (actor `"host"`).
   - `func ApartmentInDoubt(ctx, pool, apartmentID int64) (bool, error)`.
   - `func ClearStuckIfRecovered(ctx, pool, reservationID int64) error`.
   - Each takes the time from `UTCNow()` as Python does.
4. `effects_test.go` (skips without `UBYHOST_TEST_DATABASE_URL`): raise twice with one key gives one row with the second message and params; resolve sets `resolved_at`, a later raise inserts a new row; owner filled from apartment and from reservation; key fallback with nil ids contains `None`; params bytes equal `{"count": 2, "property": "Byt á<1>"}`; non-string/int param errors and writes nothing; audit row fields; in-doubt true/false (guest on an `outcome_unknown` submission vs none, archived guest ignored); stuck alert resolved only when no guest on the stay is still `error` with attempts at the cap.
5. Commit: `0551: Go G5d-3a data keys, alerts and audit matching Python`.
## 5. Do not touch
`App/` (all), other files in `go/internal/`, `go/cmd/`, `go.mod`/`go.sum` (no new dependency), compose, CI, templates/CSS/JS.
## 6. Commands
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/secure/ ./internal/ubyport/ -count=1 2>&1 | tail -30`. Database tests skip locally; CI is their gate, say so.
- From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
`git diff --stat origin/main` lists only section 3 files and this brief. gofmt, vet and non-database tests pass locally; database tests pass in CI's `go` job with 0 skipped.
## 8. Stop and ask
Stop if `alert` or `audit` lacks a column named here, or if matching Python would need a new dependency.
## 9. Report
`docs/tasks/0551-report.md`: command tails, diff stat, anything you decided beyond section 2.
