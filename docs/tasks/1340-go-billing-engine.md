# 1340: Go billing engine, a parity-checked port of billing.py and billing_order.py

Status: todo
Depends on: none | Base commit: a83df54 | Branch: task/1340-go-billing-pages
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add the subscription billing engine to the existing Go package `go/internal/billing/` as a reusable API (status machine, plan change, discount, order, cancel, resume, operator assign, trial extension, order-form validation) and a golden file written by the real Python, so Go and Python cannot drift. Later briefs build `/predplatne` and `/admin/fakturace` on this API; nothing here is a route or a job, so the port is off by construction.

This brief adds new files only. `quote.go` and `snapshot.go` are not edited. Invoice issuing, storno, PDF and mail are NOT here: the engine calls an `Invoicer` interface that the billing-job thread implements.

## 2. Context

The code is already written and dry-run (build, vet, `go test` with PostgreSQL 16: green). You do not write code. §4 step 1 runs a small extractor that copies every file out of the appendix at the end of this brief and checks its sha256. **Do not read the appendix**: it is about 2200 lines and would use your whole budget. Read lines 1 to 243 of this brief only (two reads of at most 150 lines).

Rules that apply: SQL must be PostgreSQL (the Go engine only ever runs on it); no new dependency (`go.mod` is not touched; the engine imports `ubyport` for `NormaliseEmail`, `UTCNow` and `PyString`, so `ubyport` must never import `billing`); no new outbound request; no new personal-data field (the buyer fields already exist in `billing_account`; audit rows carry action, detail and the actor string only).

### The API the customer-admin thread imports (package `billing`)

```go
type Invoicer interface {
    IssueForPeriod(ctx context.Context, owner int64, periodFrom, periodTo string, today time.Time) (int64, error)
    IssueSupplementary(ctx context.Context, owner int64, amountCZK int64, description, periodFrom, periodTo string, today time.Time) (int64, error)
    Storno(ctx context.Context, invoiceID int64, reason string, today time.Time) (int64, error)
    Send(ctx context.Context, invoiceID int64) error
}
type DB interface { Exec; Query; QueryRow }            // *pgxpool.Pool and pgx.Tx fit
type BillingAccount struct { ... }                      // one billing_account row, NULL text reads ""

func Account(ctx, q DB, owner int64) (*BillingAccount, error)        // nil when no row
func EnsureAccount(ctx, q DB, owner int64) (*BillingAccount, error)
func ApartmentCount(ctx, q DB, owner int64) (int, error)
func SetStatus(ctx, pool, owner int64, new, actor string) (bool, error)
func OperatorPause(ctx, pool, owner int64, actor string) (bool, error)
func ApplyChange(ctx, pool, owner int64, field string, value any, today time.Time, confirm bool, actor string) (ChangeResult, error)
func ApplyDiscount(ctx, pool, inv Invoicer, owner int64, percent int, reason, actor string, today time.Time) (DiscountResult, error)
func Change(ctx, pool, inv Invoicer, owner int64, field string, value any, confirm bool, today time.Time, actor string) (ChangeResult, error)
func Cancel(ctx, pool, owner int64, actor string) (bool, error)
func Resume(ctx, pool, owner int64, actor string) (bool, error)
func ReadForm(form map[string]string) (OrderValues, map[string]string)
func Place(ctx, pool, inv Invoicer, owner int64, v OrderValues, today time.Time, actor string) (PlaceResult, error)
func PlaceForOperator(ctx, pool, inv Invoicer, owner int64, v OrderValues, today time.Time, actor string) (PlaceResult, error)
func ExtendTrial(ctx, pool, owner int64, days int, actor string, today time.Time) (string, error) // "" = refused
func PeriodEnd(start time.Time, interval string) time.Time
func ICOOK(ico string) bool
func WithAuditActor(ctx context.Context, userID int64, username string, impersonatorUserID *int64) context.Context
var Statuses, Transitions, Plans, Intervals, Orderable, BuyerFields, ChangeColumns; const SupplementaryMinCZK = 50, HostActor = "host"
```

`pool` is `*pgxpool.Pool`. `today` is a `time.Time` of which only Y-M-D is used (zero means now). Actor strings are written to the audit row verbatim (for example `operator:<username>`). `ChangeResult`, `DiscountResult`, `PlaceResult` carry json tags equal to the Python dict keys; `InvoiceID` 0 means none.

