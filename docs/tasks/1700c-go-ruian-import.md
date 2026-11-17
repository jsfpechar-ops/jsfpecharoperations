# 1700c: Go RUIAN address table and monthly import job

Status: todo — scoped (2026-11-17). Executable only after its exact-diff pass: sidecars in `docs/tasks/1700c-files/`, anchors and sha256 table (§2), written to the rules in [workflow](../context/workflow.md#writing-briefs-for-haiku). Until then the executor must not start it. The exact-diff pass (sidecars, sha256, anchors) comes later; this brief is scoped only.
Depends on: none (1700d depends on this) | Base commit: current tip of the working branch | Branch: task/1700c-go-ruian-import
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (split in two briefs if the exact-diff pass finds more)
Tier: A (schema change and a new outbound download; the orchestrator reads the full diff)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1700c step k`. Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1700c step'`.

## 1. Objective

Create the table that holds the ČÚZK address points and a Go job `ruian_import` that fills it once a month, as designed in [ruian-local](../plans/ruian-local.md) (§3 table, §4 import). Owner decision 2026-11-17, `[dep]` line in [decisions](../context/decisions.md). The job stays dormant until the owner adds `ruian_import` to the job-kind env lists.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first (this brief touches no filing code); 2 privacy first (public register data only, no personal data; the one new outbound host `vdp.cuzk.gov.cz` is named in the PR text); 3 no secrets and no real data (the fixture rows are made up); 4 no new dependency (stdlib only: `archive/zip`, `encoding/csv` or a manual split, own cp1250 table; `go.mod` must not change); 5 SQL only through the existing Go DB helpers, `$n` placeholders, a schema change is a new `App/migrations_pg/` file; 11 Go first.

**Facts (verified 2026-11-17, see the plan §2):** `https://vdp.cuzk.gov.cz/vymenny_format/csv/YYYYMMDD_OB_ADR_csv.zip` (about 63 MB, 6,258 CSVs, windows-1250, `;`, 19 columns, no quotes, about 3.03 M rows); the header is in the plan. Go container: `mem_limit` 128 MB, `/data` writable, so stream. The scheduler has no monthly trigger: use a daily trigger, the job skips when the month is already loaded.

**Pattern to copy:** a handler in `jobHandlers` (`go/cmd/ubyhost-web/register_jobs.go`), the trigger list in `go/internal/scheduler/scheduler.go`, `jobIntervals` for the retry cap, `go/internal/jobs/queue.go`. The ical job (`go/internal/ical`) is the model for an outbound fetch with a timeout.

**Parity:** none (new feature, no Python twin). Tests use a tiny fixture.

**Risk:** a bad import could empty the suggest table: the swap is one transaction and a sanity gate keeps the old table on failure.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/migrations_pg/00021_ruian_address.sql` | create | `CREATE EXTENSION IF NOT EXISTS pg_trgm`, tables `ruian_address`, `ruian_import`, GIN trigram index (plan §3); goose Up/Down, plain SQL, `SET LOCAL lock_timeout = '5s'` as in `00020`. If 00021 exists by then, use the next free number. |
| `go/internal/ruian/import.go` | create | download, zip streaming, cp1250 decode, fold, `COPY` to staging, gate, swap |
| `go/internal/ruian/fold.go` | create | `Fold(string) string` (lower case, Czech diacritics removed, spaces collapsed); used by 1700d too |
| `go/internal/ruian/import_test.go` | create | tests (below) |
| `go/internal/ruian/testdata/20261031_OB_999991_ADR.csv` | create | fixture: 12 made-up rows in windows-1250, header line included, 2 villages, one `č.ev.`, one empty street, one letter after the orient number |
| `go/cmd/ubyhost-web/register_jobs.go` | edit | add `ruian_import` handler and a `jobIntervals` entry (24 h) |
| `go/internal/scheduler/scheduler.go` | edit | add `{Kind: "ruian_import", Hour: 4, Minute: 45}`; update `scheduler_test.go` and the kind-count assertions it makes |
| `docs/tasks/1700c-report.md` | create | the report (§9) |

No other file may change. `docs/ENVIRONMENT.md` is not edited here: the proposed lines are in the plan §7, the owner approves them in the PR.

## 4. Steps

0. Checks (repo root). The exact-diff pass fills in the `grep -cF` anchors and the `ls` lines proving the new files do not exist. `ls App/migrations_pg | tail -1` must still say `00020_guest_contract.sql`, else take the next number and report it.
1. Copy the sidecars and run `sha256sum -c` on the table in §2: all OK.
2. Add the migration; run `UBYHOST_TEST_DATABASE_URL` Go schema tests if the repo has them (see the test-map row for `migrations_pg`).
3. Add `fold.go` and its table test (`"Václavské náměstí"` becomes `"vaclavske namesti"`, `Ř Ž Č Ě Ů Ď Ť Ň`).
4. Add `import.go`: `Import(ctx, pool, Options{BaseURL, Now, Dir, MinRows, Client})`: find the newest month with a HEAD (this month's last day before today, then the month before), skip when `ruian_import.data_date` equals it, download to `Dir/<date>.zip.part`, stream entries, `COPY` into the staging table without the GIN index, gate (at least `MinRows` and at least 90 % of the previous row count; production `MinRows` 2,500,000, tests pass 10), build the index, rename in one transaction, update `ruian_import`, delete the zip. Advisory lock around the run. `UBYHOST_RUIAN_ENABLED=0` returns at once.
5. Add the tests with an `httptest.Server` that serves a zip built in the test from the fixture: first run loads 12 rows; second run with the same date does not download (assert the GET count); a gate failure (zip with 2 rows, `MinRows` 10) keeps the old rows and returns an error; a 404 for every date returns no error and no change.
6. Register the handler and trigger; run §6; write the report.

## 5. Do not touch

`UBYHOST_GO_PATHS`, `UBYHOST_JOB_QUEUE_KINDS`, `UBYHOST_GO_JOB_KINDS` or any server file; `go.mod`, `go.sum`; anything under `App/app/` (Python suggest stays); `docs/ENVIRONMENT.md`; filing code.

## 6. Commands

- `cd go && gofmt -l . | tail -5` prints nothing
- `cd go && go vet ./internal/ruian/... ./internal/scheduler/... ./cmd/... 2>&1 | tail -20` is silent
- `cd go && go test ./internal/ruian/... ./internal/scheduler/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30` passes, no test skipped
- `git diff --stat -- go/go.mod go/go.sum | tail -3` prints nothing
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean

## 7. Acceptance

- The migration creates `ruian_address` (11 columns, GIN `gin_trgm_ops` index) and the one-row `ruian_import`; it applies on a fresh test database through the Go migrate path.
- The import loads the fixture, skips an unchanged month, keeps the old table on a gate failure or HTTP error, and never holds more than one zip entry in memory.
- Memory: the test does not read a whole entry into one string (review point).
- `ruian_import` is a daily 04:45 trigger and a `jobIntervals` entry; the job is dormant until the env lists name it.
- `git log --oneline --grep='^1700c step'` shows one commit per step; `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report instead of continuing when: an anchor is not found verbatim; `CREATE EXTENSION pg_trgm` fails in the test database (report the error, do not work around it); `go.mod` would change; a file outside §3 would have to change; the scheduler tests need a change beyond the one new trigger; a test needs a skip.

## 9. Report

Write `docs/tasks/1700c-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has: 1. files changed (`git show --stat`); 2. each command with the last 5 lines of output and the SKIP count; 3. §7 ticked; 4. deviations; 5. questions; 6. owner steps left.

## Risk list (for the reviewer)

Read the whole diff of `import.go` (swap transaction, gate, advisory lock, the host is fixed to `vdp.cuzk.gov.cz`, no redirect to another host, size limit on the download) and the migration (`DEFAULT`s, index definition).

## Owner steps

1. Answer the open questions in the plan §9 (Q1 okres source, Q2 extension rights, Q3 disk).
2. After the deploy applied `00021`: add `ruian_import` to `UBYHOST_JOB_QUEUE_KINDS` and `UBYHOST_GO_JOB_KINDS` in the env file (see docs/ENVIRONMENT.md), then `./scripts/deploy.sh` or restart the Go service.
3. After the first run: `SELECT data_date, rows FROM ruian_import;` shows today's month and about 3 million rows. Rollback: remove `ruian_import` from both lists again.
