# 0372: Property page test: check that the app leaves a ctrl-click alone, not that Chromium opens a tab

Status: review
Depends on: 0371 | Base commit: dd868ed | Branch: task/0371-dashboard-phone-dismiss-wait (same PR as 0371)
Executor: Haiku 5.5 | Fits one session: 12 tool calls, 30k tokens

## 1. Objective

`App/tests/test_property_navigation_browser.py::test_tabs_hashes_drafts_history_and_validation_in_browser` failed in CI browser shard 2 on PR #475: `page.context.expect_page()` timed out after 30 s on the ctrl-click at line 467. The app did nothing wrong. Assert the app's real contract (it does not take over a modified click) at event level, instead of waiting for a Chromium tab.

## 2. Context

Investigation (orchestrator, 2026-10-25), with a loop of `goto` then ctrl-click on the Settings tab:

- About 1 in 4 ctrl-clicks made right after `page.goto` open no tab at all (`context.pages` stays at 1). The page stays on Overview, same document.
- In those misses the click event reaches the link with `ctrlKey: true` and `defaultPrevented: false` after every app listener. No app script took it over.
- Blocking each app script in turn (app.js, host.js, pwa.js, shell.js, skeleton.js, all CSS) still gave misses. `Control+Enter` on the focused link and `keyboard.down("Control")` also missed. Waiting 1 s after load gave 0 misses in 30 (a sleep, so not a fix).

So the new tab is Chromium's own timing. What the app owns is: a modified click is not `preventDefault`ed and does not switch the view in place. `app.js` (the property tabs handler and the unsaved-changes guard) both return early on `event.metaKey || event.ctrlKey || event.shiftKey || event.altKey`. If either lost that check, the click would be `defaultPrevented` and the view would switch to Settings, which the new assertions catch.

A listener on `window` in the bubble phase runs after every `document` listener, so it sees the final `defaultPrevented`.

Current code, `App/tests/test_property_navigation_browser.py` lines 464-470 (must match verbatim, else STOP):

```python
        # A ctrl-click is left to the browser.
        page.goto(f"{url}?lang=en")
        page.evaluate("() => { window.__navMarker = 'm2'; }")
        with page.context.expect_page() as popup:
            page.locator('.property-tabs a[data-property-tab="settings"]').click(modifiers=["Control"])
        popup.value.close()
        assert page.evaluate(_STATE_JS)["visibleViews"] == ["overview"]
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/test_property_navigation_browser.py` | edit | Replace lines 464-470 as in §4 |
| `docs/tasks/0372-property-ctrl-click-check.md` | edit | `Status: review` |
| `docs/tasks/0372-report.md` | create | Report (§9) |

No other file may change.

## 4. Steps

1. Replace the block in §2 with:

```python
        # A ctrl-click is left to the browser (0372): no app listener takes it
        # over and the page does not switch view. Whether Chromium then opens a
        # tab is its own timing (it can drop one right after load), so any tab
        # it opens is closed, not awaited.
        page.goto(f"{url}?lang=en")
        page.evaluate("""() => {
          window.__navMarker = 'm2';
          window.__modClicks = [];
          window.addEventListener('click', e => window.__modClicks.push([e.ctrlKey, e.defaultPrevented]));
        }""")
        page.context.on("page", lambda popup: popup.close())
        page.locator('.property-tabs a[data-property-tab="settings"]').click(modifiers=["Control"])
        assert page.evaluate("() => window.__modClicks") == [[True, False]]
        state = page.evaluate(_STATE_JS)
        assert state["visibleViews"] == ["overview"], state
        assert state["marker"] == "m2", "the ctrl-click navigated this tab"
```

2. Check that the new assertions would catch a regression: temporarily change the line `if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;` in the property tabs click handler of `App/app/static/app.js` (the one followed by `var link = ...closest("a[href]")` and `url.pathname !== base`) to `if (false) return;`, run §6 once, confirm it FAILS on one of the new asserts, then `git checkout App/app/static/app.js`. Write the failing assert line in the report.

3. Run §6 three times in a row; all three must pass with 0 skipped.

## 5. Do not touch

`App/app/` (only the temporary change in step 2, reverted), every other test. Do not loosen or remove any other assertion. No `wait_for_timeout` in the new code.

## 6. Commands

From `App/`:

```
UBYHOST_REQUIRE_BROWSER=1 python -m pytest tests/test_property_navigation_browser.py -q --tb=short -x -rs 2>&1 | tail -30
```

Expected: all passed, no `skipped`.

```
git diff --stat -- App/app
```

Expected: no output.

## 7. Acceptance

- [ ] Step 2 failed on a new assert with the guard removed, and `App/app` is clean again.
- [ ] §6 passes 3 times in a row, 0 skipped.
- [ ] `git diff --stat` shows only the files in §3.

## 8. Stop and ask

Stop, and write the report, if: the excerpt is not found; step 2 does not fail; a test fails twice; you reach 12 tool calls; a file outside §3 needs a change.

## 9. Report

Write `docs/tasks/0372-report.md` (300 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, §7 ticked, deviations. Do not commit or push; the orchestrator does that.

## Risk list (for the reviewer)

`App/tests/test_property_navigation_browser.py`.

## Owner steps

None.
