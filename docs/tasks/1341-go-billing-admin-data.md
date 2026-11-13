# 1341: Go port of the read side behind /admin/fakturace (package billingweb)

Status: todo
Depends on: none | Base commit: a83df54 | Branch: task/1341-go-billing-admin-data
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add a new Go package `go/internal/web/billing/` (package `billingweb`) with the queries and pure helpers behind the operator billing page: the month's invoices, the unpaid list, account counts, the accountant's CSV, the bank statement parser (GPC and CSV, cp1250 aware), unmatched payments, the revenue analytics (portfolio, MRR/ARR, watchlists, aging, forecast, movement, funnel, trend, discounts, the bulk CSV ZIP) and one typed struct `AdminPageData` that assembles what `billing_admin_page` hands to its template. No route, no rendering, no write: the admin gate and the page come from other threads. A golden file written by the real Python keeps Go and Python from drifting.

## 2. Context

The code is already written and dry-run (build, vet, `go test` with PostgreSQL 16: green; mutation checks on floor division and half-to-even rounding fail the tests as they should). You do not write code. §4 step 1 runs an extractor that copies nine files out of the appendix file `docs/tasks/1341-payload.txt` and checks each sha256. **Do not open the payload**: it is about 2000 lines and would use your whole budget. Read this brief only (it is short).

Rules that apply: SQL is PostgreSQL only (this package only ever runs on it); no new dependency (`go.mod` is not touched: `golang.org/x/text` is already a direct requirement, the package uses its `encoding/charmap` and `unicode/norm`); no new outbound request (the statement parser takes bytes and returns rows); no new personal-data field (the golden file holds synthetic rows such as `alfa@example.test` and made-up statements, rule 3); `go/internal/billing` is read-only for you (`Quote`, `Monthly`, `Price` are imported, nothing there is edited).

### The exported API (package `billingweb`, import path `.../go/internal/web/billing`)

```go
type DB interface { Query(...); QueryRow(...) }      // *pgxpool.Pool and pgx.Tx fit
func AdminPageData(ctx, q DB, month, qstr, state string, today time.Time) (AdminPage, error)
func MonthOrCurrent(value string, today time.Time) string
func Invoices(ctx, q, month) ([]Invoice, error);  func Unpaid(ctx, q, today) ([]UnpaidInvoice, error)
func AccountsByStatus(ctx, q) (map[string]int64, error);  func ExportCSV(ctx, q, month) ([]byte, error)
func Parse(data []byte) ([]Payment, error);  ParseGPC, ParseCSV(text string);  IsStatementError(err); InvoiceVS(vs)
func Unmatched(ctx, q) ([]BankPayment, error)
func GetPortfolio, RevenueTotals, Watchlists, OperatorQueue, Aging, GetForecast, DiscountOverview(ctx, q, today)
func GetMovement(ctx, q, month);  GetFunnel(ctx, q);  Trend(ctx, q, months);  ExportAllZip(ctx, q, today) ([]byte, error)
func Kc(haler int64) string  // the page formatter (whole crowns, thousands with a space)
func KcCSV(haler int64) string  // "1234,50" for the CSV files
```

`today` is a `time.Time` of which only Y-M-D is used (zero means now). Every struct carries json tags equal to the Python dict keys, so the tests compare JSON. Every function comment names its Python source and line range. Behaviours kept from Python: `round` is half to even; money sums are floored (`//`); `trial_ends_at` is compared as text; `due_date[:10]` slices; the statement columns count characters, not bytes.

### What is not ported, or differs (not a gap in the golden file)

