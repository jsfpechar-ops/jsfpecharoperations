# 0705: v2 shell built from the mockup HTML (opt-in per page)
Status: todo
Depends on: none | Base commit: claude/project-thread-50hyv5 | Branch: task/0705-v2-shell
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
Owner decision 2026-11-01 14:33: rebuild pages straight from the approved mockup `/mnt/project-files/ux-redesign/ubyhost-redesign-v2.html` instead of restyling old components. This brief builds the shared shell: a page that sets `{% set v2 = true %}` gets ONLY `tokens.css` + a new `app2.css` (mockup CSS) and a new sidebar copied from the mockup's `<aside class="side">`. Pages without `v2` are unchanged. Brief 0706 then rebuilds the Overview on this shell.

## 2. Context
- `App/app/templates/base.html` lines ~19-33 load the old stylesheets; line ~36 includes `_shell_sidebar.html`. Pages set `nav` at top level (e.g. `{% set nav = 'dashboard' %}`); top-level sets are visible to base.html, so `v2` works the same way.
- Mockup CSS: the `<style>` block of the mockup file (top ~60 lines). Mockup sidebar markup: the `<aside class="side">` block (~line 65-78). Copy both literally, then: drop the font-picker rules, `body.f-*` rules, `[data-v]`/`.view` demo switching, the `.foot` design note, and anything for views other than the shell and the "today" view (keep generic ones: `.head h1 .sub .btn .btn.ghost .btn.sm h2 .card .chip table th td .pill .p-* .todo .ic .t .quiet .cgrid .cd .crow .cn .bar .b-* .note .badge .logo .nav .me .side .main .search`).
- Colours: keep the mockup values but take the coral from the token: `--acc: var(--coral-600)` (AA-safe #d0452d) and `--accs: var(--coral-100)`. Font: `font-family: var(--font-sans)` (Manrope, self-hosted; check the token name in `tokens.css`).
- design_lint (`scripts/design_lint.py`) only checks files listed in `docs/design/catalog.json`. Do not add app2.css or the new templates to that catalog's checked lists (raw mockup hex values are intended here); if lint still flags them, add them to the lint's allow/legacy list the way other legacy files are listed, and say so in the report.

## 3. Files
Create `App/app/static/app2.css`, `App/app/templates/_shell_v2.html`. Edit `App/app/templates/base.html` (v2 branch only), `App/tests/static_versions.json` (via `--write`). Create `App/tests/test_0705_v2_shell_browser.py`. Report `docs/tasks/0705-report.md`.

## 4. Steps
1. `app2.css`: the mockup CSS as described, plus a phone rule `@media (max-width: 767px)`: `.side` becomes a full-width top bar (position static, height auto, flex-direction row, overflow-x auto, nav items without text wrap; hide `.search`, `.me` small line), `.main` padding 16px, `.todo` one column. Commit `0705 step 1`.
2. `_shell_v2.html`: the mockup `<aside class="side">` with real data: logo "UbyHost" (keep the existing logo mark SVG/IMG from `_shell_sidebar.html` if it has one, else text); the account card at the top (`workspace_user.display_name or workspace_user.username`, small line = property count `tp('nav.property_count', apartments|length)` only if `apartments` is defined, else `t('nav.account')`), links to `/settings`; the search box as a link/button opening the existing command palette (reuse the attribute the old sidebar's search trigger uses); nav links in the mockup order with the mockup icons and real hrefs and labels from the old sidebar (`/`, `/reservations`, `/apartments`, `/cleaning`, payments, stay fees, `/settings`; copy hrefs and `t()` keys from `_shell_sidebar.html`), class `nav on` + `aria-current="page"` for the current `nav`; Přehled badge = number of needs-you lines if the page passes `nav_badge`; bottom: "Pomoc a Havel" (`/guide`, label from `t('nav.guide')`), admin link if admin, account row with logout form copied from the old sidebar (same form, same CSRF field). Add `nav.property_count` keys (en "%(count)s properties"/.one "1 property"; cs "%(count)s nemovitostí"/.one "1 nemovitost"/.few "%(count)s nemovitosti"; vi "%(count)s chỗ ở") in `App/app/host_i18n.py` / `host_vi_i18n.py` (allowed files). Commit `0705 step 2`.
3. `base.html`: when `v2 | default(false)`: load only `tokens.css`, the font preload, `app2.css?v=20261101-0705`, then `{% block head_extra %}`; body class `v2`; include `_shell_v2.html` instead of `_shell_sidebar.html`; wrap content in `<main id="main-content" class="main">`. Keep every script tag as is. Everything else unchanged for non-v2 pages. `--write` static versions. Commit `0705 step 3`.
4. Test (`test_0705_v2_shell_browser.py`): render a tiny v2 page through an existing route is not possible yet, so test with Jinja directly: render `base.html` with `v2=True` and minimal context (copy how `tests/test_design_dashboard.py` or another template test builds a request/context; if too heavy, render through the dashboard route after 0706 — then mark this test as TODO in the report and test only that non-v2 `/` still loads the old CSS list). Commit `0705 step 4`.

## 5. Do not touch
Old stylesheets, old `_shell_sidebar.html`, JS, routes.

## 6. Commands (from `App/`, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`.venv/bin/python -m pytest tests/test_0705_v2_shell_browser.py tests/test_static_versions.py tests/test_design_dashboard.py tests/test_privacy_first.py -q --tb=short -rs 2>&1 | tail -20`; `python3 scripts/design_lint.py | tail -2`; `python3 scripts/context_lint.py 2>&1 | tail -2` (repo root).

## 7. Acceptance
Non-v2 pages render exactly as before (same CSS list). All listed tests pass.

## 8. Stop and ask
Stop if base.html's structure makes a clean v2 branch impossible without touching non-v2 output.

## 9. Report
`docs/tasks/0705-report.md`: status, tails, diff stat, deviations.
