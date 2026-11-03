# 0785 report (executor, blocked)

Status: blocked

## Commits
None. No fix commits made. Step 1 (baseline run) done; steps 2 to 3 not started.

## Baseline run
Command: browser files from brief §1 plus the coordinator rows (G to K) files, `-q -rs --tb=line`.
Result: 61 failed, 219 passed, 0 skipped (run took 1111 s). Per-file counts not captured
(the grep filter hid the FAILED lines). Re-run per file to get counts.

Main failure families seen in the tail:
- A: style diffs on stay/stays/overview/property (`1 style differences`, `3 style differences`), and `property ... 1 findings`.
- B/H/K: `Locator.click` timeouts and `getComputedStyle ... not of type Element` (old-shell tests on /settings or /entities).
- C: flat `.ui-section` panels (`settings-account`, `settings-security`, `settings-phone`, border 0).
- D: `no list panel` on businesses; `en/1024: horizontal overflow [763, 730]`.
- E: `8 layout findings {'cell-not-under-header': 6, 'tap-target-small': 2}`.
- F: `synthetic persistent date-change alert not rendered on operators/en/1024`; `(273 + 378) <= (256 + 313.78)` backlink alignment.
- I: `/entities?edit=4&next=/apartments` sub-tab link expectation.
- J and G: not yet isolated in this output.

## Deviations
Done: step 1 only. Left: steps 2 to 3 (groups A to K, cache-key bump, `test_static_versions.py --write`).
Stopped at the executor tool-call cap (about 14 calls used of 25). Owner or orchestrator should re-brief the remaining work, split by group.

## Questions
- Rows G to K came from the coordinator mid-task. Confirm they are in scope for 0785 (I treated them as in scope).
- The brief's 40-call budget conflicts with executor.md's 25-call cap. Which applies?

## Owner steps left
None until the fixes land.
