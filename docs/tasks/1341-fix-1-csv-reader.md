# 1341-fix-1: statement CSV reader reads quotes like Python's csv module

Status: review
Depends on: 1341 | Base commit: c058518 | Branch: task/1341-go-billing-admin-data
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

`ParseCSV` in `go/internal/web/billing/bankimport.go` reads quotes differently from Python's `csv.reader` when text follows a closing quote (`"ab"cd` is `abcd` in Python, `ab"cd` in Go), which changes `message` and, without an ID column, `bank_tx_id`, so a later Go import would duplicate payments Python imported. Replace `encoding/csv` with a small reader that copies CPython's state machine, and make `validDate` reject year 0 (Python `date()` raises, the row is skipped).

## 2. Context

The code is already written and dry-run (gofmt, vet, `go test` with PostgreSQL 16 and without, golden script, pytest, lint: all green; with the old reader five new golden cases fail, with the new one all pass). You do not write code. §4 step 1 applies a patch file with `git apply`. **Do not open the patch** (214 lines, not needed). The new golden cases come from the real Python, so Go is checked against it.

Rules that apply: no new dependency (`encoding/csv` and `io` imports are removed, nothing added); no new outbound request; no new personal-data field (synthetic rows only, rule 3); `go/internal/billing` untouched.

What the patch does, for your information only:

1. `bankimport.go`: new `pyCSVRecords(text, delim)` (quote special only at field start, `""` inside quotes, text after a closing quote appended literally and the field continues unquoted, quoted line breaks, `\n` `\r` `\r\n` end a record, blank line is an empty record, data ending inside quotes keeps what was read); `ParseCSV` uses it; `validDate` returns `""` when `year < 1`.
2. `App/scripts/billing_admin_golden.py`: 12 new parser cases (`csv_text_after_quote`, `csv_doubled_quote_then_text`, `csv_quoted_delimiter_and_newline`, `csv_empty_quoted_field`, `csv_quote_inside_unquoted_field`, `csv_space_before_quote`, `csv_trailing_delimiter`, `csv_blank_lines`, `csv_cr_line_endings`, `csv_unterminated_quote`, `csv_comma_text_after_quote`, `csv_year_zero_skipped` with `5.1.0000` and `0000-01-05`).
3. `golden_test.go`: minimum statements 16 to 28, minimum compared rows 40 to 70.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/billing/bankimport.go` | edit (patch) | `pyCSVRecords`, `ParseCSV`, `validDate` |
| `go/internal/web/billing/golden_test.go` | edit (patch) | raised minimum counts |
| `go/internal/web/billing/testdata/billing_admin_golden.json` | regenerated | written by the script |
| `App/scripts/billing_admin_golden.py` | edit (patch) | 12 new parser cases |
| `docs/tasks/1341-report.md` | edit | append "Review follow-ups" |
| `docs/tasks/1341-fix-1-csv-reader.md` | edit | `Status:` line only |
| `docs/tasks/1341-fix-1-report.md` | new | your report |
| `docs/tasks/1341-fix-1-payload.patch` | untracked input | never `git add` it; `rm` it in step 5 |

`pyutil.go` is not touched. No other file may change.

## 4. Steps

Run every command from the repo root. Commit after each step with `git add <the step's files> && git commit`, first line `1341-fix-1 step k`, a blank line, then these two trailer lines (no push):

```
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Cjmb7PxGCxDzrj8mFfHxiP
```

Each command ends with `2>&1 | tail -30`.

### Step 1: apply the patch

```bash
echo "42ff25c506c6956cb69891e0983143d506dd2f80f9d47fae2d93ef33a477e208  docs/tasks/1341-fix-1-payload.patch" | sha256sum -c 2>&1 | tail -30
git apply --check docs/tasks/1341-fix-1-payload.patch 2>&1 | tail -30
git apply docs/tasks/1341-fix-1-payload.patch 2>&1 | tail -30
git status --porcelain 2>&1 | tail -30
sha256sum go/internal/web/billing/bankimport.go 2>&1 | tail -30
```

Expected: `OK`; the check and the apply print nothing; status lists `M` for exactly `App/scripts/billing_admin_golden.py`, `go/internal/web/billing/bankimport.go`, `go/internal/web/billing/golden_test.go` and `??` for the brief and the patch; the `bankimport.go` sha256 starts `bbb8d1f3e068`. Anything else: STOP (§8). Commit: `git add App/scripts go/internal/web/billing` (message `1341-fix-1 step 1`).

### Step 2: format and vet

```bash
(cd go && gofmt -l internal/web/billing/ 2>&1 | tail -30; go vet ./internal/web/billing/ 2>&1 | tail -30)
```

Expected: no output at all. No commit.

### Step 3: regenerate the golden file

```bash
(cd App && env -u UBYHOST_DATABASE_URL .venv/bin/python scripts/billing_admin_golden.py 2>&1 | tail -30)
sha256sum go/internal/web/billing/testdata/billing_admin_golden.json 2>&1 | tail -30
```

