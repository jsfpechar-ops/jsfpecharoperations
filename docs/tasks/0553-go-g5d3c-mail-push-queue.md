# 0553: Go G5d-3c: queue the submission_problem mail and the filing_problem push, matching Python
Status: todo
Depends on: 0552 (Go renderer `mail.BuildSubmissionProblem`) | Base commit: main | Branch: claude/project-thread-bhyvh5
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 90k tokens
## 1. Objective
Plan v4 step 17 (G5), rule 1. Go writes the same `email_outbox` row and the same `push_outbox` rows Python writes when UbyPort does not take a batch. Python's worker still sends both (nothing about delivery moves). Nothing calls the new code yet; 0554 wires it into `SubmitBatch`. Nothing changes in production.
## 2. Context
- Python source of truth:
  - Mail: `App/app/mail_notify.py` `submission_problem`/`_submission_problem` (827-918), `_entity_contact_email` (135), `stays_for_submission` (177). `App/app/mail.py` `enqueue` (231-300), `normalise_email` (157, `_EMAIL_RE` 138), `mail_enabled` (185: `UBYHOST_MAIL_BACKEND` trimmed+lowercased is `console` or `ses`; default `disabled`).
  - Push: `App/app/push.py` `notify` (267-308), `_clean_params` (254, `_PARAM_MAX` 120), `filing_problem` (468-483), `enabled` (57: `UBYHOST_WEB_PUSH` default `"1"`, off for `0,false,no` after trim+lowercase).
  - Local day: `App/app/deadlines.py` `local_now` (46), zone `Europe/Prague`.
- Go already has: `mail.BuildSubmissionProblem(appBaseURL, publicBaseURL, lang, ...)` and `mail.Stay` (with `PropertyName`, fill it from the stays query) (0552, #651), `ubyport.UTCNow`, `pyJSONDumps`/`writePyString` (ensure_ascii=True) in `go/internal/ubyport/store.go`, `pyJSONParams` (ensure_ascii=False) in `effects.go`, DB test helpers in `claim_test.go`, `store_test.go`, `effects_test.go` (same package: reuse).
- **Traps:**
  - Both functions are best-effort in Python: they never fail the filing. In Go return the error to the caller and document that the caller logs it and carries on; never put an e-mail address, a reason text or a key in an error message.
  - Mail payload is `json.dumps({"text","html","lang"})` in that key order with default `ensure_ascii=True` and separators `", "`/`": "`; use `pyJSONDumps` if it keeps key order, else write the three keys explicitly. `subject` is cut to 200 characters (runes).
  - Mail idempotency: `submission_problem:<apartmentID>:<state>:<YYYY-MM-DD local Prague date>`. An existing row with that key returns its id and inserts nothing. On a unique violation (`23505`) re-read the id.
  - `reservation_id` is the stay id only when exactly one stay, else NULL. `cc_email` NULL. `state` `queued`, `attempts` 0, `next_attempt_at` = `created_at` = `updated_at` = `UTCNow()`.
  - `normalise_email`: Python uses `email.utils.parseaddr`. Support the plain address and the `Name <addr>` form; anything else (commas, several `<`, quotes) returns "" (no mail), and say so in the code comment. Then lower, regex `^[^@\s]+@[^@\s]+\.[^@\s]+$`, at most 254 characters.
  - Stays: copy the SQL exactly (guest ids from `submission.guest_ids` JSON; bad JSON or empty means no stays), group and order as Python.
  - Push key: `filing_problem:<apartmentID>:<local date>:<subscriptionID>`, `ON CONFLICT(idempotency_key) DO NOTHING`, params `{"property": name}` with `ensure_ascii=False`, each value cut to 120 characters; url `/reservations/<id>` for exactly one stay else `/reservations`. Returns the number of rows inserted. No owner means 0.
  - Mail and push read the flags from a passed-in `getenv func(string) string`, not `os.Getenv` directly, so tests set them.
## 3. Files
New: `go/internal/ubyport/notify.go`, `go/internal/ubyport/notify_test.go`. Write `docs/tasks/0553-report.md`. Nothing else.
## 4. Steps
1. `notify.go`, top comment naming the Python lines:
   - `type ApartmentRef struct{ID int64; LegalEntityID, OwnerUserID *int64; InternalName string}`.
   - `func StaysForSubmission(ctx, pool, submissionID int64) ([]mail.Stay, error)`.
   - `func QueueSubmissionProblemMail(ctx, pool, getenv, appBaseURL, publicBaseURL string, apt ApartmentRef, submissionID int64, state, reason string, transport bool, now time.Time) (int64, error)` (0 means not queued; `now` gives the local date so tests are fixed).
   - `func QueueFilingProblemPush(ctx, pool, getenv, apt ApartmentRef, submissionID int64, now time.Time) (int, error)`.
2. `notify_test.go` (skips without `UBYHOST_TEST_DATABASE_URL`): mail off gives 0 and no row; no contact email gives 0; row fields and payload bytes equal `{"text": ..., "html": ..., "lang": "en"}` from the renderer; second call same day returns the same id and one row; a different state or next local day (use 22:30 UTC vs 23:30 UTC in winter) makes a new row; one stay sets `reservation_id`, two stays NULL; `Name <A@B.CZ>` gives `a@b.cz`; push: two devices give two rows, a repeat gives 0, push off gives 0, a 130-char name is cut to 120, url for one and two stays.
3. Commit: `0553: Go G5d-3c submission_problem mail and filing_problem push queueing matching Python`.
## 5. Do not touch
`App/` (all), other files in `go/internal/`, `go/cmd/`, `go.mod`/`go.sum`, compose, CI, templates/CSS/JS.
## 6. Commands
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/ubyport/ ./internal/mail/ -count=1 2>&1 | tail -30`. If `UBYHOST_TEST_DATABASE_URL` is set in your shell, the database tests run; else they skip and CI's `go` job is their gate: say which.
- From the repo root: `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
`git diff --stat origin/main` lists only section 3 files and this brief. Tests pass with 0 skipped in CI's `go` job.
## 8. Stop and ask
Stop if `email_outbox` or `push_outbox` lacks a column named here, or if matching Python needs a new dependency.
## 9. Report
`docs/tasks/0553-report.md`: command tails, diff stat, anything you decided beyond section 2.
