# 0718: shared phone shell from the approved phone mockup (tab bar, Menu page, phone classes, phone tests)
Status: todo
Depends on: 0716 | Base commit: task/0716-v2-shell-parity | Branch: task/0718-v2-phone-shell
Executor: Haiku 5.5 | Fits one session: 30 tool calls

## 1. Objective
Below 1024 px every v2 page uses the approved phone design (owner approved 2026-11-01 16:55): `docs/design/mockup/ubyhost-phone-v1.html` (contact sheet: `/mnt/project-files/ux-redesign/phone/all-screens.png`). This brief builds the shared parts: bottom tab bar, a Menu page, the phone versions of the shared classes, and phone checks in the shared 0710 test. Page layouts (Overview "Dnes", stays, properties…) are separate briefs.

## 2. Context and decisions (orchestrator)
- Read the phone mockup's `<style>` block (sections "top row + titles", "cards", "pills, chips", "lists", "tab bar") and the `<nav class="tabs">` markup near the end. Its screens are `<section class="scr" data-s="KEY">`; at <= 480 px the frame fills the viewport.
- Tab bar: in `App/app/templates/_shell_v2.html` add `<nav class="tabs" aria-label="…">` with five `a.tab` links, icons from the existing sidebar icon set, labels from existing i18n nav keys where they exist (add keys in `host_i18n.py` en/cs and `host_vi_i18n.py` only if missing): Dnes → `/`, Kalendář → `/?cal_view=calendar`, Pobyty → `/reservations`, Nemovitosti → `/apartments`, Menu → `/menu`. Mark the current one `.tab.on` (`aria-current="page"`) from the same `nav` variable the sidebar uses; Dnes shows the needs-you count badge `.n` if the sidebar has that count. In app2.css: `.tabs` hidden at >= 1024 px; below 1024 px `position:fixed; bottom:0; left:0; right:0; height:84px` (+ `env(safe-area-inset-bottom)`), copy the mockup's `.tabs/.tab/.tab.on/.tab .n` values; hide `.side` entirely below 1024 px; `.main` gets `padding-bottom` >= 100 px so content never hides behind the bar.
- Menu page: new route `GET /menu` (signed-in hosts; put it next to the `/settings` route, same auth dependency) rendering new `App/app/templates/menu.html` with `{% set v2 = true %}`. Content as the mockup's Menu screen: `.big` "Menu", an account `.card.me` (name, property count, link to account), then a `.list` of `.row` links: Úklid `/cleaning`, Poplatek z pobytu (same href as the sidebar), Platby `/payments`, Nastavení `/settings`, Pomoc a Havel (same href/hook as the sidebar help), admin link only for admins (same condition as the sidebar), and the existing logout form as a quiet underlined button. Works without JavaScript. At >= 1024 the page still renders (plain list in the desktop look).
- Shared phone classes in app2.css, inside `@media (max-width:1023px)` scoped to `body.v2`: `.top`, `.round`, `.round.solid`, `.big`, `.sub` (phone values), `h2.sec`, phone `.card` (radius 18, padding 18, the mockup shadow), `.btn` phone size (min-height 50, radius 12, 16 px; full width inside `.card` and `.actbar`), `.btn.line`, `.btn.soft`, phone `.pill` (13 px with the dot), `.chips/.chip`, `.list/.row/.row .t/.chev/.grp`, `.ic.*`, `.av`, `.badge`, `.allgood`, `.hs` (horizontal cards), `.kind`, `.facts`, `.link`, and a bottom action bar named `.actbar` (the mockup calls it `.bar`, which the desktop calendar already uses for stay bars). Also map the page title: below 1024 px `.head h1` uses the `.big` values and `.head .sub` the `.sub` values, so pages need no second title.
- Tests (`App/tests/v2_mockup.py`, `App/tests/test_0710_v2_mockup_match_browser.py`):
  - `PHONE_MOCKUP = …/docs/design/mockup/ubyhost-phone-v1.html`; `PHONE_WIDTHS = (320, 390)`. Show a phone screen with `page.evaluate("k => document.querySelectorAll('.scr').forEach(s => s.classList.toggle('on', s.dataset.s === k))", key)`.
  - Each PAGES entry may have `"phone_view"` (mockup `data-s` key) and `"phone_selectors"`; at PHONE_WIDTHS the style test compares those against the phone mockup instead of the desktop one (same overrides mechanism; add `SELECTOR_ALIASES = {".actbar": ".bar"}` for app→mockup names). Add a new PAGES entry `{"name": "menu", "path": "/menu", "view": None, "phone_view": "menu", "phone_selectors": [".tabs", ".tab", ".tab.on", ".big", ".card.me", ".list .row", ".row .t b", ".row .t small"]}`; a `view` of None means no desktop style comparison. For overview add `"phone_view": "dnes"` and `"phone_selectors": [".tabs", ".tab", ".tab.on"]` (brief 0719 adds the Dnes page selectors).
  - Owner rule 16:57: the phone build must match the phone mockup 1:1. So at PHONE_WIDTHS the style comparison is strict (±1 px, exact colours after the AA overrides) AND also compares box metrics for every phone selector: `height`, `margin-top/right/bottom/left`, and `width` relative to the viewport (±2 px). Missing selectors fail unless in `missing_ok` with a reason.
  - Geometry below 1024 px: replace the old "`.side` top bar <= 72 px" check with: `.side` not visible; `.tabs` visible, its bottom edge at the viewport bottom, 5 `.tab` items each >= 44x44; the last element of `main` is not covered by `.tabs` when scrolled to the bottom.
