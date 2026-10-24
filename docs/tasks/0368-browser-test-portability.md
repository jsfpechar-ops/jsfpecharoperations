# 0368: Browser tests: no machine-specific screenshot paths, no fixed sleeps on the tablet menu

Status: todo
Depends on: none | Base commit: 5439abe | Branch: task/0368-browser-test-portability
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

On the first CI run of the new `browser` job (#451), tests failed only on GitHub runners: four files write screenshots to a hard-coded `/mnt/project-files/...` folder that exists only on the machine that wrote them, and the tablet menu test reads the sidebar width a fixed 100 ms after a tap, before the CSS transition ends on a slower runner. Make them portable without changing what they check.

## 2. Context

The pattern already used by fixed files (0365, 0367): `os.path.join(os.environ.get("UBYHOST_SHOTS_DIR", tempfile.gettempdir()), "<name>")`. CI sets `UBYHOST_SHOTS_DIR` to the uploaded artifact folder.

Exact lines on main:
- `App/tests/test_pwa_browser.py:18` `SHOT_DIR = "/mnt/project-files/pwa/0203/"` and line 48 `page.screenshot(path=f"{SHOT_DIR}{name}.png", full_page=True)`
- `App/tests/test_0201_tabbar_safe_area_browser.py:17` `SHOT_DIR = "/mnt/project-files/design-reset/checkpoint-6/mobile/tabbar/"`
- `App/tests/test_dashboard_rows_browser.py:27` `SHOT_DIR = pathlib.Path(os.environ.get("DASH_ROWS_SHOT_DIR", "/mnt/project-files/design-reset/checkpoint-4-shell-fixes"))`
- `App/tests/test_stay_fee_pay_steps_browser.py:16` `OUT = Path("/mnt/project-files/design-reset/stay-fee-steps/")`, and its module docstring line 3 names that path.
- `App/tests/test_0251_tablet_browser.py`: `def _sidebar_width(page): return page.locator("#app-sidebar").bounding_box()["width"]`; after each `toggle.tap()` comes `page.wait_for_timeout(100)` then an `assert _sidebar_width(page) >= 200, width` or `< 100, width`. CI failed with `assert 240 < 100` at width 1180.
- Local browser env: `export PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 UBYHOST_SHELL_BROWSERS=chromium UBYHOST_SHOTS_DIR=/tmp/0368-shots`, venv `App/.venv`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/test_pwa_browser.py` | edit | SHOT_DIR from env or temp |
| `App/tests/test_0201_tabbar_safe_area_browser.py` | edit | SHOT_DIR from env or temp |
| `App/tests/test_dashboard_rows_browser.py` | edit | default SHOT_DIR from env or temp |
| `App/tests/test_stay_fee_pay_steps_browser.py` | edit | OUT from env or temp, docstring |
| `App/tests/test_0251_tablet_browser.py` | edit | wait for the width instead of a fixed sleep |
| `docs/tasks/0368-report.md` | create | Report |

No other file may change.

## 4. Steps

1. `test_pwa_browser.py`: add `import tempfile`; line 18 becomes `SHOT_DIR = os.path.join(os.environ.get("UBYHOST_SHOTS_DIR", tempfile.gettempdir()), "pwa-0203")`; line 48 becomes `page.screenshot(path=os.path.join(SHOT_DIR, f"{name}.png"), full_page=True)`. Commit `0368 step 1`.
2. `test_0201_tabbar_safe_area_browser.py`: add `import tempfile`; line 17 becomes `SHOT_DIR = os.path.join(os.environ.get("UBYHOST_SHOTS_DIR", tempfile.gettempdir()), "0201-tabbar")`. Commit `0368 step 2`.
3. `test_dashboard_rows_browser.py`: add `import tempfile`; line 27 becomes `SHOT_DIR = pathlib.Path(os.environ.get("DASH_ROWS_SHOT_DIR") or os.path.join(os.environ.get("UBYHOST_SHOTS_DIR", tempfile.gettempdir()), "dashboard-rows"))`. Commit `0368 step 3`.
4. `test_stay_fee_pay_steps_browser.py`: add `import tempfile`; line 16 becomes `OUT = Path(os.environ.get("UBYHOST_SHOTS_DIR", tempfile.gettempdir())) / "stay-fee-steps"`; in the docstring replace `/mnt/project-files/design-reset/stay-fee-steps/` with `$UBYHOST_SHOTS_DIR/stay-fee-steps/`. Commit `0368 step 4`.
5. `test_0251_tablet_browser.py`: add after `_sidebar_width`:
   ```python
   def _wait_sidebar(page, wide):
       # The rail animates; wait for the end width instead of a fixed sleep.
       page.wait_for_function(
           "wide => { const w = document.querySelector('#app-sidebar').getBoundingClientRect().width;"
           " return wide ? w >= 200 : w < 100; }",
           arg=wide, timeout=5000)
   ```
   Then, in the tablet block, replace each of the four `page.wait_for_timeout(100)` lines (three after `toggle.tap()`, one after the `page.tap("body", ...)`) with `_wait_sidebar(page, True)` when the next assert is `>= 200`, or `_wait_sidebar(page, False)` when it is `< 100`. Keep every assert as it is. Commit `0368 step 5`.
6. Run §6. Then `grep -rn "/mnt/project-files" App/tests --include=*.py | tail -5` prints nothing. Write the report.

## 5. Do not touch

`App/app/`, `.github/`, every other test. Never skip, xfail, delete or loosen an assertion. Never push or merge.

## 6. Commands

From `App/`, env from §2: `.venv/bin/python -m pytest tests/test_pwa_browser.py tests/test_0201_tabbar_safe_area_browser.py tests/test_dashboard_rows_browser.py tests/test_stay_fee_pay_steps_browser.py tests/test_0251_tablet_browser.py -q -rs -p no:cacheprovider 2>&1 | tail -10`: all pass, 0 skipped. Then `ls /tmp/0368-shots | tail -5` shows the screenshot folders.

## 7. Acceptance

- [ ] §6 passes, 0 skipped; screenshots land under `/tmp/0368-shots`.
- [ ] No `/mnt/project-files` left in `App/tests/*.py`.
- [ ] No assertion changed.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found; a test fails twice; you reach 25 tool calls or about 50k tokens; you would need push, merge or secrets.

## 9. Report

Write `docs/tasks/0368-report.md` (600 tokens at most) and set `Status: review`.

## Risk list (for the reviewer)

`App/tests/test_0251_tablet_browser.py`

## Owner steps

1. Merge when CI is green.