### Errors: Python `raise ValueError("<code>")` to Go

Each is an exported `*billing.Error`; test with `errors.Is(err, billing.ErrX)` or `billing.Code(err) == "<code>"`. A wrapped error keeps its code.

| Python code | Go error | Raised by |
|---|---|---|
| `unknown status: <x>` | `ErrUnknownStatus` (code `unknown status`) | SetStatus |
| `one change at a time, from CHANGE_COLUMNS` | `ErrOneChange` | ApplyChange, Change (a field that is not in `ChangeColumns`) |
| `no ordered plan to change` | `ErrNoOrderedPlan` | ApplyChange, Change |
| `whitelabel_unavailable` | `ErrWhitelabelUnavailable` | ApplyChange, Change, Place, PlaceForOperator |
| `discount_out_of_range` | `ErrDiscountOutOfRange` | ApplyDiscount |
| `reason_missing` | `ErrReasonMissing` | ApplyDiscount |
| `no_plan` | `ErrNoPlan` | ApplyDiscount |
| `og` | `ErrNoAccount` | Place |
| `already_ordered` | `ErrAlreadyOrdered` | Place, PlaceForOperator |
| `bad_days` | `ErrBadDays` | ExtendTrial |
| `unknown plan or interval: <x> <y>` | `ErrUnknownPlan` | ApplyChange, ApplyDiscount (from the quote) |
| (no Python twin) | `ErrBadValue` | ApplyChange: value is not int, int64, bool or string |

Python `issue_supplementary` raises `below_minimum` under 50 Kc; that check belongs to the Invoicer implementation (the engine never asks for under 50).

### Known gaps (the page briefs close them)

1. Audit actor: `billing.WithAuditActor(ctx, userID, username, impersonatorUserID *int64)` is the Go twin of `db.set_current_actor` (auth.py calls it with `impersonating=True` only inside another workspace; pass `&userID` then, else nil). The audit insert behaves like `db.audit`: with an actor on ctx it fills `actor_user_id` and `impersonator_user_id` and replaces actor `host` by the username (any other actor string is kept); without one, both columns are NULL and the actor is written as given. Python's fallback of `owner_user_id` to `db._current_owner_id` is never needed: every engine function takes the owner. The golden file has `ctx_*` scenarios that set the actor in Python the way auth.py does.
2. `PlaceForOperator` writes `HostActor` for the inner order and status-active rows, as Python does; with `WithAuditActor` on ctx they become the username, exactly like Python. Without it they stay `host`.
3. `ReadForm` email uses `ubyport.NormaliseEmail`. It refuses a quoted display name (`"Q" <q@x.cz>`) that Python's `parseaddr` accepts: stricter, never looser. Pinned by `TestReadFormRefusesQuotedEmailName`; not in the golden file.

