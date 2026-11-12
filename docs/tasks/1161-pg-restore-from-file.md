# 1161: pg-restore.sh restores from a local .age file

Status: todo
Depends on: none | Base commit: 2cd674d | Branch: claude/dr-restore-from-file
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

`deploy/lightsail/scripts/pg-restore.sh` also accepts `--file /path/to/ubyhost-pg.dump.age`: a local age file on the host (for example downloaded from Google Drive), with no volume stamp and no AWS. This is step 3 of [portable-disaster-recovery](../plans/portable-disaster-recovery.md) (gap 2): without it a restore from Drive needs a manual copy into the app volume.

## 2. Context

Rules that apply: AGENTS.md rule 3 (public repo, no secrets: use placeholders only); the restore is destructive, so every existing guard must keep applying in both forms. Rule 2 and rule 4: no new outbound request, no new dependency.

Design (decided, do not change):

- Two forms, exactly one allowed: `pg-restore.sh <stamp>` (unchanged behaviour) and `pg-restore.sh --file <path>`. Anything else prints usage and exits 1.
- File form checks: the name ends in `.age`, the file exists, is readable, is not empty. A relative path is resolved against the folder the user ran the script from (the script does `cd` into its own folder, so the start folder is saved first).
- File form never runs `docker cp` and writes no plaintext file: `age -d` reads the host file and pipes into the same `pg_restore` line.
- Kept in both forms: `.env` present, SQLite refusal (exit 2), `UBYHOST_DATABASE_URL` required (exit 2), `AGE_IDENTITY_FILE` set and existing, `age` present, `RESTORE_CONFIRM` prompt (names the file instead of the snapshot), ubyhost container found, stop worker and ubyhost, restart trap, health wait.
- The volume check (`docker compose run ... test -f /data/backups/<stamp>/...`) runs in the stamp form only.
- Left out on purpose: a "postgres is running" check before stopping the app. The existing stamp tests do not stub a running postgres, so adding it would break them. `pg_restore` failing in the single transaction already restarts the app through the trap.

Excerpt that must exist verbatim in `deploy/lightsail/scripts/pg-restore.sh` (line 23 to 26):

```
STAMP="${1:-}"
IDENTITY="${AGE_IDENTITY_FILE:-}"
[ -n "${STAMP}" ] || die "usage: $0 <stamp>"
printf '%s' "${STAMP}" | grep -Eq '^[0-9]{8}T[0-9]{6}Z(-[0-9]+)?$' || die "stamp '${STAMP}' is not a backup name like 20260915T030000Z"
```

**Context-rollout upload (orchestrator):** put files **flat** in the rollout bundle folder under docs/plans (no subfolder). MANIFEST and place_files script at that root.

## 3. Files

| Path | Action | What |
|---|---|---|
| deploy/lightsail/scripts/pg-restore.sh | edit | add the `--file` form |
| App/tests/test_pg_backup_scripts.py | edit | four new tests |
| docs/DISASTER_RECOVERY.md | edit | steps 11 and 12 use the file form |
| docs/LIGHTSAIL.md | edit | scripts table row mentions `--file` |
| docs/plans/portable-disaster-recovery.md | edit | mark Restore bullet and step 3 done |
| docs/tasks/1161-report.md | create | the report (§9) |

No other file may change.

## 4. Steps

### Step 1: pg-restore.sh

Check the anchor first: `grep -nF 'STAMP="${1:-}"' deploy/lightsail/scripts/pg-restore.sh` must print line 23. Then replace the whole file with the content below (it was checked with `bash -n` and a stub run: the stamp form logs the same docker calls as before). Differences from today, for the reviewer: usage comment (lines 7-10), `START_DIR` before `ROOT`, the argument block (replaces the old lines 23 to 26 and the old volume check), the confirm line uses `${WHAT}`, the restore block has one branch per form, the final message uses `${SOURCE}`. The stamp branch of the restore block is the old code, line for line.

