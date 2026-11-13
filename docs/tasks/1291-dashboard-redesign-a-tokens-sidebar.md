# 1291: host dashboard redesign, part A of 3: colour tokens, cream background, new sidebar and tablet icon rail

Status: todo
Depends on: none | Base commit: origin/main | Branch: task/1291-dashboard-redesign-a
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (5 steps, 27 calls plus PR and report; tight, stop at step 5 if over 30)
Brief by Sonnet 5.5, 2026-11-12, revised 2026-11-13 (renumbered from 1132, owner answers, Figma numbers verified with the Figma MCP, geometry tests). Owner Josef approved the Figma redesign (file `4POeO1dtcL5i2U5e0gdEoU`: frames "Laptop 1280 / Dashboard – full sidebar" (node 33:98, the FINAL sidebar), "Laptop 1280 / Dashboard (chosen: B)" (12:30) and "Tablet 820 / Dashboard (B)" (14:82)). Order: **1291 (this) then 1292 then 1293**. 1292 and 1293 stop if this one is not merged or stacked on its branch.

## 1. Objective

Part A only: new colour tokens, warm cream page background on host pages, the new v2 sidebar (laptop 1024+), a tablet 768-1023 px icon rail, new icons. The dashboard body is NOT touched here (1292, 1293). Owner goals: simple, intuitive, not overwhelming, easy for old people, children and first-time visitors. Screenshots exist in Figma only: build from the pixel values below (verified against Figma 2026-11-13; Figma wins on any difference).

