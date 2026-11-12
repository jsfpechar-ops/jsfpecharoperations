# 1169: DR filing guard on a restored box

Status: review
Depends on: 1161, 1166 (both on main) | Base commit: cd8bf5f | Branch: claude/dr-filing-guard
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

`pg-restore.sh --file` (a restore on a rebuilt box) writes a marker `deploy/lightsail/.restored-box`; while that marker exists, a new `filing-guard.sh`, run by `preflight.sh` (so by every `deploy.sh`) and by `pg-restore.sh --file`, blocks unless automatic filing is off. This is step 6 of [portable-disaster-recovery](../plans/portable-disaster-recovery.md): two servers must never file the same guests with the police (AGENTS.md rule 1, owner decision 4).

## 2. Context

Rules that apply: AGENTS.md rule 1 (filing correctness beats everything), rule 3 (public repo: no secrets, no real `.env`), rule 4 (no new dependency: bash and pytest only), rule 8 (never push to `main`). No `App/` Python behaviour change.

Design (decided by the brief writer, do not change):

- **Detection.** Only `pg-restore.sh --file` writes `.restored-box` (next to `.env`, git-ignored). The stamp form restores from the box's own volume, so it is the same box and writes no marker. The current Lightsail box has no marker, so every normal deploy is unchanged: the guard exits 0 silently.
- **What "filing off" means.** In `App/app/scheduler.py`, `_target(kind)` enqueues a kind only when it is in `UBYHOST_JOB_QUEUE_KINDS`, otherwise the Python worker runs the job itself; `_job_submit` runs `reporting.sweep()`. So with `submit` in neither list the Python worker still files. Filing is off only when `UBYHOST_ENABLE_SCHEDULER` is `0`, `false` or `no` (same test as `App/app/config.py:379`) **and** `submit` is in neither `UBYHOST_GO_JOB_KINDS` nor `UBYHOST_JOB_QUEUE_KINDS`. `worker.py` stays healthy with the scheduler off (it still touches `worker.alive`).
- **Block, not warn.** Marker present and filing could run: the guard prints `!!! RESTORED BOX ...` lines and exits 3; `preflight.sh` then fails, so `deploy.sh` stops before any build; `pg-restore.sh --file` stops before it stops any container (exit 3). Marker present and filing off: a `NOTE:` line, exit 0.
- **Acknowledgement.** The owner removes the marker (`rm .restored-box`) once the old server is confirmed stopped, then turns filing back on and deploys.
- **Override.** `UBYHOST_FILING_GUARD_OVERRIDE=1` on the command line for one run: loud `WARNING`, exit 0. The guard refuses (exit 3) when that name appears in `.env`, so it can never stay on. The guard reads the three filing variables from `.env` only (it unsets them before `source .env`), because `.env` is what the containers get (`env_file`).

Excerpts that must exist verbatim:

`deploy/lightsail/scripts/preflight.sh` (lines 156 to 159):

```
if [ "${fail}" -ne 0 ]; then
  echo "Preflight failed. Fix .env (and origin certs) before deploy." >&2
  exit 1
fi
```

`deploy/lightsail/scripts/pg-restore.sh` (lines 58 to 60):

```
[ -n "${IDENTITY}" ] || die "set AGE_IDENTITY_FILE to the age identity on the host (never inside the volume)"
[ -f "${IDENTITY}" ] || die "AGE_IDENTITY_FILE=${IDENTITY} does not exist on the host"
command -v age >/dev/null 2>&1 || die "the 'age' binary is missing on the host"
```

`deploy/lightsail/.gitignore` last line: `.deployed-sha`.

`App/tests/test_pg_backup_scripts.py`: the `make_tree` loop `for name in ("backup.sh", "pg-restore.sh"):` (line 44), the syntax parametrize (line 69), `def make_dump_file(` (line 106), `def test_pg_restore_file_form_streams_host_file_without_docker_cp` (line 112), `@pytest.mark.parametrize("running", [1, 0])` (line 161).

`docs/DISASTER_RECOVERY.md`: section `## Two servers never file at once` (lines 23 to 35), rebuild step 4 (line 65), step 12 (line 99).

**Context-rollout upload (orchestrator):** put files **flat** in the rollout bundle folder under docs/plans (no subfolder). MANIFEST and place_files script at that root.

## 3. Files

