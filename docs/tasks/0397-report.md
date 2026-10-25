# 0397 report

Status: blocked

## Files changed

- App/app/routes/admin.py: `_hour_or_none` helper, hour coercion in `_refuse_apartment_save`, `lock_times_error` path, lock-tab detection in `_save_apartment_form`.
- App/app/templates/_property_editor.html: `door-code-times-error` alert, switch keeps posted state, unsaved status.
- App/tests/test_door_code_missing_times_0397.py: new, 4 tests.

## Steps

- Step 1 (`0397 step 1`, a18ee7d): done.
- Step 2 (`0397 step 2`, 56560bd): done.
- Step 3 (`0397 step 3`, 8a3d244): done. Jinja parse OK.
- Step 4 (`0397 step 4`, f806fb2): done.

## Test results

Command 1 (non-browser, 0 skipped):

```
........................................................                 [100%]
56 passed in 3.58s
```

Command 2 (browser, required 0 skipped):

```
SKIPPED [2] tests/test_property_navigation_browser.py:22: could not import 'playwright.sync_api': No module named 'playwright'
2 skipped in 0.18s
```

Command 3 (context lint): ERROR on this brief's own `Status: ready` line (not an allowed value). Also many pre-existing WARN lines about shared files, and a WARN that App/ changed after the last status.md update.

## §7 acceptance

- [ ] All §6 commands pass, 0 skipped: NOT MET. Browser command skipped 2 (playwright not installed in App/.venv). Not installed: it is not in any requirements file and would be a new dependency (rule 4).
- [x] One commit per step: met.

## Deviations

- Done: steps 1 to 4. Left: browser test command (§6 command 2) and lint status fix.
- Commit trailer uses `Co-Authored-By: Claude Opus 5.5 (1M context)`, as the owner's message asked. The session attribution reminder names Haiku 5.5; the owner's instruction was followed.
- Screenshots not taken (brief §8: reviewer takes them).
- No push, no PR.

## Questions

- Should playwright be installed into App/.venv (needs an owner decision line in decisions.md), or should the browser command run on a machine that already has it?
- Should the brief's `Status: ready` be changed to an allowed value so lint passes?

## Owner steps left

1. Decide on playwright (above), then run: `cd App && UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome .venv/bin/python -m pytest tests/test_property_navigation_browser.py tests/test_door_code_window_browser.py -q -rs --tb=short 2>&1 | tail -30`
2. Reviewer: one 390 px screenshot of the Door lock tab with the refused save.
