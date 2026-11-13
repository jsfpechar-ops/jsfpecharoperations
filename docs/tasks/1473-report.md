# 1473 report: pg-schema-dump script and proofs checklist

Status: review
Mode: one big PR (orchestrator). Not pushed, no PR opened; the orchestrator collects the commits.
Branch: worktree-agent-a39b72a6a8b7e5e58 (no task/1473 branch created).

## Files changed (git diff --stat 26d9030ea..HEAD)

- App/tests/test_pg_schema_dump_script.py (122 insertions, new)
- deploy/lightsail/scripts/pg-schema-dump.sh (83 insertions, new, mode 755)
- docs/OPERATIONS.md (47 insertions)
- docs/tasks/1473-pg-schema-dump-and-proofs.md (Status line only)
- docs/tasks/1473-report.md (new)

## Commands (last lines)

- `git apply --check` / `git apply` schema-dump.patch: applied clean; status showed ` M docs/OPERATIONS.md`, two `??` files.
- sha256sum -c (3 files): `deploy/lightsail/scripts/pg-schema-dump.sh: OK`, `App/tests/test_pg_schema_dump_script.py: OK`, `docs/OPERATIONS.md: OK`. `stat -c %a`: 755.
- pytest (4 files): `99 passed in 6.39s`
- ruff check: `All checks passed!`
- bash -n: `syntax ok`
- shellcheck: not installed locally (CI only)
- context_lint.py: `context lint: FAIL`. Five ERRORs, all in docs/tasks/1447-go-guide-editor-photo-upload.md (missing sections 4-7, 9). That file is not touched by this task and the errors are on the base commit; not fixed here.

## Acceptance (brief §7)

- [x] Step 0 plan present on the branch (`plan-on-branch`); step 1 applied as expected; step 2 3 x OK and 755.
- [x] §6 pytest and ruff and bash -n as expected. context_lint not OK (see above).
- [x] Diff lists only §3 files.
- [ ] CI shellcheck and test: not run (no push).

## Deviations

- Done: steps 1 to 4. Step 0 (fetch origin/main, switch to task branch) replaced by the one-big-PR override: stayed on the current branch, checked the plan file on HEAD.
- Steps 1 and 2 were committed as one commit `1473 step 1` (edf402938) after verification.
- Created App/.venv (not committed; ignored) with requirements.txt and requirements-dev.txt.
- Brief's step 2 (verify) and step 3 (tests) run; no PostgreSQL started, script not run against any database.

## Questions

- context_lint FAIL on base: the 1447 brief is missing sections. Orchestrator to fix or confirm it is out of scope.

## Owner steps left

- After merge and deploy: OPERATIONS.md "Production schema dump (plan S4)" steps 1-3, and "Proofs before the SQLite rollback path ends" parts A, B, C (see brief "Owner steps").