1. Left out on purpose: `export_zip` (it needs the PDFs), `bank_import.record / import_statement / mark_paid_manually` and `billing_analytics.write_month_snapshot` (the last one already exists in `go/internal/billing/snapshot.go`). `export_all_zip` holds three CSV files and no PDF; the test fails if the ZIP ever holds a `.pdf`.
2. `AdminPage` has no `posthog_url`, `signup_enabled`, `ads_export_days` (config values the page thread adds) and no `fmt_date`.
3. `_csv_amount`: Python's `float()` accepts `inf`, hex and non-ASCII digits; `inf` even crashes Python. Go reads these as "not a number" (the row is skipped). Normal, signed, exponent and `1_000` forms match.
4. `pyInt` for the GPC amount takes ASCII digits only; Python also accepts non-ASCII digits. A bad amount is an error in Go and `ValueError` in Python (golden case `gpc_bad_amount`).
5. CSV reading uses `encoding/csv` with lazy quotes. Odd quoting such as text after a closing quote may read differently from Python's `csv.reader`; the golden cases cover quotes, commas in quotes and a quoted line break.
6. SQL ties: `ORDER BY` calls that Python leaves open get an id tie-break in Go (watchlists, unverified, unmatched). The seed has no ties, so the golden comparison does not depend on it.
7. Null buyer fields in an invoice snapshot read as empty text (Python writes `billing_invoices._buyer` with `or ""`, so real rows never hold null).
8. A new dependency was NOT needed.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/billing/pyutil.go` | new | Python-behaviour helpers (strip, splitlines, floor division, CSV writer, day helpers) |
| `go/internal/web/billing/admin.go` | new | DB interface, `billing_admin` port, `Kc`, `ExportCSV` |
| `go/internal/web/billing/bankimport.go` | new | `bank_import` parser and `Unmatched` |
| `go/internal/web/billing/analytics.go` | new | `billing_analytics` port and `ExportAllZip` |
| `go/internal/web/billing/page.go` | new | `AdminPage`, `AdminPageData` |
| `go/internal/web/billing/golden_test.go` | new | pure and parser tests against the golden file (no database) |
| `go/internal/web/billing/admin_test.go` | new | database scenarios against the golden file; skips without `UBYHOST_TEST_DATABASE_URL` |
| `go/internal/web/billing/testdata/billing_admin_golden.json` | new | written by the script (not in the payload) |
| `App/scripts/billing_admin_golden.py` | new | writes the golden file from the real Python |
| `App/tests/test_billing_admin_golden.py` | new | fails when the golden file is stale |
| `docs/tasks/1341-payload.txt` | new, then removed | the file contents the step 1 extractor reads; step 6 runs `git rm` on it |
| `docs/tasks/1341-report.md` | new | your report |

No other file may change: not `go/internal/billing`, `go/cmd`, `go/internal/hostweb`, `session`, `jobs`, `go.mod`, `go.sum`, `docs/context/*`, `App/app/*`.

## 4. Steps

Run every command from the repo root (each `(cd X && ...)` is a subshell, so you stay in the root). Commit after each step with `git add <the step's files> && git commit` and a message of the first line `1341 step k`, then a blank line and these two trailer lines (no push):

```
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Cjmb7PxGCxDzrj8mFfHxiP
```

Each command ends with `2>&1 | tail -30`.

### Step 1: extract the files and check their sha256

```bash
python3 - <<'PYEOF' 2>&1 | tail -30
import hashlib, pathlib, re
text = pathlib.Path("docs/tasks/1341-payload.txt").read_text(encoding="utf-8")
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
print("files written:", found, "(expected 9)")
PYEOF
```

Expected: nine `ok` lines and `files written: 9 (expected 9)`. Any `SHA MISMATCH` or another count: STOP (§8). Commit: `git add go/internal/web/billing App/scripts App/tests` (message `1341 step 1`).

| File | sha256 starts |
|---|---|
| `go/internal/web/billing/pyutil.go` | `06d64c765004` |
| `go/internal/web/billing/admin.go` | `7e074a0f751c` |
| `go/internal/web/billing/bankimport.go` | `96054082d2e0` |
| `go/internal/web/billing/analytics.go` | `e2be53cc0af7` |
| `go/internal/web/billing/page.go` | `9fe6cd59fac6` |
| `go/internal/web/billing/golden_test.go` | `e5e45b017293` |
| `go/internal/web/billing/admin_test.go` | `3586421cb975` |
| `App/scripts/billing_admin_golden.py` | `7c18ac91df98` |
| `App/tests/test_billing_admin_golden.py` | `545300808d35` |

### Step 2: format and vet

```bash
(cd go && gofmt -l internal/web/billing/ 2>&1 | tail -30; go vet ./internal/web/billing/ 2>&1 | tail -30)
```

Expected: no output at all from either command. Anything printed: STOP. No commit.

### Step 3: write the golden file

The script assigns its own temporary data directory and database and refuses to run when `UBYHOST_DATABASE_URL` is set (it wipes tables): if it says "refusing to run", unset that variable in your shell for this command only (`env -u UBYHOST_DATABASE_URL ...`).

```bash
(cd App && (test -d .venv || (python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt)) 2>&1 | tail -30)
(cd App && env -u UBYHOST_DATABASE_URL .venv/bin/python scripts/billing_admin_golden.py 2>&1 | tail -30)
sha256sum go/internal/web/billing/testdata/billing_admin_golden.json 2>&1 | tail -30
```

Expected: `wrote .../billing_admin_golden.json`, then a sha256 line starting `cd60ba1ab98968e8`. A different hash: STOP (the Python side behaves differently from the dry run; report it). Commit: `git add go/internal/web/billing/testdata` (message `1341 step 3`).

### Step 4: start a throwaway PostgreSQL and run the Go tests

Skip the start commands if `pg_isready -h 127.0.0.1 -p 54341` already answers. Run as root:

```bash
mkdir -p /var/tmp/pg1341 && chown postgres /var/tmp/pg1341 2>&1 | tail -30
su postgres -c "/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1341/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1341/data -o '-p 54341 -c listen_addresses=127.0.0.1 -k /var/tmp/pg1341' -l /var/tmp/pg1341/log -w start" 2>&1 | tail -30
```

If the data directory already exists, skip `initdb` and run only `pg_ctl ... start`. Then:

```bash
(cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:54341/postgres go test -count=1 -v ./internal/web/billing/ 2>&1 | grep -E "^(--- |ok|FAIL)" | tail -30)
(cd go && env -u UBYHOST_TEST_DATABASE_URL go test -count=1 -v ./internal/web/billing/ 2>&1 | grep -E "^(--- |ok|FAIL)" | tail -30)
```

Expected, first command: four `--- PASS` lines (`TestAdminReadSideMatchesPython`, `TestPureHelpersMatchPython`, `TestParseMatchesPython`, `TestInvoiceVS`) and `ok`. Second command: three `--- PASS` and one `--- SKIP: TestAdminReadSideMatchesPython`, then `ok`. A failing test: read the last 30 lines, do not edit the Go files, STOP and report (the files are fixed text; a failure means the environment differs). No commit.

### Step 5: Python golden test, golden file unchanged, lint

```bash
(cd App && env -u UBYHOST_DATABASE_URL .venv/bin/python scripts/billing_admin_golden.py 2>&1 | tail -30)
git status --porcelain go/internal/web/billing/testdata 2>&1 | tail -30
(cd App && .venv/bin/python -m pytest tests/test_billing_admin_golden.py -q --tb=short -x 2>&1 | tail -30)
python3 scripts/context_lint.py 2>&1 | tail -30
```

Expected: `wrote ...`; `git status --porcelain go/internal/web/billing/testdata` prints nothing (committed and identical); pytest `1 passed`; the lint ends with `context lint: OK` (WARN lines about other briefs are fine). Then stop PostgreSQL and delete its directory:

```bash
su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1341/data -m fast stop" 2>&1 | tail -30
rm -rf /var/tmp/pg1341 2>&1 | tail -30
```

### Step 6: report and PR

Write `docs/tasks/1341-report.md` (600 tokens at most, see §9), set `Status: review` there and in this brief's header, run `git rm docs/tasks/1341-payload.txt`, commit `1341 step 6`, and open one DRAFT PR from `task/1341-go-billing-admin-data` (the orchestrator pushes if you cannot). The PR body states: nothing is routed or called yet; no new outbound request, no new personal-data field, no new dependency.

## 5. Do not touch

Every file outside §3; `go/internal/billing/*` (read-only), `go.mod`, `go.sum`, `App/app/*`; secrets, `.env`, servers. AGENTS.md hard rules that apply: 1 (nothing here is on the filing path; no route, no job), 2 (the parser makes no outbound request), 3 (no real data in the golden file), 4 (no new dependency), 5 (Postgres SQL, no schema change), 8 (draft PR, never push to `main`).

## 6. Commands

The commands in §4 are the complete list. Gate for the PR: step 2 prints nothing, step 4 `go test` is `ok` with the database URL (all four tests pass) and without it (one skip), step 5 pytest `1 passed`, `git status --porcelain go/internal/web/billing/testdata` empty, lint OK. Test-map row: platform billing, `test_billing_*.py` (only the new file is run).

## 7. Acceptance

- [ ] Step 1 printed nine `ok` lines and `files written: 9 (expected 9)`.
- [ ] `gofmt -l internal/web/billing/` and `go vet ./internal/web/billing/` print nothing.
- [ ] `go test ./internal/web/billing/` is `ok` with the database URL (`TestAdminReadSideMatchesPython` passes, 33 scenarios) and without it (the database test skips, the other three pass).
- [ ] The golden file sha256 matches step 3 and `git status --porcelain go/internal/web/billing/testdata` is empty after a rerun.
- [ ] `tests/test_billing_admin_golden.py` passes; `python3 scripts/context_lint.py` is OK.
- [ ] `git diff --stat main...HEAD` lists only the files in §3 (the payload file is gone again); nothing under `go/internal/billing` changed.
- [ ] The PostgreSQL on port 54341 is stopped and `/var/tmp/pg1341` is gone.

## 8. Stop and ask

Stop, and write the report, if:

- a sha256 mismatches or the extractor writes other than 9 files;
- the golden sha256 differs from step 3;
- a test fails twice (the Go files are fixed text: do not edit them);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1341-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of: `go/internal/web/billing/bankimport.go` (decodeText, ParseGPC column slices, csvAmount, ParseCSV), `go/internal/web/billing/analytics.go` (GetPortfolio rounding via `billing.Quote`/`Monthly`, floor division of money sums, the text comparisons in Watchlists, GetMovement), `App/scripts/billing_admin_golden.py` (the seed and the scenario `plan`: every function, month boundaries, the statement samples). The tests compare against the real Python output, so a changed rule shows as a failing scenario.

## Owner steps

1. Open the draft PR the executor created and wait for CI to turn green.
2. Merge it with `scripts/merge-pr-on-green.sh <PR number>` (nothing is routed, so the deploy changes no behaviour).
