# 2043: Rollback schema prep also removes goose's version-24 row (blocker)

Status: todo
Base commit: current tip of the working branch | Branch: task/2043-rollback-goose-row
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: A (deploy script; exact diffs only; fresh review of the full diff)

> **One PR mode.** Commit each step as `2043 step k`. Never push to `main`, never merge (the owner merges with `scripts/merge-pr-on-green.sh`), never deploy.

## 1. Objective

After a rollback, the next deploy must re-apply migration 00024. Today the rollback drops the column `guide_import.codes_left_out` but leaves goose's row for version 24, so the next deploy skips 24 and the new Go release runs without the column. A failed schema prep must also be loud.

## 2. Context

Hard rules: 4 no new dependency; 5 SQL stays Postgres-portable; 3 no secrets.

How goose decides "applied" (`go/internal/schema/goose.go`, `appliedVersions`, line 82): `SELECT DISTINCT ON (version_id) version_id, is_applied FROM goose_db_version ORDER BY version_id, id DESC`. A version counts as applied only when its newest row (highest `id`) has `is_applied = true`. `Pending` (line 54) treats every file version not in that map as pending. Deleting ALL rows with `version_id = 24` therefore makes 24 pending again. Table: `goose_db_version(id, version_id, is_applied, tstamp)`.

Current function in `deploy/lightsail/scripts/rollback-schema-prep.sh` (verify with `grep -nF`):
```
  if [ -z "${UBYHOST_DATABASE_URL:-}" ]; then
    return 0
  fi
...
    echo "Would run: ALTER TABLE guide_import DROP COLUMN IF EXISTS codes_left_out;"
...
  docker compose exec -T postgres psql -U ubyhost -d ubyhost -v ON_ERROR_STOP=1 \
    -c "ALTER TABLE guide_import DROP COLUMN IF EXISTS codes_left_out;"
```
`deploy/lightsail/scripts/deploy.sh` line 123 (inside `rollback()`): `  rollback_drop_guide_import_00024 || true`.

The script `scripts/rollback-prod.sh` (repo root) also sources this file; it needs no edit.

## 3. Files

| Path | Action | What |
|---|---|---|
| `deploy/lightsail/scripts/rollback-schema-prep.sh` | edit | one transaction, unset-URL warning, dry-run text |
| `deploy/lightsail/scripts/deploy.sh` | edit | loud error when the prep fails |
| `App/tests/test_pg_backup_scripts.py` | edit | extend the dry-run test, add an unset-URL test |
| `App/tests/test_pg_go_slot_script.py` | edit | static test for the SQL and the error text |
| `docs/tasks/2043-report.md` | create | the report |

No other file may change.

## 4. Steps

1. **Unset URL warns.** In `rollback-schema-prep.sh` replace
```
  if [ -z "${UBYHOST_DATABASE_URL:-}" ]; then
    return 0
  fi
```
with
```
  if [ -z "${UBYHOST_DATABASE_URL:-}" ]; then
    echo "WARNING: UBYHOST_DATABASE_URL is unset; skipping the schema rollback (guide_import.codes_left_out and goose version 24 stay). The old release may not start." >&2
    return 0
  fi
```
   Check: `bash -n deploy/lightsail/scripts/rollback-schema-prep.sh 2>&1 | tail -30` prints nothing.

2. **Dry-run text.** Replace the line `    echo "Would run: ALTER TABLE guide_import DROP COLUMN IF EXISTS codes_left_out;"` with
```
    echo "Would run: BEGIN; ALTER TABLE guide_import DROP COLUMN IF EXISTS codes_left_out; DELETE FROM goose_db_version WHERE version_id = 24; COMMIT;"
```

3. **One transaction.** Replace the final two lines of the function (`docker compose exec -T postgres psql ... -c "ALTER TABLE ...;"`) with
```
  docker compose exec -T postgres psql -U ubyhost -d ubyhost -v ON_ERROR_STOP=1 \
    -c "BEGIN; ALTER TABLE guide_import DROP COLUMN IF EXISTS codes_left_out; DELETE FROM goose_db_version WHERE version_id = 24; COMMIT;"
```
   Also change the echo above it to `echo "==> Dropping guide_import.codes_left_out and goose version 24 (migration 00024) so the previous release can start and the next deploy re-applies it"`. Leave the closing `}` as is.

