# 0709: drop the global restyle, phone layout and lint for the v2 Overview
Status: todo
Depends on: 0707 | Base commit: task/0707-v2-polish | Branch: task/0709-v2-cleanup
Executor: Haiku 5.5 | Fits one session: 30 tool calls

## 1. Objective
(a) Remove the earlier global restyle (briefs 0700-0704) so every page except the v2 Overview looks and behaves exactly as on `origin/main`. (b) Make the v2 Overview usable at 390 px. (c) Design lint green. (d) Stav pill for finished stays.

## 2. Context
- Owner chose 2026-11-01 14:33 to rebuild pages from the mockup on the opt-in v2 shell; the global overrides from 0700-0704 broke other pages' tests and are no longer wanted.
- Restore these files to their `origin/main` content (`git fetch origin main` first, then `git checkout origin/main -- <file>`): `App/app/static/tokens.css`, `App/app/static/host.css`, `App/app/static/host-design0123.css`, `App/app/static/host2.css`, `App/app/static/wizard.css`, `App/app/static/workflow.css`, `App/app/static/dashboard-calendar.css`, `App/app/templates/_shell_sidebar.html`, `docs/design/MASTER.md`, `App/tests/test_0284_states_browser.py`, `App/tests/test_design_guardrails_browser.py`, `App/tests/test_design_tokens.py`, `App/tests/test_signed_in_chrome.py`, `App/tests/test_design_shell_browser.py`. Delete `App/tests/test_0700_shared_look_browser.py`, `App/tests/test_0701_overview_cards_browser.py` (first copy its screenshot test into `App/tests/test_0709_v2_overview_shots_browser.py`, same env var name `UBYHOST_SHOTS_0701` renamed to `UBYHOST_SHOTS_V2`), `App/tests/test_0702_overview_calendar_card_browser.py`, `App/tests/test_0703_look_finish_browser.py`. Keep `App/tests/test_0703_look_finish.py` (the `date_long` filter stays; v2 Overview uses it).
- In `App/app/static/dashboard-calendar.js` remove the single `root.classList.toggle("is-fixed-days", ...)` line (0702); keep the 0521 14-day logic.
- In `App/app/static/app2.css` set `--acc:#d0452d; --accs:#fdece8` as literals (tokens.css goes back to the old brick coral; #d0452d is the AA-safe mockup coral).
- In `docs/design/catalog.json` remove the 0520 entries `dashboard-quiet`, `dashboard-today` (no longer used) if `grep -rn 'dashboard-quiet\|dashboard-today' App/app/templates` finds nothing. Then make design lint skip v2 templates: in `scripts/design_lint.py` add a constant `V2_TEMPLATES = {"App/app/templates/dashboard.html", "App/app/templates/_shell_v2.html"}` with comment `# v2 pages are styled by app2.css copied from the approved mockup (2026-11-01); their classes are not in the catalog` and skip T3 for those paths. Keep all other checks.
- `base.html`: set every stylesheet `?v=` key back to its origin/main value except `app2.css` (bump to `20261101-0709`); `--write` static versions.
- Phone (390 px) for v2: in `app2.css` `@media (max-width:767px)`: page must not scroll horizontally. `.side` top bar: one row, `overflow-x:auto`, logo + nav items only (hide account card, search, bottom block); `.main` padding 16px; `.head` wraps, button full width below the title; `.todo` one column; `.cal` keeps `overflow-x:auto` inside its card (grid scrolls inside the card, page does not); Dnes table: hide the Nemovitost and Termín columns (`th:nth-child(2), td:nth-child(2), th:nth-child(3), td:nth-child(3)`) so it fits.
- Dnes Stav: rows with status reported/not_required get `<span class="pill p-ok">` with the existing "reported" status text (find the key: `grep -n '"status.reported\|nahlášeno' App/app/host_i18n.py | head -5`) instead of the next_action text.

## 3. Files
As listed above plus `App/app/templates/base.html`, `App/tests/static_versions.json`, `App/app/templates/dashboard.html` (Stav only), new `App/tests/test_0709_v2_overview_shots_browser.py` (also asserts at 390 px `document.documentElement.scrollWidth <= 390`). Screenshots `docs/tasks/screenshots-0709/` (1280 and 390, cs). Report `docs/tasks/0709-report.md`.

## 4. Steps
1. Restore/delete files, JS line, app2 literals. Commit `0709 step 1: drop the global restyle`.
2. Catalog + design lint skip. Commit.
3. base.html keys + `--write`. Commit.
4. Phone CSS + Stav. Commit.
5. Test + screenshots (Read both PNGs and check them). Commit.

## 5. Do not touch
Dashboard tests (brief 0708 is updating them in parallel), routes, other templates.

## 6. Commands (from App/, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`.venv/bin/python -m pytest tests/test_0709_v2_overview_shots_browser.py tests/test_design_tokens.py tests/test_signed_in_chrome.py tests/test_design_guardrails_browser.py tests/test_0284_states_browser.py tests/test_0285_rows_browser.py tests/test_host_list_page_layout_browser.py tests/test_onboarding_wizard_browser.py tests/test_shell_lane_browser.py tests/test_a11y_guard_browser.py tests/test_static_versions.py tests/test_0703_look_finish.py -q --tb=line -rs 2>&1 | tail -30` (a11y may report findings on `/` only; list them). Repo root: `python3 scripts/design_lint.py | tail -2; python3 scripts/context_lint.py 2>&1 | tail -2`.

## 7. Acceptance
`git diff --stat origin/main -- App/app/static/tokens.css App/app/static/host.css App/app/static/host-design0123.css App/app/static/host2.css App/app/static/wizard.css App/app/static/workflow.css App/app/templates/_shell_sidebar.html` is empty. Listed tests pass except a11y findings on `/` (report them). Design lint OK. 390 px has no horizontal page scroll.

## 8. Stop and ask
Stop if restoring a file removes something 0520, 0521 or 0705-0707 need (check with grep before restoring).

## 9. Report
`docs/tasks/0709-report.md`: status, tails, a11y findings on `/`, screenshots, deviations.
