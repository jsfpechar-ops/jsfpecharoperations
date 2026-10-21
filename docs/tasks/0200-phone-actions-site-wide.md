# 0200: Phone action rows and small geometry faults on every host page

Status: done
Depends on: 0199 | Base commit: current branch head | Branch: claude/project-thread-xo8dql
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

A sweep of all 39 host pages at 360/390 px in English and Czech found no overflow, but action buttons sit in mixed shapes: some full width, some auto width, some left, some right ("Pokračovat" right on the invoice picker, "Zrušit | Vytvořit ubytování" split on Add property, the property save bar stacks two buttons of different widths, invoice actions wrap into a ragged 2+1+link block). Follow GOV.UK: on phone, text action buttons in an action row are full width and stacked, in DOM order. Plus three small faults.

## 2. Context

Rules: WCAG 2.2 AA, 44x44 px phone targets, no borderless controls, one `?v=` bump per changed CSS file + `tests/test_static_versions.py --write`. Host shared CSS for the v2 design is `App/app/static/host2.css` (linked from `App/app/templates/base.html`). Phone = `@media (max-width:760px)`. Sweep screenshots: `/tmp/claude-0/-home-user-jsfpecharoperations/32720230-0d1d-503f-bf86-113631eb131a/scratchpad/sweep/` (`<route>-en.png`, `<route>-cs.png`). The sweep test is `App/tests/test_zz_mobile_sweep_browser.py` (temporary, not committed).

## 3. Files

All in `App/app/static/host2.css` (one `/* 0200 */` block at the end), its key in `base.html`, `static_versions.json`.

### Faults and fixes (phone media query unless noted)

- A. Action rows: for `body.host-workspace :is(.actions, .action-group, .host-property-save)` on phone: `display:flex; flex-direction:column; align-items:stretch; gap:8px;` and their direct `.ui-btn` children, and `.ui-btn` inside direct `form` children, get `width:100%; justify-content:center; min-height:44px;`. Direct `form` children get `width:100%; margin:0;`. EXCLUDE icon-only buttons (`.ui-btn-icon`, `.row-menu-trigger`) and help tips: they keep their size and sit at the end of the column, right aligned (`align-self:flex-end`). Plain text links in the row (`a:not(.ui-btn)`) stay links, centred under the buttons (`align-self:center; min-height:44px; display:inline-flex; align-items:center`).
  Before writing, grep the templates for each of the three class names and list where they are used; if one of them is used for something that is not a row of actions (for example a toolbar, a segmented control, the calendar toolbar, the stay page `.stay-command-actions`, or the cleaning list row buttons), add a `:not(...)` for it and tell me. Do NOT touch `.ui-form-actions` (0199 handles the stay Guests header) or `.stay-command-actions`.
- B. Properties list on phone (`/apartments`): the row ⋮ menu sits alone on its own line at the bottom-left of each card. Put it at the card's top-right corner like the Stays list cards do (compare the Stays card CSS in host2.css: find the rule that positions `.row-menu` in stays cards below 1024 px and reuse the same approach for the properties table rows). Measure: menu right edge = card right edge - card padding (±2 px), menu top within 4 px of the property name's top.
- C. Submission detail (`/submissions/<id>`) banner: "Chyba přenosu" and the error text run together with no space ("Chyba přenosuSynthetic…"). In `.ui-banner .grow` make `strong` and `small` stack: `.ui-banner .grow > small { display:block; }` (check it does not break other banners; scope to `.ui-banner .grow > strong + small` if needed). This is a fault at every width, not only phone, so put C outside the media query.
- D. Operator phone field (`.operator-phone-prefix`, on the operator add/edit pages): the "+" prefix box is a round pill next to a square input. Give it the input's border radius and height (measure the input next to it).

## 4. Steps

1. Grep and list usages for A (step above). Read the end of host2.css (`tail -60`).
2. Write the block. Bump `host2.css?v=` in every template that has it (suffix `-0200`), regenerate the manifest.
3. Extend the sweep test (or a copy named `test_zz_0200_browser.py`) to assert at 360 and 390, en and cs, on every route: inside A containers every text `.ui-btn` has width == container content width (±1 px); no `document.documentElement.scrollWidth > innerWidth`; B and C measurements above. Then at 1280 assert A containers still lay out in a row (desktop unchanged: the first two text buttons share one top ±1 px where a container has two).
4. Save screenshots at 390 en and cs for: property-new, invoice-new-picker, invoice-detail, operator-add, properties, submission-detail, automation (property settings save bar), setup-calendar to `/mnt/project-files/design-reset/checkpoint-6/mobile/sitewide/` (`mkdir -p`, trailing slash).

## 5. Do not touch

Templates, Python, copy, host-design0123.css, host.css, dashboard-calendar.css (0199 owns them). No git commit/stash/checkout/reset/clean.

## 6. Commands

From `App/` with `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome UBYHOST_REQUIRE_BROWSER=1`:
`.venv/bin/python -m pytest tests/test_static_versions.py tests/test_design_guardrails_browser.py tests/test_host_wide_geometry_browser.py tests/test_host_list_cards_browser.py tests/test_host_controls_browser.py -q --tb=line -rfs 2>&1 | grep -E "FAILED|passed|failed|^E " | tail -10`

## 7. Acceptance

- [ ] A-D measured true at 360/390 en+cs; desktop row layout unchanged at 1280.
- [ ] Tests above pass, 0 skipped.

## 8. Stop and ask

If A would change a container that is not an action row and `:not()` cannot cleanly exclude it, or a listed test fails, stop and report. Do not commit.

## 9. Report

[0200-report.md](0200-report.md)
