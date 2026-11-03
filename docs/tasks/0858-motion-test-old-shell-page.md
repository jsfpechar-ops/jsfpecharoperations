# 0858: Motion no-JS test runs on an old-shell page again

Status: todo
Depends on: 0794 | Branch: claude/project-thread-v4nqi5 (main checkout, do NOT commit; the orchestrator commits)
Executor: Haiku 5.5 | Fits one session: 15 tool calls, 30k tokens

## 1. Objective

CI (PR #707, shard 2) fails `tests/test_motion_browser.py::test_pages_without_javascript_stay_still`: it opens `/stay-fees` as an old-shell page and clicks `.ui-nav a[href="/reservations"]`, but `/stay-fees` is now v2 (no `.ui-nav`). Point it at a page that is still old-shell and has a `details.ui-how` help block: `/payments` (held, stays old-shell; `payments.html` has `how_key`). Update the 0720 comment on line ~137 to say so ("v2, 0794: /stay-fees moved to v2"). Check the other cases in the same file for `/stay-fees` too.

## 2. Context

`tests/test_motion_browser.py` lines ~132-145. `_rail_page(context, wide_base, path)`.

## 3. Files

`App/tests/test_motion_browser.py` only.

## 4. Steps

Reproduce, change the path, rerun.

## 5. Do not touch

Anything outside §3.

## 6. Commands (from `App/`, `2>&1 | tail -30`)

`UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_motion_browser.py -q -rs --tb=short`

## 7. Acceptance

- [ ] The command: 0 failed, 0 skipped.

## 8. Stop and ask

Blocked if `/payments` has no old-shell `.ui-nav` or no `details.ui-how`: report which old-shell pages remain instead of guessing.

## 9. Report

`docs/tasks/0858-report.md`, 100 tokens at most. Do not commit or push.
