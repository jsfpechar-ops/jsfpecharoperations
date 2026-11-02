# 0854: Records pages: collapsed filter panel, "?" help icon, no duplicate empty-state button

Status: review
Depends on: 0852 (in checkout) | Branch: claude/project-thread-v4nqi5 (main checkout, do NOT commit; the orchestrator commits)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The orchestrator's 1280 screenshots of `/invoices` and `/stay-fees` (rich-host fixture) show four defects. Fix them so both pages look like `/reservations`.

## 2. Context

1. **Filter panel always open and unstyled.** `_list_filter.html` (included by `invoices.html` line ~26 and `stay_fees.html` line 14) renders a "Filters" button and the whole form open below it: full-width selects, labels tight, "Apply filters" + an underlined "Cancel" link. v2 pages load only `tokens.css` + `app2.css`, so the old `host.css` `.list-filter*` rules (9 lines, `grep -n "list-filter" App/app/static/host.css`) never apply. Port what is needed as `body.v2 ...` rules in ONE block `/* 0854 list filter v2 */` in `app2.css`: panel hidden while collapsed (match how the JS toggles it: `hidden` attribute or `.is-collapsed`; read `App/app/static/*.js` for `list-filter`/`data-filter-toggle`), open panel = one card (`var(--space-4)` padding, 12 px gaps), fields in a wrapping row (`flex-wrap`, each field `flex:1 1 200px`, max row width = lane), actions row with Apply and Cancel as same-height buttons (Cancel `.btn` ghost look, not a text link) >= 12 px apart. Must stay usable without JavaScript (no-JS: panel visible, as today).
2. **Stay fees toolbar above the title.** `stay_fees.html` puts the filter in `{% block toolbar %}`, which renders above the head. Move it under the head (same order as invoices: head, then Filters).
3. **Help toggle look.** `details.ui-how` summary inside `.head-title-row` shows "How does this work?" text, two chevrons and a bordered box. Make it a 32 px round "?" icon button only (circle-help icon, no visible text, no chevron, no border box), `aria-label` = the existing help label string, centred on the h1's line. The open panel stays as 0852 made it. All four pages.
4. **Invoices empty state.** "No invoices yet" + sentence "Issue one when a stay needs a document." + a second "Generate invoice" button. Keep only the "No invoices yet" line (the head already has the button; owner no-fine-print rule). Delete the now-unused string(s).

## 3. Files

`App/app/static/app2.css` (new 0854 block + the 0852 head rules), `App/app/templates/stay_fees.html`, `invoices.html`, `submissions.html`, `housebook.html` (help summary markup only), i18n files (unused strings only), `App/app/templates/base.html` + `App/tests/static_versions.json` (bump `app2.css?v=` to `20261102-0854`, then from `App/` run `.venv/bin/python tests/test_static_versions.py --write`), tests that assert the removed empty-state text/button or the help label text (update). Not `_list_filter.html` unless a class hook is missing (then report it).

## 4. Steps

1. Read the JS toggle and the host.css rules. 2. Port (item 1). 3. Items 2-4. 4. Commands.

## 5. Do not touch

Anything outside §3. No new dependency, colour or JS. `/reservations` must not change.

## 6. Commands (from `App/`, each `2>&1 | tail -30`)

1. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k "invoices or housebook or submissions or stay_fees" tests/test_host_filter_panels_browser.py tests/test_host_geometry.py tests/test_motion_browser.py tests/test_design_guardrails_browser.py -q -rs --tb=short`
2. `.venv/bin/python -m pytest tests/test_page_help_0277.py tests/test_design_fees.py tests/test_design_invoices.py tests/test_static_versions.py tests/test_design_lint.py tests/test_host_i18n.py tests/test_stay_fee_send_panel.py -q --tb=short`

## 7. Acceptance

- [ ] On /invoices and /stay-fees at 1280 with JS: filter panel hidden until "Filters" is clicked; open panel is one card; Apply and Cancel same height, >= 12 px apart.
- [ ] Help on all four pages: one round "?" on the h1 line, no visible text, no chevron.
- [ ] Commands 1-2: 0 failed, 0 skipped (list any failure you believe is not yours, with its message).

## 8. Stop and ask

Blocked if a fix fails twice, a file outside §3 needs a change, or 30 tool calls.

## 9. Report

`docs/tasks/0854-report.md`, 250 tokens at most. Do not commit or push.
