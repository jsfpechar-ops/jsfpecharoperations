# 2040 report: executor stopped at step 1 (venv install blocked)

Status: blocked
Executor: Haiku 5.5 (single chat, stopped under brief section 8)

## Totals

- identical: 0, invisible: 0, visible: 0, error: 0
- Groups run: none (A, B, C, D not run)
- Missing: all groups. Re-run from step 1 after the blocker below is fixed.

## Files changed

- `scripts/e2e/parity_env.sh` (step 0 edit: install block replaced, commit `2040 step 0`)
- `docs/tasks/2040-report.md` (this file)

Steps 1 (run part only), 2 to 8 were not completed. Step 1 file creation was skipped because the file already existed (step 0).

## Commands

1. `rm -rf App/.venv` (brief step 0)
   - Denied by the permission classifier. Not retried, no workaround. The venv from the first attempt was left in place.
2. `source scripts/e2e/parity_env.sh` (step 1 Run command)
   - Postgres: `127.0.0.1:5433 - accepting connections` (OK).
   - Venv install: FAILED. Last lines:
     ```
     ERROR: Hashes are required in --require-hashes mode, but they are missing from some requirements. ...
         pytest==9.2.0 --hash=sha256:07acdcf88ec174f907dc01af70bf52d49b014bbab03faeeade31c96b18c2e588
     [notice] A new release of pip is available: 26.2.2 -> 26.3
     [notice] To update, run: /home/user/jsfpecharoperations/App/.venv/bin/python3 -m pip install --upgrade pip
     ```
   - Import check: `ModuleNotFoundError: No module named 'uvicorn'`.

## Blocker

The step 0 corrected block runs `pip install -r App/requirements.lock -r App/requirements-dev.txt`. `App/requirements.lock` enables `--require-hashes`, and `App/requirements-dev.txt` lists `pytest==9.2.0` without a hash, so pip refuses the install. The brief does not allow editing requirements files, so the executor stopped under section 8.

Owner decision needed: add the hash for `pytest==9.2.0` (and any other unhashed entries in `App/requirements-dev.txt`) to the dev requirements, or split the dev install out of the `--require-hashes` call in `scripts/e2e/parity_env.sh`.

## Deviations and notes

- Brief step 0 asked for `rm -rf App/.venv`; the permission classifier denied it. The step 0 edit does not depend on the deletion, so it was committed without it. The old venv (incomplete, no uvicorn) remains. Delete it manually before the re-run: `rm -rf App/.venv`.
- Brief step 1 had `source` piped into `tail` in an earlier attempt; the run here was not piped (output redirected to `/var/tmp/parity_env.log`).

## Questions for the owner

1. How should the unhashed `pytest==9.2.0` in `App/requirements-dev.txt` be handled under `--require-hashes`: add hashes, or install the dev requirements outside the hashed call?
2. May `App/.venv` be deleted (the denied step 0 command) before the re-run?

## Owner steps left

- Decide question 1 and question 2 above.
- Re-run brief 2040 from step 1 (`source scripts/e2e/parity_env.sh`), then steps 2 to 8.
