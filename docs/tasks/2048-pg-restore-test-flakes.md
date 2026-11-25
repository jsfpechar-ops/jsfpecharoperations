# 2048: Fix the intermittent pg-restore/backup test failures (SIGPIPE under pipefail, every deploy/server script)

Status: todo
Base commit: current tip of the working branch | Branch: task/2048-pipefail-grep-q
Executor: Haiku 5.5 | Fits one session: 15 tool calls, 40k tokens
Tier: B (about 33 mechanical one-line script edits plus one static test)

> **One PR mode.** Commit as `2048 step 1`. Never push to `main`, never merge (the owner merges with `scripts/merge-pr-on-green.sh`), never deploy.
> Commit trailer lines:
> Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
> Claude-Session: https://claude.ai/code/session_014N5J8NCpdqN2TbR61gYRQf

## 1. Objective

Make `tests/test_pg_backup_scripts.py` pass every run. Today about half of full-file runs fail 1-3 tests (`test_pg_restore_streams_dump_into_pg_restore_go_only`, `..._file_form_with_override_writes_the_marker`, `..._file_form_streams_host_file_without_docker_cp`, and others in the same family such as `test_backup_dumps_postgres_only...`, `test_pg_restore_restarts_the_app_when_stop_fails`). One test alone fails about 1 run in 8.

## 2. Context

Root cause (verified: 12 full-file runs, 9 failed; 40 single-test runs; stub logs of passing and failing runs compared). This is NOT a test-stub race like 2047. It is a real, rare non-determinism in the scripts, and it reaches the disaster-recovery path.