Out of scope: phone layout (below 768 px keeps today's bottom tab bar; owner said phone is good), other pages' bodies, door locks and invoices pages (routes keep working), admin, guest pages, auth forms, the legacy `_shell_sidebar.html`.

## 2. Context and rules

AGENTS rules 6 (light mode only), 7 (browser and geometry tests 0 skipped, 390 px shot per changed page), 9 (copy), 10 (UX gate). No new dependency, no new outbound request, no new personal-data field. Tokens only: no raw hex and no inline `style=` in templates (the old search button has inline styles; remove them while you rewrite it). 12 px minimum between neighbours. No truncated labels.

Facts (verified, 2026-11-12):
- Live shell: `App/app/templates/_shell_v2.html` (57 lines). It has `.ui-brand`, an env badge, `.org` box (name + property count), `button.search` with `<kbd>Ctrl K`, `nav.side-nav` with six `a.nav` links, then `details.me-menu.host-account` (summary `.me`, list `.me-menu-list` with Settings, admin links, Guide, Ask Havel, Support, Logout), then phone `nav.tabs`.
- Today the sidebar is hidden below 1024 px (`app2.css` ~line 243: `body.v2 .side{display:none}`, and `body.v2 .tabs{display:flex;...}` inside `@media (max-width:1023px)`), so tablets get the bottom tab bar. The rail changes this: tab bar only below 768 px.
- Sidebar CSS: `.side{width:220px...}` line 21, `.org` 24, `.search` 44, `.side-nav` 113, `.me-menu` 2369-2379, phone rules 88-102 and 238-250. `:root` vars at line 2 of `App/app/static/app2.css` (`--bg:#f6f6f4`, `--s`, `--ink`, `--ink2`, `--ink3`, `--line`, `--side`, `--side2`, `--acc:#d0452d`, `--acc-text:#b83d28`, `--accs:#fdece8`, `--ok`, `--oks`, `--warn`, `--warns`, `--bad`, `--bads`).
- `App/app/static/tokens.css` has semantic tokens (`--canvas:#f7f7f5`, `--blue:#245cb5; --blue-bg:#e9f0fc`, `--teal:#08736b; --teal-bg:#e1f5f2`, `--green:#167044; --green-bg:#e6f5ec`, `--red:#b42318; --red-bg:#fcebea`). `docs/design/MASTER.md` section 2 lists them.
- Nav labels use existing i18n keys: `nav.overview` (decided 2026-11-13: en becomes "Dashboard", cs stays "Přehled", vi stays "Tổng quan"; step 3), `nav.stays`, `nav.properties`, `nav.cleaning`, `nav.stay_fees`, `nav.payments`, `nav.settings`, `nav.guide`, `nav.ask_havel`, `host.search`. "Booking site" has a route in the repo (`nav == 'booking_sites'` is used in `_shell_tabbar.html`); find its URL and label key with `grep -n "booking_sites\|nav.booking" App/app/templates/_shell_tabbar.html App/app/templates/menu.html | head`.
- `_icons.html` is the only icon source (lucide-static 0.552.0). It already has `users`, `coins`, `calendar-days`, `settings`, `circle-help`, `message-circle-question`, `chevron-down`, `search`. Missing: `brush-cleaning`, `wallet`, `chevrons-up-down`, `book-open` exists, `triangle-alert` exists.

## 3. Files

| Path | Action |
|---|---|
| `App/app/static/tokens.css` | add semantic tokens (step 1) |
| `App/app/static/app2.css` | map `:root` vars, new sidebar and rail rules, tab bar breakpoint |
| `App/app/templates/_icons.html` | add `brush-cleaning`, `wallet`, `chevrons-up-down` |
| `App/app/templates/_shell_v2.html` | rewrite sidebar block and tab bar icons |
| `App/app/templates/_shell_tabbar.html`, `App/app/templates/menu.html` | swap icons only (sparkles to brush-cleaning, credit-card to wallet, receipt-text to coins) |
| `App/app/templates/base.html` | bump `app2.css?v=` (line 23, now `20261111-1124c`) and `tokens.css?v=` (lines 22 and 27, now `20261103-0920`) to `20261112-1291a` |
| `App/app/host_i18n.py` | en `nav.overview` (line 43) to "Dashboard"; other nav keys only if missing (step 3) |
| `App/app/host_vi_i18n.py`, `App/app/host_design_i18n.py` | read only; add a key only if a nav key is missing (vi, cs, en) |
| `App/tests/dash_geometry_support.py`, `App/tests/test_1291_sidebar_geometry_browser.py` | new, step 5 |
| `docs/design/MASTER.md` | section 2: new token lines (step 4) |
| `App/tests/test_icons_nav_1060.py`, `App/tests/test_0705_v2_shell_browser.py` | adjust only assertions that name the removed `.org` box, the `Ctrl K` hint, or the old icons; do not weaken others |
| other `App/tests/*.py` found by `grep -rn "Overview" App/tests App/app/templates \| head -30` | change only an assertion that checks the nav LABEL "Overview" to "Dashboard" (expected hits: tests that open the nav or command palette). Titles and docstrings that merely say "Overview" stay. Never weaken another assertion. List every file you touched in the report |

No other file. Anchors are verbatim; if one is not found, STOP (executor.md).

## 4. Steps

### Step 1: tokens and cream background (at most 5 calls)
1. In `tokens.css` `:root`, after the `--brand-*` lines (anchor `--on-brand: #ffffff;`), add:
```
  --page-cream: #faf6f0;
  --coral-red: #d0452d;
  --coral-red-deep: #b83d28;
  --coral-red-soft: #fdece8;
  --tile-blue-bg: #e8f0fb;  --tile-blue-ink: #245cb5;
  --tile-teal-bg: #e1f2ef;  --tile-teal-ink: #08736b;
  --tile-done-bg: #e6f5ec;  --tile-done-ink: #167044;
  --danger: #d0452d;        --danger-bg: #fcebea;
  --attention-bg: #fde9c2;  --line-2: #c9c9c2;
```
`--attention-bg` is the amber icon-tile and warning tile fill and `--line-2` the secondary button border (both from Figma; `--warns` is `#fff4d6`, different). Before adding, `grep -n -- "--line-2\|--attention-bg" App/app/static/tokens.css App/app/static/app2.css | head -3`; if one exists with another value, STOP. `--brand` (#c85a52) stays untouched (owner confirmed 2026-11-13: `--coral-red` is added next to it).
2. In `app2.css` line 2 `:root{...}` change `--bg:#f6f6f4` to `--bg:var(--page-cream)`; `--acc:#d0452d` to `--acc:var(--coral-red)`; `--acc-text:#b83d28` to `--acc-text:var(--coral-red-deep)`; `--accs:#fdece8` to `--accs:var(--coral-red-soft)`. Also map `--side2` check: Figma search fill is `#f1f1ee` (= today's `--side2`, leave it). Check tokens.css loads before app2.css (`base.html` lines 22-23: yes). White cards stay `--s:#fff`. Light mode only: add nothing for dark.
3. Contrast check (run once, one command, not a test): `python3 -c "..."` computing WCAG ratios for `#b83d28` on `#fdece8`, `#b83d28` on `#faf6f0`, white on `#d0452d`, `#6b6b65` (ink3) on `#faf6f0`. Each must be 4.5 or more. Any fail: STOP and report the numbers.
4. Run: `grep -n "page-cream\|coral-red" App/app/static/tokens.css App/app/static/app2.css | wc -l | tail -30` expect 9 or more. Commit `1291 step 1`.

Coral stays a signal only (one primary button, active nav, count chip, urgent icon, text links), never a page or card background.

### Step 2: icons (at most 4 calls)
In `_icons.html` add three entries to `ICONS` (copy exactly, same quoting style as the neighbours):
```
'brush-cleaning': '<path d="m16 22-1-4"/><path d="M19 13.99a1 1 0 0 0 1-1V12a2 2 0 0 0-2-2h-3a1 1 0 0 1-1-1V4a2 2 0 0 0-4 0v5a1 1 0 0 1-1 1H6a2 2 0 0 0-2 2v.99a1 1 0 0 0 1 1"/><path d="M5 14h14l1.973 6.767A1 1 0 0 1 20 22H4a1 1 0 0 1-.973-1.233z"/><path d="m8 22 1-4"/>',
'wallet': '<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>',
'chevrons-up-down': '<path d="m7 15 5 5 5-5"/><path d="m7 9 5-5 5 5"/>',
```
The third is the lucide 0.552.0 path; verify with `npm pack lucide-static@0.552.0` into the scratchpad directory and `grep` of `icons/chevrons-up-down.svg`; if it differs, use the package's paths and note it. No `npm install`, no package.json change. Swap icons in `_shell_tabbar.html` (cleaning to `brush-cleaning`, payments to `wallet`, stay fees to `coins`) and `menu.html` lines 16-18 (same three), keeping sizes. Do not touch `_cleaning_table.html` or `_shell_sidebar.html`. Run `.venv/bin/python -m pytest tests/test_icons_nav_1060.py -q --tb=short -x 2>&1 | tail -30` from `App/`. Commit `1291 step 2`.

### Step 3: sidebar markup (at most 6 calls)
Rewrite `_shell_v2.html` lines 5-47 (the `<aside>`), keep the phone `nav.tabs` (line 49 on) but replace its `/menu` tab untouched. Target order inside `aside.side#app-sidebar`:
1. `.ui-brand` logo (unchanged, mark uses coral via CSS) and the env badge (unchanged).
2. REMOVE the whole `{% if current_user %}<div class="org">...</div>{% endif %}` block.
3. Search: `<button class="search" type="button" data-command-open>{{ icon('search', 22) }}<span>{{ t('host.search') }}</span></button>`. No `<kbd>`, no inline style. (Keep `data-command-open`; `data-command-shortcut` goes away. Check `grep -rn "data-command-shortcut" App/app/static/*.js | head -3`; if JS needs it to exist, STOP.)
4. `nav.side-nav` with two `div.nav-group` groups (small gap between): group 1 = Dashboard (`/`, existing custom house path svg `M3 10.5 12 3l9 7.5V21H3z`, key `nav.overview`, NO badge), Stays (`/reservations`, `users`), Properties (`/apartments`, existing custom document svg), Cleaning (`/cleaning`, `brush-cleaning`); group 2 = Stay fees (`/stay-fees`, `coins`), Payments (`/payments`, `wallet`), Booking site (URL and key from the grep in section 2; icon `globe` if it is already in `_icons.html`, else `external-link`; report the choice). NO Smart locks, NO Invoices links in the sidebar.
5. `div.side-bottom` (margin-top:auto): Ask Havel `{% if havel_on %}<a class="nav" href="/havel" data-sheet-open="havel-sheet" data-havel-launcher>{{ icon('message-circle-question', 22) }}{{ t('nav.ask_havel') }}</a>{% endif %}`, Help (`/guide`, `circle-help`, `nav.guide`), Settings (`/settings`, `settings`, `nav.settings`, `on` when `nav == 'settings'`), then `<hr class="side-sep">` then the existing `details.me-menu.host-account` whose `summary.me` becomes: `<i>{{ initial }}</i><span class="me-name">{{ first_name }}</span>{{ icon('chevrons-up-down', 18) }}`. `first_name` = `{% set me_name = workspace_user.display_name or workspace_user.username %}{% set first_name = me_name.split(' ')[0] %}`. Keep `aria-label="{{ t('nav.account') }}: {{ me_name }}"`.
6. Account menu list: remove the now duplicate Settings, Guide, Ask Havel links; ADD `{{ icon('key-round', 18) }}` Smart locks (`/smart-locks`; confirm the route with `grep -rn "smart-locks\|smart_locks" App/app/templates/menu.html | head -3`, label key from there) and Invoices (`/invoices`, icon `receipt-text`, key `nav.invoices` if it exists, else the key used in `menu.html`) so both stay reachable; keep admin links, Support and Logout.
7. Active state: keep `class="nav on"` + `aria-current="page"` logic exactly as now.
Nav label (owner, 2026-11-13): in `host_i18n.py` change en `"nav.overview": "Overview"` (line 43) to `"Dashboard"`; keep the key; cs stays "Přehled" (line 2202), vi stays "Tổng quan" (`host_vi_i18n.py` line 316). `host_design_i18n.py` already holds en "Dashboard" and cs "Přehled" (it overlays `host_i18n`); run `.venv/bin/python -c "from app import host_i18n as h; print(h.t('en','nav.overview') if hasattr(h,'t') else 'no t')" | tail -3` only if unsure which wins; if it prints "Overview" after your edit, STOP. Then `grep -rn "Overview" App/tests App/app/templates | head -30` and update only assertions that check the nav label (section 3 last row). The languages with host nav strings are exactly en, cs, vi; guest/guide languages (de, es, fr, uk) have no `nav.overview` host key, nothing to set.
Do not add any other new user-visible string; if a key above is missing in `host_i18n.py`, add it for en, cs (`host_i18n.py`) and vi (`host_vi_i18n.py`), same indentation, and run `.venv/bin/python -m pytest tests/test_host_i18n.py -q --tb=short -x 2>&1 | tail -30`. Commit `1291 step 3`.

### Step 4: sidebar CSS, rail, tab bar breakpoint, docs (at most 6 calls)
All in `app2.css`, scoped `body.v2`; append one block `/* 1291 sidebar */` at the end, then fix the two old rules named below.
- Laptop 1024+ (Figma 33:98, verified): `.side{width:240px;padding:16px 12px;border-right:1px solid var(--line);display:flex;flex-direction:column}` (keep sticky/full height; items are `100%` of the 216 px inner width). Logo row 44 px high, gap 10, padding 0 8; mark 30x30 radius 9 in `--coral-red`, letter 17/700 white; wordmark 19/700 `--ink`. `.side .nav{height:48px;border-radius:12px;gap:14px;padding:0 14px;font-size:16px;font-weight:500;line-height:22px;color:var(--ink2);display:flex;align-items:center}`; svg 22x22, `stroke-width:1.8`. `.side .nav.on{background:var(--coral-red-soft);color:var(--coral-red-deep);font-weight:600}`, its icon `stroke-width:2.1`. `.side .nav+.nav{margin-top:4px}`; `.side .nav-group+.nav-group{margin-top:18px}` (gap between group boxes is 18, no divider). `.side .search{height:40px;border-radius:10px;gap:10px;padding:0 12px;margin-bottom:20px;background:var(--side2);font-size:15px;font-weight:500;color:var(--ink3);width:auto}` with a 18 px search icon (20 px from the search bottom to the first nav item). `.side-sep{border:0;border-top:1px solid var(--line);margin:4px 0}`. Account `.side .me-menu > summary.me{display:flex;align-items:center;gap:12px;height:52px;padding:8px 10px;border-radius:12px}`; `.me i` 36x36 circle, 15/700, bg `--coral-red-soft`, ink `--coral-red-deep`; `.me-name{flex:1;min-width:0;overflow-wrap:anywhere;font-weight:600;font-size:16px;color:var(--ink)}`; chevrons icon 18 px. Number changes versus the first draft (Figma wins): search 48 to 40 high, radius 12 to 10, icon 22 to 18, font 16 to 15; icon-label gap 12 to 14; group gap 16 to 18; search margin 16 to 20; account row 48 to 52, avatar 32 to 36; separator margin 12 to 4.
- Tablet 768-1023 px (`@media (min-width:768px) and (max-width:1023px)`; Figma 14:82, verified): `.side` is a visible rail, `width:88px;padding:16px 8px;align-items:center;overflow-y:auto`, border-right 1px `--line`. Mark 36x36 radius 10 (letter 20/700); hide `.ui-brand span`, `.search span`, `.me-name`, `.me .ui-icon:last-child`. Each `.nav` and the search button: `width:72px;min-height:64px;border-radius:14px;flex-direction:column;justify-content:center;gap:4px;padding:8px 0;font-size:12px;line-height:17px;font-weight:500;text-align:center;white-space:normal`, icon 24 px; `.side .nav+.nav,.side .nav-group+.nav-group{margin-top:6px}`; active = `--coral-red-soft` pill, label 700 `--coral-red-deep`. Avatar 40x40 at the bottom. "Properties" at 12 px is 60 px wide so it fits the 72 px box; a longer cs or vi label may take two lines, never an ellipsis. Decided: the rail carries the same destinations as the laptop sidebar (the Figma tablet frame still shows an older "More" item; the final sidebar frame 33:98 wins). The me-menu list opens to the right of the rail (`left:calc(100% + 8px);bottom:0`). Tablet 768-1023 switches to this design: icon rail, no bottom tab bar (owner confirmed 2026-11-13).
- Tab bar: change the two rules at ~lines 243-244 so `body.v2 .side{display:none}` and `body.v2 .tabs{display:flex...}` apply only to `max-width:767px` (they are inside `@media (max-width:1023px)`; split the media query, keep every tab-bar declaration unchanged). The phone rules at 88-102 and line 2379 already target 767 px and stay.
- `docs/design/MASTER.md` section 2 (anchor `## 2. Tokens`): add one line under the semantic layer listing the new tokens from step 1 and a note "page background cream `--page-cream`, host pages, light mode". Do not edit other docs here (1293 does the rest).
Run from `App/`:
`.venv/bin/python -m pytest tests/test_0705_v2_shell_browser.py tests/test_0895_sidebar_inert_heal_browser.py tests/test_host_account_navigation.py tests/test_icons_nav_1060.py -q --tb=short -x -rs 2>&1 | tail -30`. Fix test assertions only where they name removed items (section 3 last row). Commit `1291 step 4`.

### Step 5: geometry and design tests (at most 6 calls)
1. Read `App/tests/test_host_geometry.py` lines 1-66 (launch pattern: the `REQUIRE_BROWSER` block, `chromium_launch_kwargs`, module fixture `base`, `_browser_session_cookie`) and `grep -n "add_cookies\|new_context\|sync_playwright" App/tests/test_host_geometry.py | head`. No new dependency: Playwright and pytest already exist.
2. Create `App/tests/dash_geometry_support.py` (no tests inside; 1292 and 1293 import it): `WIDTHS=(1440,1280,1024,820,768,390,320)`; `open_page(browser, base, cookie, path, width, lang='en')` (context viewport width x 1000, `reduced_motion='reduce'`, session cookie, `?lang=`); `rect(page, sel, nth=0)` and `css(page, sel, prop, nth=0)` via `getBoundingClientRect()` / `getComputedStyle()`; `near(a, b, tol=1)`; `contrast_failures(page, root_sel)` (every visible text node under root: computed `color` against the effective background found by walking up and compositing until alpha 1, WCAG ratio `(L1+0.05)/(L2+0.05)` with the standard sRGB relative luminance, return those below 4.5); `clipped_texts(page, root_sel)` (a, button, label, h1-h3, strong, span, p with `scrollWidth > clientWidth + 1`); `small_targets(page, root_sel)` (visible a, button, summary narrower or lower than 44); `overlap(r1, r2)` (intersection area above 1 px squared); `big_coral(page, root_sel)` (elements wider and taller than 60 px, not a, button, input, whose background is rgb(208,69,45) or rgb(184,61,40)); `focus_outline(page, sel)` (press Tab up to 40 times until `document.activeElement` matches sel, return outline width and style); `shot(page, name)` (full page PNG to `$UBYHOST_SHOTS_DIR/dashboard-redesign/<name>.png`).
3. Create `App/tests/test_1291_sidebar_geometry_browser.py`, module `REQUIRE_BROWSER` block copied from `test_host_geometry.py`, `from tests.test_host_geometry import base, _browser_session_cookie`, `@pytest.mark.parametrize("width", WIDTHS)` on pages `/` and `/reservations`. Assert (±1 px unless said):
   - ALL widths: `document.documentElement.scrollWidth <= innerWidth`; `body` background rgb(250,246,240); `.side` and `.main` boxes do not overlap; `clipped_texts` empty for `.side` and `nav.tabs`; `contrast_failures` empty for `.side` and `nav.tabs`; `big_coral` empty for `.side`.
   - 1440, 1280, 1024 (laptop): `.side` width 240, left 0, border-right 1 px, padding 16 12; every `.side .nav` height 48, width 216, radius 12, svg 22x22, font 16, weight 500 (the `.on` one 600, color rgb(184,61,40), background rgb(253,236,232)), icon x offset 14 and label starts 14 px after the icon; vertical gap 4 inside a group and 18 between the two groups; `.search` height 40, radius 10, icon 18, font 15, 20 px above the first nav item, no `kbd`; no `.org`; the Dashboard label reads "Dashboard"; mark 30x30 radius 9; `summary.me` height 52, avatar 36x36, `.me-name` 16/600; `.side-sep` 1 px high; `.tabs` hidden; `small_targets` empty; `focus_outline` of the first `.nav`, `.search` and `summary.me` has width >= 2 px and style not none.
   - 820 and 768 (rail): `.side` width 88, `.tabs` `display:none`, each nav 72x64 (min-height 64 for cs/vi), radius 14, icon 24, label 12 px, vertical gap 6, mark 36, avatar 40, `.me-name` hidden, labels not cut, `small_targets` empty.
   - 390 and 320 (phone, unchanged): `.side` `display:none`, `nav.tabs` visible and fixed at the bottom of the viewport, each tab at least 44x44.
   - Content states: a second test at widths 1280, 768, 390 with `lang` cs and vi: no clipped text, no horizontal scroll, rail labels never ellipsised. If setting a 45-character `display_name` needs more than one call, leave that case out and say so in the report.
   - Screenshots 390, 768, 820, 1280 of `/` and `/reservations` through `shot()`.
4. Run `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_1291_sidebar_geometry_browser.py -q --tb=short -x -rs 2>&1 | tail -30` (0 skipped). A failing number: fix the CSS, never the number. If a Figma number cannot be met without changing a file outside section 3: stop and report.
5. Open the PNGs in `/tmp/shots/dashboard-redesign` (390, 768, 820, 1280) with the Read tool and write one sentence per shot into the report (AGENTS rule 10). Commit `1291 step 5`.

## 5. Do not touch

- The phone layout: `dash-phone` markup, `ph-*` rules and the phone tab bar structure (only icons and the 768 px breakpoint change, as listed in section 4).
- Guest pages, admin pages, login and auth forms.
- Routes and templates for Smart locks and Invoices (they only move into the account menu).
- Migrations, `db.py`, any SQL, any new dependency, any new outbound request.
- Anything not listed in section 3 Files.

## 6. Commands (from `App/`, each ends `| tail -30`)

```
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_1291_sidebar_geometry_browser.py -q --tb=short -x -rs 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py -q --tb=short -x -rs 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_0710_v2_mockup_match_browser.py -q --tb=short -x -rs 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_design_*.py tests/test_host_i18n.py -q --tb=short -x 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x -rs 2>&1 | tail -30
```
Rows used (test-map): host pages and host CSS, any host template/CSS/JS, v2 pages, static files and cache keys, design system, copy and translations. Browser files 0 skipped (`-rs`); a skip is a fail. No full suite.

## 7. Acceptance

- Host pages have the cream background; cards stay white; `grep -n "#faf6f0\|#d0452d" App/app/templates/*.html | wc -l` is 0 (tokens only).
- Laptop 1280 sidebar: no name box, search without `Ctrl K`, groups [Dashboard, Stays, Properties, Cleaning] [Stay fees, Payments, Booking site], bottom Ask Havel (only with `havel_on`), Help, Settings, hairline, avatar row with first name; no Smart locks or Invoices link in the sidebar, both in the account menu and routes `/smart-locks`, `/invoices` still 200.
- Items 48 px high, radius 12, icon 22, label 16/500, active 600 coral-red-deep on coral-red-soft, no count badge; search 40 high; `test_1291_sidebar_geometry_browser.py` green with 0 skipped at 1440, 1280, 1024, 820, 768, 390, 320 (contrast >= 4.5, targets >= 44, focus ring >= 2 px, no clipped text, no horizontal scroll).
- Nav label is "Dashboard" in en (cs "Přehled", vi "Tổng quan"); the label-checking tests you changed are listed in the report.
- Tablet 820: 88 px rail, 24 px icon with 12 px label under it, active pill; no horizontal scroll; no bottom tab bar between 768 and 1023; phone (390) unchanged.
- Icons: Cleaning brush-cleaning, Stay fees coins, Payments wallet in the sidebar, phone tab bar and `/menu`.
- UX gate (AGENTS rule 10, you do it, never ask the owner): screenshots at 390, 768, 1280 of `/` (dashboard) and one other host page (`/reservations`); write per page in the PR "390: ...; 768: ...; 1280: ..."; tick the [design-system checklist](../design/design-system.md) in the PR body; never silence a lint finding.
- Section 5 green, 0 skipped.

## 8. Stop and ask

Stop and report if: an anchor is missing; the tab bar and rail cannot coexist without touching phone markup; a contrast ratio is below 4.5; `data-command-shortcut` is needed by JS; `test_layout_lint_browser.py` flags something you cannot fix in 2 tries; a Figma number cannot be met without changing a file outside section 3: stop and report; more than 25 tool calls (30 hard cap).

## 9. Report (branch, PR and what to report)

Branch `task/1291-dashboard-redesign-a`, open one **draft** PR, never push to `main`. Merge only with `scripts/merge-pr-on-green.sh` (owner step; green merges auto-deploy, keep the draft until the owner says it may ship; 1292 and 1293 stack on this branch). Do not edit status, decisions or known-issues. Write `docs/tasks/1291-report.md` (600 tokens at most): files changed, each command with its last 5 lines, section 6 ticked, per-page screenshot notes, Deviations (`Done: steps 1 to k. Left: steps k+1 to 4.` if you hit the cap), Questions, owner steps.
