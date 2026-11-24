# 2040 report: executor stopped at step 1

Status: blocked
Executor: Haiku 5.5 (single chat, stopped under brief section 8)

## Totals

- identical: 0, invisible: 0, visible: 0, error: 0
- Groups run: none (A, B, C, D not run)
- Missing: all groups. Re-run after the blocker below is fixed.

## Files changed

- `scripts/e2e/parity_env.sh` (new, from brief step 1, made executable)
- `docs/tasks/2040-report.md` (this file)

Steps 3 to 8 were not run.

## Commands

1. `source scripts/e2e/parity_env.sh` (with `pg_isready`, venv import check)
   - Last lines:
     ```
     ERROR: Hashes are required in --require-hashes mode, but they are missing from some requirements.
         playwright==1.63.0 --hash=sha256:ad21bc07516b187965a7521c5cf0df0bd657b17482eaad74335272d35a2b07de
     /bin/bash: line 27: /pg_isready: No such file or directory
     ModuleNotFoundError: No module named 'playwright'
     ```
   - Postgres did start on 127.0.0.1:5433 (`accepting connections`, checked with the full path to `pg_isready`).
   - The venv `App/.venv` was created but the pip install failed, so the venv is incomplete.

## Blocker

`App/requirements.lock` runs under `--require-hashes`. The brief's step 1 installs `playwright==1.63.0` with no hash on the command line, and pip refuses it. Brief section 8 says to stop here. The fix needs an owner decision: add the hash to the lock file, or give the playwright hash/version to pin. The executor does not guess.

## Deviations and notes

- The brief's step 1 run command pipes `source` into `tail -5`, which runs the script in a subshell. The variables (`$PGBIN` and the rest) were then empty in the calling shell. Run `source` without a pipe, or use `. scripts/e2e/parity_env.sh; ... | tail -n`.
- Because `App/.venv` exists now, the script's `[ ! -x App/.venv/bin/python ]` check will skip the install on the next run. Delete `App/.venv` before re-running after the fix.

## Questions for the owner

1. How should `playwright==1.63.0` be pinned under `--require-hashes` (add its hash to `App/requirements.lock`, or allow an unpinned install in the parity script)?

## Owner steps left

- Decide the question above, then ask for a re-run of brief 2040 from step 1 with `rm -rf App/.venv` first.