```bash
#!/usr/bin/env bash
# Restore the PostgreSQL dump that backup.sh wrote into a snapshot folder (brief 0464).
#
# Usage (from deploy/lightsail):
#   AGE_IDENTITY_FILE=/root/ubyhost-backup.agekey ./scripts/pg-restore.sh 20260915T030000Z
#   RESTORE_CONFIRM=yes AGE_IDENTITY_FILE=... ./scripts/pg-restore.sh <stamp>
#   AGE_IDENTITY_FILE=... ./scripts/pg-restore.sh --file /path/to/ubyhost-pg.dump.age
#
# Give exactly one source: a <stamp> (dump read from the app volume) or --file
# (a local .age file on the host, e.g. downloaded from Google Drive; no volume, no AWS).
# Refuses while .env still points the app at SQLite. The dump is decrypted
# on the host and streamed straight into pg_restore: no plaintext file is written.
set -euo pipefail

START_DIR="$PWD"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

die() { echo "ERROR: $*" >&2; exit "${2:-1}"; }

[ -f .env ] || die "missing .env in ${ROOT}"
if grep -Eq '^UBYHOST_DB=' .env; then
  die "the app still runs on SQLite (UBYHOST_DB is set in .env); restore only after cutover" 2
fi
grep -Eq '^UBYHOST_DATABASE_URL=' .env || die "UBYHOST_DATABASE_URL is not set in .env; the app is not on PostgreSQL" 2

IDENTITY="${AGE_IDENTITY_FILE:-}"
USAGE="usage: $0 <stamp> | $0 --file /path/to/ubyhost-pg.dump.age"
MODE=""
STAMP=""
DUMP_FILE=""
if [ "$#" -eq 2 ] && [ "$1" = "--file" ]; then
  MODE="file"
  DUMP_FILE="$2"
elif [ "$#" -eq 1 ] && [ "$1" != "--file" ]; then
  MODE="stamp"
  STAMP="$1"
else
  die "${USAGE}"
fi

if [ "${MODE}" = "stamp" ]; then
  [ -n "${STAMP}" ] || die "${USAGE}"
  printf '%s' "${STAMP}" | grep -Eq '^[0-9]{8}T[0-9]{6}Z(-[0-9]+)?$' || die "stamp '${STAMP}' is not a backup name like 20260915T030000Z"
  SOURCE="${STAMP}"
  WHAT="snapshot ${STAMP}"
else
  [ -n "${DUMP_FILE}" ] || die "${USAGE}"
  case "${DUMP_FILE}" in /*) ;; *) DUMP_FILE="${START_DIR}/${DUMP_FILE}" ;; esac
  case "${DUMP_FILE}" in *.age) ;; *) die "${DUMP_FILE} is not an .age file" ;; esac
  [ -f "${DUMP_FILE}" ] || die "${DUMP_FILE} does not exist on the host"
  [ -r "${DUMP_FILE}" ] || die "${DUMP_FILE} is not readable"
  [ -s "${DUMP_FILE}" ] || die "${DUMP_FILE} is empty"
  SOURCE="${DUMP_FILE}"
  WHAT="file ${DUMP_FILE}"
fi

[ -n "${IDENTITY}" ] || die "set AGE_IDENTITY_FILE to the age identity on the host (never inside the volume)"
[ -f "${IDENTITY}" ] || die "AGE_IDENTITY_FILE=${IDENTITY} does not exist on the host"
command -v age >/dev/null 2>&1 || die "the 'age' binary is missing on the host"

if [ "${MODE}" = "stamp" ]; then
  docker compose run --rm --no-deps -T --entrypoint sh ubyhost \
    -c "test -f /data/backups/${STAMP}/ubyhost-pg.dump.age" >/dev/null 2>&1 \
    || die "no ubyhost-pg.dump.age in snapshot ${STAMP}"
fi

if [ "${RESTORE_CONFIRM:-}" != "yes" ]; then
  echo "This replaces every table in the ubyhost PostgreSQL database with ${WHAT}."
  read -r -p "Type yes to continue: " CONFIRM
  [ "${CONFIRM}" = "yes" ] || die "aborted"
fi

CONTAINER="$(docker compose ps -aq ubyhost)"
[ -n "${CONTAINER}" ] || die "could not find the ubyhost container; run ./scripts/deploy.sh first"

TMP="$(mktemp -d)"
chmod 700 "${TMP}"
trap 'rm -rf "${TMP}"' EXIT

echo "==> Stopping worker and ubyhost"
docker compose stop worker ubyhost
# From here on, any failure brings the app back up (a no-op after the explicit start below).
trap 'rm -rf "${TMP}"; docker compose up -d ubyhost worker >/dev/null 2>&1 || true' EXIT

if [ "${MODE}" = "stamp" ]; then
  echo "==> Pulling ${STAMP} and restoring it into PostgreSQL"
  docker cp "${CONTAINER}:/data/backups/${STAMP}/ubyhost-pg.dump.age" "${TMP}/ubyhost-pg.dump.age"
  age -d -i "${IDENTITY}" "${TMP}/ubyhost-pg.dump.age" \
    | docker compose exec -T postgres pg_restore -U ubyhost -d ubyhost --clean --if-exists --single-transaction
  rm -f "${TMP}/ubyhost-pg.dump.age"
else
  echo "==> Restoring ${DUMP_FILE} into PostgreSQL"
  age -d -i "${IDENTITY}" "${DUMP_FILE}" \
    | docker compose exec -T postgres pg_restore -U ubyhost -d ubyhost --clean --if-exists --single-transaction
fi

echo "==> Starting ubyhost and the worker"
docker compose up -d ubyhost worker

echo "==> Waiting for health"
for _ in $(seq 1 30); do
  if docker compose exec -T ubyhost python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)" \
    >/dev/null 2>&1; then
    echo "PostgreSQL restore complete from ${SOURCE}. Sign in and open one stay to confirm data."
    exit 0
  fi
  sleep 2
done

echo "ubyhost did not become healthy: run ./scripts/logs.sh ubyhost" >&2
exit 1
```