Expected: `wrote .../billing_admin_golden.json`, then a sha256 starting `e2ed47c6844d`. A different hash: STOP and report. Commit: `git add go/internal/web/billing/testdata` (message `1341-fix-1 step 3`).

### Step 4: Go tests with and without PostgreSQL, Python test, lint

Skip the start commands if `pg_isready -h 127.0.0.1 -p 54342` already answers. Run as root:

```bash
mkdir -p /var/tmp/pg1341f && chown postgres /var/tmp/pg1341f 2>&1 | tail -30
su postgres -c "/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1341f/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1341f/data -o '-p 54342 -c listen_addresses=127.0.0.1 -k /var/tmp/pg1341f' -l /var/tmp/pg1341f/log -w start" 2>&1 | tail -30
(cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:54342/postgres go test -count=1 -v ./internal/web/billing/ 2>&1 | grep -E "^(--- |ok|FAIL)" | tail -30)
(cd go && env -u UBYHOST_TEST_DATABASE_URL go test -count=1 -v ./internal/web/billing/ 2>&1 | grep -E "^(--- |ok|FAIL)" | tail -30)
(cd App && env -u UBYHOST_DATABASE_URL .venv/bin/python scripts/billing_admin_golden.py 2>&1 | tail -30)
git status --porcelain go/internal/web/billing/testdata 2>&1 | tail -30
(cd App && .venv/bin/python -m pytest tests/test_billing_admin_golden.py -q --tb=short -x 2>&1 | tail -30)
python3 scripts/context_lint.py 2>&1 | tail -30
su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1341f/data -m fast stop" 2>&1 | tail -30
rm -rf /var/tmp/pg1341f 2>&1 | tail -30
```

Expected: first `go test`: four `--- PASS` (`TestAdminReadSideMatchesPython`, `TestPureHelpersMatchPython`, `TestParseMatchesPython`, `TestInvoiceVS`) and `ok`; second: three `--- PASS`, one `--- SKIP: TestAdminReadSideMatchesPython`, `ok`; `git status --porcelain go/internal/web/billing/testdata` prints nothing; pytest `1 passed`; lint ends `context lint: OK` (WARN lines about other briefs are fine). A failing test: do not edit the Go files, STOP. No commit.

### Step 5: report

Delete the patch (`rm docs/tasks/1341-fix-1-payload.patch`; it was never added). Append this to the end of `docs/tasks/1341-report.md` exactly:

```
## Review follow-ups

1341-fix-1 fixed the CSV reader (own state machine copied from CPython's csv module) and year 0 in `validDate`. Known differences left, none on a path used yet:

3. `csvAmount` with `inf`: Go skips the row, Python fails the whole upload with an error.
4. `Trend(months <= 0)` differs from Python's list slicing; the page always passes 12.
5. Unicode digits in the `\d` regexes of Python are not matched by the Go `[0-9]` ones, and `"invoice": null` in a buyer snapshot reads differently (`_buyer`).
```

Set `Status: review` in this brief. Write `docs/tasks/1341-fix-1-report.md` (600 tokens at most, see §9). Commit `git add docs/tasks` (message `1341-fix-1 step 5`); `git status --porcelain` must then print nothing. Do not push; the orchestrator does.

## 5. Do not touch

Every file outside §3; `go/internal/billing/*`, `go.mod`, `go.sum`, `pyutil.go`, `App/app/*`; secrets, `.env`, servers. Hard rules: 1 (not on the filing path), 2, 3, 4, 5, 8.

## 6. Commands

The commands in §4 are the complete list. Test-map row: platform billing, only `tests/test_billing_admin_golden.py`.

## 7. Acceptance

- [ ] Step 1 sha256 `OK` and `bankimport.go` sha256 starts `bbb8d1f3e068`.
- [ ] `gofmt -l` and `go vet` print nothing.
- [ ] Golden sha256 starts `e2ed47c6844d`; rerun leaves `testdata` clean.
- [ ] `go test` with the database URL: four PASS and `ok`; without: three PASS, one SKIP.
- [ ] pytest `1 passed`; lint OK.
- [ ] `git diff --stat c058518..HEAD` lists only the §3 files (no patch file).
- [ ] PostgreSQL on port 54342 is stopped and `/var/tmp/pg1341f` is gone.

## 8. Stop and ask

Stop, and write the report, if:

- a sha256 mismatches or `git apply --check` fails;
- the golden sha256 differs from step 3;
- a test fails twice (the Go files are fixed text: do not edit them);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1341-fix-1-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of `go/internal/web/billing/bankimport.go` (`pyCSVRecords` against CPython `Modules/_csv.c` `parse_process_char`: START_RECORD, START_FIELD, IN_FIELD, IN_QUOTED_FIELD, QUOTE_IN_QUOTED_FIELD, EOF handling; `validDate`) and the new cases in `App/scripts/billing_admin_golden.py`.

## Owner steps

1. Nothing beyond the 1341 PR: this commit set is added to the same branch and PR. Merge as in the 1341 brief once CI is green.
