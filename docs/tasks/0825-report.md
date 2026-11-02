# 0825 report

Status: blocked
Executor: Haiku 5.5. Not committed, not pushed.

## Files changed (working tree only)

- `App/app/static/app2.css`: new block `/* 0825 empty state centred (start/end) */` after the 0820 rule at the end of the file.
- `App/app/templates/base.html`: `app2.css?v=20261102-0825`.
- `App/tests/static_versions.json`: rewritten by the first `--write`.
- Temp file `App/tests/test_tmp_0825_measure.py`: created for measuring, deleted.

## Measurements (empty user, EN, content centre vs centre of head bottom to viewport bottom)

| Page | 390 before | 390 after | 1280 before | 1280 after |
|---|---|---|---|---|
| submissions | off (page scrolled, not measurable) | 0 | off (block at top) | 0 |
| invoices | -207 | +52 | -260 | +48 |
| housebook | not measurable (text-only panel) | not measurable | not measurable | not measurable |
| stay-fees | -179 | +58 | -228 | +56 |

Target is within 24 px. Only submissions meets it. Invoices, housebook and stay-fees do not.

Scroll after fix: submissions at 390 still scrolls (scroll height 1189 against 844). Invoices and stay-fees at 390 do not scroll in the measurement.

## Commands (last lines)

1. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest <brief files> -q -rs --tb=short`:
   `6 failed, 43 passed, 108 deselected in 72.61s`. All six are in `test_0710_v2_mockup_match_browser.py::test_v2_page_geometry`: `submissions` at 390 and 768, `invoices` at 320, 390 and 768 fail with `main content ends at 1000 under the tab bar (top 916)`. The new `margin-bottom` and `min-height` make the wrapper extend under the tab bar.
2. `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_design_lint.py -q --tb=short`:
   `2 failed, 4 passed`. `app2.css` changed after the version bump, so the key `20261102-0825` is stale. `--write` refused with `app2.css changed but still has ?v=20261102-0825`. The key needs a new value.

Not run: the other brief commands after the first failure in cmd 1 are included in that run. No other tests run.

## Screenshots

The measurement run wrote `/mnt/project-files/records-pages/empty-<page>-<width>.png` (8 files). I did not look at them or confirm all 8 exist.

## Deviations

- Done: steps 1 and 3. Step 2 is partial: fixed for submissions only.
- Left: step 2 for invoices, housebook and stay-fees (offset about +50 px). Fix the two failing commands and bump the static key.
- Submissions has no `.head` in its empty branch. The free area starts at the wrapper top (202 px at 390, 164 px at 1280).
- The v2 bottom bar (`.ui-tabbar`) is not rendered at 390 in this test, so the free area runs to the viewport bottom.
- The `margin-bottom: -104px` / `-96px` cancels a bottom reserve in the shell, measured as the overflow. The source of that reserve was not identified.
- The top offsets (134/100 px, and 202/164 px for submissions) are hard-coded. They depend on the env banner height and are fragile.

## Questions for the orchestrator

- Approve a different approach for the wrapper height (JS-free but not based on fixed shell offsets), or accept the constants and fix the bottom reserve at its source?
- Bump the static key to a new value (for example `20261102-0825b`), or keep `0825`?

## Owner steps left

None. No deploy or server step.