- `deploy/lightsail/scripts/lib-docker.sh` helpers use `docker compose ... config --services 2>/dev/null | grep -qx NAME`. `pg-restore.sh` and `backup.sh` run under `set -euo pipefail`.
- `grep -q` exits at the first matching line. If the producer is still writing, it dies of SIGPIPE (status 141) and, with `pipefail`, the whole pipeline reports failure although the service IS listed. The helper then answers "no".
- The test stub prints the services with several separate `echo` calls (`ubyhost-go`, `postgres`, `caddy`), so it loses the race some of the time. Real `docker compose config --services` also prints one line per `Fprintln`, so production has the same window (smaller, but real; it grows when `ubyhost` is listed before `ubyhost-go` and `worker`).
- Consequences when it hits in `pg-restore.sh`: `compose_has_go_app` false makes `ubyhost_restore_stop_services` return an empty list, so the app is NOT stopped and `pg_restore --clean` runs against a live app (evidence: failing run's stub log has no `stop` line yet the restore ran; assertion `"stop ubyhost-go ubyhost-go-b" in recorded` fails with returncode 0). Other hits give "could not find a running app container" (exit 1, restore aborted) or "no ubyhost-pg.dump.age in snapshot" (exit 1). In `backup.sh`: false "no app container" exits.
- Fix: read the whole pipe so the producer never gets SIGPIPE. Replace `grep -qx NAME` with `grep -x NAME >/dev/null` (same match, same exit status, no early exit). Owner decision: apply this EVERYWHERE it can bite, not only lib-docker.sh and backup.sh. deploy.sh has about 15 instances (false "not found" there can cause a needless rollback or a mid-deploy abort). Single-line producers (`ps -q ... | grep -q .`, `echo "$var" | grep -q`) are also rewritten, for a clean static test.
- Production behaviour change: none on success paths; the helpers stop returning a false "service not found" on a rare timing. A prototype (scratch copy with only the lib-docker.sh and backup.sh edits) passed 20 of 20 full-file runs (`87 passed`); unpatched, 9 of 12 runs failed.

## 3. Files

| Path | Action | What |
|---|---|---|
| every `*.sh` in `deploy/lightsail/scripts/` that contains `pipefail`, plus `deploy/lightsail/scripts/lib-docker.sh` (sourced, has no `pipefail` line itself) and `scripts/rollback-prod.sh` | edit | rewrite each `\| grep -...q...` pipeline |
| `App/tests/test_pg_go_slot_script.py` | edit | add one static regression test (step 3) |
| `docs/tasks/2048-report.md` | create | the report |

Expected today (29 pipeline lines in 10 pipefail files + 4 in lib-docker.sh): backup-gdrive.sh 1, backup-s3.sh 1, backup.sh 1, deploy.sh 15, finish-bootstrap.sh 2, monitoring-watchdog.sh 4, pg-restore.sh 1, restore.sh 1, smoke-remote.sh 2, rollback-prod.sh 1, lib-docker.sh 4. A different count: stop and ask.

## 4. Steps

1. Discovery (paste the output into the report as "before"):
   `grep -nE '\|[[:space:]]*grep[[:space:]]+-[a-zA-Z]*q' $(grep -l pipefail deploy/lightsail/scripts/*.sh scripts/rollback-prod.sh) deploy/lightsail/scripts/lib-docker.sh | cut -c1-160 | tail -60`
2. Rewrite every hit, by line, never with a global replace: drop the `q` from the grep flags and append `>/dev/null` right after the grep arguments, keep everything else on the line. Examples:
   - `| grep -qx ubyhost-go` -> `| grep -x ubyhost-go >/dev/null`
   - `| grep -q .` -> `| grep . >/dev/null`
   - `| grep -Eq '^[0-9]{8}...$'` -> `| grep -E '^[0-9]{8}...$' >/dev/null`
   - `| grep -qx 'ubyhost-go\(-b\)\?'` -> `| grep -x 'ubyhost-go\(-b\)\?' >/dev/null`
   - `| grep -qx worker && out="worker"` -> `| grep -x worker >/dev/null && out="worker"`
   - a line ending `\` or `; then` keeps its ending after `>/dev/null`.
   - `echo "${result}" | grep -q '"status":"success"'` -> `echo "${result}" | grep '"status":"success"' >/dev/null`.
   - Inside the double-quoted strings passed to `app_data_exec` (deploy.sh ~288, ~294: `head -c 21 ... | grep -q 'age-encryption.org/v1'`): rewrite too, as `grep 'age-encryption.org/v1' >/dev/null`. The inner `sh -c` has no `pipefail`, so this one is for consistency only; say so in the report. Keep the quoting intact (the `>/dev/null` sits inside the string).
   Leave `grep -q` that reads a FILE (no pipe) unchanged.
3. Add the static test to `App/tests/test_pg_go_slot_script.py` (match the file's existing helpers and style): glob `deploy/lightsail/scripts/*.sh` plus `scripts/rollback-prod.sh`, keep files whose text contains `pipefail` plus `lib-docker.sh`, and fail with a list of `file:line` for any line matching `\|\s*grep\s+-[a-zA-Z]*q`. Message: "grep -q exits at the first match, the producer then dies of SIGPIPE (141) and under pipefail the pipeline reports failure although the line matched; use `grep ... >/dev/null`". Run it once to see it pass.
4. Post-change: the discovery command must print nothing (count 0). Write the before list and "after: 0" in the report.

## 5. Do not touch

`App/app/**`, `go/**`, any other test, `DOCKER_STUB`, and `deploy.sh` behaviour other than this grep rewrite (no other line, no reformatting). `docs/` except the report. No comments added to scripts.

## 6. Commands

- Syntax, every changed script: `for f in $(git diff --name-only -- '*.sh'); do bash -n "$f" || echo "FAIL $f"; done; echo done | tail -30` (expect only `done`).
- Shellcheck if installed: `shellcheck -S error deploy/lightsail/scripts/*.sh 2>&1 | tail -30`.
- Flake check (from `App/`, expect exactly `20 87 passed`, or the current passed count if it differs, never a `failed` line):
  `for i in $(seq 20); do .venv/bin/python -m pytest tests/test_pg_backup_scripts.py -q --tb=no -p no:cacheprovider 2>&1 | tail -1 | sed 's/ in .*//'; done | sort | uniq -c`
- Once each (from `App/`): `.venv/bin/python -m pytest tests/test_pg_go_slot_script.py -q --tb=short -x 2>&1 | tail -30`, then the other files of the test-map "Deploy scripts" row, `tests/test_pg_app_role_script.py tests/test_pg_cutover_script.py tests/test_pg_schema_dump_script.py` (row: `test_pg_*script*.py`), one command per file.
- From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` (expect no errors)

## 7. Acceptance

- [ ] The step 1 discovery command prints nothing after the change; the before list is in the report.
- [ ] Flake check prints a single line `20 87 passed`.
- [ ] `bash -n` loop prints only `done`; every §6 test file passes; context lint passes.
- [ ] The new static test fails if one `| grep -q` is put back (check once by hand on a scratch copy, do not commit it).
- [ ] `git diff --stat` shows only scripts, `test_pg_go_slot_script.py` and the report; each script diff is only the grep rewrite.

## 8. Stop and ask

Any anchor not found verbatim or a different hit count than §3; any `failed` in the flake check or a script test; the fix needs an edit outside the listed files. Do not guess and do not edit tests to hide a failure: report the stderr of one failing run.

## 9. Report

Write `docs/tasks/2048-report.md` (400 tokens at most): files changed, before list (compact: counts per file is enough if the list is long, full list in the PR body), each §6 command with its last 5 lines, §7 ticked, Deviations. Set `Status: review`, open one draft PR, do not merge. Owner steps: merge with `scripts/merge-pr-on-green.sh` when ready; no secrets or servers involved.
