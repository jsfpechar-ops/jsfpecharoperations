# 0642: Go: queue the "cancelled stay with guest forms" mail and push like Python
Status: review
Depends on: none | Base commit: origin/main | Branch: task/0642-go-cancelled-notify
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 90k tokens
## 1. Objective
Third slice of porting the `ical` job to Go. When a calendar cancels a stay whose guests already filled forms, Python queues one host e-mail (`App/app/mail_notify.py` `cancelled_with_guests`, 1131-1190) and one push per device (`App/app/push.py` `cancelled_with_guests`, 528-548). Go gets the same two outbox inserts so the later sync slice can call them. Nothing calls them yet; nothing changes in production.
## 2. Context
- The police port already queues mail and push: `go/internal/ubyport/notify.go` (`QueueSubmissionProblemMail` 192, `QueueFilingProblemPush` 275, `mailPayload`, `pushEnabled`, `cutRunes`, `normaliseEmail`) and `go/internal/mail/submission_problem.go` (HTML blocks, `fmtDate`, colours). Reuse them; do not copy them.
- Python push: `notify()` in `App/app/push.py` 267 (read it whole: key format `<kind>:<key>:<subscription id>`, params JSON, `_PARAM_MAX`), `_day` 461.
- English strings: `App/app/host_i18n.py` 676-681. Only `en` is ported (`HOST_MAIL_LANGUAGE = "en"`). Mail helpers `_shell`, `_block_*`, `_app`, `_text`, `_entity_contact_email` 135 in `App/app/mail_notify.py`: read only what you need.
- Golden: `App/scripts/mail_golden.py` writes the Python oracle into `App/tests/golden/mail/`; the Go mail tests compare against it. Add the two variants (`cancelled`, `disappeared`) there the same way the existing cases are made.
- **Traps:**
  - Payload is `mailPayload` (text, html, lang "en", ensure_ascii). Subject cut to 200 runes. Idempotency key `cancelled_with_guests:<reservation>:<variant>`; mail row carries `apartment_id`, `owner_user_id`, `reservation_id` NULL (Python `enqueue` gets no reservation_id here: check `mail.enqueue` in `App/app/mail.py` and match it exactly). An existing key returns the existing id; a 23505 race returns the winner's id.
  - Python returns None on any error and logs; Go returns an error and the caller decides. No contact e-mail, no apartment or no reservation: return 0 and nil.
  - Push params `{"property": internal_name or "", "date": DD.MM.YYYY}`, each cut to 120 runes, Python `json.dumps` key order as written. URL `/reservations/<id>`. Push off (`pushEnabled`) or no owner: 0 rows.
## 3. Files
- Edit `go/internal/ubyport/notify.go`: add exported `QueuePush(ctx, pool, getenv, ownerUserID int64, kind, key, url string, params AlertParams) (int, error)` and `EnqueueMail(ctx, pool, m OutboxMail) (int64, error)` (struct with kind, key, reservation/apartment/owner ids, to, subject, text, html); make `QueueFilingProblemPush` and `QueueSubmissionProblemMail` call them. Behaviour of both stays byte-identical: their existing tests must pass unchanged.
- New `go/internal/mail/cancelled_with_guests.go` + `_test.go`: `BuildCancelledWithGuests(appBaseURL, lang, propertyName, dateFrom, variant string, reservationID int64) (Content, error)`.
- New `go/internal/ubyport/cancelled_notify.go` + `_test.go`: `QueueCancelledWithGuestsMail(ctx, pool, getenv, apartmentID, reservationID int64, variant string) (int64, error)` and `QueueCancelledWithGuestsPush(ctx, pool, getenv, apartmentID, reservationID int64) (int, error)`.
- Edit `App/scripts/mail_golden.py`; new golden files under `App/tests/golden/mail/` it writes.
- Write `docs/tasks/0642-report.md`.
## 4. Steps
1. Refactor notify.go onto `QueuePush`/`EnqueueMail`; run the ubyport tests before going on.
2. Mail builder + golden test for both variants (text, HTML and subject equal byte for byte).
3. The two queue functions; DB tests in the style of `notify_test.go` (they skip without `UBYHOST_TEST_DATABASE_URL`; set it, see section 6): one mail row with exact columns, second call returns the same id; push one row per device, second call 0 rows, push off 0 rows.
4. Commit: `0642: Go queues the cancelled-stay-with-guests mail and push like Python`.
## 5. Do not touch
`App/app/` (all), other `go/internal/` packages, `go/cmd/`, `go.mod`/`go.sum`, compose, CI, templates/CSS/JS.
## 6. Commands
- Local Postgres: `pg_ctlcluster 16 main start; su postgres -c "psql -c \"ALTER USER postgres PASSWORD 'ubyhost'\""`, then `export UBYHOST_TEST_DATABASE_URL=postgres://postgres:ubyhost@127.0.0.1/postgres`.
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/ubyport/ ./internal/mail/ -count=1 2>&1 | tail -30`.
- From the repo root: from `App/`: `.venv/bin/python scripts/mail_golden.py` (read its argparse for the output flag; create `.venv` first if missing: `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt`), then `git diff --stat`, and `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
`git diff --stat origin/main` lists only section 3 files and this brief. gofmt, vet and tests pass with the DB URL set, 0 skipped in the new tests. Existing ubyport tests unchanged and green.
## 8. Stop and ask
Stop if the refactor would change any existing outbox row, or matching Python needs a new dependency.
## 9. Report
`docs/tasks/0642-report.md`: command tails, diff stat, any difference from Python.
