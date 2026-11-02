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
