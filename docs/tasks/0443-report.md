# 0443 report: PR 583 CI (executor)

Status: blocked
Branch: vibe/guest-direct-progression-fe276e at eb41c086 (PR 583 head, verified)

## 1. Files changed

None. `git diff --stat` is empty. `docs/tasks/0443-pr583-ci-fix.md` is untracked (created on the wrong branch by the orchestrator; not committed).

## 2. Commands

- `cd App && .venv/bin/python -m pytest tests/test_claim_copy.py tests/test_demo_stay_exclusion.py -q --tb=short` → `21 passed in 1.02s`. Both originally failing tests pass on eb41c086.
- `gh run view 41153269204 --log-failed` on current head eb41c086:
  - `test`: pass. `browser shard 1, 2, 3`: pass.
  - `browser shard 4`: `1 failed, 142 passed`.
    `tests/test_dashboard_calendar_browser.py:635`: `assert result.value.status == 201`, got 409.
    The 409 comes from `App/app/routes/admin.py:3207-3211`, the overlap check. The test sets arrival to today and departure to today+2, which overlaps an existing fixture stay. The overlap checkbox (`allow_overlap`) is only ticked when visible (line 629), so it is not ticked.
  - `browser` (aggregator): fails only because shard 4 failed.

## 3. §7 acceptance

- [x] test_claim_copy passes locally.
- [x] test_demo_stay_exclusion passes locally.
- [ ] Cleaning-list browser test: not re-run locally; shard 3 passed on eb41c086.
- [ ] Test-map rows: not run; CI `test` passed on eb41c086.
- [ ] context_lint: not run.
- [x] No assertion weakened, no file changed.

## 4. Deviations and blocker

The old failures (f4fae9de) are already fixed on eb41c086. The current failure is new: `browser shard 4`, `tests/test_dashboard_calendar_browser.py`, a date-dependent overlap 409. The fix would be in that test file (set `allow_overlap` or move the dates). That file is not in brief §3, so I stopped per §8.

**Owner decision needed:** approve adding `App/tests/test_dashboard_calendar_browser.py` to §3 and I will fix it, or rerun the failed job (`gh run rerun 41153269204 --failed`) in case it is flaky.
