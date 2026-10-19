# 0164: property summary stops scrolling sideways; the guard catches hidden list scroll

Status: done
Depends on: 0146-fix-1 | Branch: claude/project-thread-5hw8cf
Executor: Sonnet 5.5 | Fits one session

## 1. Objective

`test_properties_inline_controls_browser.py::test_summary_fits_every_width_both_languages_rail_states` fails on this branch (it passes on main). At 1024 px the property summary table on `/apartments` is 1058 px wide inside an 896 px panel, so the panel scrolls sideways and the "Only when I press send" selects sit past its edge. The cause is the 0158 rule giving `.property-inline-url` `max-width: 16rem` with `white-space: nowrap`: the guest-link column grew from 202 px to 386 px. The layout guard missed it because it skips everything inside a scroller.

Fix the column, then teach the guard that a list panel must not scroll sideways at all.

## 2. Context

MASTER 11.0 says list tables stack into cards instead of scrolling. `design_guard.js` skips scrollers (`inScroller`) for the under-rail and past-edge checks; that stays. The new check is separate: a list panel (`.list-cards`, `.ui-table-wrap`) whose `scrollWidth` exceeds its `clientWidth` by more than 1 px is a finding. S2 lint: no bare px in margin, padding, gap or font-size.

## 3. Files

`App/app/static/host2.css` (append), `App/app/templates/base.html` (host2.css key), `App/tests/static_versions.json`, `App/tests/design_guard.js`, `docs/design/MASTER.md` (one bullet), `docs/tasks/0164-*`.

## 4. Steps

1. Append to `App/app/static/host2.css`:

```
/* 0164: the guest-link URL in the property summary keeps its column narrow */
.host-workspace .property-summary-panel .property-inline-url { max-width: 11rem; }
```

   Lint from the repo root: `python3 scripts/design_lint.py 2>&1 | tail -2` (OK). Change the host2.css key in `App/app/templates/base.html` (grep `host2.css?v=`) to `20261019-0164`, then from `App/`: `.venv/bin/python tests/test_static_versions.py --write && .venv/bin/python -m pytest tests/test_static_versions.py -q 2>&1 | tail -3` (passed).
2. From `App/`: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_properties_inline_controls_browser.py -q -rs 2>&1 | tail -6` (foreground, timeout 600000). Expected: passed. If it still fails on `panelScroll`, try `9rem` once; if it still fails, stop and report the assertion.
3. In `App/tests/design_guard.js`, directly above the line `  // 4. buttons that share a row have one height and one centre line`, insert:

```
  // 3b. a list panel never scrolls sideways (tables stack into cards instead)
  for (const p of ws.querySelectorAll('.list-cards, .ui-table-wrap')) {
    if (!vis(p)) continue;
    if (p.scrollWidth > p.clientWidth + 1) out.push(['list-scrolls-sideways', name(p).slice(0, 60), p.scrollWidth, p.clientWidth]);
  }
```

4. In `docs/design/MASTER.md` section `### 11.0`, add to the item-1 list of what the guard fails on: `- a list panel that scrolls sideways (list-scrolls-sideways);`.
5. From `App/`: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_design_guardrails_browser.py -q -rs 2>&1 | tail -15` (foreground, timeout 900000). If it fails with `list-scrolls-sideways` findings on other pages, do NOT loosen the check: read `/tmp/ubyhost-layout-guard.json`, list each page, width and panel in the report, fix each one with the smallest host2.css rule that lets the table wrap or stack (one rule per page, appended under the 0164 comment), rerun once. If findings remain after that, stop and report them.
6. Then `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_host_properties_navigation.py tests/test_host_list_cards_browser.py tests/test_host_wide_geometry_browser.py -q -rs 2>&1 | tail -6` (passed, 0 skipped). From the repo root: `git checkout -- docs/tasks/0102-evidence; git clean -fdq docs/tasks/0102-evidence`.
7. Commit: `git add App/app/static/host2.css App/app/templates/base.html App/tests/static_versions.json App/tests/design_guard.js docs/design/MASTER.md docs/tasks/0164-* && git commit` with message `0164: property summary column, guard catches list panels that scroll sideways` and the two trailers.

## 5. Do not touch

Anything else; hard rules 1, 3, 8. Never add an allowlist or skip to the guard.

## 6. Commands

As in each step.

## 7. Acceptance

- [ ] Summary test passes, the guard has the new check and passes on every route, 0 skipped.

## 8. Stop and ask

An anchor is missing, a test fails twice, or findings remain after one round of fixes.

## 9. Report

`docs/tasks/0164-report.md`; `Status: review`. List every page the new check flagged and the rule added.