| Path | Action | What |
|---|---|---|
| deploy/lightsail/scripts/filing-guard.sh | create (mode 755) | the guard |
| deploy/lightsail/scripts/preflight.sh | edit | run the guard before the final fail check |
| deploy/lightsail/scripts/pg-restore.sh | edit | `--file`: write the marker, run the guard |
| deploy/lightsail/.gitignore | edit | ignore `.restored-box` |
| App/tests/test_pg_backup_scripts.py | edit | guard, preflight and pg-restore tests |
| docs/DISASTER_RECOVERY.md | edit | "Two servers never file at once" rewritten; steps 4 and 12 |
| docs/plans/portable-disaster-recovery.md | edit | gap 6 and step 6 row name brief 1169 |
| docs/ENVIRONMENT.md | edit | one row for `UBYHOST_FILING_GUARD_OVERRIDE` |
| docs/tasks/1169-dr-filing-guard.md | edit | `Status:` only |
| docs/tasks/1169-report.md | create | the report |

No other file may change.

## 4. Steps

Work on branch `claude/dr-filing-guard` (it exists; `git checkout claude/dr-filing-guard`).

### Step 1: create the guard

Create `deploy/lightsail/scripts/filing-guard.sh` with exactly this content:

```bash
#!/usr/bin/env bash
# Filing guard for a restored box (brief 1169, disaster recovery step 6).
#
# pg-restore.sh --file writes .restored-box next to .env: this box was rebuilt
# from a backup file, and the old server may still be filing the same guests.
# While that marker exists, automatic filing must stay off: UBYHOST_ENABLE_SCHEDULER=0
# and `submit` in neither UBYHOST_GO_JOB_KINDS nor UBYHOST_JOB_QUEUE_KINDS.
# (With `submit` in neither list the Python worker files guests itself, so the
# lists alone never prove that filing is off.)
# The owner removes the marker once the old server is confirmed off:
# docs/DISASTER_RECOVERY.md, "Two servers never file at once".
#
# Usage (from deploy/lightsail): ./scripts/filing-guard.sh
#   exit 0: no marker; or marker and filing off; or the one-run override is set
#   exit 3: marker and automatic filing could run
# One-run override, never in .env: UBYHOST_FILING_GUARD_OVERRIDE=1 ./scripts/deploy.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

MARKER=".restored-box"
[ -f "${MARKER}" ] || exit 0

OVERRIDE="${UBYHOST_FILING_GUARD_OVERRIDE:-}"

if [ ! -f .env ]; then
  echo "ERROR: restored box and no .env in ${ROOT}" >&2
  exit 3
fi
if grep -Eq '^[[:space:]]*(export[[:space:]]+)?UBYHOST_FILING_GUARD_OVERRIDE=' .env; then
  echo "ERROR: UBYHOST_FILING_GUARD_OVERRIDE must not be in .env; set it on the command line for one run" >&2
  exit 3
fi

# Only .env counts: it is what the containers get (env_file).
unset UBYHOST_ENABLE_SCHEDULER UBYHOST_GO_JOB_KINDS UBYHOST_JOB_QUEUE_KINDS
# shellcheck disable=SC1091
set -a
source .env
set +a

has_submit() {
  local list
  list="$(printf '%s' "${1:-}" | tr -d '[:space:]')"
  case ",${list}," in
    *,submit,*) return 0 ;;
  esac
  return 1
}

reasons=()
case "${UBYHOST_ENABLE_SCHEDULER:-1}" in
  0|false|no) ;;
  *) reasons+=("UBYHOST_ENABLE_SCHEDULER is not 0: the Python worker files guests") ;;
esac
if has_submit "${UBYHOST_GO_JOB_KINDS:-}"; then
  reasons+=("submit is in UBYHOST_GO_JOB_KINDS")
fi
if has_submit "${UBYHOST_JOB_QUEUE_KINDS:-}"; then
  reasons+=("submit is in UBYHOST_JOB_QUEUE_KINDS")
fi

if [ "${#reasons[@]}" -eq 0 ]; then
  echo "NOTE: restored box (${ROOT}/${MARKER}): automatic filing is off. Remove the marker once the old server is confirmed off (docs/DISASTER_RECOVERY.md)." >&2
  exit 0
fi

echo "!!! RESTORED BOX: the old server may still be filing the same guests with the police." >&2
for reason in "${reasons[@]}"; do
  echo "!!!   ${reason}" >&2
done
if [ "${OVERRIDE}" = "1" ]; then
  echo "WARNING: UBYHOST_FILING_GUARD_OVERRIDE=1: continuing with automatic filing on. Remove ${ROOT}/${MARKER} once the old server is confirmed off." >&2
  exit 0
fi
echo "ERROR: automatic filing stays blocked while ${ROOT}/${MARKER} exists. Stop the old server, then follow docs/DISASTER_RECOVERY.md, \"Two servers never file at once\"." >&2
exit 3
```

