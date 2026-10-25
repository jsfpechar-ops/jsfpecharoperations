# 0370: Tablet menu test: the screenshot must not close the menu

Status: review
Depends on: none | Base commit: 911bfb9 | Branch: task/0370-tablet-menu-shot
Executor: Haiku 5.5 | Fits one session: 12 tool calls, 30k tokens

## 1. Objective

`App/tests/test_0251_tablet_browser.py` fails on CI at line 128 (the menu does not close on the second toggle tap). Root cause, reproduced by the orchestrator: CI sets `UBYHOST_SHOTS_DIR`, so `_shot(page, f"menu-open-{width}")` takes a **full-page** screenshot. A full-page screenshot resizes the viewport for a moment, the tablet media query fires, and `app.js` (`onRailChange`) closes the open menu, which is correct app behaviour. The next tap then opens the menu instead of closing it. Without `UBYHOST_SHOTS_DIR` the test passes. Fix the test: the open-menu shot must be a viewport screenshot.

## 2. Context

Lines 65-68 on main:
```
def _shot(page, name):
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(SHOTS) / f"0251-{name}.png"), full_page=True)
```
Line 125: `                _shot(page, f"menu-open-{width}")`. Line 102 (`overview-…`) stays full page.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/test_0251_tablet_browser.py` | edit | `_shot` gets a `full_page` flag; menu shot uses the viewport |
| `docs/tasks/0370-report.md` | create | Report |

No other file may change.

## 4. Steps

1. Change `def _shot(page, name):` to `def _shot(page, name, full_page=True):` and `full_page=True)` on its screenshot line to `full_page=full_page)`. Change line 125 to
   `                # A full-page shot resizes the viewport, which closes the menu (0370).`
   `                _shot(page, f"menu-open-{width}", full_page=False)`
   Commit `0370 step 1`.
2. Write the report. Commit `0370 step 2`.

## 5. Do not touch

Any assertion, any other line, any file in `App/app/`.

## 6. Commands

From `App/` (use `/home/claude/wt-0368-browser-test-portability/App/.venv` if `App/.venv` is missing):
`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 UBYHOST_SHOTS_DIR=/tmp/0370-shots <venv>/bin/python -m pytest tests/test_0251_tablet_browser.py -q --tb=line 2>&1 | tail -5`
Run it once on the base commit first (it must fail), then after step 1 (it must pass). Then `ls /tmp/0370-shots | tail -8`.

## 7. Acceptance

- [ ] §6 fails before step 1 and passes after, with `UBYHOST_SHOTS_DIR` set.
- [ ] `0251-menu-open-1180.png` and `0251-menu-open-1024.png` exist in `/tmp/0370-shots`.
- [ ] No assertion changed.

## 8. Stop and ask

If §6 still fails after step 1, stop and write the error in the report.

## 9. Report

`docs/tasks/0370-report.md`: status, what changed, §6 tails (before and after), the `ls` output, acceptance ticks.
