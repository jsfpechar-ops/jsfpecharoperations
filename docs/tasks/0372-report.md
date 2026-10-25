# 0372 report

Status: review

## Files changed

- `App/tests/test_property_navigation_browser.py`: ctrl-click block (old lines 465-471) replaced as in brief §4. Asserts that the window click has `ctrlKey` true and `defaultPrevented` false, that the view stays on overview, and that the marker survives. Any popup is closed, not awaited.
- `docs/tasks/0372-property-ctrl-click-check.md`: `Status: review`.
- `docs/tasks/0372-report.md`: this report.

`git diff --stat -- App/app` is empty.

## Commands

Step 2 (guard removed, `if (false) return;` at the property tabs handler in `App/app/static/app.js`, then reverted with `git checkout`):

    UBYHOST_REQUIRE_BROWSER=1 python -m pytest tests/test_property_navigation_browser.py -k test_tabs_hashes_drafts_history_and_validation_in_browser -q --tb=short -x -rs
    tests/test_property_navigation_browser.py:477: in test_tabs_hashes_drafts_history_and_validation_in_browser
        assert page.evaluate("() => window.__modClicks") == [[True, False]]
    E   assert [[True, True]] == [[True, False]]
    1 failed, 11 deselected in 4.33s

Step 3 (§6, three runs):

    run 1: 12 passed in 13.22s
    run 2: 12 passed in 12.54s
    run 3: 12 passed in 13.21s

No skipped tests in any run.

## Section 7

- [x] Step 2 failed on a new assert with the guard removed; `App/app` is clean.
- [x] §6 passed 3 times in a row, 0 skipped.
- [x] `git diff --stat` shows only the §3 files.

## Deviations

- Step 2 ran only the `-k` test named in the failing assert, not the whole §6 file (the failure is in that test).
- Not committed or pushed, as the caller asked. Brief and executor.md both mention a `NNNN step k` commit; this was overridden.
- The `if (event.metaKey ...) return;` guard appears twice in `app.js` (property tabs handler and the unsaved-changes guard). The edit used the tabs handler (followed by `link.target`, `url.pathname !== base`), as the brief describes.

## Questions

None.

## Owner steps

None.
