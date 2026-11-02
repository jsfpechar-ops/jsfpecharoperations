# 0732 report: Úklid phone v2

Status: blocked. Steps 1, 2, 3 and 5 done. Step 4 (mockup compare at 320/390/768) is still red for cleaning.

## Commits
- c7950e7 `0732 step 1`: copy keys (cleaning_i18n.py, host_vi_i18n.py)
- 0ac83f7 `0732 step 2` (amended once for the icon import): markup (`_cleaning_table.html`, `cleaning.html`), CSS (`app2.css` 0546 block), key `20261102-0732` in `base.html`, `tests/static_versions.json`
- 446d404 `0732 step 3`: `tests/test_0541_cleaning_header.py`, `tests/test_design_cleaning.py`
- 78ffbea `0732 step 4` (red compare): `tests/v2_mockup.py`, `tests/test_host_quiet_dashboard_browser.py`
- 39225b5 `0732 step 5`: `docs/tasks/screenshots-0732/` (cleaning-390, cleaning-320, cleaning-1280)

## Test tails
- Step 3, first run: `40 failed, 42 passed in 251.17s`. Cause: `'icon' is undefined` in the phone block. Fixed by importing `icon` in `_cleaning_table.html`.
- Step 3, second run: `2 failed, 80 passed in 53.28s` (the two assertions on the old phone markup, fixed).
- Step 3, after fixes: `8 passed in 2.18s` (test_0541 and test_design_cleaning).
- Step 4 compare: `3 failed, 30 passed, 25 deselected in 45.49s`. All 3 failures are cleaning-320, -390, -768. Overview and menu pass.
- Step 5 screenshots: `1 passed, 57 deselected in 30.71s`.
- `design_lint.py`: OK. `context_lint.py`: OK.

## Step 4 cleaning differences (still red)
- `.hs .pill` colour: app green (`p-ok`), mockup amber `rgb(138,82,0)`. The brief says `p-ok` for Scheduled. The mockup says amber. Owner decision needed.
- `.hl` font-size 24px vs mockup 30px at all widths. The mockup's 30px rule is `body.v2 .head h1.hl` (app2.css line 651), so it does not match `.ph-top h1.hl`.
- `h2.sec`: app 15.75px vs 13px. Margins also differ at 320 (0 vs 26px). Some rule inside `.cleaning-page` overrides it; not diagnosed.
- `.row .t b`, `.row .t small`, `.promo b`: the `.t` column is narrow at 320 and 390 (95 px vs 242 px at 320), so text wraps. This is layout, not text length.
- `.promo` height: 121px vs 99px at 320.
- `.cleaning-more .btn.line`: missing from the mockup. The mockup has the "Show 4 more" link without a details wrapper. Needs a selector or missing_ok decision in `v2_mockup.py`.
- No BOX_OVERRIDES added. None of the differences are text-length only.

## Deviations
- Step 2 needed `{% from "_icons.html" import icon with context %}` in `_cleaning_table.html`. The brief did not list it.
- Step 2 plain-row CSS is global as the brief wrote it, not scoped to `.cleaning-phone`. The menu compare still passes.
- Step 3 also fixed the `<h1>` count and the `actbar` assertion in `test_design_cleaning.py`, and the head slice anchor in `test_0541`.
- Step 4 "before" compare was not recorded (tool budget).
- Step 4 fixture: today cleaning 10:00-15:00 added in `dashboard_rich_host`. Menu compare still passes with it.
- Commit trailer: Opus 5.5 only, as instructed. No push. No PR opened.

## Questions
1. Scheduled pill: green (`p-ok`, brief and the 0731 decision) or amber (v2 mockup)?
2. Should `.cleaning-more .btn.line` be aliased to `.btn.line` in the mockup compare, or added to missing_ok?

## Owner steps left
- Decide question 1 and question 2, then run `.venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k "cleaning" -q` from App/.
- Fix the `.hl`, `h2.sec` and row-width diffs in a follow-up brief. Those need a look at the cascade, not more copy changes.

## Addendum 0732b (executor)

Status: blocked. Done: steps 1 to 3. Left: step 4 (differences below need an owner or orchestrator decision), step 5 (screenshots not retaken).

- Step 1 and 2: `h1.hl` 30px and `h2.sec` 13px below 1024 px added in the cleaning block of `App/app/static/app2.css`. The `h2.sec` and `.hl height` diffs are gone at 320, 390 and 768.
- Step 3: five selectors in the cleaning PAGES entry changed. Cache key `20261102-0732b` in `base.html`, `tests/static_versions.json` regenerated with `--write` (41 files).
- Step 3 test set: `82 passed in 51.58s` (0 skipped).
- Step 4 run: `3 failed, 30 passed, 25 deselected in 46.55s`. Failures: cleaning-320, cleaning-390, cleaning-768. Overview and menu pass.
- Step 4 remaining diffs (not fixed, no BOX_OVERRIDES added):
  - `.btn.line` padding 14/16px and height 54 vs 50px, margin-top 8px at 320: the mockup's `.btn.line` has no padding. This is a style diff, not width or height from fixture text. It fails at 768 too.
  - `.nm` and `.meta` width 135px app vs 173px mockup at 320 and 390: layout, not text.
  - `.promo` height 121 vs 99px and `.promo b` height 46 vs 24px at 320: the `.t` column wraps. Layout.
  - `.list.plain .row:not(:has(.pill))` height 73 vs 75px and `.t b` 22 vs 24px at 320 and 390.
  - `.kind` width 87 vs 85px at 320 and 390 (2px).