- `base.html`: bump the app2.css key to `20261101-0718`; from App/ `.venv/bin/python tests/test_static_versions.py --write | tail -1`. Add `menu.html` to `V2_TEMPLATES` in `scripts/design_lint.py`.

## 3. Files
`App/app/templates/_shell_v2.html`, new `App/app/templates/menu.html`, the routes file that holds `/settings` (one small handler), `App/app/host_i18n.py`/`App/app/host_vi_i18n.py` (only missing keys), `App/app/static/app2.css`, `App/app/templates/base.html` (key), `App/tests/static_versions.json`, `scripts/design_lint.py` (one entry), `App/tests/v2_mockup.py`, `App/tests/test_0710_v2_mockup_match_browser.py`, new `App/tests/test_0718_menu_page.py` (signed-in GET /menu 200, contains every link above, admin link hidden for non-admins, logout form present), screenshots `docs/tasks/screenshots-0718/` (menu and overview at 390, overview at 768), report `docs/tasks/0718-report.md`.

## 4. Steps
1. Tab bar + hide sidebar + padding. Commit.
2. Menu route, template, test file. Commit.
3. Phone classes. Commit.
4. Test helper changes. Commit.
5. Key, manifest, lint entry, screenshots (Read them), commands. Commit + report.

## 5. Do not touch
`dashboard.html` (brief 0719), `app.js`, `_shell_sidebar.html`.

## 6. Commands (from App/, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0718_menu_page.py tests/test_0710_v2_mockup_match_browser.py tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py tests/test_host_account_navigation.py tests/test_design_shell.py tests/test_static_versions.py -q --tb=line -rs 2>&1 | tail -30`. Overview phone style findings for Dnes-page selectors are expected to wait for 0719; everything else must pass with 0 skipped. Repo root: `python3 scripts/design_lint.py | tail -1; python3 scripts/context_lint.py | tail -1`.

## 7. Acceptance
Menu page and tab bar pass the 0710 checks at 320 and 390; geometry passes at all six widths; listed tests pass, 0 skipped.

## 8. Stop and ask
Stop if the needs-you count is not available in the shell context without a new query, or if `/menu` clashes with an existing route.

## 9. Report
`docs/tasks/0718-report.md`: status, test tails, screenshots, deviations.
