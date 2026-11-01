# 0707 report: v2 Overview polish

Status: review

## Files changed
- App/app/static/app2.css (items 1-6, 7 grid rows)
- App/app/routes/admin.py (item 7: `_overview_calendar_rows` labels, guest count, lanes)
- App/app/templates/dashboard.html (item 6 hooks: none added, CSS targets existing classes; item 8: awaiting_guest pill)
- App/app/templates/base.html (app2.css ?v=20261101-0707)
- App/tests/static_versions.json (--write)
- docs/tasks/screenshots-0707/overview-cs-1280.png, overview-cs-390.png

## Per item
1. Links: `body.v2 a{color:inherit;text-decoration:none}`, quiet links ink-3 (underline on hover), `.btn` keeps white/ink. Done.
2. Skip link hidden until focus. Done.
3. Env banner styled with warn colours in v2. Done (root `.env-banner`).
4. `.ui-tabbar` and `.havel-fab` hidden in v2, CSS only, no JS change. Done.
5. Demo-clear button (`form[action="/demo/reset"] button`) styled as quiet link. Done.
6. Row menu: trigger without border, ink-3, letter-spacing .1em; panel white card with shadow; items 8px 12px, hover #f6f6f4. Hidden state kept (`[hidden]` rule); `.is-open` keeps position fixed. Trigger icon is still the ellipsis-vertical icon, not `···`.
7. Bar labels: source name, "Pobyt" fallback, " · N" when guests > 0. Lanes via greedy grid-row, `grid-auto-rows:44px` on `.crow`. Visible in screenshot ("Pobyt · 1").
8. Waiting stays (`awaiting_guest` with `progress.not_registered`) show `.pill.p-warn` with `tp('host.missing', ...)`. Not applied to reported/not_required (next_action already renders text there) nor to p-ok "Hotovo, nahlášeno policii". Demo row in the screenshot has no not_registered value, so no pill is visible.

## Commands
- `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_privacy_first.py -q` : 8 passed
- `.venv/bin/python -m pytest tests/test_0701_overview_cards_browser.py -k shot -q -rs` : 1 passed, 3 deselected, no skips
- `python3 scripts/context_lint.py` : OK
- `python3 scripts/design_lint.py` : FAIL, 30 DESIGN lines in dashboard.html. The new `pill` and `p-warn` classes (item 8) are not in the catalog. Baseline not checked.
- `py_compile App/app/routes/admin.py` : OK

## Deviations
- Item 7 fallback uses the literal "Pobyt", not `t('calendar.kind_stay')` (admin.py has no `t` import). EN users see "Pobyt".
- Item 6 trigger icon not replaced with `···`.
- Item 8 partial (see above).

## Questions
- Design lint: is there a catalog name for the pill (`pill`, `p-warn`), or should the classes be added to the catalog?
- Item 8: should reported/not_required rows get the p-ok pill instead of next_action text?

## Owner steps left
- Push and open the PR yourself (executor did not push).
- Decide the two questions above.

## Screenshot notes (390 px)
- The 390 px page overflows: the calendar grid runs past the viewport, and the header shows the desktop sidebar's nav as a row that is cut off. This is outside the brief (no mobile fix asked). Needs its own brief.
