# 0911: App shell fixes: Production badge, 404 inside the app, compact preview banner, menu labels

Status: todo. Source: UX review 2026-11-04 (finding 9, "Production" badge paragraph, the "All pages" and "Account menu" rows). Executor: Haiku 5.5, one run. Run after 0910 is merged.
Read first: AGENTS.md, docs/context/executor.md, this brief.

## 0. Before you start
- Start only after PR #772 is merged. It edits `base.html` and `app2.css`, which this brief edits too. Branch from a fresh `origin/main`.
- No guest or public template. No Payments file.

## 1. Objective
- Customers no longer see the "Production" badge. Admins still see it, and everyone sees it on staging or mock.
- A logged-in 404 renders inside the app shell.
- The support-preview banner stays on one line and says "24 hours left" instead of "1440 minutes left".
- The account menu stops showing two "Help" items.
- The floating Havel button stops covering the bottom of the page.

## 2. Context (verified 2026-11-04)
- The badge appears in two places: `templates/_shell_v2.html:7` and `templates/_shell_sidebar.html:11`, both as `<span class="env-badge ui-env {{ ubyport_env }}" ...>{{ t('env.' ~ ubyport_env) }}</span>`. Values: `prod` ("Production"), `staging`, `mock` (`host_i18n.py` ~594-597). `ubyport_env` is a template global (`templating.py:594`).
- 404: `main.py` ~226-237 `http_error_handler` renders `error.html` with `{"error_kind": "not_found"}`. `templates/error.html` (7 lines) extends `auth_base.html` and fills `auth_body`. Other pages fill `{% block body %}` in `base.html` (see `guide.html:9`). `error.html` also renders `error_kind == "server"`, which must stay on `auth_base.html`.
- Preview banner: `templates/base.html` 136-151 (`.impersonation-bar`). Minutes are shown at 142-145 with `tp('impersonation.minutes_left', support_minutes)`. CSS is in `static/app.css` 628-664. No JS updates the minutes.
- Keys: `impersonation.minutes_left`, `.one`, `.few` in `host_i18n.py` en ~623-625 and cs ~2692-2694; vi `host_vi_i18n.py` ~736 (check whether vi has `.one`/`.few`: `grep -n "impersonation.minutes_left" App/app/host_vi_i18n.py`).
- Account menu: `nav.guide` = "Help" (`host_i18n.py:31`). `nav.support` = "Help & support" in en (`host_i18n.py:109`), "Nápověda a podpora" in cs (`:2176`), "Trợ giúp và hỗ trợ" in vi (`host_vi_i18n.py:370`). It is used in `_shell_sidebar.html:41` and `_shell_v2.html:42`.
- Havel button: `static/app2.css:754` `body.v2 .havel-fab{position: fixed; right: var(--space-6); bottom: var(--space-6); ...}`, hidden at phone width by `app2.css:131`. Main element: `base.html:60` `<main id="main-content" class="main">` (v2) and `:66` (old shell).

## 3. Files
`templates/_shell_v2.html`, `templates/_shell_sidebar.html`, `templates/error.html`, `templates/base.html` (lines 142-145 only), `static/app.css` (628-664 only), `static/app2.css` (one appended rule), `host_i18n.py`, `host_vi_i18n.py`, the cache keys of `app.css`/`app2.css`, and the tests.

## 4. Steps
1. **Badge.** In both shell files, wrap the `<span class="env-badge ...">` in `{% if ubyport_env != 'prod' or (current_user and current_user.role == 'admin') %}...{% endif %}`.
2. **404 in the shell.** Replace `templates/error.html` with:
   ```jinja
   {% extends ("base.html" if current_user and error_kind == 'not_found' else "auth_base.html") %}
   {% block title %}{{ t('error.' ~ error_kind ~ '.title') }} · UbyHost{% endblock %}
   {% block body %}
   <div class="head"><div><h1 class="big">{{ t('error.' ~ error_kind ~ '.title') }}</h1></div></div>
   <p>{{ t('error.' ~ error_kind ~ '.body') }}</p>
   <p><a class="ui-btn ui-btn-primary" href="/">{{ t('error.home') }}</a></p>
   {% endblock %}
   {% block auth_body %}
   <h1>{{ t('error.' ~ error_kind ~ '.title') }}</h1>
   <p class="lede">{{ t('error.' ~ error_kind ~ '.body') }}</p>
   <p><a class="btn primary" href="/">{{ t('error.home') }}</a></p>
   {% endblock %}
   ```
   If rendering fails because `base.html` needs a variable the handler does not pass (for example `nav`), add `{% set nav = '' %}` at the top. Do not edit `main.py` unless that is impossible; if it is, STOP.
