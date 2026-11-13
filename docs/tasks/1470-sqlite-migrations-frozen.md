# 1470: freeze App/app/migrations/ at 0045 (plan sqlite-retirement S1)

Status: review (work complete; the lint failure the executor reported came from an unrelated unfinished brief, 1447)
Depends on: none (plan approved, decisions line 2026-11-13 "SQLite plan 1-6 approved") | Base commit: origin/main once it holds `docs/plans/sqlite-retirement.md` (patch made on 4de1f158c) | Branch: task/1470-sqlite-migrations-frozen
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier A (migrations).

## 1. Objective

Add a test that fails any PR adding, editing, renaming or deleting a file in `App/app/migrations/`, so goose files in `App/migrations_pg/` become the only place for a new schema change. Point the context lint and `docs/LIGHTSAIL.md` at goose numbers instead of SQLite numbers.

## 2. Context

Go-first rule ([go-first](../context/go-first.md)): this brief names a file under `App/` but not under `App/app/`; it is a test plus port plumbing (rule 1, "parity tests, removal PRs").

All changes are in one patch, `docs/tasks/1470-files/freeze.patch` (made with `git diff`). Do not open it; step 1 applies it. If `git apply --check` fails, an anchor moved: STOP (§8), never `--reject`, never hand edits.

**Why.** Python's PostgreSQL apply (`App/app/db.py`, `apply_postgresql_schema`) still translates and runs the 44 SQLite files 0002-0045 before the goose files, so a new or edited SQLite file would change production outside goose. Plan step S1, owner decision 1.

**Design of the new test, `App/tests/test_sqlite_migrations_frozen.py`.** A checked-in dict `FROZEN` holds the name and sha256 of every entry in `App/app/migrations/` (45: `.gitkeep` plus 0002-0045). CRLF is read as LF before hashing, so a Windows checkout does not fail. No git history is needed. Four tests:
- `test_no_file_added_or_removed`: names on disk equal `FROZEN` (a rename fails here).
- `test_no_file_edited`: every hash matches; a subdirectory fails too.
- `test_the_runner_reads_exactly_the_frozen_files`: `db.MIGRATIONS_DIR` is that folder and `db.migration_files()` returns versions 2..45, so moving the runner to another folder also fails.
- `test_the_manifest_stops_at_0045`: `FROZEN` has 45 entries numbered up to 0045 and `LAST_FROZEN == 45`, so "fixing" the test needs several deliberate edits, which the reviewer sees in the diff.
Every failure prints: frozen at 0045, see `docs/plans/sqlite-retirement.md` step S1, do not edit `FROZEN`, undo the change, write a new goose file in `App/migrations_pg/` (number = highest there + 1).

**Existing checks stay consistent.** `App/tests/test_migrations.py` builds `SHIPPED` from `db.migration_files()` and writes its demo file `NEXT` (0046) into a `tmp_path` copy, never into the real folder: unchanged, still passes. `scripts/context_lint.py` `next_numbers()` printed `migration 0046`, which would now send writers to a frozen folder. The patch changes it to print the next goose number:

```diff
-    migs = [int(p.name[:4]) for p in (ROOT / "App/app/migrations").glob("[0-9][0-9][0-9][0-9]_*.sql")]
+    goose = [int(p.name[:5]) for p in (ROOT / "App/migrations_pg").glob("[0-9][0-9][0-9][0-9][0-9]_*.sql")]
     return (f"next free: task {max(tasks, default=0) + 1:04d} | "
-            f"migration {max(migs, default=1) + 1:04d}")
+            f"goose migration {max(goose, default=0) + 1:05d} (App/app/migrations/ is frozen)")
```

**LIGHTSAIL paragraph.** Inserted after the line ending ``Confirm `ubyport_env` with `./scripts/status.sh` or Settings.`` (section "Day-to-day commands", just above `### Automatic backups`). That spot does not touch the lines brief 1263's patch uses as context ("Schema apply" section, `## Day-to-day commands` heading), so both patches apply in either order. Text added:

> **Schema changes are goose files only (brief 1470).** `App/app/migrations/` (SQLite 0002-0045) is frozen: `App/tests/test_sqlite_migrations_frozen.py` fails any PR that adds, edits, renames or deletes a file there. A new schema change is one goose file in `App/migrations_pg/` (number = highest + 1), applied with the `pg_schema.py apply` row above. It has no SQLite twin, so the Python tests that run on SQLite do not see it; the existing twins stay as they are. Why, and the steps that follow: [plan](plans/sqlite-retirement.md).

Writer's dry run (worktree on 4de1f158c, venv from `requirements*.txt`): the new file `4 passed`; ruff `All checks passed!`. Appending a line to `0045_guest_details_mail.sql` failed `test_no_file_edited`; adding `0046_demo.sql` failed `test_no_file_added_or_removed` and `test_the_runner_reads_exactly_the_frozen_files`; a rename failed `test_no_file_added_or_removed`; after undoing, 4 passed. `test_migrations.py` and the `test_pg_*script*.py` files: all passed with the new file present. Context lint: `next free: task ... | goose migration 00017 (App/app/migrations/ is frozen)`, `context lint: OK`. The patch also applies to origin/main ed39902f7.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/test_sqlite_migrations_frozen.py` | new (patch) | the freeze test with `FROZEN` |
| `scripts/context_lint.py` | edit (patch) | next free goose number instead of SQLite |
| `docs/LIGHTSAIL.md` | edit (patch) | one paragraph |
| `docs/tasks/1470-report.md` | new | your report |
| `docs/tasks/1470-sqlite-migrations-frozen.md` | exists | Status line only |