Then:

```
chmod 755 deploy/lightsail/scripts/filing-guard.sh && bash -n deploy/lightsail/scripts/filing-guard.sh 2>&1 | tail -30
git add deploy/lightsail/scripts/filing-guard.sh && git commit -q -m "1169 step 1" && git ls-files -s deploy/lightsail/scripts/filing-guard.sh | tail -1
```

Expected: no output from `bash -n`; the last line starts with `100755`.

### Step 2: preflight runs the guard

In `deploy/lightsail/scripts/preflight.sh`, replace

```
if [ "${fail}" -ne 0 ]; then
  echo "Preflight failed. Fix .env (and origin certs) before deploy." >&2
```

with

```
# Brief 1169: a box rebuilt with pg-restore.sh --file must not file while the
# old server may still file. No .restored-box marker (every normal box): no-op.
if ! bash "${ROOT}/scripts/filing-guard.sh"; then
  die "filing guard: restored box with automatic filing on (see the lines above)"
fi

if [ "${fail}" -ne 0 ]; then
  echo "Preflight failed. Fix .env (and origin certs) before deploy." >&2
```

Run `bash -n deploy/lightsail/scripts/preflight.sh 2>&1 | tail -30` (no output), then `git commit -qam "1169 step 2"`.

### Step 3: pg-restore --file writes the marker and runs the guard

In `deploy/lightsail/scripts/pg-restore.sh`, replace

```
command -v age >/dev/null 2>&1 || die "the 'age' binary is missing on the host"
```

with

```
command -v age >/dev/null 2>&1 || die "the 'age' binary is missing on the host"

if [ "${MODE}" = "file" ]; then
  # Brief 1169: a restore from a file means a rebuilt box, and the old server may
  # still be filing. The marker stays until the owner removes it
  # (docs/DISASTER_RECOVERY.md, "Two servers never file at once").
  printf 'restored %s from %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(basename "${DUMP_FILE}")" > .restored-box
  bash "${ROOT}/scripts/filing-guard.sh" \
    || die "turn automatic filing off in .env first (UBYHOST_ENABLE_SCHEDULER=0, submit in neither job list)" 3
fi
```

Run `bash -n deploy/lightsail/scripts/pg-restore.sh 2>&1 | tail -30` (no output), then `git commit -qam "1169 step 3"`.

### Step 4: ignore the marker

Append one line `.restored-box` at the end of `deploy/lightsail/.gitignore` (after `.deployed-sha`; the file must end with a newline):

```
printf '.restored-box\n' >> deploy/lightsail/.gitignore && tail -2 deploy/lightsail/.gitignore
```

Expected: `.deployed-sha` then `.restored-box`. Commit `1169 step 4`.

### Step 5: tests

Seven edits in `App/tests/test_pg_backup_scripts.py`.

5a. Replace

```
    for name in ("backup.sh", "pg-restore.sh"):
```

with

```
    for name in ("backup.sh", "pg-restore.sh", "filing-guard.sh"):
```

5b. Replace

```
@pytest.mark.parametrize("name", ["backup.sh", "pg-restore.sh", "pg-cutover.sh"])
```

with

```
@pytest.mark.parametrize("name", ["backup.sh", "pg-restore.sh", "pg-cutover.sh", "filing-guard.sh", "preflight.sh"])
```

5c. In `test_pg_restore_streams_dump_into_pg_restore` (the stamp test), replace

```
    assert "up -d ubyhost worker" in recorded


def test_pg_restore_rejects_bad_stamp(tmp_path):
```

with

```
    assert "up -d ubyhost worker" in recorded
    assert not (root / ".restored-box").exists()


def test_pg_restore_rejects_bad_stamp(tmp_path):
```