Run: `bash -n deploy/lightsail/scripts/pg-restore.sh 2>&1 | tail -30` (no output). Commit: `1161 step 1`.

### Step 2: tests

Anchor: `grep -nF 'def test_pg_restore_rejects_bad_stamp' App/tests/test_pg_backup_scripts.py` (line 98). Insert the code below on a new line directly after the last line of that test (the line `    assert "stop" not in calls(log)` at line 103), keeping two blank lines before the next `@pytest.mark.parametrize("running"...` at line 106. Do not edit the existing tests.

```python


def make_dump_file(tmp_path, name="ubyhost-pg.dump.age", text="ciphertext"):
    dump = tmp_path / name
    dump.write_text(text)
    return dump


def test_pg_restore_file_form_streams_host_file_without_docker_cp(tmp_path):
    root, bindir, log = make_tree(tmp_path, PG_ENV)
    identity = tmp_path / "agekey"
    identity.write_text("stub")
    dump = make_dump_file(tmp_path)
    result = run_script("pg-restore.sh", root, bindir, log, args=["--file", str(dump)],
                        extra_env={"AGE_IDENTITY_FILE": str(identity), "RESTORE_CONFIRM": "yes"})
    assert result.returncode == 0, result.stderr
    recorded = calls(log)
    assert "cp " not in recorded
    assert "stop worker ubyhost" in recorded
    assert "pg_restore -U ubyhost -d ubyhost --clean --if-exists --single-transaction" in recorded
    assert "up -d ubyhost worker" in recorded


def test_pg_restore_file_form_missing_file_exits_1_before_stopping(tmp_path):
    root, bindir, log = make_tree(tmp_path, PG_ENV)
    identity = tmp_path / "agekey"
    identity.write_text("stub")
    result = run_script("pg-restore.sh", root, bindir, log,
                        args=["--file", str(tmp_path / "missing.age")],
                        extra_env={"AGE_IDENTITY_FILE": str(identity), "RESTORE_CONFIRM": "yes"})
    assert result.returncode == 1
    assert "stop" not in calls(log)


def test_pg_restore_file_form_refuses_a_name_that_is_not_age(tmp_path):
    root, bindir, log = make_tree(tmp_path, PG_ENV)
    identity = tmp_path / "agekey"
    identity.write_text("stub")
    dump = make_dump_file(tmp_path, name="ubyhost-pg.dump")
    result = run_script("pg-restore.sh", root, bindir, log, args=["--file", str(dump)],
                        extra_env={"AGE_IDENTITY_FILE": str(identity), "RESTORE_CONFIRM": "yes"})
    assert result.returncode == 1
    assert "stop" not in calls(log)


@pytest.mark.parametrize("args", [[], ["20260101T000000Z", "--file", "x.age"], ["--file"]])
def test_pg_restore_needs_exactly_one_source(tmp_path, args):
    root, bindir, log = make_tree(tmp_path, PG_ENV)
    identity = tmp_path / "agekey"
    identity.write_text("stub")
    result = run_script("pg-restore.sh", root, bindir, log, args=args,
                        extra_env={"AGE_IDENTITY_FILE": str(identity), "RESTORE_CONFIRM": "yes"})
    assert result.returncode == 1
    assert "usage:" in result.stderr
    assert "stop" not in calls(log)
```

