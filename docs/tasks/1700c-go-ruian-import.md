# 1700c: Go RUIAN address table and monthly import

Status: todo
Depends on: none (1700d depends on this) | Base commit: current tip of the working branch | Branch: task/1700c-go-ruian-import
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (this brief needs about 12 calls)
Tier: A (schema change and a new outbound download; the orchestrator reads the full diff)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1700c step k` (`k` is the step number). Never create a branch, never push, never open a PR. Acceptance checks use `git log --oneline --grep='^1700c step'`.

## 1. Objective

Create the table that holds the ČÚZK address points and a Go import that fills it once a month, as designed in [ruian-local](../plans/ruian-local.md) (§3 table, §4 import). Owner decision 2026-11-17, `[dep]` line in [decisions](../context/decisions.md). The import is dormant until the owner sets `UBYHOST_RUIAN_IMPORT=1`.

## 2. Context

Hard rules (AGENTS.md): 1 filing is not touched; 2 privacy: public register data only, no personal data, no retention line; the one new outbound host `vdp.cuzk.gov.cz` (monthly GET plus a HEAD every six hours, no data sent) goes into the PR text; 3 no secrets, fixture rows are made up; 4 no new dependency (`golang.org/x/text` is already a direct requirement, `go/go.mod` line 13, and `charmap.Windows1250` is in it; `go.mod` and `go.sum` must not change); 5 plain SQL through `pgxpool`, `$n` placeholders, the schema change is the new `App/migrations_pg/00021_ruian_address.sql`; 11 Go first, no Python golden (Go tests with hand-written expected values).

**All code is pre-written, compiled and tested.** Sidecars: `docs/tasks/1700c-files/<repo path>.txt`. Step 1 copies them; never retype or edit them. Step 2 applies one patch (`edits.patch.txt`) to four existing files.

| sha256 | file | action | lines |
|---|---|---|---|
| `b0fda9adb206ca097ce8fcd0e2d5bd52948d8238019cb74d5824be404ead10c4` | `App/migrations_pg/00021_ruian_address.sql` | create | 38 |
| `1e570cab4b7fe68fb0c8e2e84d549d1f13c56f1cef2335fc41da67ba509bfaa1` | `go/internal/ruian/attribution.go` | create | 9 |
| `5ee792b89a15c4a11d36bad84ac63198587a76d498fffea3bc329edc7fef8ae4` | `go/internal/ruian/fold.go` | create | 36 |
| `88fc5d97bc8bfef8bcda57ae16aa9725db9e281e8e9abc1cdc0cf802601789f3` | `go/internal/ruian/okres.go` | create | 38 |
| `cede1ab6b379bc65caca48bbca488f79c5a5103139fcc65509984cce335a21be` | `go/internal/ruian/okres.csv` | create | 6258 |
| `37015d6b3dd802540da30453d20e3cbd87a705bd31c31b8c1631b414a94e8f9c` | `go/internal/ruian/row.go` | create | 110 |
| `40835be6aa75c79fe7d3b6f0b06c155d407a09eee508a7f4c2e86199b7ed921e` | `go/internal/ruian/import.go` | create | 239 |
| `1075de19f520a132c66fb45cb6d8eef588c1f4f2759494c0f4ca7e0fab319d4e` | `go/internal/ruian/ruian_test.go` | create | 303 |
| `3fa054d3d933ec645a535f2fd636bb089e08dbd31d142c5ebf6230adab73141e` | `go/internal/ruian/testdata/20261031_OB_999991_ADR.csv` | create | 14 |
| `14e77b9e4ce3fd1a80f1cbb48a6550d517346e87cfcad208abe9977e8ab2af42` | `go/cmd/ubyhost-web/register_ruian_import.go` | create | 60 |
| `0d63908f8a613bd7172ad6125ae311418077344254aa07d5508a8253b3dea13b` | `go/cmd/ubyhost-web/register_ruian_import_test.go` | create | 37 |
| `dd1b22347b8103209e966b4a61f68557483a61c249e41b2caddc288a27f39ab3` | `docs/tasks/1700c-files/edits.patch.txt` | patch (4 files) | 60 |

**How the code is built (for the reviewer; the executor only copies and runs).**

- `00021_ruian_address.sql`: goose-only (no SQLite twin, like 00020). `CREATE EXTENSION IF NOT EXISTS pg_trgm`, `UNLOGGED` `ruian_address` (the plan's 11 columns plus `okres`, see item d), GIN `gin_trgm_ops` index, logged one-row `ruian_import`. `SET LOCAL lock_timeout = '5s'` as in 00020.
- `row.go`: `parseLine` (19 `;` columns, no quotes; skips a line without numeric code, numeric obec code or house number; `č.ev.` sets `is_evid`; `orient_no` = number plus letter; `district` = Název MOMC, else Název obvodu Prahy; `okres` from the bundled list) and `zipRows`, a `pgx.CopyFromSource` that streams every `.csv` entry line by line through `charmap.Windows1250` (never a whole entry in memory).
- `import.go`: `Run(ctx, pool, Options)`: session advisory lock (a second run returns at once); HEAD for the last day of last month, then the month before (404 on both: no error, no change; other status: error); skip when `ruian_import.data_date` is that month and the table is not empty (an empty table after a crash is re-imported); GET to `Dir/<date>.zip.part` (25 min, 300 MB cap, redirects only to the same host, `User-Agent: UbyHost`); staging `UNLOGGED` table without indexes, `COPY`; gate (`MinRows`, and at least 90 % of the previous count when the table was not empty), then one transaction builds primary key and GIN index (`maintenance_work_mem` 256 MB), `ANALYZE`, then one transaction swaps (`DROP`, rename table and both indexes, upsert `ruian_import`). Any error drops the staging table and keeps the old rows; the zip is always deleted.
- `register_ruian_import.go`: a background task (`registerBackground`, like `job_purge`), not a job-queue kind: the scheduler plan is locked to Python's `add_job` list (`go/internal/scheduler/parity_test.go`), so a new kind would need a Python change. Dormant unless `UBYHOST_RUIAN_IMPORT` is exactly `1`, `UBYHOST_RUIAN_ENABLED` is not `0` and `UBYHOST_ENABLE_SCHEDULER` is not off. First check 5 minutes after start, then every 6 hours (the check is one HEAD and one query when nothing is new). Data folder `$UBYHOST_DATA_DIR/ruian`, default `/data/ruian`.
- `okres.csv` (+ `okres.go`): obec code to okres name, 6,258 lines.
- `attribution.go`: the one place of the credit line `ruian.Attribution`.
- `edits.patch.txt`: `backup.sh` (adds `--exclude-table-data=ruian_address` to the existing `pg_dump` line, after the database name so `test_pg_backup_scripts.py`'s `pg_dump -U ubyhost -Fc ubyhost` still matches), `go/internal/schema/testdata/goose_statements_golden.json` (the five statement hashes of 00021; the Go test `TestGooseFilesMatchPython` fails without them), `App/tests/test_db_postgres.py` lines 260-261 (73 to 75 tables, 3 to 5 extra), `docs/ENVIRONMENT.md` (one row `UBYHOST_RUIAN_IMPORT`).

**Resolved open items (plan §9 Q1, Q2, Q4, Q5; each with its evidence).**

- **a. Extension rights (Q2).** `ubyhost_app` cannot run `CREATE EXTENSION pg_trgm`: `deploy/lightsail/scripts/pg-app-role.sql:18-24` makes it `NOSUPERUSER` and grants only `CONNECT ON DATABASE`; PostgreSQL's trusted-extension rule needs `CREATE` on the database. Checked on PostgreSQL 16 with a `NOSUPERUSER` role that owns schema `public`: without the extension the migration fails with `permission denied to create extension "pg_trgm"`; with the extension created by a superuser first, the same migration runs through (`NOTICE: extension "pg_trgm" already exists, skipping`, `IF NOT EXISTS` returns before the permission check). So the migration stays as written and the owner runs the one command in "Owner steps" **before the merge** (a green merge auto-deploys and `deploy.sh` runs pending migrations first; without the step the deploy stops at 00021 and the app keeps running the old version).
- **b. Licence (Q4).** ČÚZK states the CSV address data (`RUIAN-CSV-ADR-OB`, per municipality, and the hierarchy set `RUIAN-CSV-HIE-ST`) is open data under CC BY 4.0: https://geoportal.gov.cz/php/micka/record/basic/CZ-00025712-CUZK_SERIES-MD_RUIAN-CSV-HIE-ST?dlang=eng ("Dataset is provided as Open Data (licence CC-BY 4.0)"); the ADR record is `CZ-00025712-CUZK_SERIES-MD_RUIAN-CSV-ADR-OB` on geoportal.cuzk.cz. CC BY needs a credit. The credit text lives in one place: the constant `ruian.Attribution` (`go/internal/ruian/attribution.go`, "Adresní data: ČÚZK, RÚIAN (CC BY 4.0)"). Brief 1700d shows it once where the suggestions appear; no other copy.
- **c. `č.ev.` in Python (Q5).** Python stores no flag and no marker: `App/app/ruian.py:147-149` copies the RÚIAN `cislodomovni` value into `addr_house_no` whatever the building type is, so an evidence number lands in `addr_house_no` exactly like a house number. The Go table keeps `is_evid` for display and returns `house_no` the same way (1700d).
- **d. Okres list (Q1).** There is no okres column in the address CSV (plan a5). The bundled list is `go/internal/ruian/okres.csv`, generated once on 2026-11-17 from two ČÚZK files, both CC BY 4.0: `OKRES_KOD` per `OBEC_KOD` in `strukturovane-CSV/vazby-cr.csv` of `https://vdp.cuzk.gov.cz/vymenny_format/csv/20261031_strukt_ADR.csv.zip` (34 MB, dataset `RUIAN-CSV-HIE-ST`; found through https://atom.cuzk.cz/RUIAN-CSV-HIE-ST/datasetFeeds/CZ-00025712-CUZK_RUIAN-CSV-HIE-ST_1.xml), and the 76 okres names (`<oki:Nazev>`) from `https://vdp.cuzk.gov.cz/vymenny_format/soucasna/20261031_ST_UKSH.xml.zip`. 6,258 obce, 76 okresy; Praha (554782) has an empty okres code, so it gets Python's text "Hlavní město Praha" (`App/app/ruian.py:168-169`). Refresh by hand once a year (owner task, not a job); the recipe is in the header comment of `okres.go`. New column `okres` in `ruian_address` (the plan §3 table had none): the import fills it, so 1700d reads it and needs no lookup.
- **e. Backup exclusion.** `deploy/lightsail/scripts/backup.sh:57` is the only daily and pre-deploy dump (`docker compose exec -T postgres pg_dump -U ubyhost -Fc ubyhost`). The patch adds `--exclude-table-data=ruian_address`: the dump keeps the `UNLOGGED` table definition and the GIN index, not the 3 M rows, and a restore gives an empty table that the import refills at the next check. `pg-cutover.sh:142` (rehearsal dump) is not changed: a rehearsal compares row counts and is rare. WAL-G: an `UNLOGGED` table writes no WAL, and base backups skip unlogged relation files (PostgreSQL documentation, "Unlogged tables"; not measured here).

