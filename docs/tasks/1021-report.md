# 1021 report: Litestream retired (BLOCKED at acceptance)

Status: review; decisions.md cap fixed by orchestrator, see git log

## 1. Files changed (`git diff --stat HEAD`)

22 files, 31 insertions, 629 deletions. Five files deleted: `deploy/lightsail/litestream.yml`, `deploy/lightsail/scripts/litestream_env.sh`, `deploy/lightsail/scripts/restore_test.sh`, `.github/workflows/restore-drill.yml`, `App/tests/test_litestream_env.py`. Plus this report and the brief status line.

## 2. Commands (last lines)

- Steps 2 to 22: one script with anchor checks, all anchors matched. `OK wrote 17 files`. Step 18a anchor found verbatim.
- `bash -n` on deploy.sh, preflight.sh, restore.sh: no output.
- shellcheck: not installed. Only the three edited scripts got `bash -n`.
- YAML parse of docker-compose.yml and both workflows: `YAML OK`.
- `grep -ci litestream` on the section 7 files: 0 for compose, .env.example, all `deploy/lightsail/scripts/*.sh`, both workflows, test_wp32, ENVIRONMENT, OBSERVABILITY, architecture, runbook, README.md. deploy/lightsail/README.md 2, docs/LIGHTSAIL.md 1, docs/OPERATIONS.md 1 (all expected).
- Step 17a check (`Once Litestream replicates`): no output.
- Step 23 final grep: only historical files plus README, LIGHTSAIL, OPERATIONS and decisions.
- `pytest test_wp32_container_sizing.py test_pg_backup_scripts.py`: `29 passed in 0.44s`, no skips.
- `python3 scripts/context_lint.py`: `ERROR docs/context/decisions.md: ~2251 tokens > cap 2200` then `context lint: FAIL`.

## 3. Section 7

Ticked: litestream greps, deleted files, bash -n, YAML, the two pytest files (0 skipped), decision line is last. Not ticked: context lint. No template, CSS or guest-page change, so no screenshots.

## 4. Deviations

- Step 20 (runbook): the brief's `BACKUP_S3_BUCKET` does not exist. Used `UBYHOST_S3_BUCKET`, the name in `backup-s3.sh`.
- `restore.sh` still handles old SQLite snapshots (kept on purpose). `restore_test.sh` and `restore-drill.yml` are deleted, so no scheduled restore drill runs now. A PostgreSQL drill needs its own brief.
- Not run: shellcheck (missing), full suite (not allowed).

## 5. Questions

- The brief's decision line (step 22) pushes `docs/context/decisions.md` over the 2200-token cap. The file passed lint before this change. Compacting it is outside the brief's named edits, so I did not do it. Decide: compact decisions.md, or shorten the appended line.

## 6. Owner steps left

Brief section "Owner steps", items 1 to 11, only after the PR is merged and 1020 is deployed.
