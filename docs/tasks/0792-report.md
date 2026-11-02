# 0792 report: Faktury (/invoices) on the v2 look

Status: blocked
Branch: claude/project-thread-tluz48 (uncommitted, per orchestrator: no commit, no push)

## Files changed

- `App/app/templates/invoices.html`: rewritten to the v2 pattern (v2 flag, empty blocks, stays head with how-details, invoice settings ghost head button taken from `page_tabs()`, primary "New invoice" button, phone add button, `_list_filter.html` under the head, phone cards `.stay`/`.sav`, desktop `.stays-desk` table with status pills and PDF `a.btn.ghost.sm`, pagination and the same empty states). Page body is wrapped in `div.invoices-page`. No route, data or string key changed.
- `App/app/static/app2.css`: only inside `/* 0792 invoices v2 (start) */` ... `(end)`: a max-width 1023 px rule for tap targets of `.invoices-page .ui-btn`, `.month-step` and the filter month input, and a `.invoices-page input[type=month]` rule.
- `App/tests/v2_mockup.py`: one `invoices` entry appended to `PAGES` (from the brief), `missing_ok` for table/card selectors (reason "fixture has no invoice") and `.tab.on` (no tab strip), and one `BOX_OVERRIDES` key `invoices:.mh .big, .head h1@320` (text-dependent h1 width). The file was also edited by other executors; their entries were left alone.

## Commands (last lines)

- `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k invoices -q --tb=line -rs | tail -30`
  Last result: `5 failed, 7 passed, 106 deselected`. Remaining finding in every failing width: `tap target 145x37 (min 44): <a class="ui-btn ui-btn-secondary"> "Generate invoice"` (the filter panel's submit link). My `body.v2 .invoices-page .ui-btn` rule did not raise it, so the element is probably rendered outside `.invoices-page` (filter panel moved by app.js) or has its own height. Not investigated further (tool budget).

## Not done

- Old page tests (`grep -ln '/invoices' tests/*.py` lists about 35 files): NOT run, and no assertions were updated.
- Screenshots at 390 and 1440 px: NOT taken.
- Desktop table, pagination and phone card markup were not checked by a browser beyond the 0710 selectors.

## Deviations

- The brief's `<p class="sub">` line was omitted: the old page had no subtitle and no new copy was added.
- The executor doc refers to brief sections 6, 7 and 8; this brief and the common brief have no numbered sections. Followed the test command and the report rules in 0790 instead.
- Done: steps 1 to 4 (template, CSS, 0710 entry, 0710 run). Left: fix the "Generate invoice" tap target, old test run and assertion updates, screenshots, then status review.

## Questions

- Should the filter panel's submit link be styled through the shared filter component (outside this brief), or should `.invoices-page` be applied around the filter panel after app.js moves it?

## Owner steps left

- None yet. Nothing was committed or pushed.
