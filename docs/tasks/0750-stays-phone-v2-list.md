# 0750 brief: phone v2 stays list (Airbnb reservations style)

Status: review
Executor: Haiku 5.5, alone, on branch `claude/project-thread-rub7xm` in `/home/claude/jsfpecharoperations` (already checked out; do not switch branches, do not push, do not commit).
Another Haiku works on brief 0751 (stay page) in the same folder at the same time: edit only the lines this brief names; never revert changes you did not make.

## 1. Objective

Below 1024 px, `/reservations` looks like screen `pobyty` of `docs/design/mockup/ubyhost-phone-v2.html`:
title "Pobyty" left with a round soft "+" button right on the same row; the range chips become `.seg.scroll` pills (sideways scroll, ink pill for the active one);
group labels are centred small caps `h2.sec`; each stay is one compact white card (56 px round initial, name, "property · dates", ONE status line with a dot and no pill background, chevron).
The phone CSV/house-book link and the phone links block stay hidden on phone (compact rule). Desktop (>= 1024 px) must not change at all.

## 2. Context

- Design: read the `/* stays list + stay page (0750` CSS block and the `data-s="pobyty"` section of `docs/design/mockup/ubyhost-phone-v2.html`. Do not edit the mockup.
- Template: `App/app/templates/reservations.html`: line ~26 `<div class="stays-phone"><div class="top">…` (phone top with the + button), line ~27 `.head.stays-head` with `h1.big`, line ~98 `.chips`, lines ~155-185 the phone list (`.stays-phone`, `div.grp`, `.list`, `a.row`, `.av`, `.t`), lines ~298-302 `.stays-links`.
- CSS: `App/app/static/app2.css` lines ~435-470 (stays block). Shared phone v2 classes already exist (search `0729` and `0735` in app2.css: `.seg`, `h2.sec`, `.mh`): reuse them, do not copy them.
- `.ph-hide` hides below 1024 px, `.ph-only` shows only below 1024 px (grep app2.css to confirm).
- Status pills come from macros (`v2_status_pill`, `progress_pill`) and render `span.pill.p-ok|p-warn|p-bad|p-n`: keep the macros, restyle them inside `.stays-phone .card.stay` only.
- Standing rule for tests: you may change assertions that only check the phone stays list below 1024 px (div.grp, .row, .av, the phone + button, the house-book link) in `App/tests/test_*stays*`, `test_*reservations*browser*`, `test_host_list_cards_browser.py`, `test_design_guardrails_browser.py`, `test_host_wide_geometry_browser.py`, and the `stays` entry of `App/tests/v2_mockup.py`. Change no desktop assertion.

## 3. Files

The template, `app2.css`, i18n files, `App/tests/v2_mockup.py` and the tests in section 2.

## 4. Steps

1. `reservations.html`:
   a. Delete the phone top `<div class="stays-phone"><div class="top">…</div></div>` line. Put the + button inside `.head.stays-head` next to the h1 as `<button class="round stays-add ph-only" type="button" data-toggle-panel="add-stay-panel" aria-label="{{ t('stays.add_stay') }}">{{ icon('plus', 22) }}</button>` (keep the `{% if apartments %}` guard), so h1 and button sit on one row (`.mh`-like flex on phone).
   b. Below 1024 px the `.chips` row must render like `.seg.scroll` from the mockup: add class `seg scroll` styling for phone via CSS on the existing `.chips` (or add the classes in the markup if the desktop chips keep their look; check at 1280 px). Hidden chips (`ph-hide`) stay hidden.
   c. Phone list: replace `<div class="grp">…</div><div class="list">` + `a.row` with `<h2 class="sec">…</h2>` and per stay `<a class="card stay" href="…same href…"><span class="sav">{{ initial }}</span><span class="in"><b>…</b><small>…</small>{{ the same pill macros }}</span>{{ icon('chevron-right', 20, 'chev') }}</a>`. Keep the existing date/name logic and hrefs.
   d. `.stays-links` and the phone house-book link: hidden below 1024 px (add `ph-hide` to the block or hide `.stays-phone-only`); keep `.stays-more` (load more) visible.
2. `app2.css`: in the stays block add one `@media (max-width:1023px){…}` rule set with values copied from the mockup block (`.stays-add`, `.seg.scroll` behaviour for the chips, `.stays-phone h2.sec`, `.card.stay`, `.sav`, `.in`, `.in b`, `.in small`, `.stay .pill…`, `.chev`), every selector prefixed `body.v2 .stays-phone` or `body.v2 .stays-head` as needed. Delete phone rules that only styled the removed `.grp`/`.row`/`.av` stays markup (grep first; leave rules other pages use). No `!important`.
3. `App/tests/v2_mockup.py`, `stays` entry: add `"phone_mockup": PHONE_MOCKUP_V2,`; set `"phone_selectors"` to
   `[".tabs", ".tab.on", ".mh .big, .head h1", ".stays-add", "h2.sec", ".card.stay", ".sav", ".stay .in b", ".stay .in small", ".stay .pill.p-ok", ".stay .pill.p-warn", ".card.stay .chev"]`
   (if the h1 selector does not match in one of the two pages, use one selector that matches both, as the properties entry does with `.big, .head h1`).
   `missing_ok`: `.stay .pill.p-ok` and `.stay .pill.p-warn`: "tone depends on data". Remove the old `stays:` BOX_OVERRIDES keys that name removed selectors; add new ones only for text-dependent box sizes, under `# text-dependent: app copy vs phone v2 mockup demo copy (0750)`, keyed `"stays:selector@width"`.
4. Tests, from `App/` (do NOT reinstall playwright; the venv pins 1.63.0):
   `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k "stays and not stay_" -q --tb=short -x 2>&1 | tail -30`
   (check the test ids with `--collect-only -q | grep -i stay | head` first and pick the stays-list ones). Style failures mean wrong CSS: fix the CSS, never override a style.
   Then run the stays-list browser tests: `ls tests | grep -i -E 'stays|reservations' ` and run the ones with `browser` in the name plus `test_host_list_cards_browser.py test_design_guardrails_browser.py test_host_wide_geometry_browser.py`, same env vars, `-q --tb=short 2>&1 | tail -30`.
5. Take a 390 px screenshot of `/reservations?range=upcoming` as the rich test host (reuse the login/fixture helper the 0710 test uses) to `docs/tasks/screenshots-0750/stays-390.png`.

## 5. Do not touch

Desktop (>= 1024 px) markup and rules, `docs/design/mockup/`, `reservation_detail.html` (0751), `base.html`, `static_versions.json`, `catalog.json` (the orchestrator bumps the cache key and the catalog).

## 6. Commands

The test commands in step 4, from `App/`.

## 7. Acceptance

The 0710 stays test and the listed browser tests pass with 0 skipped (test_static_versions and design_lint may fail until the orchestrator bumps them; say so).

## 8. Stop and ask

A test outside the standing rule fails, or the 30-call cap comes near: write the report with what is left.

## 9. Report

`docs/tasks/0750-report.md`: changed files, command tails, overrides added, new CSS classes (for catalog.json), deviations.
