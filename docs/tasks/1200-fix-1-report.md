# 1200-fix-1 report

Status: review

## Files changed (`git diff --stat a4aa068`)

- `App/app/scheduler.py` (step 1): `start()` warns on non-PostgreSQL and schedules `deadlines` only on PostgreSQL.
- `App/tests/test_job_queue.py` (step 2): SQLite registration test expects all kinds but `deadlines` and checks the warning; PostgreSQL test checks `deadlines` is scheduled.
- `docs/DEPLOYMENT.md` (step 3): one sentence on Render staging having no deadline watch since 1200.
- `docs/tasks/1200-fix-1.md`: not changed by this run. It shows in the stat because commit 32b5786 added it after the base commit.

Commits: `ee6e60b` step 1, `5cb21f0` step 2, `9dfe4d3` step 3, plus this report commit.

## Commands (last 5 lines each)

Hash check (`sha256sum`): all three match §4 step 4.
```
bd829fdebf57f90ef927e9de608f0e21ff242b802a8ce0eee970a8aabc9677ff  App/app/scheduler.py
21707b13efe06c5c66d8fda2ac0194429ce738f65379ce464902257101032a26  App/tests/test_job_queue.py
83dd5c4f990ca6bc268abc88a94f281a23e69670a90e35435012f2901ca7cb5b  docs/DEPLOYMENT.md
```

§6 SQLite test set (`pytest -q --tb=short -x -rs`): expected `773 passed, 18 skipped`, got `773 passed, 18 skipped`. The 18 skips are 1 playwright (`test_police_letter_flow.py`) and 17 PostgreSQL-only `test_job_queue.py` tests.

§6 ruff (`--select E9,F63,F7,F82,F401,F841`): `All checks passed!`

§6 `python3 scripts/context_lint.py`: `context lint: OK`, with the expected status.md WARN and two pre-existing brief-collision WARNs (test_0705, test_signed_in_chrome).

PostgreSQL dry run: not run (no `UBYHOST_DATABASE_URL` in this session).

## §7 acceptance

- [x] `git diff --stat a4aa068` lists the §3 files (the brief file is the earlier commit noted above)
- [x] step 4 hashes match
- [x] §6 tests pass, ruff clean, lint OK

## Deviations

- Patch files were written to the session scratchpad instead of `/tmp/p1200f*.diff`, per environment rules. Contents and `git apply --check` were unaffected.
- Commit trailer: the brief and your message specify `Co-Authored-By: Claude Opus 5.5`. I used that line as written. The session attribution reminder names Haiku 5.5. Owner may want to pick one.
- Commit subjects follow the brief (`1200-fix-1 step K`), not the executor.md `NNNN step k` form.

## Questions

None.

## Owner steps left

- Push the branch (not done by the executor). PR #964 already covers the branch; no new PR.
- Optional: run the PostgreSQL dry run from §6 with a test database.
