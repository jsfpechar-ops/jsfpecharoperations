# 0789 brief: Settings and its sub-pages in the Airbnb settings pattern (Josef 15:23)

Status: todo
Executor: Haiku 5.5, alone, on branch `claude/project-thread-vov8xp` (PR #700). Split into parts if over the allowance (one part per page). Josef sees phone screenshots (390) before merge.

## 1. Objective

Josef's references (Airbnb host app, 2026-11-02 15:23), saved in `/mnt/project-files/settings-area/airbnb-ref/`: IMG_2199 (account settings index), IMG_2200/IMG_2201 (a sub-page such as Privacy), IMG_2197/IMG_2198 (pill tabs + value cards). Open them before you start. Apply to `/settings` and every settings sub-page at **every width** (Josef 15:25: "apply this Airbnb to everywhere, even on desktop and tablet"): phone, tablet (768-1023, icon rail) and desktop use the same index list, back button, big title, sub-pages, toggles, value cards and pills, centred in the 720 lane. No desktop-only cards, tiles or two-column grids on these pages.

1. **`/settings` becomes an index (IMG_2199):** a round 40 px light-grey back button top left (`←`, a plain link to the Menu tab / previous page), a big bold title "Settings" (32 px phone), then a plain list with no cards: per row a 24 px line icon, the label (17 px), a chevron `›` at the right; 64 px rows, no descriptions; a 1 px divider between groups. Rows: Account, Login & security, Phone app, Data & archive, Business & legal details (`/entities`), Data requests (`/privacy-requests`), Archive (`/settings/archived`), Technical, Help.
2. **Each group opens its own sub-page** (`/settings/<group>`, server-rendered; reuse the existing forms and POST targets unchanged; a route that only renders a template slice is fine): back button + big title, then section headers (h2, 20 px bold) and rows like IMG_2200/2201: toggle rows (label left, switch right) for on/off settings, bordered cards with a chevron for links, value cards (label + big bold value, IMG_2198) for read-only values like retention years or PIN state.
3. **Pill tabs (IMG_2197)** only where one sub-page has several parallel views (e.g. Archive types, activity filters): horizontal scrollable pills, 44 px tall, grey fill, active black with white text, 12 px apart.
4. Everything Josef already asked for stays: no descriptions or fine print (the help `?` 8 px after the last word holds them), 12 px minimum between controls, nothing at a card edge.

## 2. Context

0780-0788 briefs and reports. Shared look: `docs/design/MASTER.md` and the phone v2 classes (memory: Airbnb-minimal phone style is approved for the whole app; reuse shared phone classes, `.card`, pills). Geometry tests: `App/tests/test_0786_settings_geometry_browser.py` (help tip, 12 px neighbours, text blocks). Old-shell tests use `/payments`.

## 3. Files

`App/app/templates/settings.html`, `entities.html`, `privacy_requests.html`, `settings_archived.html`, new shared partials for the back-button header, the index row and the pill tabs, new sub-page templates, the 0780/0781 blocks of `App/app/static/app2.css`, `App/app/` settings routes: only new GET routes that render the sub-page templates with the data the current settings route already loads (no new logic), tests touching these pages, `base.html` + `static_versions.json` (cache key).

## 4. Steps

1. Test first in `test_0786_settings_geometry_browser.py`: at 390, 768 and 1280, en and cs: the back button is top left (x < 32) and >= 40 px; the h1 sits below it; /settings rows are >= 56 px, each with icon, label and chevron vertically centred within 1 px, no row text longer than 40 characters; every sub-page card has a 1 px border, radius >= 12, padding >= 20; no paragraph longer than 60 characters; pills (where present) >= 44 px tall, 12 px apart, active one black with `aria-current`.
2. Build the partials; turn `/settings` into the index; move each group into its sub-page; restyle the three existing sub-pages the same way.
3. Keep all existing behaviour tests green (forms, POST targets, help tips without JS, PWA, push, passkeys, 2FA, archive filters).
4. Cache key bump, `tests/test_static_versions.py --write`.
5. Screenshots at 390, 768 and 1280 of the index and every sub-page to `/mnt/project-files/settings-area/airbnb/`.

## 5. Do not touch

`App/app/static/app.js`, Python logic beyond the new GET render routes, payments, other pages.

## 6. Commands

From `App/`: `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0786_settings_geometry_browser.py tests/test_host_help_browser.py tests/test_design_settings.py tests/test_settings_technical.py tests/test_operator_naming.py tests/test_pwa.py tests/test_pwa_browser.py tests/test_0710_v2_mockup_match_browser.py -q --tb=line -p no:cacheprovider 2>&1 | grep -E "^(FAILED|ERROR)|^E  |passed|failed" | cut -c1-240 | tail -20` (no `-n`, xdist is not installed). From the repo root: `python3 scripts/design_lint.py`, `python3 scripts/context_lint.py`.

## 7. Acceptance

All pass, 0 skipped; screenshots exist.

## 8. Stop and ask

A Python logic or `app.js` change; a form that cannot work without JS in the new layout.

## 9. Report

`docs/tasks/0789-report.md`: commits, counts, screenshot paths.
