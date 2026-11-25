# 2047: Fix the flaky test_backup_waits_for_a_transient_gap_then_succeeds (test stub race)

Status: todo
Base commit: current tip of the working branch | Branch: task/2047-backup-gap-flake
Executor: Haiku 5.5 | Fits one session: 15 tool calls, 40k tokens
Tier: B (test-only edit, one anchor)

> **One PR mode.** Commit as `2047 step 1`. Never push to `main`, never merge (the owner merges with `scripts/merge-pr-on-green.sh`), never deploy.
> Commit trailer lines:
> Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
> Claude-Session: https://claude.ai/code/session_014N5J8NCpdqN2TbR61gYRQf

## 1. Objective

Make `App/tests/test_pg_backup_scripts.py::test_backup_waits_for_a_transient_gap_then_succeeds` pass every time. Today it fails about 1 run in 3 with unchanged code.

## 2. Context

Root cause (verified by running the test 12 times and reading the stub log of each run): the test is racy; `backup.sh` is correct and production is not affected.

- The retry loop (`wait_for_app_container`, `deploy/lightsail/scripts/backup.sh` lines 27-39) is sequential and deterministic: one `ubyhost_app_service` call per attempt, 3 tries.
- The stub counts calls to `ps -q --status running ubyhost-go-b` in the file `$STUB_LOG.n` and answers only when the count is 2 or more. The 3 retry attempts do pass, as intended.
- After the wait, the real backup runs `data_sh` / `ubyhost_app_exec` inside pipelines (for example `tar | age | docker compose exec ... cat > ...`). Each pipeline stage can call `ubyhost_app_service`, so several stub processes run at the same time (the log shows paired `ps ... ubyhost-go` / `ps ... ubyhost-go` / `ubyhost-go-b` / `ubyhost-go-b` lines).
- The stub does `n=$(cat file); echo $((n+1)) > file`. One process truncates the file while another reads it, so the read returns empty or a stale value (n = 0 or 1), the stub prints nothing, `ubyhost_app_service` fails, and `data_sh` prints "Refusing backup" and exits 1. Evidence: failing runs end with `.n` containing 3 or 4; passing runs end with 21-22.
- The failure text starts with "No app container running (attempt 1/3) ... (attempt 2/3)" because pytest shows the whole stderr; those two lines are the normal retries, not the failure.

Fix: once the count reaches 2, create a marker file `$STUB_LOG.up`. After that, answer from the marker alone and never touch the counter again. The counter is then only used in the sequential wait phase, so there is no concurrent writer.

Current stub patch in the test (verify with `grep -nF 'STUB_LOG.n' App/tests/test_pg_backup_scripts.py`, around lines 649-654):
```
        DOCKER_STUB.replace(
            '*"ps -q --status running ubyhost-go-b"*)',
            '*"ps -q --status running ubyhost-go-b"*) [ "${GO_SLOT:-a}" = b ] \\\n'
            '    && { n=$(cat "$STUB_LOG.n" 2>/dev/null || echo 0); echo $((n+1)) > "$STUB_LOG.n"; '
            '[ "$n" -ge 2 ] && echo gobid; } ;;\n  *"NEVERMATCH"*)',
        )
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/test_pg_backup_scripts.py` | edit | replace the two stub lines that contain `STUB_LOG.n` |
| `docs/tasks/2047-report.md` | create | the report |

No other file may change.

## 4. Steps

1. In `App/tests/test_pg_backup_scripts.py`, in `test_backup_waits_for_a_transient_gap_then_succeeds`, replace exactly these two lines:
```
            '    && { n=$(cat "$STUB_LOG.n" 2>/dev/null || echo 0); echo $((n+1)) > "$STUB_LOG.n"; '
            '[ "$n" -ge 2 ] && echo gobid; } ;;\n  *"NEVERMATCH"*)',
```
with these three lines:
```
            '    && { [ -e "$STUB_LOG.up" ] || { n=$(cat "$STUB_LOG.n" 2>/dev/null || echo 0); '
            'echo $((n+1)) > "$STUB_LOG.n"; [ "$n" -ge 2 ] && : > "$STUB_LOG.up"; }; '
            '[ -e "$STUB_LOG.up" ] && echo gobid; } ;;\n  *"NEVERMATCH"*)',
```
Keep the `\\\n` line above it and the closing `)` lines unchanged. Do not touch the assertions.

2. Add a comment line directly above `DOCKER_STUB.replace(` is NOT needed; do not add comments.

## 5. Do not touch

`deploy/lightsail/scripts/backup.sh`, `lib-docker.sh`, `DOCKER_STUB`, any other test, `go/`, `docs/` (except the report).

## 6. Commands

- Flake check (from `App/`, expect exactly `20 1 passed`):
  `for i in $(seq 20); do .venv/bin/python -m pytest tests/test_pg_backup_scripts.py -q --tb=line -k transient_gap 2>&1 | grep -E 'passed|failed' | sed 's/ in .*//'; done | sort | uniq -c`
  (a `failed` line, or a count under 20, means the fix is not done)
- File run (from `App/`): `.venv/bin/python -m pytest tests/test_pg_backup_scripts.py -q --tb=short -x 2>&1 | tail -30` (expect all passed, 0 failed)
- From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` (expect no errors)

A prototype of this exact patch passed 20 of 20 runs; the unpatched test failed 4 of 12.

## 7. Acceptance

- [ ] `grep -nF 'STUB_LOG.up' App/tests/test_pg_backup_scripts.py | tail -30` shows 3 matches in one stub string.
- [ ] The flake loop prints `20 1 passed`.
- [ ] The file run passes; context lint passes.
- [ ] `git diff --stat` shows only the test file (plus the report).

## 8. Stop and ask

Any anchor not found verbatim; the flake loop shows any `failed`; the fix needs an edit outside the test file. Do not guess. If it still fails, do not change `backup.sh`: report the stderr of one failing run instead.

## 9. Report

Write `docs/tasks/2047-report.md` (400 tokens at most): file changed, each §6 command with its last 5 lines, §7 ticked, Deviations, Questions. Set `Status: review`, open one draft PR, do not merge. Owner steps: merge with `scripts/merge-pr-on-green.sh` when ready; no secrets or servers involved. Add one line to `docs/context/known-issues.md` only if the owner asks.
