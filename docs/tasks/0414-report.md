# 0414 report: Check-in/out times on the Door lock tab

Status: review

## Files changed

- App/app/routes/admin.py: `_with_lock_tab_hours` helper (folds `lock_checkin_hour` / `lock_checkout_hour` into the saved hours), `FormData` import, one call at the top of `_save_apartment_form`.
- App/app/templates/_property_editor.html: two time selects inside `#door-code` (`required` while the switch is on), text line and amber warning removed, duplicate `switch_on` set removed, `data-hour-twin` on the Property tab selects.
- App/app/static/host.js: sync between twin selects, `required` follows the switch live.
- App/app/templates/base.html: `host.js?v=20261026-door-lock-times`.
- App/tests/test_door_lock_tab_times_0414.py: new, 5 tests.
- docs/tasks/0414-door-lock-tab-times.md: Status set to in-progress, then review.

## Commits

`0414 step 1` (63a0dba0, includes the Status line), `0414 step 2` (1a1fe134), `0414 step 3` (d20225fe), `0414 step 4` (f6d2a523), then this report.

## Commands

Brief §6 command 1 (`pytest ... -q --tb=short`), last lines:

```
........................................................................ [ 46%]
........................................................................ [ 92%]
...........                                                              [100%]
155 passed in 4.20s
```

Brief §6 command 2 (`python3 scripts/context_lint.py`), last lines:

```
WARN  5 commit(s) touched App/ after the last status.md update. Orchestrator: update docs/context/status.md at review.
next free: task 0415 | migration 0023
context lint: OK
```

Also run: Jinja parse of `_property_editor.html` (ok), `node --check App/app/static/host.js` (no output, no error).

## Section 7 acceptance

- [x] Command 1 passes (155 passed, includes the 0397 and 0400 files, no edits to them).
- [x] Lint OK.
- [x] One commit per step.
- [ ] Browser tests and 390 px screenshots: not run here. Playwright is not installed in this container and the brief says not to install it. CI and the reviewer cover them. The Door lock tab's layout changed, so the reviewer needs a 390 px screenshot of the Door lock tab.

## Deviations

- Step 1 and step 2 were applied with the anchors exactly as given (each anchor occurred once). Step 1's two edits were made in one edit call, same result.
- The Status line change to `in-progress` was committed with step 1, not as a separate commit.
- No PR opened and nothing pushed, per the owner's instruction for this run.
- `test_door_code_missing_times_0397.py` needed no change; all its assertions still pass.

## Questions

None.

## Owner steps left

1. Review and open the PR from `claude/project-thread-qi1fv7` when ready (not done here).
2. Check the Door lock tab at 390 px on a property without times.
3. After merge, deploy as usual (manual).