5d. Replace

```
def make_dump_file(tmp_path, name="ubyhost-pg.dump.age", text="ciphertext"):
```

with

```
FILING_OFF = "UBYHOST_ENABLE_SCHEDULER=0\nUBYHOST_GO_JOB_KINDS=ical,push\nUBYHOST_JOB_QUEUE_KINDS=ical,push\n"


def make_dump_file(tmp_path, name="ubyhost-pg.dump.age", text="ciphertext"):
```

5e. Replace

```
def test_pg_restore_file_form_streams_host_file_without_docker_cp(tmp_path):
    root, bindir, log = make_tree(tmp_path, PG_ENV)
```

with

```
def test_pg_restore_file_form_streams_host_file_without_docker_cp(tmp_path):
    root, bindir, log = make_tree(tmp_path, PG_ENV + FILING_OFF)
```

5f. In the same test, replace

```
    assert "cp " not in recorded
    assert "stop worker ubyhost" in recorded
    assert "pg_restore -U ubyhost -d ubyhost --clean --if-exists --single-transaction" in recorded
    assert "up -d ubyhost worker" in recorded
```

with

```
    assert "cp " not in recorded
    assert "stop worker ubyhost" in recorded
    assert "pg_restore -U ubyhost -d ubyhost --clean --if-exists --single-transaction" in recorded
    assert "up -d ubyhost worker" in recorded
    assert "from ubyhost-pg.dump.age" in (root / ".restored-box").read_text()


def test_pg_restore_file_form_refuses_while_filing_is_on(tmp_path):
    root, bindir, log = make_tree(tmp_path, PG_ENV + "UBYHOST_GO_JOB_KINDS=ical,submit\n")
    identity = tmp_path / "agekey"
    identity.write_text("stub")
    dump = make_dump_file(tmp_path)
    result = run_script("pg-restore.sh", root, bindir, log, args=["--file", str(dump)],
                        extra_env={"AGE_IDENTITY_FILE": str(identity), "RESTORE_CONFIRM": "yes"})
    assert result.returncode == 3, result.stderr
    assert "RESTORED BOX" in result.stderr
    assert (root / ".restored-box").exists()
    assert "stop" not in calls(log)
```

(The anchor in 5f appears once: the stamp test has no `"cp " not in recorded` line.)

5g. Insert this block directly above the line `@pytest.mark.parametrize("running", [1, 0])` (keep that line and everything below it unchanged):