3. **Hours, not minutes.** In `base.html` 142-145, inside the existing `{% if support_minutes is not none %}`, show `tp('impersonation.hours_left', support_minutes // 60)` when `support_minutes >= 120`, else the current minutes text. Keep the `data-impersonation-minutes` attribute. New keys:
   - en: `impersonation.hours_left` "%(count)s hours left", `.one` "%(count)s hour left", `.few` "%(count)s hours left".
   - cs: "zbývá %(count)s hodin", `.one` "zbývá %(count)s hodina", `.few` "zbývají %(count)s hodiny".
   - vi: "Còn %(count)s giờ", plus `.one`/`.few` only if vi has them for minutes.
4. **One-line banner.** Read `app.css` 628-664. Set `.impersonation-bar` to `display:flex; align-items:center; flex-wrap:nowrap; gap:12px` (keep its other declarations). Set `.impersonation-copy` to `flex:1 1 auto; min-width:0; display:flex; flex-wrap:wrap; align-items:baseline; column-gap:12px`. Keep `.impersonation-bar form { margin:0; flex:0 0 auto; }`. Write no fixed px except the 12px gap (MASTER tokens if `var(--space-3)` equals 12px: check `grep -n "\-\-space-3:" App/app/static/tokens.css`).
5. **Menu labels.** `nav.support` becomes en "Contact support", cs "Kontaktovat podporu", vi "Liên hệ hỗ trợ". `nav.guide` stays "Help".
6. **Havel button clearance.** Append to `app2.css`, under the same media condition in which `.havel-fab` is visible (read `app2.css` 128-133 to get it): `body.v2 #main-content{padding-bottom:calc(var(--control-h) + var(--space-3) + var(--space-6) * 2)}`. If `grep -n "havel-fab" App/app/static/host2.css` finds a fixed button for the old shell, add the same rule there for `#main-content`.
7. Bump the `?v=` keys of `app.css` and `app2.css` (`grep -rn "static/app2\?.css?v=" App/app/templates | head`). Follow `test_static_versions.py`.
8. **Confirm only (no code).** The review says Settings → Account and Security show no preview banner. Read `base.html:136` (the condition `current_user.id != workspace_user.id`) and grep `workspace_user` in `routes/admin.py` around `_settings_page`. Report in one line whether those two groups set `workspace_user` to the admin on purpose (owner already confirmed they show the admin's own data). Change nothing.
9. **Screenshot check (no code).** In the 1280 shot of any host page, open the account menu (the test may already do this; if not, skip) and report whether it covers nav items. Report only.

## 5. Do not touch
`main.py` (unless step 2 forces it: STOP first), guest and public templates, Payments files, `_components.html`, `layout_lint.js`.

## 6. Commands (from `App/`, `2>&1 | tail -30`)
- New tests in `tests/test_0911_shell.py`:
  - a customer page HTML has no `env-badge` when `UBYPORT_ENV=prod`; admin HTML has it;
  - logged-in GET `/does-not-exist` returns 404 with `id="app-sidebar"`; logged-out GET returns 404 without it;
  - an impersonation page with 1440 minutes left shows "24 hours left".
- `.venv/bin/python -m pytest tests/test_0911_shell.py tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_admin_customers.py -q --tb=short -x -rs`, 0 skipped.
- Copy row: `test_*_i18n.py test_no_em_dashes.py test_flash_literals.py`.
- UX gate: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x -rs`, 0 skipped. Open the 390/768/1280 shots of the dashboard (sidebar and badge) and one settings page. Take one 390 px Chromium screenshot of the logged-in 404 and one of a page in admin preview (banner) with your own small Playwright snippet inside the new test, saved under `/tmp/shots/0911/`. PR body: per page "390: ...; 768: ...; 1280: ...".
- `python3 scripts/context_lint.py`.

## 7. Acceptance
- [ ] Customer on prod: no badge. Admin or staging: badge shown.
- [ ] Logged-in 404 sits inside the sidebar shell with the preview banner when previewing. A 500 still uses the auth layout.
- [ ] The banner is one row at 768 and 1280 px, "Exit preview" stays on the right, and the text reads "24 hours left".
- [ ] The account menu has "Help" and "Contact support".
- [ ] The Havel button covers no content at the page bottom (1280 shot).
- [ ] Light mode only, 12 px neighbour rule, no new dependency.

## 8. Stop and ask
An anchor is missing; `base.html` cannot render for the 404 without editing `main.py`; PR #772 is not merged yet.

## 9. Report
`docs/tasks/0911-report.md`, with the results of steps 8 and 9 and the 390 px shots (404, banner, dashboard).
