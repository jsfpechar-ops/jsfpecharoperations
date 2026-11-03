# 0780 brief: Settings page on the v2 look

Status: todo
Executor: Haiku 5.5, alone, in the worktree `/tmp/wt0780` (branch `task/0780`, already checked out; do not switch branches, do not push).

## 1. Objective

`/settings` (`App/app/templates/settings.html`) moves onto the v2 shell (`app2.css`, like `reservations.html`) and looks like
the `data-v="settings"` screen of `docs/design/mockup/ubyhost-redesign-v2.html`: header with only the h1 "Nastavení",
one 720 px column, each group = an `h2` title followed by ONE white card holding that group's sections.
Restyle only: every form, button, link, id, `name=` and route stays; no copy changes except removing the lede.

## 2. Context

- Mockup: lines ~240-250 of `docs/design/mockup/ubyhost-redesign-v2.html` (`.view.set`, `.card .row`). Do not edit the mockup.
- Pattern to copy: top of `App/app/templates/reservations.html` (`{% set v2 = true %}`, empty `page_title`/`meta`/`primary_action`/`secondary_actions` blocks, `<div class="head ..."><div><h1 class="big">…</h1></div></div>` as the first body markup). Exactly one visible h1.
- v2 pages load ONLY `tokens.css` + `app2.css` (see `App/app/templates/base.html` lines 19-35). Anything settings used from `host.css`, `components.css`, `host-controls.css`, `host2.css` is unstyled after the switch: you add what is needed to `app2.css`.
- Macro `settings_group` in `App/app/templates/_components.html` ~line 530 (used only by settings.html).
- Phone (below 1024 px) uses the shared phone v2 classes already in app2.css (0718 `.card`, `h2.sec`, 0735 `.mh`); see `App/app/templates/menu.html` for a phone page header.

## 3. Files

`App/app/templates/settings.html`, `App/app/templates/_components.html` (only `settings_group`), `App/app/static/app2.css`,
`App/app/templates/base.html` (cache key), `App/tests/static_versions.json`, `App/tests/v2_mockup.py`, `docs/design/catalog.json`,
tests allowed by the standing rule in step 6, new `docs/tasks/0780-report.md`.

## 4. Steps

1. `settings.html`: add `{% set v2 = true %}` under the extends line; empty blocks `page_title`, `meta` (lede removed), `primary_action`, `secondary_actions`.
   First markup in `body`: `<div class="head settings-head"><div><h1 class="big">{{ t('nav.settings') }}</h1></div></div>`, then wrap the rest of the body in `<div class="settings-lane">`.
2. Delete the `<nav class="host-property-grid">` card index (lines ~12-17). Its billing link must survive: inside the account group's card add, when `billing_on()`, a row
   `<a class="set-row" href="/predplatne"><span>{{ t('billing.plan.title') }}</span><span class="set-row-v">{{ t('common.open') }}</span></a>`.
3. `settings_group` macro: keep the `section`, its id and `aria-labelledby`; the h2 gets `class="settings-group-title sec"`; wrap `{{ caller() }}` in `<div class="card settings-card">`.
4. `app2.css`: add ONE block at the end titled `/* 0780 settings page (v2) */` with page rules only (`.settings-*`, `.set-row`):
   - `.settings-lane{max-width:720px}`; group title like the mockup `main h2` (check its computed size in the mockup, do not invent); first group no top margin.
   - inside `.settings-card`: each `.ui-section` separated by a 1px `var(--line)` hairline, 16 px vertical padding, none above the first; the old `h2`/`h3` inside sections render 16px/700, no coloured bar or background.
   - `.set-row`: flex, space-between, min-height 48px, label ink, value `var(--ink3)` (mockup `.card .row`).
   - From 1024 px buttons are 40 px high, below 1024 px 44 px (tap rule).
   Generic old classes the page needs (fields, `.ui-pair`, `.checkline`, `.help-tip`, `.heading-with-tip`, `details.technical`, passkey and device lists, `.host-audit-filter`): look first whether app2.css already styles them; if not, add them in a block at the very end titled `/* v2 ports of shared ui-* classes */` (another thread may add the same block: keep rules generic, short, values from tokens.css).
5. New classes into `docs/design/catalog.json`; from the repo root `python3 scripts/design_lint.py 2>&1 | tail -5`.
   Cache key: app2.css `?v=` in base.html to `20261102-0780`, then from `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`.
6. `App/tests/v2_mockup.py`: add a PAGES entry `{"name": "settings", "path": "/settings", "view": "settings", "selectors": [".side .nav.on", ".head h1", "main h2", "main .card"]}`.
   Standing rule for tests: you may update assertions that check the OLD settings markup (the `host-property-grid` index, the lede, `settings-group-title` without `sec`, host.css-only classes) to the new markup. Never delete an assertion about a form, link, route or behaviour. If anything else fails, stop and write it in the report.
7. Tests, from `App/` (do NOT reinstall playwright; the venv pins 1.63.0 for /opt/pw-browsers):
   `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k settings -q --tb=short -x 2>&1 | tail -30`
   Style failures: fix the CSS. Box failures caused only by text length: a `"selector@width"` BOX_OVERRIDES entry under `# text-dependent: settings copy vs mockup (0780)`.
   Then: `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_design_settings.py tests/test_settings_data_panel.py tests/test_settings_technical.py tests/test_push_settings_browser.py tests/test_passkeys.py tests/test_two_factor_setup_page.py tests/test_static_versions.py -q --tb=short 2>&1 | tail -30` (0 skipped).
8. Screenshots: `UBYHOST_SHOTS_V2=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k screenshots -q 2>&1 | tail -5`; list the settings-*.png paths in the report. Do not commit other changed PNGs (`git checkout -- docs/tasks/screenshots-*` for files you did not create).
9. From the repo root `python3 scripts/context_lint.py 2>&1 | tail -5`. Commit (do not push): `0780: settings page on the v2 look` ending with
   ```
   Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>
   ```

## 5. Do not touch

`App/app/static/app.js`, the mockup, other pages' templates, existing app2.css blocks of other pages, any route or Python file.

## 6. Commands

The test commands in section 4, run from `App/`, plus `python3 scripts/design_lint.py` and `python3 scripts/context_lint.py` from the repo root.

## 7. Acceptance

- Step 7 commands pass with 0 skipped; one visible h1; no sideways scroll at 320-1440 (0710 geometry).
- `git grep -n "host-property-grid" App/app/templates/settings.html` prints nothing.

## 8. Stop and ask

A non-settings test fails; a form needs a markup change beyond steps 1-3; you reach 25 tool calls (commit what passes, report the rest).

## 9. Report

`docs/tasks/0780-report.md`: commits, test results with counts, screenshot paths, anything stopped on.