```python
# Brief 1169: the filing guard on a restored box (marker .restored-box).
PREFLIGHT_ENV = (
    "UBYHOST_DOMAIN=ubyhost.example\n"
    "ACME_EMAIL=ops@ubyhost.example\n"
    "UBYHOST_PUBLIC_BASE_URL=https://ubyhost.example\n"
    "UBYHOST_DEPLOYMENT=production\n"
    "UBYHOST_UBYPORT_ENV=prod\n"
    "UBYHOST_BACKUP_AGE_RECIPIENT=age1test\n"
    "UBYHOST_BACKUP_PING_URL=https://ping.example/backup\n"
)
SUBMIT_ON = "UBYHOST_GO_JOB_KINDS=ical,submit\nUBYHOST_JOB_QUEUE_KINDS=ical,submit\n"


def make_guard_tree(tmp_path, env_text, marker):
    """A throwaway deploy/lightsail tree with preflight, the guard and site_urls.py."""
    root = tmp_path / "deploy" / "lightsail"
    (root / "scripts").mkdir(parents=True)
    for name in ("preflight.sh", "filing-guard.sh"):
        shutil.copy(SCRIPTS / name, root / "scripts" / name)
    (tmp_path / "App" / "app").mkdir(parents=True)
    shutil.copy(ROOT / "App/app/site_urls.py", tmp_path / "App" / "app" / "site_urls.py")
    (root / ".env").write_text(env_text)
    if marker:
        (root / ".restored-box").write_text("restored 2026-11-12T00:00:00Z from ubyhost-pg.dump.age\n")
    return root


def run_guard(root, script="filing-guard.sh", extra_env=None):
    env = {"PATH": os.environ["PATH"], "UBYHOST_ALLOW_SMALL_HOST": "1"}
    env.update(extra_env or {})
    return subprocess.run(
        ["bash", str(root / "scripts" / script)],
        cwd=root, env=env, capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL,
    )


def test_filing_guard_without_marker_is_silent_even_with_submit(tmp_path):
    root = make_guard_tree(tmp_path, SUBMIT_ON, marker=False)
    result = run_guard(root)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""


@pytest.mark.parametrize("env_text", [
    "",
    "UBYHOST_ENABLE_SCHEDULER=1\n",
    "UBYHOST_ENABLE_SCHEDULER=0\nUBYHOST_GO_JOB_KINDS=\"ical, submit\"\n",
    "UBYHOST_ENABLE_SCHEDULER=0\nUBYHOST_JOB_QUEUE_KINDS=submit\n",
])
def test_filing_guard_blocks_restored_box_while_filing_can_run(tmp_path, env_text):
    root = make_guard_tree(tmp_path, env_text, marker=True)
    result = run_guard(root)
    assert result.returncode == 3, result.stderr
    assert "RESTORED BOX" in result.stderr
    assert "ERROR: automatic filing stays blocked" in result.stderr


def test_filing_guard_allows_restored_box_with_filing_off(tmp_path):
    root = make_guard_tree(tmp_path, FILING_OFF, marker=True)
    result = run_guard(root)
    assert result.returncode == 0, result.stderr
    assert "NOTE: restored box" in result.stderr
    assert "RESTORED BOX" not in result.stderr


def test_filing_guard_reads_env_file_not_the_caller(tmp_path):
    root = make_guard_tree(tmp_path, SUBMIT_ON, marker=True)
    result = run_guard(root, extra_env={"UBYHOST_ENABLE_SCHEDULER": "0", "UBYHOST_GO_JOB_KINDS": "ical"})
    assert result.returncode == 3, result.stderr


def test_filing_guard_override_for_one_run_warns_and_passes(tmp_path):
    root = make_guard_tree(tmp_path, SUBMIT_ON, marker=True)
    result = run_guard(root, extra_env={"UBYHOST_FILING_GUARD_OVERRIDE": "1"})
    assert result.returncode == 0, result.stderr
    assert "RESTORED BOX" in result.stderr
    assert "WARNING: UBYHOST_FILING_GUARD_OVERRIDE=1" in result.stderr


def test_filing_guard_refuses_override_kept_in_env_file(tmp_path):
    root = make_guard_tree(tmp_path, SUBMIT_ON + "UBYHOST_FILING_GUARD_OVERRIDE=1\n", marker=True)
    result = run_guard(root, extra_env={"UBYHOST_FILING_GUARD_OVERRIDE": "1"})
    assert result.returncode == 3, result.stderr
    assert "must not be in .env" in result.stderr


def test_preflight_passes_on_a_normal_box_with_submit(tmp_path):
    root = make_guard_tree(tmp_path, PREFLIGHT_ENV + SUBMIT_ON, marker=False)
    result = run_guard(root, script="preflight.sh")
    assert result.returncode == 0, result.stderr
    assert "Preflight OK" in result.stdout
    assert "RESTORED BOX" not in result.stderr


def test_preflight_fails_on_a_restored_box_with_submit(tmp_path):
    root = make_guard_tree(tmp_path, PREFLIGHT_ENV + SUBMIT_ON, marker=True)
    result = run_guard(root, script="preflight.sh")
    assert result.returncode == 1
    assert "ERROR: filing guard: restored box with automatic filing on" in result.stderr
    assert "Preflight failed." in result.stderr


def test_preflight_passes_on_a_restored_box_with_filing_off(tmp_path):
    root = make_guard_tree(tmp_path, PREFLIGHT_ENV + FILING_OFF, marker=True)
    result = run_guard(root, script="preflight.sh")
    assert result.returncode == 0, result.stderr
    assert "Preflight OK" in result.stdout
    assert "NOTE: restored box" in result.stderr


```

Run (§6 test command), expect all pass, then `git commit -qam "1169 step 5"`.

### Step 6: docs

6a. In `docs/DISASTER_RECOVERY.md`, replace the whole section from `## Two servers never file at once` down to (not including) `## Show the "we're down" page` with the text below (without the two ```` fence lines; keep one blank line before `## Show the "we're down" page`):

````markdown
## Two servers never file at once

Before any rebuild step, make sure the old server cannot file. Removing `submit` from the job lists is not enough: with `submit` in neither list, the Python worker files guests itself. Only a stopped server, or `UBYHOST_ENABLE_SCHEDULER=0`, stops automatic filing.