Audit gap 1 and 2 of the first draft are closed by `WithAuditActor` (see above).
4. `ICOOK` accepts ASCII digits only (Python accepts any Unicode decimal digit). Zip check uses `unicode.IsDigit` like the golden `form_zip_fullwidth_digits` case.
5. The row type is `BillingAccount` because Go cannot have a type and a function both named `Account`.
6. `ApplyChange` takes `field` and `value` apart; Python's "exactly one key" rule becomes "field must be in ChangeColumns". Add-on values are 0/1 ints (a Go bool is turned into 0/1; Python would store JSON `true` in the pending change, so pass ints like the Python callers do).
7. No row lock is taken by `ApplyChange`, `Place` and the others (Python takes none); only `SetStatus` and `OperatorPause` take `pg_advisory_xact_lock(hashtext('billing_account'), owner)` in a transaction and write the audit row after commit, as Python does.
8. `updated_at` and audit `at` use `ubyport.UTCNow()` (`2026-11-13T10:00:00+00:00`, same as `db.utcnow()`).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/billing/errors.go` | new | `Error`, `Code`, the sentinels |
| `go/internal/billing/invoicer.go` | new | the `Invoicer` interface |
| `go/internal/billing/engine.go` | new | account, status machine, ApplyChange, ApplyDiscount |
| `go/internal/billing/order.go` | new | ReadForm, Place, Change, Cancel, Resume, PlaceForOperator, ExtendTrial, PeriodEnd |
| `go/internal/billing/engine_test.go` | new | golden parity test, table test, error-code test, Send-failure test |
| `go/internal/billing/testdata/engine_golden.json` | new | written by the script (not in the appendix) |
| `App/scripts/billing_engine_golden.py` | new | writes the golden file from the real Python |
| `App/tests/test_billing_engine_golden.py` | new | fails when the golden file is stale |
| `docs/tasks/1340-payload.txt` | new, then removed | the file contents the step 1 extractor reads; step 6 runs `git rm` on it, so it is not in the PR's final diff |
| `docs/tasks/1340-report.md` | new | your report |

No other file may change: not `quote.go`, `snapshot.go`, `go/cmd/`, `go/internal/jobs`, `hostweb`, `session`, `ubyport`, `docs/context/*`, `docs/ENVIRONMENT.md`, `App/app/*`.

## 4. Steps

Run every command from the repo root (each `(cd X && ...)` is a subshell, so you stay in the root). Commit after each step with `git add <the step's files> && git commit -m "1340 step k"` (no push). Each command ends with `2>&1 | tail -30`.

### Step 1: extract the files and check their sha256

Run this exactly (it reads the payload file, writes the seven files, and prints one line per file; every line must say `ok`):

```bash
python3 - <<'EOF' 2>&1 | tail -30
import hashlib, pathlib, re
text = pathlib.Path("docs/tasks/1340-payload.txt").read_text(encoding="utf-8")
pattern = re.compile(r"^~~~~file (\S+) ([0-9a-f]{64})\n(.*?)\n~~~~$", re.S | re.M)
found = 0
for m in pattern.finditer(text):
    path, want, body = m.group(1), m.group(2), m.group(3) + "\n"
    got = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if got != want:
        print("SHA MISMATCH", path, got)
        continue
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(path).write_text(body, encoding="utf-8")
    print("ok", path)
    found += 1
print("files written:", found, "(expected 7)")
EOF
```

Expected: seven `ok` lines and `files written: 7 (expected 7)`. Any `SHA MISMATCH` or a count other than 7: STOP (§8). Commit: `git add go/internal/billing App/scripts App/tests && git commit -m "1340 step 1"`.

| File | sha256 starts |
|---|---|
| `go/internal/billing/errors.go` | `7c8d75687433` |
| `go/internal/billing/invoicer.go` | `a817bcd2bcd1` |
| `go/internal/billing/engine.go` | `b28c8af665e5` |
| `go/internal/billing/order.go` | `5c03055adb2e` |
| `go/internal/billing/engine_test.go` | `3beaa216fb5a` |
| `App/scripts/billing_engine_golden.py` | `566b1b55750e` |
| `App/tests/test_billing_engine_golden.py` | `0a1f93a196ca` |

### Step 2: format and vet

```bash
(cd go && gofmt -l internal/billing/ 2>&1 | tail -30; go vet ./internal/billing/ 2>&1 | tail -30)
```

Expected: no output at all from either command. Anything printed: STOP. No commit (no file changes).

### Step 3: create the venv if missing and write the golden file

```bash
(cd App && (test -d .venv || (python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt)) 2>&1 | tail -30)
(cd App && .venv/bin/python scripts/billing_engine_golden.py 2>&1 | tail -30)
sha256sum go/internal/billing/testdata/engine_golden.json 2>&1 | tail -30
```

Expected: `wrote .../engine_golden.json`, then the sha256 line must start with `5c43a6d54b315a31`. A different hash: STOP (the Python side behaves differently from the dry run; report it). Commit: `git add go/internal/billing/testdata && git commit -m "1340 step 3"`.

### Step 4: start a throwaway PostgreSQL and run the Go tests

Skip the start commands if `pg_isready -h 127.0.0.1 -p 54340` already answers. Run as root:

```bash
mkdir -p /var/tmp/pg1340 && chown postgres /var/tmp/pg1340 2>&1 | tail -30
su postgres -c "/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1340/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1340/data -o '-p 54340 -c listen_addresses=127.0.0.1 -k /var/tmp/pg1340' -l /var/tmp/pg1340/log -w start" 2>&1 | tail -30
```

If the data directory already exists, skip `initdb` and run only `pg_ctl ... start`. Then:

```bash
(cd go && gofmt -l internal/billing/ 2>&1 | tail -30)
(cd go && go vet ./internal/billing/ 2>&1 | tail -30)
(cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:54340/postgres go test -count=1 ./internal/billing/ 2>&1 | tail -30)
(cd go && env -u UBYHOST_TEST_DATABASE_URL go test -count=1 -v ./internal/billing/ 2>&1 | grep -E "^(--- |ok|FAIL)" | tail -30)
```

Expected: the first two print nothing; the third prints `ok   github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billing` (about 10 to 20 seconds, 119 database sub-tests); the fourth shows `--- PASS` for the pure tests, `--- SKIP` for `TestEngineMatchesPython`, `TestPlaceSendFailureKeepsOrder`, `TestAuditActorContext` and `TestWriteMonthSnapshotMatchesFixturePrices`, and ends with `ok`. A failing test: read the last 30 lines, do not edit the Go files, STOP and report (the files are fixed text; a failure means the environment differs). No commit.

### Step 5: Python golden test, golden file unchanged, lint

```bash
(cd App && .venv/bin/python scripts/billing_engine_golden.py 2>&1 | tail -30)
git status --porcelain go/internal/billing/testdata 2>&1 | tail -30
(cd App && .venv/bin/python -m pytest tests/test_billing_engine_golden.py -q --tb=short -x 2>&1 | tail -30)
python3 scripts/context_lint.py 2>&1 | tail -30
```

Expected: `wrote ...`; `git status --porcelain go/internal/billing/testdata` prints nothing (the golden file is committed and identical); pytest `1 passed`; the lint ends with `context lint: OK` (WARN lines about other briefs are fine). Then stop PostgreSQL: `su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1340/data -m fast stop" 2>&1 | tail -30`.

### Step 6: report and PR

Write `docs/tasks/1340-report.md` (600 tokens at most, see §9), set `Status: review` there and in this brief's header, run `git rm docs/tasks/1340-payload.txt`, commit `1340 step 6`, and open one DRAFT PR from `task/1340-go-billing-pages` (the orchestrator pushes if you cannot).

## 5. Do not touch

`go/internal/billing/quote.go`, `snapshot.go` and their tests; every file outside §3; `go.mod`, `go.sum`; `App/app/*`; secrets, `.env`, servers. AGENTS.md hard rules that apply: 1 (nothing here is on the filing path; the engine registers no route or job), 3 (no secrets; the golden file holds only synthetic rows such as `owner1@example.test`), 4 (no new dependency), 5 (Postgres SQL, schema untouched), 8 (draft PR, never push to `main`).

## 6. Commands

The commands in §4 are the complete list; their expected output is stated in each step. Gate for the PR: step 2 and step 4 print no `gofmt`/`vet` output, step 4 `go test` is `ok` with and without `UBYHOST_TEST_DATABASE_URL`, step 5 pytest `1 passed`, `git status --porcelain go/internal/billing/testdata` empty, lint OK.

## 7. Acceptance

- [ ] Step 1 printed seven `ok` lines and `files written: 7 (expected 7)`.
- [ ] `gofmt -l internal/billing/` and `go vet ./internal/billing/` print nothing.
- [ ] `go test ./internal/billing/` is `ok` with the database URL set (119 sub-tests of `TestEngineMatchesPython` pass) and without it (database tests skip, pure tests pass).
- [ ] The golden file sha256 matches step 3 and `git status --porcelain go/internal/billing/testdata` is empty after a rerun of the script.
- [ ] `tests/test_billing_engine_golden.py` passes; `python3 scripts/context_lint.py` is OK.
- [ ] `git diff --stat main...HEAD` lists only the files in §3 (the payload file is gone again); `quote.go` and `snapshot.go` are untouched.

## 8. Stop and ask

Stop, and write the report, if:

- a sha256 mismatches or the extractor writes other than 7 files;
- the golden sha256 differs from step 3;
- a test fails twice (the Go files are fixed text: do not edit them);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1340-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of: `go/internal/billing/engine.go` (SetStatus, OperatorPause, ApplyChange rounding and supplementary rule, ApplyDiscount storno/reissue order), `go/internal/billing/order.go` (Place, Change, PlaceForOperator, ExtendTrial, PeriodEnd), `App/scripts/billing_engine_golden.py` (the scenario list: every function and every error code). The tests compare against the real Python output, so a changed rule shows as a failing sub-test.

## Owner steps

1. None for this brief: it adds a library and tests only. Merge the draft PR when CI is green (`scripts/merge-pr-on-green.sh`).
2. The page briefs that follow import `go/internal/billing`; nothing changes in production until one of them registers a route.
