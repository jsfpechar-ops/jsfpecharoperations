# 0781 brief: Společnosti, Soukromí (privacy requests) and Archiv on the v2 look

Status: todo
Executor: Haiku 5.5, alone, in the worktree `/tmp/wt0781` (branch `task/0781`, already checked out; do not switch branches, do not push).

## 1. Objective

Three old-look pages move onto the v2 shell (`app2.css`, like `reservations.html`) and use the mockup's list look
(`docs/design/mockup/ubyhost-redesign-v2.html`, `data-v="props"`: `.head` with h1 left and at most one button right, then a white `.card` holding a `<table>`):
- `/entities` (`entities.html`): companies table + its add/edit form. The form sits in its own `.card` under the table, fields in one column (pairs side by side from 1024 px), actions row at the end, primary right.
- `/privacy-requests` (`privacy_requests.html`): one form in one `.card`, 720 px lane, inputs all the same height (the 0711 v2 control height), no 1080 px wide inputs.
- `/settings/archived` (`settings_archived.html`): the type chips stay chips (`.chips`/`.chip` look from the stays page), each table in a `.card`.
Restyle only: every form, `name=`, id, link, route and row menu stays; no copy changes except removing the meta lede where the mockup head has none (keep it as `.head .sub` if it explains something the page needs).

## 2. Context

- Pattern: top of `App/app/templates/reservations.html` (`{% set v2 = true %}`, empty `page_title`/`meta`/`primary_action`/`secondary_actions`/`tabs` blocks, `<div class="head"><div><h1 class="big">…</h1></div>…</div>` first in `body`). Exactly one visible h1 per page.
- v2 pages load ONLY `tokens.css` + `app2.css` (`App/app/templates/base.html` lines 19-35); classes these pages took from `components.css`/`host.css` (`ui-table`, `ui-table-stack`, `ui-field`, `ui-pair`, `ui-chips`, `row-menu*`, `ui-badge`, `ui-empty`, `table-cards`, `panel`) are unstyled after the switch.
- Reuse first: stays list classes in app2.css (0526/0527/0750 blocks: `.card` table, `.chips`, row menus). Phone (below 1024 px): rows become the shared phone list look (0750 stays block, `.list`, `.row`), table hidden or stacked as the stays page does; no sideways page scroll at 320.
- Another thread (settings, 0780) and the guest book/invoices thread may add the block `/* v2 ports of shared ui-* classes */` at the end of app2.css. Add generic ports only there, short and token-based; page rules in your own block.
- `entities.html` uses `{% block tabs %}{{ ui_section_tabs() }}{% endblock %}` and `back_url`: drop the tabs (v2 has no tab strips); keep the back link only when `next_path` is set (a `crumb` line above the h1, mockup `.crumb`).
- Sidebar/tab bar: `App/app/templates/_shell_v2.html` line ~50: add `'entities', 'privacy_requests'` to both `nav in [...]` lists of the Menu tab so the phone tab bar marks Menu. Change nothing else in the shell.

## 3. Files

The three templates, `App/app/templates/_shell_v2.html` (step above only), `App/app/static/app2.css`, `App/app/templates/base.html` (cache key),
`App/tests/static_versions.json`, `App/tests/v2_mockup.py`, `docs/design/catalog.json`, tests allowed by the standing rule, new `docs/tasks/0781-report.md`.

## 4. Steps

1. Switch each template to v2 as in section 2. One page per commit is fine.
2. `app2.css`: one block per page at the end of the page blocks: `/* 0781 entities */`, `/* 0781 privacy requests */`, `/* 0781 archive */`; generic ports in `/* v2 ports of shared ui-* classes */` at the very end. From 1024 px controls/buttons 40 px high, below 1024 px 44 px.
3. New classes into `docs/design/catalog.json`; from the repo root `python3 scripts/design_lint.py 2>&1 | tail -5`.
   Cache key: app2.css `?v=` in base.html to `20261102-0781`, then from `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`.
4. `App/tests/v2_mockup.py`: three PAGES entries, `"view": "props"`, selectors `[".head h1", "main .card"]`: `{"name": "entities", "path": "/entities", ...}`, `{"name": "privacy_requests", "path": "/privacy-requests", ...}`, `{"name": "archive", "path": "/settings/archived", ...}`.
   Standing rule for tests: you may update assertions on the OLD markup of these three pages (section tabs, `panel`, `table-cards`, `lc-entities`, lede text, host.css-only classes). Never delete an assertion about a form, field, link, route or behaviour. Anything else failing: stop, write it in the report.
5. Tests from `App/` (do NOT reinstall playwright):
   `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k "entities or privacy_requests or archive" -q --tb=short -x 2>&1 | tail -30`
   Style failures: fix the CSS. Box failures caused only by text length: a `"selector@width"` BOX_OVERRIDES entry under `# text-dependent: app copy vs mockup (0781)`.
   Then: `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_entity_editor_fields.py tests/test_entity_editor_navigation.py tests/test_invoice_entity.py tests/test_privacy_requests.py tests/test_archive_stays_on_page.py tests/test_host_account_navigation.py tests/test_design_shell.py tests/test_static_versions.py -q --tb=short 2>&1 | tail -30` (0 skipped).
6. Screenshots: `UBYHOST_SHOTS_V2=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k screenshots -q 2>&1 | tail -5`; list the new entities-/privacy_requests-/archive-*.png paths in the report; do not commit PNGs you did not create.
7. From the repo root `python3 scripts/context_lint.py 2>&1 | tail -5`. Commit (do not push): `0781: companies, privacy requests and archive on the v2 look` ending with
   ```
   Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>
   ```

## 5. Do not touch

`App/app/static/app.js`, the mockup, settings.html, other pages' templates and app2.css blocks, Python routes.

## 6. Acceptance

Step 5 passes with 0 skipped; one visible h1 per page; no sideways scroll at 320-1440.

## 7. Stop and ask

A test outside step 5 fails; a form needs markup changes beyond wrappers and classes; you reach 25 tool calls (commit what passes, report the rest).