Run the §6 test command. Commit: `1161 step 2`.

### Step 3: docs/DISASTER_RECOVERY.md

Anchor: `grep -nF 'Place the dump in the volume' docs/DISASTER_RECOVERY.md` (line 85). Replace lines 85 to 95 (step 11 and step 12 including their code blocks) so that steps 8, 10, 13 stay as they are.

Old (exact):

````
11. Place the dump in the volume (workaround until brief for a restore-from-file option):

```bash
docker run --rm -v ubyhost-data:/data -v "$PWD/restore-in":/in alpine sh -c 'mkdir -p /data/backups/<stamp> && cp /in/ubyhost-pg.dump.age /data/backups/<stamp>/'
```

12. Restore the database. The script refuses while `.env` contains `UBYHOST_DB=`:

```bash
RESTORE_CONFIRM=yes AGE_IDENTITY_FILE=/root/ubyhost-backup.agekey ./scripts/pg-restore.sh <stamp>
```
````

New (exact):

````
11. The dump from step 8 is already on the server in `restore-in`. Keep it outside the volume: the restore reads it straight from the host and writes no plaintext file. If you downloaded it elsewhere, copy it to the server first (any path ending in `.age` works).

12. Restore the database from that file. The script refuses while `.env` contains `UBYHOST_DB=`:

```bash
RESTORE_CONFIRM=yes AGE_IDENTITY_FILE=/root/ubyhost-backup.agekey ./scripts/pg-restore.sh --file ./restore-in/ubyhost-pg.dump.age
```
````

Run: `grep -nF -e '--file' docs/DISASTER_RECOVERY.md | tail -30` (one match) and `grep -c 'restore-from-file option' docs/DISASTER_RECOVERY.md | tail -30` (prints 0). Commit: `1161 step 3`.

### Step 4: docs/LIGHTSAIL.md

Anchor: `grep -nF 'AGE_IDENTITY_FILE=… ./scripts/pg-restore.sh <stamp>' docs/LIGHTSAIL.md` (line 219).

Old (exact):

```
| `AGE_IDENTITY_FILE=… ./scripts/pg-restore.sh <stamp>` | Stop app and worker, restore the age-encrypted PostgreSQL dump from a snapshot, start (refuses while on SQLite) |
```

New (exact):

```
| `AGE_IDENTITY_FILE=… ./scripts/pg-restore.sh <stamp>` or `… ./scripts/pg-restore.sh --file /path/to/ubyhost-pg.dump.age` | Stop app and worker, restore the age-encrypted PostgreSQL dump from a snapshot or from a local `.age` file on the host (for example from Drive), start (refuses while on SQLite) |
```