No other file may change. The orchestrator, not you, edits `AGENTS.md` hard rule 5 and `docs/context/rules.md` "Database" in the same PR.

## 4. Steps

**Step 0** (repo root). `git fetch origin main 2>&1 | tail -1; git cat-file -e origin/main:docs/plans/sqlite-retirement.md && echo plan-on-main`. Expected: `plan-on-main`; otherwise STOP. Then `git switch -c task/1470-sqlite-migrations-frozen origin/main 2>&1 | tail -2`.

**Step 1. Check anchors, apply** (repo root):

```bash
grep -cF 'Confirm `ubyport_env` with `./scripts/status.sh` or Settings.' docs/LIGHTSAIL.md; grep -cF 'migs = [int(p.name[:4])' scripts/context_lint.py; ls -A App/app/migrations | wc -l; test ! -e App/tests/test_sqlite_migrations_frozen.py && echo absent
git apply --check docs/tasks/1470-files/freeze.patch && git apply docs/tasks/1470-files/freeze.patch && git status --short 2>&1 | tail -5
```

Expected: `1`, `1`, `45`, `absent`; then ` M docs/LIGHTSAIL.md`, ` M scripts/context_lint.py`, `?? App/tests/test_sqlite_migrations_frozen.py`. Anything else: STOP.

**Step 2. Verify and commit** (repo root):

```bash
sha256sum -c <<'EOF' 2>&1 | tail -3
9d55a4cd2c2772701704e9da7bdebc5b35209aae18034e4d15c6ac1c43a35f10  App/tests/test_sqlite_migrations_frozen.py
93ef36a94b3c5850f101408b1d6af5157d6250f41a4eeafc6e036a7c0d600850  scripts/context_lint.py
EOF
grep -cF '**Schema changes are goose files only (brief 1470).**' docs/LIGHTSAIL.md
git add App/tests/test_sqlite_migrations_frozen.py scripts/context_lint.py docs/LIGHTSAIL.md && git commit -m "1470 step 1-2" 2>&1 | tail -2
```

Expected: 2 x `OK`, then `1`, then the commit line. A `FAILED`: STOP.

**Step 3.** Run §6. **Step 4.** Write the report (§9), commit it as `1470 step 4: report`, open one draft PR.

## 5. Do not touch

`App/app/migrations/**` (never, not even to test the freeze), `App/app/**`, `App/migrations_pg/**` (briefs 1471, 1472 own it), `App/tests/test_migrations.py`, `AGENTS.md`, `docs/context/*`, `.github/workflows/*`. Hard rules 3, 4, 5 and 8: no secrets, no new dependency, never push to main.

## 6. Commands

From `App/` (create `.venv` only if missing: `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -3`):

```bash
.venv/bin/python -m pytest tests/test_sqlite_migrations_frozen.py tests/test_migrations.py -q --tb=short 2>&1 | tail -3
.venv/bin/ruff check tests/test_sqlite_migrations_frozen.py 2>&1 | tail -2
```

Expected: `passed`, no `failed` (the new file gives 4); `All checks passed!`.

From the repo root: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -2`. Expected: `next free: task NNNN | goose migration 000NN (App/app/migrations/ is frozen)` and `context lint: OK`.

## 7. Acceptance

- [ ] Step 0 `plan-on-main`; step 1 anchors and patch as expected; step 2 2 x `OK` and `1`.
- [ ] §6 as expected.
- [ ] `git diff --stat origin/main..HEAD` lists only §3 files; `git diff origin/main..HEAD -- App/app/migrations | wc -l` prints `0`.

## 8. Stop and ask

Stop, and write the report, if: the plan is not on main; an anchor count is wrong or the patch does not apply; a hash is `FAILED`; a test fails twice (the new test failing on main means a file in `App/app/migrations/` changed after 4de1f158c: write `git log --oneline -3 -- App/app/migrations` in the report, never edit `FROZEN`); you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push to main, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1470-report.md` (600 tokens at most) and set `Status: review`. It has: the files changed (`git diff --stat origin/main..HEAD`), each command with its last 5 lines, §7 ticked, Deviations, Questions, Owner steps left.

## Risk list (for the reviewer)

Full diff of `App/tests/test_sqlite_migrations_frozen.py` (`FROZEN` has 45 entries; no `skip`, no `sqlite_only` or other mark, so it runs in every job; the path is built from the test file, not from a variable another test patches) and `scripts/context_lint.py` (only `next_numbers()` changes).

## Owner steps

None. Merge with `scripts/merge-pr-on-green.sh` once CI is green.

## Notes for the coordinator

- The freeze cannot catch: a PR that edits a migration and `FROZEN` together (the reviewer must reject any diff to `FROZEN`), deleting the test file, or a schema change made in `db.SCHEMA`/`ADDED_COLUMNS` (`db.py`; rules.md already forbids it).
- Brief 1263's LIGHTSAIL paragraph "Writing a goose twin" says to copy SQLite data lines into the twin; once 1470 lands there are no new twins. Shorten it when 1263 runs, or in a later doc brief (S13).
- Lint overlap: open brief 1210 also edits `docs/LIGHTSAIL.md`, but other sections ("Deploy from GitHub Actions", rollback by SHA); either may go first, the 1470 patch context does not touch them.