**Verified by the brief writer** (in a throwaway worktree of the branch tip 331fd5d, steps 0-5 applied exactly as written from the sidecars, PostgreSQL 16 on port 55700, Go 1.26.0): every `sha256sum -c` line OK, `git apply` clean, `gofmt -l`, `go build ./...` and `go vet` silent, `go.mod` and `go.sum` unchanged, four `ok` lines in step 5, the nine named tests `--- PASS`, SKIP count 3 (the probes), `context lint: OK`. The Python checks of step 6 were not run (no `App/.venv`).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/migrations_pg/00021_ruian_address.sql` | create | tables, extension, index |
| `go/internal/ruian/attribution.go`, `fold.go`, `okres.go`, `okres.csv`, `row.go`, `import.go`, `ruian_test.go` | create | the package |
| `go/internal/ruian/testdata/20261031_OB_999991_ADR.csv` | create | fixture: 13 made-up lines in windows-1250 (12 load, 1 has no house number) |
| `go/cmd/ubyhost-web/register_ruian_import.go`, `register_ruian_import_test.go` | create | background task, switches |
| `deploy/lightsail/scripts/backup.sh` | edit (patch) | `--exclude-table-data` |
| `go/internal/schema/testdata/goose_statements_golden.json` | edit (patch) | hashes of 00021 |
| `App/tests/test_db_postgres.py` | edit (patch) | table counts 75 and 5 |
| `docs/ENVIRONMENT.md` | edit (patch) | one row |
| `docs/tasks/1700c-files/**` | keep | sidecars (do not edit) |
| `docs/tasks/1700c-report.md` | create | the report (§9) |

No other file may change.

## 4. Steps

0. Checks (repo root). Anything else than the stated result: STOP (§8).
   - `ls App/migrations_pg | tail -1` prints `00020_guest_contract.sql` (else the number is taken: STOP and report).
   - `grep -cF 'registerBackground("job_purge", jobPurgeTask)' go/cmd/ubyhost-web/register_job_purge.go | tail -1` prints `1`.
   - `grep -cF 'func killSwitch(getenv func(string) string) bool {' go/cmd/ubyhost-web/register_scheduler.go | tail -1` prints `1`.
   - `grep -cF 'golang.org/x/text v0.44.0' go/go.mod | tail -1` prints `1`.
   - `ls go/internal/ruian 2>&1 | tail -1` says "No such file".
   - `find docs/tasks/1700c-files -name '*.txt' | wc -l | tail -1` prints `12`.

1. Copy the sidecars and check them (one call, repo root). Never retype or edit them:

   ```bash
   cd docs/tasks/1700c-files && for f in $(find . -name '*.txt' ! -name 'edits.patch.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "../../../$(dirname "$f")" && cp "$f.txt" "../../../$f"; done; cd ../../.. && sha256sum -c - <<'EOF' 2>&1 | tail -13
   b0fda9adb206ca097ce8fcd0e2d5bd52948d8238019cb74d5824be404ead10c4  App/migrations_pg/00021_ruian_address.sql
   1e570cab4b7fe68fb0c8e2e84d549d1f13c56f1cef2335fc41da67ba509bfaa1  go/internal/ruian/attribution.go
   5ee792b89a15c4a11d36bad84ac63198587a76d498fffea3bc329edc7fef8ae4  go/internal/ruian/fold.go
   88fc5d97bc8bfef8bcda57ae16aa9725db9e281e8e9abc1cdc0cf802601789f3  go/internal/ruian/okres.go
   cede1ab6b379bc65caca48bbca488f79c5a5103139fcc65509984cce335a21be  go/internal/ruian/okres.csv
   37015d6b3dd802540da30453d20e3cbd87a705bd31c31b8c1631b414a94e8f9c  go/internal/ruian/row.go
   40835be6aa75c79fe7d3b6f0b06c155d407a09eee508a7f4c2e86199b7ed921e  go/internal/ruian/import.go
   1075de19f520a132c66fb45cb6d8eef588c1f4f2759494c0f4ca7e0fab319d4e  go/internal/ruian/ruian_test.go
   3fa054d3d933ec645a535f2fd636bb089e08dbd31d142c5ebf6230adab73141e  go/internal/ruian/testdata/20261031_OB_999991_ADR.csv
   14e77b9e4ce3fd1a80f1cbb48a6550d517346e87cfcad208abe9977e8ab2af42  go/cmd/ubyhost-web/register_ruian_import.go
   0d63908f8a613bd7172ad6125ae311418077344254aa07d5508a8253b3dea13b  go/cmd/ubyhost-web/register_ruian_import_test.go
   dd1b22347b8103209e966b4a61f68557483a61c249e41b2caddc288a27f39ab3  docs/tasks/1700c-files/edits.patch.txt
   EOF
   ```

   Every line must end with `: OK` (12 lines). Then commit "1700c step 1" (`git add -A && git commit -m "1700c step 1"`).

2. Apply the patch to the four existing files (one call, repo root):

   ```bash
   git apply --check docs/tasks/1700c-files/edits.patch.txt 2>&1 | tail -5 && git apply docs/tasks/1700c-files/edits.patch.txt 2>&1 | tail -5; git diff --stat | tail -6
   ```

   Expected: no error, then 4 files changed (`App/tests/test_db_postgres.py`, `deploy/lightsail/scripts/backup.sh`, `docs/ENVIRONMENT.md`, `go/internal/schema/testdata/goose_statements_golden.json`; 13 insertions, 3 deletions). `git apply --check` failing means an anchor moved: STOP. Then commit "1700c step 2" (`git add -A && git commit -m "1700c step 2"`).

3. Format, build and vet (one call, from `go/`):

   ```bash
   cd go && gofmt -l internal/ruian cmd internal/schema 2>&1 | tail -5; go build ./... 2>&1 | tail -30; go vet ./internal/ruian/... ./internal/schema/... ./cmd/... 2>&1 | tail -30; git diff --stat HEAD -- go.mod go.sum | tail -3
   ```

   Expected: no output at all. Anything printed: STOP (§8). Nothing changed, so no commit.

4. PostgreSQL. If `UBYHOST_TEST_DATABASE_URL` is already set to a server where you may create databases and the `postgres` role is a superuser (the migration runs `CREATE EXTENSION pg_trgm`, and the contrib package must be installed), use it and skip this step. Else start a throwaway one (as root; `pg_ctl` refuses root, so it runs as `postgres`). Skip the start if `su postgres -c '/usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1700c/data status' | head -1` says `server is running`:

   ```bash
   mkdir -p /var/tmp/pg1700c && chown postgres /var/tmp/pg1700c && su postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/tmp/pg1700c/data -A trust >/dev/null && /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1700c/data -o "-p 55700 -k /var/tmp/pg1700c" -l /var/tmp/pg1700c/log start' 2>&1 | tail -3
   ```

   Expected: a line with `server started`. Use `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55700/postgres` in step 5. No PostgreSQL 16 binaries at that path, or `pg_trgm` missing (`ls /usr/share/postgresql/16/extension/pg_trgm.control`): write "CI only" in the report and STOP before step 5.

5. Run the tests (one call, from `go/`):

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55700/postgres go test ./internal/ruian/... ./internal/schema/... ./internal/scheduler/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
   ```

   Expected: four `ok` lines (`.../internal/ruian`, `.../internal/schema`, `.../internal/scheduler`, `.../cmd/ubyhost-web`). Then the named tests and the skip count:

   ```bash
   cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55700/postgres go test ./internal/ruian/ ./internal/schema/ ./cmd/ubyhost-web/ -count=1 -v -run '^TestFold$|^TestOkres$|^TestCandidates$|^TestParseLineAndStream$|^TestImport$|^TestImportLock$|^TestGooseFilesMatchPython$|^TestRuianImportSwitches$|^TestRuianImportTaskRegisteredOnce$' 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
   ```

   Expected: nine `--- PASS` lines (the nine names above) and three `ok`; no `--- SKIP`, no `--- FAIL`. Whole-run skip count: `cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55700/postgres go test ./internal/ruian/... ./internal/schema/... ./cmd/ubyhost-web/... -count=1 -v 2>&1 | grep -c -- '--- SKIP' | tail -1` prints `3`: the three environment probes `TestJobRunProbe`, `TestRouteProbe`, `TestJobProbe` of `cmd/ubyhost-web` skip on every run (they need `GO_JOBRUN_DB`, `GO_PROBE_IN`, `GO_PROBE_JOBS_OUT`); `internal/ruian` has none. Write that in the report.

6. Python check (repo root). If `App/.venv/bin/python` exists run `cd App && .venv/bin/python -m pytest tests/test_pg_backup_scripts.py tests/test_go_schema_golden.py -q --tb=short 2>&1 | tail -5` (expected: all passed, 0 skipped; `tests/test_db_postgres.py` needs a PostgreSQL target, leave it to CI). Else write "Python checks: CI only (no App/.venv)". Nothing changed, so no commit.

7. Write the report (§9), set `Status: review` in this file and commit "1700c step 7".

## 5. Do not touch

`UBYHOST_GO_PATHS`, `UBYHOST_JOB_QUEUE_KINDS`, `UBYHOST_GO_JOB_KINDS`; `go.mod`, `go.sum`; `go/internal/scheduler/**` (the Python-locked plan); anything under `App/app/` (Python suggest stays); Caddy and compose files; filing code; the sidecars.

## 6. Commands

Exactly the commands of §4 (steps 3, 5, 6). Test-map row: none yet for `go/internal/ruian`; the coordinator adds `go test ./internal/ruian/...` (PostgreSQL) from the report. Never the full suite. Last, from the repo root: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -5` prints `context lint: OK`.

## 7. Acceptance

- [ ] `sha256sum -c` of step 1 printed `: OK` for all 12 lines; `git apply` of step 2 changed exactly the four files.
- [ ] The format, build and vet step printed nothing; `git diff --stat HEAD -- go/go.mod go/go.sum` is empty.
- [ ] Step 5: four `ok` lines, nine `--- PASS`, SKIP count `3` (the probes named in step 5) and none in `internal/ruian`.
- [ ] The tests prove: 12 rows load from 13 lines; a second run with the same month does not download (GET count); a truncated table is reloaded; a 2-row zip with `MinRows` 10 keeps the old rows and leaves no staging table; 404 on both months returns no error and no change; the table is `UNLOGGED` after the swap; a held advisory lock makes `Run` return at once.
- [ ] `git log --oneline --grep='^1700c step' | tail -10` lists the step commits and `git show --stat --format=%s $(git log --format=%h --grep='^1700c step') | tail -40` lists only the paths of §3.
- [ ] The import is dormant: `UBYHOST_RUIAN_IMPORT` unset starts nothing (`TestRuianImportSwitches`).

## 8. Stop and ask

Stop, and write the report, if: an anchor, a hash or a file count of step 0, 1 or 2 is not as stated; `git apply --check` fails; a test fails twice (read the last 30 lines, fix nothing in the sidecar files yourself); `CREATE EXTENSION pg_trgm` fails in the test database (report the error, do not work around it); `go.mod` would change; a file outside §3 would have to change; you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md); you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1700c-report.md` (600 tokens at most) and set this brief's `Status: review`. The report has: 1. files changed (`git show --stat`); 2. each command with the last 5 lines of its output and the SKIP count; 3. §7 ticked; 4. deviations; 5. questions; 6. owner steps left.

## Risk list (for the reviewer)

- `import.go`: the swap (`DROP TABLE ruian_address` takes an exclusive lock for the length of the transaction, a moment; a reader that waits sees the new table), the gate, the advisory lock, redirects only to the same host, the 300 MB cap, staging dropped on every error. The unit tests use a fake server; the real file (63 MB, 6,258 entries, about 3.03 M rows) was parsed here only with Python, not with the Go code, so the first real run is the first full test: watch memory (limit 128 MB, the code streams) and time (index build 3 to 8 minutes).
- Deviation from the scope brief: no `ruian_import` job kind and no scheduler change. The Go scheduler plan is checked against Python's `add_job` list (`go/internal/scheduler/parity_test.go`, `TestPlanMatchesPythonAddJobCalls`), so a Go-only kind would need a Python scheduler edit. A background task with its own 6-hour check does the same work. Consequences: no `job` row, so a failure is a log line (`ruian import failed`), not the `job_failed` alert; the switch is the new variable `UBYHOST_RUIAN_IMPORT`, not the kind lists. The orchestrator records this in decisions when the chain closes.
- The migration needs the owner step below before the merge; a green merge auto-deploys.
- The Python golden `goose_statements_golden.json` was extended by hand with hashes computed by the Go `UpStatements`; `App/tests/test_go_schema_golden.py` (CI) is the check that Python agrees. No `App/.venv` was available to the brief writer.
- Disk: about 1.2 GB steady, 2.5 GB during the swap (plan §5, estimated, not measured).

## Owner steps

1. **Before merging the PR** (the deploy applies migration 00021 and needs the extension; `ubyhost_app` may not create it). On the server:
   1. Open the terminal on the server and run `cd /opt/ubyhost/deploy/lightsail`.
   2. Run `docker compose exec -T postgres psql -U ubyhost -d ubyhost -c 'CREATE EXTENSION IF NOT EXISTS pg_trgm;'`. It must print `CREATE EXTENSION`.
   3. Run `docker compose exec -T postgres psql -U ubyhost -d ubyhost -c '\dx pg_trgm'`. One row with `pg_trgm` must show.
2. Merge with `scripts/merge-pr-on-green.sh`. The deploy applies 00021; nothing else happens (the import is dormant).
3. To switch the import on: open the env file that holds the Go service variables (see docs/ENVIRONMENT.md), add the line `UBYHOST_RUIAN_IMPORT=1`, then restart the Go service (`./scripts/deploy.sh` or the restart you use). About 5 minutes later it starts; the first full load takes 5 to 15 minutes. Watch with `./scripts/logs.sh` for `ruian import done`.
4. Check: `docker compose exec -T postgres psql -U ubyhost -d ubyhost -c 'SELECT data_date, rows FROM ruian_import;'` shows last month's end date and about 3,000,000 rows.
5. Rollback: remove the `UBYHOST_RUIAN_IMPORT` line and restart. The table is harmless and can stay.
6. Once a year (owner task): refresh `go/internal/ruian/okres.csv` as the header of `okres.go` describes.
