# 1473: read-only production schema dump script, and the rollback-window proofs (plan sqlite-retirement S4, S10)

Status: todo
Depends on: none (S4 needs 1472 only to use the file, not to write the script) | Base commit: origin/main once it holds `docs/plans/sqlite-retirement.md` (patch made on 4de1f158c) | Branch: task/1473-pg-schema-dump
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier A (deploy, data loss).

## 1. Objective

Add `deploy/lightsail/scripts/pg-schema-dump.sh`, a read-only script the owner runs on the server to write a schema-only dump of production (for the S3 goose check) and to print row counts (for the restore drill), with a test that fakes `docker`. Add to `docs/OPERATIONS.md` the checklist of the four proofs that must exist before the SQLite rollback path ends, with owner steps and where each is recorded.

## 2. Context

No file under `App/app/` changes (go-first rule does not apply). All changes are in one patch, `docs/tasks/1473-files/schema-dump.patch` (made with `git diff`). Do not open it; step 1 applies it. If `git apply --check` fails, an anchor moved: STOP (§8), never `--reject`, never hand edits.

**House pattern** (`deploy/lightsail/scripts/pg-app-role.sh`, `backup.sh`): run from `deploy/lightsail`, reach the database with `docker compose exec -T postgres psql -U ubyhost -d ubyhost -X -v ON_ERROR_STOP=1` or `docker compose exec -T postgres pg_dump -U ubyhost ...`; the postgres service has `network_mode: none`, so only `exec` reaches it.

**The script** (`pg-schema-dump.sh`, mode 755):
- `./scripts/pg-schema-dump.sh <new file>`: refuses (exit 2, nothing read) if the file or `<file>.partial` exists, if the folder is missing, or if the argument starts with `-`; stops if the postgres container is not running. Then `umask 077`, `set -o noclobber`, and `docker compose exec -T -e PGOPTIONS="-c default_transaction_read_only=on" postgres pg_dump -U ubyhost -d ubyhost --schema-only --no-owner --no-privileges --lock-wait-timeout=10s` into `<file>.partial`. It deletes the file and exits 1 if any line starts `COPY ` or `INSERT INTO ` or contains `pg_catalog.setval(`, or if there is no `CREATE TABLE public.`. Only then `mv -n` to the final name. It prints the table and line count, the sha256 and the number of `COMMENT ON` lines (0 expected).
- `./scripts/pg-schema-dump.sh --counts [ubyhost|ubyhost_restoretest]`: one `psql -c` with a single `SELECT` (exact row count of every public table via `query_to_xml`), in the same read-only session. Any other database name: exit 2, nothing read.
- Read-only twice over: pg_dump reads in a `READ ONLY` snapshot of its own, and every session starts with `default_transaction_read_only=on` (a `CREATE TABLE` in such a session fails: "cannot execute CREATE TABLE in a read-only transaction"). `--lock-wait-timeout` makes it give up after 10 s instead of queueing behind a deploy's schema lock.

**What the dump file holds** (checked against what pg_dump 16.15 really wrote for the goose schema 00001-00016, 71 tables, 4,521 lines): `SET` lines, one random `\restrict` / `\unrestrict` token pair (pg_dump 16.10+ safety token, not a secret, differs per run), the 7 functions (6 invoice guards and `ubyhost_sqlite_date`, code only), tables, columns and types, defaults (short codes such as `'CZK'`, `'pending'`, `'{}'`), CHECK rules (codes and date patterns), indexes (partial-index `WHERE` clauses with codes), constraints and triggers. Not in it: rows (including `schema_migrations` and the 00011 rate rows), sequence values, owners, grants, roles, passwords, the database name. The goose files have no `COMMENT ON`, no view, no policy and no extension. The dump shows the production schema as it is, so a comment, view or function someone added by hand on the server would appear: that is why the script prints the `COMMENT ON` count and the owner steps say to stop if it is not 0.

