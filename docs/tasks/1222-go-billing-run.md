# 1222: Go billing run (`billing` job: trials, roll, invoices, apartments, dunning)

Status: todo
Depends on: 1221 (the `billingjob.Invoicer` code must be on the branch; it needs 1220 `go/internal/pdf` too) | Base commit: cdcaefc | Branch: task/1222-go-billing-run
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add the Go port of `App/app/billing_jobs.run` and the registration of the `billing` job kind, so the owner can later hand the daily billing run to the Go service with one environment line. Nothing is switched on by this PR (`UBYHOST_GO_JOB_KINDS` is unchanged); Python stays the owner of the job until the owner switches it.

## 2. Context

- **What the run does** (Python is the oracle, `billing_jobs.run(day)`): nothing while `UBYHOST_BILLING_ENABLED` is not `1`/`true`/`yes`; else (1) `billing_trial.run`: start due trials (verified e-mail, Prague dates), send the 7/3/0-day reminder mails to hosts without a plan, finish ended trials (`active` on the ordered plan with its first period, else `paused`); (2) for every account in status `active`/`overdue`/`canceling` with a plan: `roll` (canceling and over: `paused`; else next period from `pending_change_json`, audit `billing_period`), `invoice_period` (issue and mail the period invoice once), `follow_apartments` (more or fewer active apartments than billed: `billing.apply_change` path with half-even rounding, a supplementary invoice and mail on an annual rise, carry under 50 Kč, pending change for a fall); one account's error never stops the others (audit `billing_run_failed`, `errors` count); (3) dunning: 7 days late reminder, 14 days late read-only (`paused`) plus mail, from 44 days a monthly mail (`monthly<(late-14)//30>`), status moves `active->overdue->paused` through the Python transition table and advisory lock. It returns the counts `rolled, invoiced, apartments, errors, trial_{started,reminded,active,paused}, dunning_{overdue,reminded,paused}` (four keys only while billing is off).
- **Go API.** `billingjob.Runner{Pool, Invoicer (nil: built on Pool), Owner (0: everyone)}.Run(ctx, today time.Time) (Counts, error)`; `Counts.Map()` gives Python's keys, `Counts.Total()` the number the job queue records (every count except `errors`). `BillingEnabled()` reads the environment at each call. The invoicing calls are brief 1221's `Invoicer` methods (`IssueForPeriod`, `IssueSupplementary`, `Send`, `Recipient`, `MailEnabled`, `AppBaseURL`, `PublicBaseURL`, `OperatorEmail`, `SupplementaryMinCZK`); `account`, `periodItems`, `fmtDate`, `floorDiv` are 1221's unexported helpers, used here because the files share the package. A failure in the trial step or the dunning step stops the run with an error (the exception does that in Python); the per-account loop never does.
- **Mails (new, Czech, `lang="cs"`):** `mail.BuildBillingTrial` (`billing_trial`, key `billing-trial-<owner>-<end>-<days>`) and `mail.BuildBillingOverdue` (`billing_overdue`, key `billing-overdue-<invoice>-<stage>`; the `monthlyN` stages read as `second`). Both go to the billing recipient with the operator in cc, payload `{"text","html","lang":"cs","reply_to"}` written as Python's `json.dumps`; nothing when mail is off or no recipient (not counted as reminded, as in Python). They reuse `thousands` and the footer constant of 1221's `mail/billing_invoice.go`.
- **Registration:** `go/cmd/ubyhost-web/register_job_billing.go` calls `registerJob("billing", 24*60, billingHandler)` from `init()`. The factory does not touch the pool while building (the existing tests call it with a nil pool). The handler passes `time.Now().Local()` (Python's `date.today()` is the server's local date) and returns `Counts.Total()`; per-account errors do not fail the job (Python's `_job_ok`).
- **Golden.** `App/scripts/billing_run_golden.py` seeds a throwaway SQLite with 44 hosts (one scenario each: trials started/not/future/at the Prague date boundary, reminders at 7/3/0 days to the login or billing address and with nobody to mail, trial finished to active and to paused, roll with a pending Max and TTLock, canceling over and not over, annual roll, annual rise with supplementary invoice, a rise banker-rounded 892.5 to 892, a carried 10 Kč, fall with and without a pending change, a missing buyer name failing with the others going on, dunning at 7/12/14/43/44/45 days, supplementary kind, voided, paid, storno, two invoices, no recipient) and calls the real `billing_jobs.run` five times (day, same day again, billing off, mail off, 2026-12-30 with mail `ses`). It dumps each run's counts plus `billing_account`, `platform_invoice` (without `pdf_blob`, `pdf_sha256`; `has_pdf`), the sequence, `audit` and `email_outbox` rows to `go/internal/billingjob/testdata/run.golden.json` (326 KB). `run_golden_test.go` replays the same seed and runs on Postgres and compares everything; it skips without `UBYHOST_TEST_DATABASE_URL`. `run_test.go` (no database) checks period end, activation dates, pending JSON writer, whole months, the enable switch and the mail texts against Python-produced values.
- All code was written and dry-run by the brief writer on a copy with 1220 and 1221 applied: gofmt, vet, `go build ./...`, `go test ./...` green; the DB tests pass on Postgres 16; two mutations (monthly threshold 44 to 45, half-even to half-up rounding) make `TestRunMatchesPython` fail; the golden script reproduces the file byte for byte on a second run. The files are under `docs/tasks/1222-files/` with a sha256 each; you only copy and verify. Do not edit them.
- **Known differences from Python (accepted):** (1) PDF bytes come from `go/internal/pdf` (as in 1221); (2) a mail that cannot be queued (mail disabled, no recipient, `EnqueueMail` error) is logged and the account is still counted, as `mail.enqueue` swallows errors; (3) the account list and the dunning list are ordered by owner and invoice id, Python's are unordered (only the invoice numbering order could differ); (4) `settle` (after a payment) is not ported: the run does not call it; (5) activation stamps accept RFC 3339, `YYYY-MM-DDTHH:MM:SS`, a space instead of `T`, or a date, which covers what the app writes; (6) the Go interval is 24 h from start, Python's job runs at 06:00 (the run is idempotent, a second run on the same day changes nothing, see golden run 2).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/billingjob/run.go` | create | `Runner`, `Counts`, `Run`, roll, invoice_period |
| `go/internal/billingjob/account.go` | create | account row, status machine, audit, pending JSON, `periodEnd` |
| `go/internal/billingjob/trial.go` | create | trial start/finish/reminders, trial and overdue mail queueing |
| `go/internal/billingjob/dunning.go` | create | dunning stages and monthly buckets |
| `go/internal/billingjob/apartments.go` | create | follow_apartments, apply_change, supplementary |
| `go/internal/billingjob/run_test.go` | create | helper tests (no database) |
| `go/internal/billingjob/run_golden_test.go` | create | golden replay on Postgres |
| `go/internal/billingjob/testdata/run.golden.json` | create | Python counts and rows, written by the script |
| `go/internal/mail/billing_trial.go` | create | `BuildBillingTrial` |
| `go/internal/mail/billing_overdue.go` | create | `BuildBillingOverdue` |
| `go/cmd/ubyhost-web/register_job_billing.go` | create | job registration |
| `App/scripts/billing_run_golden.py` | create | the golden script |
| `docs/tasks/1222-files/*` | keep | the attachments (already committed by the brief writer; leave them) |
| `docs/tasks/1222-report.md` | create | the report |

No other file may change.

## 4. Steps

Attachment sha256 (first 12 hex characters shown; the full values are in step 0):

- `run.go` 7123e1f25e12
- `account.go` 150ba25f307b
- `trial.go` 2617286a5572
- `dunning.go` 8ee412ce3815
- `apartments.go` 44d278e57b3d
- `run_test.go` d3765e6d378f
- `run_golden_test.go` 6599d7d1efd7
- `billing_trial.go` 56df8fb602b0
- `billing_overdue.go` 5e13b6fb40ec
- `register_job_billing.go` 7579ba395855
- `billing_run_golden.py` d092c274db89
- `run.golden.json` 823ef19d7dbd

### Step 0: anchors

From the repo root:

```bash
git status --short | head -5; ls go/internal/billingjob/invoicer.go go/internal/mail/billing_invoice.go go/internal/pdf/invoice.go 2>&1 | tail -3; ls go/internal/billingjob/run.go 2>&1 | tail -1; ls docs/tasks/1222-files | wc -l; cd docs/tasks/1222-files && sha256sum -c <<'EOF2' 2>&1 | tail -13
150ba25f307be08c785e3b38cd3a376c12abad529a6f65fa704bb556de023689  account.go
44d278e57b3d3ffdebe2b586a0e53e135b105f3f7621836841d3bd0e5e316f71  apartments.go
5e13b6fb40ec29a50ee606ece64dc9cd4847dc93ce7f7cc1ca14cc526a3891ea  billing_overdue.go
d092c274db8925750e6898af848f58d00661f67a01aec91a368d2130a032a4ab  billing_run_golden.py
56df8fb602b07d5ed7bd170f21a5fb14341f0c49097927a7ae6f79c78d27352e  billing_trial.go
8ee412ce381539c39a9fc67602550070553fb3034996bda4a6389e9943df990c  dunning.go
7579ba3958552861dc534093a8c67df3e1b2469315a26cd0c159d4cf43165eb5  register_job_billing.go
7123e1f25e12df761e2667f8d16894273259d0e13575685f54258dba3fddb21f  run.go
823ef19d7dbd6503d2274fbe57c08a9fdaf1a29b525454abf9aa6b85d72db486  run.golden.json
6599d7d1efd787952fa7a5ae3bf9a73bf7bf0f015229bf055654dc0ec5fc7edd  run_golden_test.go
d3765e6d378fa6c27639c27cf078aaa976159c312a6dfef9d849c09b3655326e  run_test.go
2617286a55d40cb4022b796147bdf6aa1984827ab81c415b97662cd6d0e343b1  trial.go
EOF2
```

Expected: empty status, the three Go files listed (briefs 1220 and 1221 applied; if any `ls: cannot access`, STOP: 1222 needs both), `ls: cannot access` for `run.go`, `12`, twelve lines ending `OK`. Anything else: STOP (§8).

### Step 1: the Go code

```bash
for f in run.go account.go trial.go dunning.go apartments.go run_test.go run_golden_test.go; do cp docs/tasks/1222-files/$f go/internal/billingjob/$f; done
cp docs/tasks/1222-files/run.golden.json go/internal/billingjob/testdata/
cp docs/tasks/1222-files/billing_trial.go docs/tasks/1222-files/billing_overdue.go go/internal/mail/
cp docs/tasks/1222-files/register_job_billing.go go/cmd/ubyhost-web/
cd go && test -z "$(gofmt -l internal/billingjob internal/mail cmd)" && go vet ./internal/billingjob ./internal/mail ./cmd/... 2>&1 | tail -10; go build ./... 2>&1 | tail -5; go test ./internal/billingjob ./internal/mail ./cmd/... -count=1 -v 2>&1 | grep -E '^(--- (FAIL|SKIP)|ok|FAIL|panic)' | tail -12; git status --short go.mod go.sum | tail -3
```

Expected: gofmt and vet silent, build silent, `--- SKIP` for `TestInvoicerMatchesPython`, `TestRunMatchesPython` and `TestRunDisabledDoesNothing` (no database variable yet), `ok` three times, no change to `go.mod` or `go.sum` (no new dependency; if either changes: STOP). Commit: `1222 step 1`.

### Step 2: the database test

Needs a Postgres. CI uses `postgresql://postgres:ubyhost@127.0.0.1:5432/ubyhost_test`; locally use any reachable Postgres 16 or 17 on which the user may create databases:

```bash
cd go && UBYHOST_TEST_DATABASE_URL="$UBYHOST_TEST_DATABASE_URL" go test ./internal/billingjob -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -15
```

Expected: `--- PASS` for `TestInvoicerMatchesPython`, `TestRunMatchesPython`, `TestRunDisabledDoesNothing`, the eight no-database tests of 1221 and 1222, and `ok` (the log shows a few `ERROR billing run failed for one account ... buyer_missing` lines: they are the two hosts the golden seeds without a buyer name). If no database is reachable, say so in the report and leave this step to CI (do not mark it done). A failing row or count diff: STOP (§8), do not edit the golden or the Go code.

### Step 3: the Python golden script, and proof that it reproduces the file

```bash
cp docs/tasks/1222-files/billing_run_golden.py App/scripts/billing_run_golden.py
cd App && (test -d .venv || (python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt)) 2>&1 | tail -3
.venv/bin/python scripts/billing_run_golden.py 2>&1 | tail -1; cd .. && git status --short go/internal/billingjob/testdata | tail -3; sha256sum go/internal/billingjob/testdata/run.golden.json | cut -c1-12
```

Expected: `wrote .../run.golden.json` (the script logs two `buyer_missing` tracebacks above it: Python's `log.exception` for the two seeded failures; `tail -1` hides them), no change shown for the testdata file (the script reproduces the committed JSON byte for byte; otherwise STOP and report), checksum prefix `823ef19d7dbd`. Commit: `1222 step 3`.

### Step 4: final check

Run the §6 commands, write the report, set `Status: review`. Push is NOT yours (§8).

## 5. Do not touch

Everything outside §3. In particular `go/internal/pdf`, `go/internal/billing`, `go/internal/ubyport`, the 1221 files (`go/internal/billingjob/{doc,invoicer,items,send,unit_test,invoicer_test}.go`, `go/internal/mail/billing_invoice.go`), `go/cmd/ubyhost-web/register_jobs.go` and the other `register_*.go`, `App/app/*` (read-only), `docs/context/*`, `docs/ENVIRONMENT.md`. Hard rules: 2 (the golden holds invented data only; the two new mails are kinds the Python job already sends to the same recipients; no new outbound request), 4 (no dependency; `time/tzdata` is the standard library), 5 (SQL stays in the Go package, parameterised, Postgres only; no schema change), 8 (no push, no merge).

## 6. Commands

```bash
cd go && test -z "$(gofmt -l internal/billingjob internal/mail cmd)" && go vet ./internal/billingjob ./internal/mail ./cmd/... && go build ./... 2>&1 | tail -5
cd go && go test ./internal/billingjob ./internal/mail ./cmd/... -count=1 2>&1 | tail -10
cd go && UBYHOST_TEST_DATABASE_URL="$UBYHOST_TEST_DATABASE_URL" go test ./internal/billingjob -count=1 -v 2>&1 | grep -cE '^--- PASS'
python3 scripts/context_lint.py 2>&1 | tail -5
```

Expected: silent / `ok` three times / `11` (with a database; `8` plus three `SKIP` without) / lint clean.

## 7. Acceptance

- [ ] `TestRunMatchesPython` passes against Postgres (counts of all five runs, accounts, invoices, sequence, audit and mail rows equal Python's), or the report says no database was reachable.
- [ ] `go build ./...` and vet clean; gofmt silent; `go.mod`/`go.sum` unchanged.
- [ ] `billing` is registered (`TestEveryHandlerHasInterval` and `TestLaneKindsDisjoint` pass) and `UBYHOST_GO_JOB_KINDS` is not touched anywhere.
- [ ] `git diff --stat` lists only §3 files (plus `docs/tasks/1222-files` unchanged).
- [ ] The golden script reproduces the committed JSON byte for byte.

## 8. Stop and ask

Stop, and write the report, if: an anchor or checksum differs; the 1221 or 1220 files are missing; a test fails twice; you reach 25 tool calls or about 50k tokens (report `blocked`, `Done: steps 1 to k`); `go.mod` or `go.sum` change; a file outside §3 needs a change; a step is unclear; you need push, merge or deploy (hand that to the owner).

## 9. Report

Write `docs/tasks/1222-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

`go/internal/billingjob/apartments.go` (read against `billing.apply_change` and `billing_order.change`: rounding, carry, pending, audit actor `host`), `go/internal/billingjob/dunning.go` (against `billing_jobs.dunning`), `go/internal/billingjob/trial.go` (against `billing_trial.run/start/finish`, activation dates, mail queueing), `go/internal/billingjob/run.go` and `account.go` (roll, status machine, advisory lock), `go/internal/mail/billing_overdue.go` and `billing_trial.go` (against `mail_notify.build_billing_*`).

## Notes for the coordinator (lines to add after the merge; the executor does not edit these files)

- `docs/ENVIRONMENT.md`, `UBYHOST_GO_JOB_KINDS` row: add `billing` to the list of kinds ("`billing` is the daily billing run: trials, periods, invoices, apartment counts, dunning; it needs `UBYHOST_BILLING_ENABLED`, the operator and billing variables the Python job reads, and the mail variables").
- `docs/context/status.md` (5 lines at most): "Go billing run ported (1222), not switched on; owner switches with `UBYHOST_GO_JOB_KINDS`."
- `docs/context/test-map.md`: row for `go/internal/billingjob`, `go/internal/mail/billing_*`, `go/cmd/ubyhost-web/register_job_billing.go`: `cd go && go test ./internal/billingjob ./internal/mail ./cmd/...` (with `UBYHOST_TEST_DATABASE_URL`); golden: `App/scripts/billing_run_golden.py`.
- `docs/context/decisions.md`: "1222: the billing run is ported to Go with a Python golden over five runs; Python keeps the job until the owner adds `billing` to `UBYHOST_GO_JOB_KINDS`; `settle` stays Python."
- `docs/context/known-issues.md`: the accepted differences of §2 (PDF bytes, mail errors logged, ordered lists, 24 h interval against 06:00).

## Owner steps

1. Merge when CI is green (the CI Postgres runs both golden replays). Nothing changes in production by this PR.
2. To hand the job to Go later (not before you have looked at one Go run in a copy): open the server `.env`, keep `billing` in `UBYHOST_JOB_QUEUE_KINDS`, add `billing` to `UBYHOST_GO_JOB_KINDS` (comma separated, no spaces), then run `./scripts/deploy.sh`. Python stops queueing that kind by itself.
3. The Go job runs once every 24 hours after the service starts, not at 06:00. A second run on the same day is harmless.
4. To hand it back: remove `billing` from `UBYHOST_GO_JOB_KINDS`, run `./scripts/deploy.sh`.