1. On the **old** server, stop it: `docker compose stop`. Or, if it must keep running, set `UBYHOST_ENABLE_SCHEDULER=0` in its `.env`, remove `submit` from `UBYHOST_GO_JOB_KINDS` and `UBYHOST_JOB_QUEUE_KINDS`, and run `./scripts/deploy.sh`.
2. On the **new** box, before the first deploy (rebuild step 4), turn automatic filing off in `.env`: set `UBYHOST_ENABLE_SCHEDULER=0` and remove `submit` from both variables. Check:

```bash
grep -n 'UBYHOST_ENABLE_SCHEDULER\|UBYHOST_GO_JOB_KINDS\|UBYHOST_JOB_QUEUE_KINDS' .env
```

3. The restore (rebuild step 12) writes the marker file `.restored-box` next to `.env`. While it exists, `pg-restore.sh --file` and `./scripts/deploy.sh` stop with `RESTORED BOX` if automatic filing is on. Leave filing off until the owner is sure the old server is off.
4. When sure (the old server is stopped, or deleted in its provider console), acknowledge it on the new box:

```bash
rm .restored-box
```

5. Turn filing back on: in `.env` set `UBYHOST_ENABLE_SCHEDULER=1` and add `submit` back to both variables (as on the old server). Then deploy:

```bash
./scripts/deploy.sh
```

Override for one run, only when the owner knows the old server cannot file and the marker must stay: `UBYHOST_FILING_GUARD_OVERRIDE=1 ./scripts/deploy.sh`. Never put it in `.env`; the guard refuses that.

````

6b. In `docs/DISASTER_RECOVERY.md`, rebuild step 4, replace

```
Without it the restored data cannot be decrypted.
```

with

```
Without it the restored data cannot be decrypted. Turn automatic filing off in the same `.env` (see "Two servers never file at once", step 2).
```

6c. In `docs/DISASTER_RECOVERY.md`, step 12, replace

```
12. Restore the database from that file. The script refuses while `.env` contains `UBYHOST_DB=`:
```

with

```
12. Restore the database from that file. The script refuses while `.env` contains `UBYHOST_DB=`, and while automatic filing is on. It writes the marker `.restored-box` (see "Two servers never file at once"):
```

6d. In `docs/plans/portable-disaster-recovery.md`, replace

```
6. No guard against two servers filing. No "we're down" page (CLOUDFLARE.md has none). The page: brief 1166.
```

with

```
6. Two-server filing guard: brief 1169. No "we're down" page (CLOUDFLARE.md has none). The page: brief 1166.
```

6e. In the same file, replace

```
| 6 | Filing guard: runbook step plus a check in `deploy.sh`/preflight that warns when `submit` is in `UBYHOST_GO_JOB_KINDS` on a restored box | M | Haiku brief | 3 |
```

with

```
| 6 | Filing guard: runbook step plus a check in `deploy.sh`/preflight that blocks on a restored box (`.restored-box`) while filing is on (brief 1169) | M | Haiku brief | 3 |
```

6f. In `docs/ENVIRONMENT.md`, directly below the line that starts with ``| `RESTORE_CONFIRM` |``, insert:

```
| `UBYHOST_FILING_GUARD_OVERRIDE` | unset | `filing-guard.sh` (run by `preflight.sh` and `pg-restore.sh --file`). `1` on the command line lets one run continue on a restored box (`.restored-box` present) with automatic filing on. Refused when it is in `.env`. Owner only: DISASTER_RECOVERY.md, "Two servers never file at once" |
```

Run `python3 scripts/context_lint.py 2>&1 | tail -30`, then `git commit -qam "1169 step 6"`.

### Step 7: report

Run all of §6, write `docs/tasks/1169-report.md` (§9), set `Status: review` in this brief, commit `1169 step 7`. Do not push (the orchestrator pushes and opens the draft PR).

## 5. Do not touch

- `App/app/` (no Python behaviour change), `go/`, `deploy/lightsail/scripts/deploy.sh` (it already runs `./scripts/preflight.sh` after `chmod +x scripts/*.sh`), `deploy/lightsail/docker-compose.yml`, `.github/workflows/`.
- Any `.env` or secret (rule 3). Use only the fake values in the tests.
- Owner decisions in `docs/plans/portable-disaster-recovery.md` ("Owner decisions" list): do not reword them.
- Rule 8: never push to `main`; no push at all, no merge.