**The test** (`App/tests/test_pg_schema_dump_script.py`, no Docker, no database): a fake `docker` on PATH logs every call and prints a canned dump. 7 tests: strict, executable and `bash -n`; no writing word (`UPDATE `, `DELETE `, `DROP `, `ALTER `, `TRUNCATE`, `GRANT `, `pg_restore`, `createdb`, `dropdb`, `read_only=off`, `--clean`) outside comments; an existing output is refused with no docker call and left unchanged; no argument and `--schema` are refused; a good run writes mode 600 with the read-only `PGOPTIONS` and the three pg_dump flags; a dump with a `COPY`, `INSERT INTO` or `setval` line leaves no file; `--counts` is read-only and refuses `postgres`.

**OPERATIONS section.** Two new subsections inserted just above `### App database role (K-S11)` (end of `## Backup and restore`): "Proofs before the SQLite rollback path ends (plan S10)" (a table of proofs (a)-(d) from plan section 6 with a `Recorded` column, all `not yet`, and owner steps A decrypt test, B restore drill on staging into the scratch database `ubyhost_restoretest`, C off-site copies) and "Production schema dump (plan S4)". Recording: the owner writes the proof letter, date and last output lines in the orchestrator chat; the orchestrator sets `Done <date>` in the table and adds one `[ops]` line to `docs/context/decisions.md`.

Writer's dry run (worktree on 4de1f158c): new test `7 passed`; with `test_pg_app_role_script.py`, `test_pg_backup_scripts.py`, `test_pg_cutover_script.py`: all passed. ruff `All checks passed!`; `bash -n` ok; shellcheck 0.11.0 (all severities) exit 0. Against a disposable local PostgreSQL 16.15 (goose Up sections 00001-00016, `docker` replaced by a shim that runs the command locally): the dump wrote `71 tables, 4521 lines`, mode 600, `COMMENT ON lines: 0`, 0 `COPY`/`INSERT` lines; a second run on the same path exit 2 with "already exists"; `--counts` printed 71 `table 0` lines; `--counts postgres` exit 2. Two dumps differed only in the `\restrict` lines. The patch also applies to origin/main ed39902f7.

## 3. Files

| Path | Action | What |
|---|---|---|
| `deploy/lightsail/scripts/pg-schema-dump.sh` | new (patch, mode 755) | the read-only script |
| `App/tests/test_pg_schema_dump_script.py` | new (patch) | fake-docker tests |
| `docs/OPERATIONS.md` | edit (patch) | proofs checklist and schema dump steps |
| `docs/tasks/1473-report.md` | new | your report |
| `docs/tasks/1473-pg-schema-dump-and-proofs.md` | exists | Status line only |

No other file may change.

## 4. Steps

**Step 0** (repo root). `git fetch origin main 2>&1 | tail -1; git cat-file -e origin/main:docs/plans/sqlite-retirement.md && echo plan-on-main`. Expected: `plan-on-main`; otherwise STOP. Then `git switch -c task/1473-pg-schema-dump origin/main 2>&1 | tail -2`.

**Step 1. Check anchors, apply** (repo root):

```bash
grep -cxF '### App database role (K-S11)' docs/OPERATIONS.md; test ! -e deploy/lightsail/scripts/pg-schema-dump.sh && test ! -e App/tests/test_pg_schema_dump_script.py && echo absent
git apply --check docs/tasks/1473-files/schema-dump.patch && git apply docs/tasks/1473-files/schema-dump.patch && git status --short 2>&1 | tail -5
```

Expected: `1`, `absent`; then ` M docs/OPERATIONS.md` and `??` for the two new files. Anything else: STOP.

**Step 2. Verify and commit** (repo root):

```bash
sha256sum -c <<'EOF' 2>&1 | tail -3
88fa1fe40b3dc23bf2d670f848684df9b3941be3428ba68e7fda509521df1db2  deploy/lightsail/scripts/pg-schema-dump.sh
5ba2469670851d9adf4894c3e9bc5bff84fdd5072f9d04f357df0d4db52d2967  App/tests/test_pg_schema_dump_script.py
5320a11451f791786e5d4b9ca03fe61963418ecde205f93a9d3507d72064efe2  docs/OPERATIONS.md
EOF
stat -c %a deploy/lightsail/scripts/pg-schema-dump.sh
git add deploy/lightsail/scripts/pg-schema-dump.sh App/tests/test_pg_schema_dump_script.py docs/OPERATIONS.md && git commit -m "1473 step 1-2" 2>&1 | tail -2
```