4. **Loud failure in deploy.sh.** In `deploy.sh` replace the single line `  rollback_drop_guide_import_00024 || true` with
```
  if ! rollback_drop_guide_import_00024; then
    echo "ERROR: schema rollback prep failed; old release may not start" >&2
  fi
```
   The rollback continues (no `exit`). Check: `grep -nF 'schema rollback prep failed' deploy/lightsail/scripts/deploy.sh | tail -30` shows one line. `set -e` is safe: the call sits in an `if`.

5. **Extend the dry-run test.** In `App/tests/test_pg_backup_scripts.py`, in `test_rollback_schema_prep_dry_run_reports_drop`, after the line `    assert "DROP COLUMN" in result.stdout` add
```
    assert "DELETE FROM goose_db_version WHERE version_id = 24" in result.stdout
```
   Then, directly after that test function (before `def test_deploy_defers_remove_orphans_until_go_slot_is_healthy`), add:
```python
def test_rollback_schema_prep_warns_when_database_url_unset(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy(SCRIPTS / "rollback-schema-prep.sh", scripts / "rollback-schema-prep.sh")
    env = {"PATH": os.environ["PATH"]}
    result = subprocess.run(
        ["bash", "-c", "source scripts/rollback-schema-prep.sh; rollback_drop_guide_import_00024"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "UBYHOST_DATABASE_URL is unset" in result.stderr
```

6. **Static test.** Append to `App/tests/test_pg_go_slot_script.py`:
```python
def test_rollback_prep_deletes_goose_row_in_one_transaction():
    prep = (SCRIPTS / "rollback-schema-prep.sh").read_text(encoding="utf-8")
    assert "BEGIN; ALTER TABLE guide_import DROP COLUMN IF EXISTS codes_left_out; DELETE FROM goose_db_version WHERE version_id = 24; COMMIT;" in prep
    assert "ON_ERROR_STOP=1" in prep
    deploy = DEPLOY.read_text(encoding="utf-8")
    rollback = deploy.split("rollback() {", 1)[1].split("\n}\n", 1)[0]
    assert "ERROR: schema rollback prep failed; old release may not start" in rollback
    assert "rollback_drop_guide_import_00024 || true" not in rollback
```

## 5. Do not touch

`go/` (including `goose.go`), any migration file, `scripts/rollback-prod.sh`, the rest of `rollback()`, `docs/`, other tests.

## 6. Commands

- `shellcheck -S error deploy/lightsail/scripts/*.sh 2>&1 | tail -30` (no output = pass; if shellcheck is missing, say so in the report)
- `bash -n deploy/lightsail/scripts/deploy.sh 2>&1 | tail -30`
- `cd App && .venv/bin/python -m pytest tests/test_pg_backup_scripts.py tests/test_pg_go_slot_script.py -q --tb=short -x 2>&1 | tail -30` (expect all passed, 0 failed)
- `python3 scripts/context_lint.py 2>&1 | tail -30` (from repo root; expect no errors)

## 7. Acceptance

- [ ] `grep -nF 'DELETE FROM goose_db_version WHERE version_id = 24' deploy/lightsail/scripts/rollback-schema-prep.sh` shows 2 lines (dry-run text and real SQL).
- [ ] The real SQL is one `-c "BEGIN; ...; COMMIT;"` with `-v ON_ERROR_STOP=1`.
- [ ] Unset URL prints a WARNING to stderr.
- [ ] deploy.sh prints the exact ERROR line on a failed prep and does not exit.
- [ ] The §6 commands pass; context lint passes.

## 8. Stop and ask

Any anchor not found verbatim; a test fails twice; the function body differs from the quote in §2. Do not guess.

## 9. Report

Write `docs/tasks/2043-report.md` (600 tokens at most): files changed, each §6 command with its last 5 lines, §7 ticked, Deviations, Questions. Set `Status: review`, open one PR (draft), do not merge. Owner steps: merge with `scripts/merge-pr-on-green.sh` when ready; no secrets or servers involved.
