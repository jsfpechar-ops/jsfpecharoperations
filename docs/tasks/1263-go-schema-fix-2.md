# 1263: Go schema fix 2 (goose twin parity test, no rebuild of a pulled Go image)

Status: review
Depends on: PR #982 merged to main | Base commit: main after the PR #982 merge (patch made on 1fd70c01, the PR head) | Branch: task/1263-go-schema-fix-2
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier A (migrations, deploy).

## 1. Objective

Add a PostgreSQL test proving that every goose twin, applied by Go alone, gives the same defaults, constraints and index definitions as Python's apply (which runs the SQLite migration first), and stop `deploy.sh` from rebuilding a Go image it has just pulled from CI when `UBYHOST_SCHEMA_APPLY=go`. Both must land before anyone sets the switch to `go`.

## 2. Context

All changes are in one patch, `docs/tasks/1263-files/fix.patch`, made with `git diff` on 1fd70c01 (head of PR #982). After that PR merges, main holds the same text, so the patch applies to main. Do not open the patch; step 1 applies it. If `git apply --check` fails, an anchor has moved: STOP (§8), never `--reject`, never hand edits.

**Finding 1 (confirmed).** Python `apply_postgresql_schema` (`App/app/db.py`) calls `_postgres_schema_ddl`, which runs every translated `App/app/migrations/*.sql` file first. Only after that does it run the goose files, so on production every twin in `App/migrations_pg/` has been a no-op (`IF NOT EXISTS`, `ON CONFLICT DO NOTHING`). Go apply (`go/internal/schema/migrate.go`) runs the goose files alone. Both checks (`expected.go` `Compare`, Python `postgres_schema_status`) compare column name, type, NOT NULL, index names, triggers, functions and version. They do not compare DEFAULT, CHECK/FK/UNIQUE or index definitions.

**Design (test only, no behaviour change).** A new test, `test_go_applied_goose_twins_match_python_defaults_and_constraints`, goes in `App/tests/test_go_schema_migrate.py`. It builds database A with Python. It builds database B with Python too, then runs the Down sections of all goose files after the baseline (newest first), deletes their `goose_db_version` rows and runs Go apply. It then compares A and B on `information_schema.columns` (default, identity), `pg_constraint` (name, type, `pg_get_constraintdef`) and `pg_indexes.indexdef`. Option (b), a wider `Compare`, would change `check` on both sides and need new goldens; (a) catches the same drift at no runtime risk. The test also changes a default and drops a CHECK to show that both `check` commands still say OK while the comparison fails.

**Known drift found by the writer's run (frozen allowlist in the test).** Goose 00004, 00011 and 00013 write `REFERENCES ...` without `DEFERRABLE INITIALLY IMMEDIATE`, but Python's translation (`App/app/db_postgres.py` near line 340) adds it to every FK. That affects 6 FKs, on `site_booking`, `stay_fee_rate` and `guest_form_draft`. Production ran the SQLite files, so it has DEFERRABLE. The test lists these 6 in `KNOWN_NOT_DEFERRABLE` and must not grow; new twins write DEFERRABLE. The existing goose files are not changed.

**What it cannot catch:** data backfills (the test databases are empty), and a twin whose Down does not fully undo it (the Up then no-ops). The patch adds a "Writing a goose twin" paragraph that says so in `docs/LIGHTSAIL.md`, section "Schema apply: Python or Go".

**Finding 2 (confirmed).** In `deploy/lightsail/scripts/deploy.sh`, go mode runs `docker compose --profile go build ubyhost-go` without a condition. After a GitHub deploy pulled `UBYHOST_GO_IMAGE` and tagged it `ubyhost-go:local` (`GO_IMAGE_PULLED=1`), that build overwrites the CI image (compose `image: ubyhost-go:local`). The patch wraps the build in `if [ "${GO_IMAGE_PULLED}" = "1" ]`, which prints `==> Using the pulled Go image for the schema apply` and otherwise builds as before. It also fixes the comment near the later build and adds the pulled case to the `go` row in LIGHTSAIL.md. **Tests:** no test runs `deploy.sh` (only `test_pg_*script*.py` cover other scripts, and there is no fake-docker harness for deploy.sh), so this branch is covered only by `bash -n` and CI `shellcheck -S error`. Building a harness is out of scope.

Writer's dry run, in a worktree on 1fd70c01 with PostgreSQL 16 and Go toolchain 1.25.14: `test_go_schema_migrate.py` 5 passed (8.9 s). Without a URL it gave 5 skipped. A mutation run (twin 00016 `DEFAULT 0`, CHECK removed from 00011, then both reverted) failed the new test, naming both rows. ruff `All checks passed!`, `bash -n` ok, shellcheck 0.11.0 `-S error` exit 0.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/tests/test_go_schema_migrate.py | edit (patch) | new fingerprint test + `KNOWN_NOT_DEFERRABLE` |
| deploy/lightsail/scripts/deploy.sh | edit (patch) | skip the go-mode build when the Go image was pulled |
| docs/LIGHTSAIL.md | edit (patch) | `go` row; "Writing a goose twin" paragraph |
| docs/tasks/1263-report.md | new | your report |
| docs/tasks/1263-go-schema-fix-2.md, docs/tasks/1263-files/fix.patch | exist | this brief (Status line only) and the patch |

No other file may change.

## 4. Steps

**Step 0.** Check that PR #982 is merged: `git fetch origin main && git merge-base --is-ancestor 1fd70c01 origin/main && echo merged`. Expected: `merged`. Otherwise STOP. Then branch from main: `git switch -c task/1263-go-schema-fix-2 origin/main 2>&1 | tail -2`.

**Step 1. Check the anchors and apply the patch** (repo root):

```bash
grep -cF 'echo "==> Building the Go image for the schema apply"' deploy/lightsail/scripts/deploy.sh; grep -cF 'def test_go_apply_rolls_back_a_failing_goose_file' App/tests/test_go_schema_migrate.py; grep -cF '### Schema apply: Python or Go' docs/LIGHTSAIL.md
git apply --check docs/tasks/1263-files/fix.patch && git apply docs/tasks/1263-files/fix.patch && git status --short 2>&1 | tail -10
```

Expected: `1` three times, then 3 files ` M` (the three in §3). Any `0`, or `git apply --check` fails: STOP.

**Step 2. Verify and commit** (repo root):

```bash
sha256sum -c <<'EOF' 2>&1 | tail -5
d56092d0072257c9343580318b0b4b952f9564b286202e787a2cb40af8ffb64f  App/tests/test_go_schema_migrate.py
ef4f1f47963497cc4b1742043e2cda5e7c07795811bf261eec439c98f1bb1187  deploy/lightsail/scripts/deploy.sh
532542f06b24184ac5b8b2d0522da3ba7a844f987cd879eb81db0a8fbb579217  docs/LIGHTSAIL.md
EOF
```

Expected: 3 x `OK`. A `FAILED` means main changed that file after 1fd70c01 (the patch still applied). Write the file and `git log --oneline 1fd70c01..origin/main -- <file>` in Deviations and go on. Then commit:

```bash
git add App/tests/test_go_schema_migrate.py deploy/lightsail/scripts/deploy.sh docs/LIGHTSAIL.md && git commit -m "1263 step 1-2" 2>&1 | tail -3
```

**Step 3.** Run §6. **Step 4.** Write the report (§9), commit it as `1263 step 4: report`, open one draft PR.

## 5. Do not touch

`App/migrations_pg/**` (the 6 known FKs stay as they are), `App/app/**`, `go/**`, `App/scripts/pg_schema_golden.py`, `go/internal/schema/expected_schema.json`, `.github/workflows/*`, `docs/context/*`, `docs/ENVIRONMENT.md`. Rules 3, 4 and 8: no secrets, no new dependency, never push to main.

## 6. Commands

From `App/` (create `.venv` only if missing: `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -3`):

```bash
env -u UBYHOST_DATABASE_URL -u UBYHOST_TEST_DATABASE_URL .venv/bin/python -m pytest tests/test_go_schema_migrate.py -q -rs --tb=short 2>&1 | tail -3
.venv/bin/ruff check tests/test_go_schema_migrate.py --select E9,F63,F7,F82,F401,F841 2>&1 | tail -2
bash -n ../deploy/lightsail/scripts/deploy.sh && echo syntax ok
```

Expected: `5 skipped`; `All checks passed!`; `syntax ok`. If `shellcheck` is on PATH: `shellcheck -S error ../deploy/lightsail/scripts/deploy.sh; echo "sc exit $?"` gives `sc exit 0` (if not installed, write "shellcheck: CI only" in the report).

**Optional, needs a disposable PostgreSQL** (the server CI job `test-postgres-full` provides). The 1262 report ran it locally with PostgreSQL 16 started as the `postgres` user under `/var/tmp` (e.g. `initdb -D /var/tmp/pg1263/data -A trust`, `pg_ctl -o '-p 5434 -k /var/tmp/pg1263' start`). Then, from `App/`:

```bash
UBYHOST_TEST_DATABASE_URL="postgresql://postgres@/postgres?host=/var/tmp/pg1263&port=5434" env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_go_schema_migrate.py -q -rs --tb=short 2>&1 | tail -6
```

Expected: `5 passed` (needs `go` on PATH; the test builds the binary with `GOTOOLCHAIN=auto`). Stop the server afterwards. Never point this at a production database. If you cannot start PostgreSQL, write "PostgreSQL run: CI only" in the report.

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -1` shows `context lint: OK`.

## 7. Acceptance

- [ ] Step 0 `merged`; step 1 three `1`s and the patch applied; step 2 3 x OK (or the documented deviation).
- [ ] §6 as expected.
- [ ] `git diff --stat origin/main..HEAD` lists only §3 files.
- [ ] After push, CI `test-postgres-full`: 5 `test_go_schema_migrate.py` tests PASS (not skip); `shellcheck` and `test` green.

## 8. Stop and ask

Stop, and write the report, if: PR #982 is not on main; an anchor count is not `1` or the patch does not apply; a test fails twice (the new test failing on main means a twin merged after 1fd70c01 differs from its SQLite file: report the diff lines, do not edit the allowlist); you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push to main, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1263-report.md` (600 tokens at most) and set `Status: review`. It has: the files changed (`git diff --stat origin/main..HEAD`), each command with its last 5 lines, §7 ticked, Deviations, Questions, Owner steps left.

## Risk list (for the reviewer)

Full diff of `deploy/lightsail/scripts/deploy.sh` (the go branch must still build when `GO_IMAGE_PULLED` is not `1`, and still exit 1 on a failed build) and `App/tests/test_go_schema_migrate.py` (the allowlist holds exactly the 6 FKs and only strips ` DEFERRABLE` from them; the new test uses throwaway databases only).

## Owner steps

None. Merge with `scripts/merge-pr-on-green.sh` once CI is green.

## Notes for the coordinator

- known-issues line: `[schema] Goose twins 00004, 00011, 00013 declare FKs without DEFERRABLE INITIALLY IMMEDIATE (Python's translation adds it); production is unaffected (SQLite files ran first); a Go-only build of those tables would have immediate FKs. Frozen in KNOWN_NOT_DEFERRABLE, test_go_schema_migrate.py. Brief 1263.`
- No test sees goose twin data backfills; review them by reading (LIGHTSAIL "Writing a goose twin").