Commit: `1161 step 4`.

### Step 5: docs/plans/portable-disaster-recovery.md

Anchor 1: `grep -nF 'Restore: `pg-restore.sh <stamp>`' docs/plans/portable-disaster-recovery.md` (line 15).

Old (exact):

```
- Restore: `pg-restore.sh <stamp>` reads the dump from the app volume, not from a file (`pg-restore.sh:44-55`). Rebuild steps and a quarterly drill: `docs/LIGHTSAIL.md:286-310`.
```

New (exact):

```
- Restore: `pg-restore.sh <stamp>` reads the dump from the app volume; `pg-restore.sh --file <path>.age` restores from a local file on the host, no volume and no AWS (brief 1161, 2026-11-12). Rebuild steps and a quarterly drill: `docs/LIGHTSAIL.md:286-310`.
```

Anchor 2: `grep -nF '| 3 | `pg-restore.sh` option' docs/plans/portable-disaster-recovery.md` (line 44).

Old (exact):

```
| 3 | `pg-restore.sh` option to restore from a local `.age` file (no volume stamp, no AWS) | M | Haiku brief | 1 |
```

New (exact):

```
| 3 | `pg-restore.sh` option to restore from a local `.age` file (no volume stamp, no AWS) (brief 1161, done) | M | Haiku brief | 1 |
```

Leave gap 2 (line 21) untouched. Commit: `1161 step 5`.

### Step 6: report

Write `docs/tasks/1161-report.md` per §9, set `Status: review`, commit `1161 step 6`, open one PR (draft is fine).

## 5. Do not touch

- Every path not in §3. In particular `docs/context/status.md` and `docs/context/test-map.md` (both at the token cap), `backup.sh`, `backup-gdrive.sh`, `restore.sh`.
- Hard rules: no secrets or real stamps in docs (placeholders only, rule 3); no new dependency (rule 4); no push, merge or deploy.

## 6. Commands

The [test-map](../context/test-map.md) has no row naming `test_pg_backup_scripts.py`; its row "Deploy scripts, Caddyfile, compose" gives shellcheck. Run both, plus the lint:

From `App/`:

```
.venv/bin/python -m pytest tests/test_pg_backup_scripts.py -q --tb=short -x 2>&1 | tail -30
```

Expected: all pass (the four new tests plus the existing ones; the parametrized usage test counts as three).

From the repo root:

```
bash -n deploy/lightsail/scripts/pg-restore.sh 2>&1 | tail -30
shellcheck -S error deploy/lightsail/scripts/pg-restore.sh 2>&1 | tail -30
python3 scripts/context_lint.py 2>&1 | tail -30
```

Expected: no output from the first two (if `shellcheck` is not installed, say so in the report and skip it); the lint ends without errors.

## 7. Acceptance

- [ ] `bash -n deploy/lightsail/scripts/pg-restore.sh` prints nothing.
- [ ] The pytest command passes, with the old stamp tests unchanged.
- [ ] `grep -c 'docker cp' deploy/lightsail/scripts/pg-restore.sh` prints 1 (stamp branch only).
- [ ] `grep -nF -e '--file' docs/DISASTER_RECOVERY.md docs/LIGHTSAIL.md docs/plans/portable-disaster-recovery.md | tail -30` shows a match in each of the three files.
- [ ] `python3 scripts/context_lint.py` ends without errors.
- [ ] `git diff --stat` lists only the §3 files.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1161-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `deploy/lightsail/scripts/pg-restore.sh`: destructive restore path. Check that the stamp branch behaves as before (same checks in the same order, same `docker cp`, same `age` and `pg_restore` lines, same trap), that the file branch writes no plaintext and never stops the app before every file check has passed, and that the `--file` check cannot be bypassed by a relative path.
- `docs/DISASTER_RECOVERY.md` steps 11 and 12: the command a stressed owner will paste.

## Owner steps

None needed to merge. After the merge, use the `--file` form in the step-8 timed drill of the plan (`docs/plans/portable-disaster-recovery.md`).
