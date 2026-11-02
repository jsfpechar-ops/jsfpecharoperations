# 0789 brief: Settings and its sub-pages in the Airbnb settings pattern (Josef 15:23)

Status: todo
Executor: Haiku 5.5, alone, on branch `claude/project-thread-vov8xp` (PR #700). Split into parts if over the allowance (one part per page). Josef sees phone screenshots (390) before merge.

## 1. Objective

Josef's reference: Airbnb host app, listing Settings (his screenshots IMG_2197/IMG_2198, 2026-11-02 15:23). Apply the same pattern to `/settings` and every settings sub-page (`/entities`, `/privacy-requests`, `/settings/archived`), phone first, desktop the same structure in the 720 lane:

1. **Header:** a round 40 px light-grey `×` button top left (closes back to the Menu tab / previous page; a plain link, works without JS), then a big bold title ("Settings", 32 px phone) under it. No crumb, no lede.
2. **Pill tabs:** one horizontal, scrollable row of pill tabs under the title (44 px tall, grey fill; the active tab black fill, white text; 12 px apart; no scrollbar). Tabs = the settings groups: Account, Security, Phone app, Data & archive, Privacy, Technical, Help on `/settings` (each tab shows only its group, `?tab=` query param, server-rendered, no JS needed; default Account); the sub-pages (Business & legal details, Data requests, Archive) appear as tabs too and link to their pages, marked active there.
3. **Cards:** one plain bordered card per setting (1 px border, 16 px radius, 24 px padding, 16 px between cards): a medium label (16 px, 500), optionally one short grey qualifier line, and the value big and bold (e.g. "Off", "2", "6 years") or the action button. No section intro text, no descriptions (the help `?` stays next to the label for anything explanatory). A card that edits something opens its form (link or `details`), not inline fields everywhere.
4. Everything Josef already asked for stays: help `?` 8 px after the last word, 12 px minimum between any two controls, no fine print, no element at a card edge.

## 2. Context

0780-0788 briefs and reports. Shared look: `docs/design/MASTER.md` and the phone v2 classes (memory: Airbnb-minimal phone style is approved for the whole app; reuse shared phone classes, `.card`, pills). Geometry tests: `App/tests/test_0786_settings_geometry_browser.py` (help tip, 12 px neighbours, text blocks). Old-shell tests use `/payments`.

## 3. Files

`App/app/templates/settings.html`, `entities.html`, `privacy_requests.html`, `settings_archived.html`, a new shared partial for the header + pill tabs (e.g. `_settings_tabs.html`), the 0780/0781 blocks of `App/app/static/app2.css`, the settings route only if `?tab=` needs passing to the template (read-only, no logic change), tests touching these pages, `base.html` + `static_versions.json` (cache key).

## 4. Steps

1. Test first in `test_0786_settings_geometry_browser.py`: at 390 and 1280, en and cs: the `×` is top left (x < 32) and >= 40 px; the h1 sits below it; the pill row exists, active pill has black background and `aria-current="page"`, pills >= 44 px tall and 12 px apart; every `.card` in main has a 1 px border, radius >= 12, padding >= 20; no card contains a paragraph longer than 60 characters.
2. Build the header partial and tabs; restructure `/settings` into tabbed groups of cards; then the three sub-pages.
3. Keep all existing behaviour tests green (forms, POST targets, help tips without JS, PWA, push, passkeys, 2FA, archive filters).
4. Cache key bump, `tests/test_static_versions.py --write`.
5. Screenshots at 390 and 1280 of every tab and sub-page to `/mnt/project-files/settings-area/airbnb/`.

## 5. Do not touch

`App/app/static/app.js`, Python logic beyond passing `tab`, payments, other pages.

## 6. Commands

From `App/`: `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0786_settings_geometry_browser.py tests/test_host_help_browser.py tests/test_design_settings.py tests/test_settings_technical.py tests/test_operator_naming.py tests/test_pwa.py tests/test_pwa_browser.py tests/test_0710_v2_mockup_match_browser.py -q --tb=line -p no:cacheprovider 2>&1 | grep -E "^(FAILED|ERROR)|^E  |passed|failed" | cut -c1-240 | tail -20` (no `-n`, xdist is not installed). From the repo root: `python3 scripts/design_lint.py`, `python3 scripts/context_lint.py`.

## 7. Acceptance

All pass, 0 skipped; screenshots exist.

## 8. Stop and ask

A Python logic or `app.js` change; a form that cannot work without JS in the new layout.

## 9. Report

`docs/tasks/0789-report.md`: commits, counts, screenshot paths.
