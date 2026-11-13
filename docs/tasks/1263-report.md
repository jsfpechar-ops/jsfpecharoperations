# 1263 report: Go schema fix 2

Status: review

## Files changed (`git diff --stat 4de1f158c..HEAD`)

- App/tests/test_go_schema_migrate.py (+88): new fingerprint test and `KNOWN_NOT_DEFERRABLE`
- deploy/lightsail/scripts/deploy.sh (+15 -6): go-mode build skipped when `GO_IMAGE_PULLED=1`
- docs/LIGHTSAIL.md (+4 -2): `go` row and "Writing a goose twin" paragraph
- docs/tasks/1263-report.md (new)

## Commands (last 5 lines)

- Step 1 anchors: `1`, `1`, `1`. `git apply --check` and `git apply` ran clean. Status showed the 3 files as ` M`.
- Step 2 `sha256sum -c`: 3 x OK. Commit `1263 step 1-2` (e597e6017).
- `pytest tests/test_go_schema_migrate.py -q -rs` (no DB URL): `5 skipped in 0.13s`
- `pytest` with `UBYHOST_TEST_DATABASE_URL` on local PostgreSQL 16, port 5545: `.....` / `5 passed in 18.09s`
- `ruff check ... --select E9,F63,F7,F82,F401,F841`: `All checks passed!`
- `bash -n deploy.sh`: `syntax ok`
- `shellcheck -S error`: not installed, CI only
- `python3 scripts/context_lint.py`: `context lint: OK`

## Section 7 acceptance

- [x] Step 1 three `1`s and patch applied; step 2 3 x OK
- [x] §6 as expected (shellcheck: CI only)
- [x] `git diff --stat` lists only §3 files
- [ ] CI `test-postgres-full` and `shellcheck`: pending after push (not pushed)

## Deviations

- Step 0 `git fetch origin main` and `merge-base` not run. The orchestrator's note treats PR #982 as merged, and the branch contains 1fd70c01 (ancestor check passed).
- Branch: stayed on the worktree branch, per orchestrator. No `task/1263-go-schema-fix-2`.
- Commits: `1263 step 1-2`, then this report. No push, no PR.
- Created `App/.venv` (not committed) and installed requirements.txt and requirements-dev.txt.
- Ran the optional PostgreSQL test on port 5545 under /var/tmp/pg1263. Server stopped and data deleted.
- The §2 sha256 checks passed, so main did not change these files after 1fd70c01.

## Questions

None.

## Owner steps left

None from this task. The orchestrator merges PR #982's follow-up via `scripts/merge-pr-on-green.sh` once CI is green.
