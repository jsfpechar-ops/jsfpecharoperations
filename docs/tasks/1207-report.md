# 1207 report: requirements.lock refresh and drift test

Status: blocked

Branch: exec-1207 (local only, not pushed, no PR). Base: claude/bold-goodall-m62grb (contains 966).

## Files changed

- `App/requirements.lock` (regenerated, commit `f3a3579e`, "1207 step 5"): header unchanged, pillow/pyasn1/certifi unchanged.
- `App/tests/test_requirements_lock_sync.py` (new, commit `fc50f59a`, "1207 step 7").
- `docs/context/test-map.md` (one row after "Database, migrations", commit "1207 step 8").
- `docs/tasks/1207-report.md` (this file).

## Lock pin changes (from -> to)

Top-level: anthropic 2.3.0 -> 2.6.0; boto3 1.43.108 -> 1.43.126; cryptography 50.0.1 -> 50.0.2; fastapi 0.142.2 -> 0.162.2; psycopg[binary] 3.3.6 -> 3.3.8 (spelling changed from `psycopg==`); reportlab 5.0.1 -> 5.1.0; python-multipart 0.0.32 -> 0.0.33; starlette 1.7.0 -> 1.10.0; stripe 16.0.1 -> 16.1.0.
Transitive: botocore 1.43.118 -> 1.43.127; psycopg-binary 3.3.6 -> 3.3.8.
No other package changed, added or removed.

## Commands (last lines)

- `uv pip install --require-hashes -r App/requirements.lock` and dev requirements: installed; `uv pip check`: "All installed packages are compatible" (81 packages). pip not present in venv, so `uv pip check` used.
- `python -c "import app.main"`: no output (no traceback).
- `pytest tests/test_requirements_lock_sync.py`: 1 passed. Skew test (fastapi 0.162.1 in requirements.txt): 1 failed, names fastapi. Restored with git checkout: 1 passed.
- payments (6 files): 127 passed, 1 skipped (skip reason not inspected).
- db (5 files, `-rs`): 21 passed, 55 skipped; all skips are `test_db_postgres.py` (no UBYHOST_DATABASE_URL).
- login/passkeys (7 files): 148 passed.
- invoices (4 files): 36 passed, 2 warnings.
- ai (4 files): 23 passed.
- mail (4 files): 32 passed, 3 warnings.
- forms/booking (4 files): 80 passed.
- `python3 scripts/context_lint.py`: FAIL: `ERROR docs/context/test-map.md: ~1216 tokens > cap 1200`. Test-map was at or near the cap before my row (about 12 tokens added). Not fixed here (out of brief scope).

## Checklist (section 7)

- [x] pillow 13.0.0, pyasn1 0.6.5, certifi 2026.10.18 unchanged
- [x] lock header unchanged
- [x] drift test passes; fails on skew
- [x] diff limited to the section 2 packages
- [x] fresh --require-hashes install, uv pip check clean, import clean
- [x] §6 pytest batches pass (only test_db_postgres.py skips)
- [ ] pip-audit: not run (tool-call budget reached)
- [ ] context_lint clean: FAIL (see above)

## Deviations

- Done: steps 1 to 9 except pip-audit. Left: step 9 (pip-audit), and the context lint fix.
- `pip-audit` not run; budget ended.
- Used the 1205 pip-tools venv (`$S/1205/pt`) for pip-compile instead of creating `$S/pt`.
- Commit for steps 5 and 7 stage the lock and test file respectively; the git commit for the report is separate.
- Payments batch: 1 skip not identified.

## Questions

- Test-map is over the 1200-token cap. Owner or orchestrator to compact an existing row in test-map (or split the file).
- Should Dependabot's pip group for `/App` be paused, or the lock regeneration scripted? (Owner decision; not done here.)

## Owner steps left

1. Orchestrator: fix test-map token cap, then run `python3 scripts/context_lint.py`.
2. Run pip-audit: `uv venv --python 3.13 <scratch>/audit && uv pip install --python <scratch>/audit/bin/python pip-audit==2.9.0 && cd App && <scratch>/audit/bin/pip-audit --require-hashes -r requirements.lock --strict`.
3. Open the draft PR from `exec-1207` (title `Refresh requirements.lock to match requirements.txt, add drift test`). Wait for CI `test` and `test-postgres` green before marking ready.