## 6. Commands

The [test-map](../context/test-map.md) row "Deploy scripts, Caddyfile, compose" gives shellcheck; the tests for these scripts live in `test_pg_backup_scripts.py`.

From `App/`:

```
.venv/bin/python -m pytest tests/test_pg_backup_scripts.py -q --tb=short -x 2>&1 | tail -30
```

If `App/.venv` does not exist, use a throwaway pytest-only venv; `--noconftest` skips `tests/conftest.py`, which imports the app and needs `requests`:

```
python3 -m venv /tmp/v1169 && /tmp/v1169/bin/pip install -q pytest 2>&1 | tail -3
/tmp/v1169/bin/python -m pytest tests/test_pg_backup_scripts.py -q --tb=short -x --noconftest 2>&1 | tail -30
```

Expected: 0 failed. In the pytest-only venv: `51 passed, 4 skipped` (the 4 skips need `yaml`); with `App/.venv`: 55 passed.

From the repo root:

```
bash -n deploy/lightsail/scripts/filing-guard.sh deploy/lightsail/scripts/preflight.sh deploy/lightsail/scripts/pg-restore.sh 2>&1 | tail -30
shellcheck -S error deploy/lightsail/scripts/filing-guard.sh deploy/lightsail/scripts/preflight.sh deploy/lightsail/scripts/pg-restore.sh 2>&1 | tail -30
python3 scripts/context_lint.py 2>&1 | tail -30
git diff --stat cd8bf5f 2>&1 | tail -30
```

Expected: no output from `bash -n` and shellcheck (if `shellcheck` is not installed, say so in the report and skip it; CI runs it); the lint ends `context lint: OK`; the diff lists only §3 files.

## 7. Acceptance

- [ ] `git ls-files -s deploy/lightsail/scripts/filing-guard.sh` starts with `100755`.
- [ ] The pytest command reports 0 failed, including `test_filing_guard_without_marker_is_silent_even_with_submit`, `test_filing_guard_blocks_restored_box_while_filing_can_run` (4 cases), `test_filing_guard_allows_restored_box_with_filing_off`, `test_filing_guard_override_for_one_run_warns_and_passes`, `test_preflight_passes_on_a_normal_box_with_submit`, `test_preflight_fails_on_a_restored_box_with_submit`, `test_pg_restore_file_form_refuses_while_filing_is_on`.
- [ ] `grep -c 'restored-box' deploy/lightsail/scripts/pg-restore.sh` prints 1 (written in the file branch only).
- [ ] `grep -n 'rm .restored-box' docs/DISASTER_RECOVERY.md` shows one match.
- [ ] `grep -n '1169' docs/plans/portable-disaster-recovery.md` shows two matches.
- [ ] `python3 scripts/context_lint.py` ends `context lint: OK`.
- [ ] `git diff --stat cd8bf5f` lists only the §3 files.

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

Write `docs/tasks/1169-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `deploy/lightsail/scripts/filing-guard.sh`: exits 0 silently with no marker (production deploy unchanged); the scheduler test matches `config.py:379` (`0`, `false`, `no`); `submit` matched as a whole item; `.env` is the only source of the three variables; override refused in `.env`; every other path exits 3.
- `deploy/lightsail/scripts/preflight.sh`: the guard call sits before the final `fail` check and uses `die` (sets `fail=1`), so a block always ends in `Preflight failed.`.
- `deploy/lightsail/scripts/pg-restore.sh`: marker and guard only in the `--file` branch, before the confirm prompt and before `docker compose stop`; stamp form unchanged.
- `docs/DISASTER_RECOVERY.md` "Two servers never file at once": the commands a stressed owner will paste.

## Owner steps

None needed to merge; nothing changes on the current Lightsail box (it has no `.restored-box`).

1. After the merge, read the new "Two servers never file at once" section in `docs/DISASTER_RECOVERY.md` once, so the order (filing off, restore, confirm old server off, `rm .restored-box`, filing on) is known before an outage.
2. In the next timed drill (plan step 8), check that `./scripts/deploy.sh` on the throwaway box stops with `RESTORED BOX` while filing is on.
