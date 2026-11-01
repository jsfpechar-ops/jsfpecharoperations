# 0711: make the v2 Overview pass the mockup-match and geometry tests at every size
Status: todo
Depends on: 0710 | Base commit: task/0710-v2-match-tests | Branch: task/0711-v2-match-fixes
Executor: Haiku 5.5 | Fits one session: 30 tool calls

## 1. Objective
`tests/test_0710_v2_mockup_match_browser.py` passes for Overview at 320, 390, 768, 1024, 1280 and 1440 px with 0 skipped. Read `docs/tasks/0710-report.md` first: it lists every finding.

## 2. Context and decisions (orchestrator, 2026-11-01)
- Phone layout: the owner wants a separate Airbnb-style phone design (another thread is drawing it). Below 1024 px keep only the basics: no sideways scroll, tap targets, readable text. Do not restyle the phone top bar beyond that.
- Accessibility beats the mockup. In `App/app/static/app2.css` `:root`: `--ink3:#6b6b65` (mockup #8a8a84 fails AA). Active nav text: `.nav.on{color:#b83d28}` (coral on #fdece8 fails AA). Text smaller than 12 px in the app becomes 12 px (`.cd`, `.org small`, `.me small`, the search `kbd`).
- In `App/tests/v2_mockup.py` record these as data, not by weakening checks:
  - `SELECTOR_OVERRIDES = {".side .nav.on": {"color": "rgb(184, 61, 40)"}, ".cal .cd": {"font-size": "12px"}}`, comment `# accessibility (AA contrast, 12 px minimum), 2026-11-01`. When a selector/prop is in it, compare the app with the override value instead of the mockup.
  - `DESKTOP_ONLY = {".side", ".side .nav", ".side .nav.on"}`: style-compare these only at width >= 1024 (phone design pending).
  - Replace the selector `.cal .bar` with `.cal .bar.b-ok` and `.cal .bar.b-warn` (tone depends on data; compare like with like). If the demo data has no bar of a tone, add it to `missing_ok` with the reason.
  - `main table td border colour`: check whether the first `td` differs only because the mockup's first row is not the last row. Compare `main tbody tr:first-child td` instead if so.
- Calendar: copy the mockup's rules exactly (mockup lines 65-69: `.cal{padding:6px 14px 10px;overflow-x:auto}`, `.cgrid{...min-width:780px}` etc.) so the grid scrolls inside its card and the page never scrolls sideways (768 and 1024 currently overflow).
- Stav cell: a stay waiting for guests renders `<span class="pill p-warn">` with its current text (today it is plain text, so `main .pill` is missing).
- Tap targets: below 1024 px every `.btn`, `.btn.sm`, the logo link, `summary`, and the row-menu trigger is at least 44x44 px (use `min-height`/`min-width` and padding in the `@media (max-width:1023px)` block, not by changing the desktop look). At 1024 px and above, the row-menu trigger, `summary`, the demo-clear link and the property link in table rows are at least 24 px tall (padding or `display:inline-block; min-height:24px; line-height:24px`).
- Needs-you card overlap (report: "Airbnb: add it as a scheduled" vs "Open the guest message"): inspect at the reported widths; the card's text block must be `min-width:0` and the button must wrap below the text, never sit on top of it.
- Missing English plural: the sidebar shows the raw key `nav.property_count.few` in English. Look at how another plural key (e.g. `dashboard.today.guests`) is defined in `App/app/host_i18n.py` for `en` and `vi`, and add `nav.property_count.few` (and `.many` if that pattern has it) the same way in `host_i18n.py` and `host_vi_i18n.py`.
- `base.html`: bump only the `app2.css` `?v=` key to `20261101-0711`, then from App/ run `.venv/bin/python -m pytest tests/test_static_versions.py -q --write | tail -2`.

## 3. Files
`App/app/static/app2.css`, `App/app/templates/dashboard.html` (Stav pill and card markup only if needed), `App/app/templates/_shell_v2.html` (only if a tap-target fix needs a class), `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`, `App/app/templates/base.html`, `App/tests/static_versions.json`, `App/tests/v2_mockup.py`, screenshots `docs/tasks/screenshots-0711/`, report `docs/tasks/0711-report.md`.

## 4. Steps
1. Colours, 12 px, calendar rules, Stav pill. Commit `0711 step 1: AA colours, calendar card, Stav pill`.
2. Tap targets and card overlap. Commit.
3. Helper overrides (section 2). Commit.
4. Plural key, base.html key, `--write`. Commit.
5. Run the commands; fix until green. `UBYHOST_SHOTS_V2=1` run, copy the app PNGs to `docs/tasks/screenshots-0711/`, Read the 390, 768 and 1280 ones. Commit.

## 5. Do not touch
`App/app/static/dashboard-calendar.js`, `App/app/templates/_dashboard_calendar.html` and `calendar.days14` keys (brief 0712 removes those in parallel). Other pages, other stylesheets, routes.

## 6. Commands (from App/, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py tests/test_0709_v2_overview_shots_browser.py tests/test_a11y_guard_browser.py tests/test_design_guardrails_browser.py tests/test_static_versions.py -q --tb=line -rs 2>&1 | tail -40`. Repo root: `python3 scripts/design_lint.py | tail -2; python3 scripts/context_lint.py 2>&1 | tail -2`.

## 7. Acceptance
All listed tests pass with 0 skipped (the a11y and guardrail tests include `/` with no findings). Design lint and context lint OK. `git diff --stat task/0710-v2-match-tests` shows only section 3 files.

## 8. Stop and ask
Stop if a fix would need a change to an old (non-v2) stylesheet or another page, or if the a11y guard still reports contrast findings after the colour changes (list 10).

## 9. Report
`docs/tasks/0711-report.md`: status, test tails, what changed per finding, screenshots, deviations.