Expected: 3 x `OK`, `755`, the commit line. If only `docs/OPERATIONS.md` is `FAILED`, main changed it after 4de1f158c but the patch applied: write `git log --oneline -3 -- docs/OPERATIONS.md` under Deviations and go on. Any other `FAILED`, or not `755` (run `chmod 755` on the script once, then recheck): STOP.

**Step 3.** Run §6. **Step 4.** Write the report (§9), commit it as `1473 step 4: report`, open one draft PR.

## 5. Do not touch

Every other file in `deploy/lightsail/` (including `pg-restore.sh`, `backup.sh`, `pg-cutover.sh`), `App/app/**`, `App/migrations_pg/**`, `.github/workflows/*`, `docs/LIGHTSAIL.md` (brief 1470), `docs/context/*`. Never run the script against any database: you have no server. Hard rules 3, 4 and 8: no secrets, no new dependency, never push to main.

## 6. Commands

From `App/` (create `.venv` only if missing: `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -3`):

```bash
.venv/bin/python -m pytest tests/test_pg_schema_dump_script.py tests/test_pg_app_role_script.py tests/test_pg_backup_scripts.py tests/test_pg_cutover_script.py -q --tb=short 2>&1 | tail -3
.venv/bin/ruff check tests/test_pg_schema_dump_script.py 2>&1 | tail -2
bash -n ../deploy/lightsail/scripts/pg-schema-dump.sh && echo syntax ok
```

Expected: `passed`, no `failed` (the new file gives 7); `All checks passed!`; `syntax ok`. If `shellcheck` is on PATH: `shellcheck -S error ../deploy/lightsail/scripts/pg-schema-dump.sh; echo "sc exit $?"` gives `sc exit 0` (if not installed, write "shellcheck: CI only").

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -1` shows `context lint: OK`.

## 7. Acceptance

- [ ] Step 0 `plan-on-main`; step 1 as expected; step 2 3 x `OK` (or the documented OPERATIONS deviation) and `755`.
- [ ] §6 as expected.
- [ ] `git diff --stat origin/main..HEAD` lists only §3 files.
- [ ] After push, CI `shellcheck` and `test` green.

## 8. Stop and ask

Stop, and write the report, if: the plan is not on main; an anchor count is wrong or the patch does not apply; a hash other than OPERATIONS is `FAILED`; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push to main, merge, secrets, SSH, a server or deploy.

## 9. Report

Write `docs/tasks/1473-report.md` (600 tokens at most) and set `Status: review`. It has: the files changed (`git diff --stat origin/main..HEAD`), each command with its last 5 lines, §7 ticked, Deviations, Questions, Owner steps left.

## Risk list (for the reviewer)

Full diff of `deploy/lightsail/scripts/pg-schema-dump.sh` (every `docker compose exec` carries `PGOPTIONS=-c default_transaction_read_only=on`; the only SQL is one `SELECT`; the output is refused if it exists, written `.partial` then `mv -n`; a data line deletes it) and `docs/OPERATIONS.md` (the owner commands: `createdb`/`pg_restore`/`dropdb` only ever name `ubyhost_restoretest` and run on staging; the key file is deleted in B11 and A7).

## Owner steps

After the PR merges and production and staging are deployed:
1. The schema dump: follow `docs/OPERATIONS.md`, "Production schema dump (plan S4)", steps 1-3. Give the file to the orchestrator for brief 1472's check.
2. The proofs: follow `docs/OPERATIONS.md`, "Proofs before the SQLite rollback path ends", parts A, B and C. After each part, write in the orchestrator chat the proof letter, the date and the last lines printed.

## Notes for the coordinator

- Proof (b) copies real guest data (encrypted, then into a scratch database) to staging for a few minutes, as plan section 6 asks. A scratch database on production would keep the data on one box; say so to the owner if staging's protection is weaker.
- 1472's normaliser must drop the `\restrict`/`\unrestrict` lines before diffing.
- `pg-restore.sh` `die()` prints its exit code inside the message (`echo "ERROR: $*"` with a second argument); the new script uses `$1`. Not fixed here.