## Deviations
- `?v=` key is in `App/app/templates/base.html`, not `App/app/static/app2.css`. Bumped there.
- `tests/static_versions.json` was regenerated (the brief's `--write`).

## Questions
1. For `.btn.line` padding: should the app drop the padding below 1024 px, or should the mockup compare treat it as missing_ok?
2. For `.nm`, `.meta` and `.promo` widths and heights: are these fixture text (a BOX_OVERRIDES case) or a layout fix in the cleaning files?

## Owner steps left
- Answer question 1 and question 2 (orchestrator), then run `cd App && PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k "cleaning or overview or menu" -q -rs --tb=short`.
- Step 5 screenshots after step 4 is green.

## Addendum 0732c (executor)

Status: blocked. Done: steps 1 to 2, the `?v=` bump and manifest of step 3. Left: step 3 box overrides (blocked by a shared-key conflict, see Deviations), step 4 (screenshots not retaken, no `0732c` report tails for the final run).

- Step 1: `body.v2 .cleaning-more>summary.btn{margin-top:0;padding:0;min-height:50px}` (max-width 1023 px) in `App/app/static/app2.css`. The `.btn.line` diff is gone.
- Step 2: `body.v2 .cleaning-phone .list.plain .row .t b{font-size:17px}` (max-width 1023 px). The `.t b` diff is gone.
- `App/app/templates/base.html` key `20261102-0732c`. `tests/static_versions.json` regenerated with `--write` (41 files).
- Step 3 brief set: `82 passed in 52.49s` (0 skipped).
- Mockup browser `-k "cleaning or overview or menu"`: `2 failed, 31 passed, 25 deselected in 45.13s`. Overview and menu pass. Failures: cleaning-320 (6 diffs), cleaning-390 (5 diffs).
- Remaining cleaning diffs: `.kind` 87.36 vs 85.08, `.nm` and `.meta` 135.23 vs 173.44 (320 and 390), `.promo` 121.19 vs 98.98 and `.promo b` 46 vs 23.8 (320), `.list.plain .row:not(:has(.pill))` 74 vs 75.39 (320 and 390), `.hl` 34.5 (390, equal values, likely rounding).

## Deviations
- The addendum's overrides were not added. `BOX_OVERRIDES` is keyed by selector only, not by page. `.kind`, `.nm`, `.meta` and `.promo` are shared with overview and menu. Adding the cleaning values made overview (3 diffs at 320 and 390) and menu (2 diffs at 320) fail, so `App/tests/v2_mockup.py` was reverted to HEAD.
- The addendum's `# cleaning phone v2 (0732)` comment does not exist. The nearest is the `# cleaning phone (0549b)` comment.
- Commit trailer: `Co-Authored-By: Claude Opus 5.5` only, as the brief says.

## Questions
1. Should the overrides be page-scoped (a per-page key), or should the cleaning layout change for `.nm`, `.meta`, `.kind` and `.promo`?
2. `.list.plain .row:not(:has(.pill))` (74 vs 75.39 at 320 and 390) is not in the addendum. Override or fix?

## Owner steps left
- Answer question 1 and question 2 (orchestrator), then rerun `cd App && PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k "cleaning or overview or menu" -q -rs --tb=short`.
- Step 4 screenshots after that run is green.

## 0732d

Command: `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k "cleaning or overview or menu" -q --tb=short 2>&1 | tail -30` (from App/)

```
E   AssertionError: cleaning at 320 px: 1 style differences
E     .list.plain .row:not(:has(.pill)) height at 320 px: app=74px mockup=75.3906px
E   assert not ['.list.plain .row:not(:has(.pill)) height at 320 px: app=74px mockup=75.3906px']
E   AssertionError: cleaning at 390 px: 2 style differences
E     .hl height at 390 px: app=34.5px mockup=34.5px
E     .list.plain .row:not(:has(.pill)) height at 390 px: app=74px mockup=75.3906px
E   assert not ['.hl height at 390 px: app=34.5px mockup=34.5px', '.list.plain .row:not(:has(.pill)) height at 390 px: app=74px mockup=75.3906px']
2 failed, 31 passed, 25 deselected in 46.00s
```

Screenshots: `docs/tasks/screenshots-0732/cleaning-390.png`, `cleaning-320.png`, `cleaning-1280.png`.
