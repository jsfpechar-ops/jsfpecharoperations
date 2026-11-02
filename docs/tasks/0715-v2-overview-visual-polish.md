# 0715: Overview visual polish found in the 6-size screenshots
Status: todo
Depends on: 0714 | Base commit: claude/project-thread-50hyv5 | Branch: task/0715-v2-overview-polish
Executor: Haiku 5.5 | Fits one session: 30 tool calls

## 1. Objective
Fix what the orchestrator saw in `docs/tasks/screenshots-0710/overview-{390,768,1280}.png` compared with `mockup-today-1280.png`. Read those PNGs first.

## 2. Context and decisions (orchestrator, 2026-11-01)
1. Header quiet links ("How does this work? · + Cleaning · Clear demo data"): today they break over two lines with a dangling "·" and, on phone, a large gap. Put them in one flex row (`display:flex; flex-wrap:wrap; gap:4px 14px; align-items:center`), drop the "·" separators from the markup, and keep each link's tap target (44 px below 1024, 24 px above). On phone they may wrap but no orphan separator.
2. Stav column: "Waiting for guest" is plain text; the mockup shows a warn pill ("Čeká na 2 ze 3 hostů"). Render every Stav state as a pill: waiting/incomplete → `pill p-warn`, failed/overdue → `pill p-bad`, reported/not required → `pill p-ok`. Then remove `main .pill` from `missing_ok` in `App/tests/v2_mockup.py`.
3. Calendar bars show "Pobyt" in the English page. The fallback label must come from i18n: find the stay label key (`grep -n '"Pobyt"\|calendar.stay\b' App/app/host_i18n.py App/app/routes/admin.py`) and use `t(...)` for the current language (en "Stay", cs "Pobyt", vi from host_vi_i18n). Where `_overview_calendar_rows` builds the label, keep the order: source/summary name, then the translated fallback, plus " · N".
4. Tablet (768-1023 px): the two-column "What needs you" cards are cramped next to the 220 px sidebar. Make `.todo` one column below 1024 px (still two columns at 1024+). Update geometry check 8 in `v2_mockup.py` accordingly (two columns at >= 1024, one column below 1024).
5. Phone month line ("This month 1 guest · 12 nights · 0 reported…") wraps awkwardly at 390. Let it wrap as whole items: each `<b>` + its word stays together (`white-space:nowrap` on each item group); add wrapping spans in dashboard.html if needed.
6. The mockup screenshots are taken mid fade-in. In `App/tests/test_0710_v2_mockup_match_browser.py` and `v2_mockup.py`, open both pages with `reduced_motion="reduce"` (browser context option) so screenshots and computed styles are final.
- Then bump the app2.css key in `base.html` to `20261101-0715` and from App/ run `.venv/bin/python tests/test_static_versions.py --write | tail -1`. Regenerate the 0710 screenshots (`UBYHOST_SHOTS_V2=1`) and Read the 390, 768 and 1280 app PNGs and the 1280 mockup PNG; commit only `docs/tasks/screenshots-0710/` PNGs (revert any other regenerated evidence PNGs under docs/tasks).

## 3. Files
`App/app/static/app2.css`, `App/app/templates/dashboard.html`, `App/app/routes/admin.py` (label only), `App/app/host_i18n.py` / `App/app/host_vi_i18n.py` (only if a new key is needed), `App/app/templates/base.html` (key), `App/tests/static_versions.json`, `App/tests/v2_mockup.py`, `App/tests/test_0710_v2_mockup_match_browser.py`, `docs/tasks/screenshots-0710/*.png`, report `docs/tasks/0715-report.md`.

## 4. Steps
1. Items 1, 2, 5 (template + CSS). Commit.
2. Items 3, 4, 6. Commit.
3. Key, manifest, screenshots, commands. Commit + report.

## 5. Do not touch
`app.js`, `dashboard-calendar.js`, other pages and stylesheets.

## 6. Commands (from App/, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py tests/test_0709_v2_overview_shots_browser.py tests/test_a11y_guard_browser.py tests/test_design_guardrails_browser.py tests/test_dashboard_queue_copy.py tests/test_0520_overview_today.py tests/test_static_versions.py -q --tb=line -rs 2>&1 | tail -30` (0 skipped). Repo root: `python3 scripts/design_lint.py | tail -1; python3 scripts/context_lint.py | tail -1`.

## 7. Acceptance
All listed tests pass, 0 skipped; screenshots show the six items fixed.

## 8. Stop and ask
Stop if a Stav state has no clear tone (list it) or the label key does not exist in all three languages.

## 9. Report
`docs/tasks/0715-report.md`: status, test tails, per item what changed, deviations.
