# 1132: host dashboard redesign, part A of 3: colour tokens, cream background, new sidebar and tablet icon rail

Status: todo
Depends on: none | Base commit: d9033975 | Branch: claude/great-fermi-lw5ogs (stack 1132, then 1133, then 1134)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (4 steps of at most 6 calls)
Brief by Sonnet 5.5, 2026-11-12. Owner Josef approved the Figma redesign (file `4POeO1dtcL5i2U5e0gdEoU`: frames "Laptop 1280 / Dashboard (chosen: B)", "Laptop 1280 / Dashboard – full sidebar", "Tablet 820 / Dashboard (B)"). Order: **1132 (this) then 1133 then 1134**. 1133 and 1134 stop if this one is not merged or stacked on its branch.

## 1. Objective

Part A only: new colour tokens, warm cream page background on host pages, the new v2 sidebar (laptop 1024+), a tablet 768-1023 px icon rail, new icons. The dashboard body is NOT touched here (1133, 1134). Owner goals: simple, intuitive, not overwhelming, easy for old people, children and first-time visitors. Screenshots exist in Figma only: build from the pixel values below.

Out of scope: phone layout (below 768 px keeps today's bottom tab bar; owner said phone is good), other pages' bodies, door locks and invoices pages (routes keep working), admin, guest pages, auth forms, the legacy `_shell_sidebar.html`.

## 2. Context

AGENTS rules 6 (light mode only), 7 (browser and geometry tests 0 skipped, 390 px shot per changed page), 9 (copy), 10 (UX gate). No new dependency, no new outbound request, no new personal-data field. Tokens only: no raw hex and no inline `style=` in templates (the old search button has inline styles; remove them while you rewrite it). 12 px minimum between neighbours. No truncated labels.

Orchestrator decisions (2026-11-13): keep `nav.overview` en string "Overview" until the owner picks cs ("Přehled" vs "Nástěnka"); this brief does not change i18n for that key. `--brand` in `tokens.css` stays `#c85a52`; this brief adds `--coral-red*` and maps `app2.css` accents to them. Booking site in the sidebar: `/booking-sites`, `t('nav.booking_sites')`, icon `external-link` (see `_shell_tabbar.html` line 21). Smart locks in the account menu: `/smart-locks`, `t('nav.smart_locks')`, icon `key-round`. Invoices: `/invoices`, `t('nav.invoices')`, icon `receipt-text`.

Facts (verified, 2026-11-12):
- Live shell: `App/app/templates/_shell_v2.html` (57 lines). It has `.ui-brand`, an env badge, `.org` box (name + property count), `button.search` with `<kbd>Ctrl K`, `nav.side-nav` with six `a.nav` links, then `details.me-menu.host-account` (summary `.me`, list `.me-menu-list` with Settings, admin links, Guide, Ask Havel, Support, Logout), then phone `nav.tabs`.
- Today the sidebar is hidden below 1024 px. Anchor, verbatim, `App/app/static/app2.css` lines 242 to 244:

```
@media (max-width:1023px){
  body.v2 .side{display:none}
  body.v2 .tabs{display:flex;position:fixed;left:0;right:0;bottom:0;height:84px;background:#fff;border-top:1px solid var(--line);padding:6px 4px 22px;padding-bottom:calc(22px + env(safe-area-inset-bottom));z-index:5}
```

If any line above is not found verbatim, STOP (section 8). The rail changes this: tab bar only below 768 px.
- Sidebar CSS: `.side{width:220px;background:var(--side);border-right:1px solid var(--line);color:var(--ink2);display:flex;flex-direction:column;padding:16px 10px;position:sticky;top:0;height:100vh;flex:none}` line 21; `.org` rules near line 24; `.search` near 44; `.side-nav` near 113; `.me-menu` near 2369-2379; phone rules 88-102 and 238-250. `:root` anchor line 2 of `App/app/static/app2.css`:

```
:root{--bg:#f6f6f4;--s:#fff;--ink:#1c1c1a;--ink2:#55554f;--ink3:#6b6b65;--line:#ebebe7;--side:#fff;--side2:#f1f1ee;--acc:#d0452d;--acc-text:#b83d28;--accs:#fdece8;--ok:#167044;--oks:#e6f5ec;--warn:#8a5200;--warns:#fff4d6;--bad:#b42318;--bads:#fdecea;--info:#eaf3fb;
```

(The line continues with `font-family:var(--font-sans);color:var(--ink);font-size:14px}` on the next physical line.)
- `App/app/static/tokens.css` has semantic tokens (`--canvas:#f7f7f5`, `--blue:#245cb5; --blue-bg:#e9f0fc`, `--teal:#08736b; --teal-bg:#e1f5f2`, `--green:#167044; --green-bg:#e6f5ec`, `--red:#b42318; --red-bg:#fcebea`). `docs/design/MASTER.md` section 2 lists them.
- Nav labels use existing i18n keys: `nav.overview`, `nav.stays`, `nav.properties`, `nav.cleaning`, `nav.stay_fees`, `nav.payments`, `nav.settings`, `nav.guide`, `nav.ask_havel`, `host.search`, `nav.booking_sites`, `nav.smart_locks`, `nav.invoices`.
- `_icons.html` is the only icon source (lucide-static 0.552.0). It already has `users`, `coins`, `calendar-days`, `settings`, `circle-help`, `message-circle-question`, `chevron-down`, `search`. Missing: `brush-cleaning`, `wallet`, `chevrons-up-down`, `book-open` exists, `triangle-alert` exists.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/static/tokens.css` | edit | Add `--page-cream`, `--coral-red*`, `--tile-*`, `--danger*` (step 1) |
| `App/app/static/app2.css` | edit | Map `:root` vars, sidebar and rail CSS, split tab-bar media query (step 4) |
| `App/app/templates/_icons.html` | edit | Add `brush-cleaning`, `wallet`, `chevrons-up-down` (step 2) |
| `App/app/templates/_shell_v2.html` | edit | Rewrite `<aside>` sidebar; keep phone `nav.tabs` (step 3) |
| `App/app/templates/_shell_tabbar.html` | edit | Icon swaps on cleaning, payments, stay fees (step 2) |
| `App/app/templates/menu.html` | edit | Icon swaps lines 16-18 (step 2) |
| `App/app/templates/base.html` | edit | Bump `tokens.css?v=` and `app2.css?v=` to `20261112-1132a` |
| `App/app/host_i18n.py`, `App/app/host_vi_i18n.py` | edit only if needed | Missing nav keys from step 3 |
| `docs/design/MASTER.md` | edit | Section 2 token list (step 4) |
| `App/tests/test_icons_nav_1060.py`, `App/tests/test_0705_v2_shell_browser.py` | edit | Assertions for removed `.org`, `Ctrl K`, old icons only |

No other file may change. Anchors are verbatim; if one is not found, STOP (executor.md).

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
```
2. In `app2.css` line 2 `:root{` block change `--bg:#f6f6f4` to `--bg:var(--page-cream)`; `--acc:#d0452d` to `--acc:var(--coral-red)`; `--acc-text:#b83d28` to `--acc-text:var(--coral-red-deep)`; `--accs:#fdece8` to `--accs:var(--coral-red-soft)`. Check tokens.css loads before app2.css (`base.html` lines 22-23: yes). White cards stay `--s:#fff`. Light mode only: add nothing for dark.
3. Contrast check (run once, one command, not a test):

```
python3 -c "
def lum(h):
    r,g,b=[int(h[i:i+2],16)/255 for i in (1,3,5)]
    def lin(x): return x/12.92 if x<=0.03928 else ((x+0.055)/1.055)**2.4
    return 0.2126*lin(r)+0.7152*lin(g)+0.0722*lin(b)
def ratio(fg,bg):
    L1,L2=lum(fg),lum(bg); hi,lo=(max(L1,L2),min(L1,L2)); return (hi+0.05)/(lo+0.05)
for fg,bg in [('#b83d28','#fdece8'),('#b83d28','#faf6f0'),('#ffffff','#d0452d'),('#6b6b65','#faf6f0')]:
    r=ratio(fg,bg); print(fg,'on',bg,':',round(r,2)); assert r>=4.5, (fg,bg,r)
print('contrast ok')
" 2>&1 | tail -30
```

Expected: four ratios, each at least 4.5, then `contrast ok`. Any fail: STOP and report the numbers.
4. Run: `grep -n "page-cream\|coral-red" App/app/static/tokens.css App/app/static/app2.css | wc -l | tail -30` expect 9 or more. Commit `1132 step 1`.

Coral stays a signal only (one primary button, active nav, count chip, urgent icon, text links), never a page or card background.

### Step 2: icons (at most 4 calls)
In `_icons.html` add three entries to `ICONS` (copy exactly, same quoting style as the neighbours):
```
'brush-cleaning': '<path d="m16 22-1-4"/><path d="M19 13.99a1 1 0 0 0 1-1V12a2 2 0 0 0-2-2h-3a1 1 0 0 1-1-1V4a2 2 0 0 0-4 0v5a1 1 0 0 1-1 1H6a2 2 0 0 0-2 2v.99a1 1 0 0 0 1 1"/><path d="M5 14h14l1.973 6.767A1 1 0 0 1 20 22H4a1 1 0 0 1-.973-1.233z"/><path d="m8 22 1-4"/>',
'wallet': '<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>',
'chevrons-up-down': '<path d="m7 15 5 5 5-5"/><path d="m7 9 5-5 5 5"/>',
```
The third is the lucide 0.552.0 path; verify with `npm pack lucide-static@0.552.0` into the scratchpad directory and `grep` of `icons/chevrons-up-down.svg`; if it differs, use the package's paths and note it. No `npm install`, no package.json change. Swap icons in `_shell_tabbar.html` (cleaning to `brush-cleaning`, payments to `wallet`, stay fees to `coins`) and `menu.html` lines 16-18 (same three), keeping sizes. Do not touch `_cleaning_table.html` or `_shell_sidebar.html`. Run `.venv/bin/python -m pytest tests/test_icons_nav_1060.py -q --tb=short -x 2>&1 | tail -30` from `App/`. Commit `1132 step 2`.

### Step 3: sidebar markup (at most 6 calls)
Rewrite `_shell_v2.html` lines 5-47 (the `<aside>`), keep the phone `nav.tabs` (line 49 on) but replace its `/menu` tab untouched. Target order inside `aside.side#app-sidebar`:
1. `.ui-brand` logo (unchanged, mark uses coral via CSS) and the env badge (unchanged).
2. REMOVE the whole org block (anchor, verbatim, `_shell_v2.html` lines 8 to 15):

```
  {% if current_user %}
  <div class="org">
    <i>{{ (workspace_user.display_name or workspace_user.username)[:1] | upper }}</i>
    <div>{{ workspace_user.display_name or workspace_user.username }}
      <small>{% if apartments is defined %}{{ tp('nav.property_count', apartments | length) }}{% else %}{{ t('nav.account') }}{% endif %}</small>
    </div>
  </div>
  {% endif %}
```
3. Search: `<button class="search" type="button" data-command-open>{{ icon('search', 22) }}<span>{{ t('host.search') }}</span></button>`. No `<kbd>`, no inline style. (Keep `data-command-open`; `data-command-shortcut` goes away. Check `grep -rn "data-command-shortcut" App/app/static/*.js | head -3`; if JS needs it to exist, STOP.)
4. `nav.side-nav` with two `div.nav-group` groups (small gap between): group 1 = Dashboard (`/`, existing custom house path svg `M3 10.5 12 3l9 7.5V21H3z`, key `nav.overview`, NO badge), Stays (`/reservations`, `users`), Properties (`/apartments`, existing custom document svg), Cleaning (`/cleaning`, `brush-cleaning`); group 2 = Stay fees (`/stay-fees`, `coins`), Payments (`/payments`, `wallet`), Booking site (`/booking-sites`, `nav.booking_sites`, `external-link`). NO Smart locks, NO Invoices links in the sidebar.
5. `div.side-bottom` (margin-top:auto): Ask Havel `{% if havel_on %}<a class="nav" href="/havel" data-sheet-open="havel-sheet" data-havel-launcher>{{ icon('message-circle-question', 22) }}{{ t('nav.ask_havel') }}</a>{% endif %}`, Help (`/guide`, `circle-help`, `nav.guide`), Settings (`/settings`, `settings`, `nav.settings`, `on` when `nav == 'settings'`), then `<hr class="side-sep">` then the existing `details.me-menu.host-account` whose `summary.me` becomes: `<i>{{ initial }}</i><span class="me-name">{{ first_name }}</span>{{ icon('chevrons-up-down', 18) }}`. `first_name` = `{% set me_name = workspace_user.display_name or workspace_user.username %}{% set first_name = me_name.split(' ')[0] %}`. Keep `aria-label="{{ t('nav.account') }}: {{ me_name }}"`.
6. Account menu list: remove the now duplicate Settings, Guide, Ask Havel links; ADD Smart locks (`/smart-locks`, `nav.smart_locks`, `key-round`) and Invoices (`/invoices`, `nav.invoices`, `receipt-text`) so both stay reachable; keep admin links, Support and Logout.
7. Active state: keep `class="nav on"` + `aria-current="page"` logic exactly as now.
Do not add any new user-visible string; if a key above is missing in `host_i18n.py`, add it for en, cs (`host_i18n.py`) and vi (`host_vi_i18n.py`), same indentation, and run `.venv/bin/python -m pytest tests/test_host_i18n.py -q --tb=short -x 2>&1 | tail -30`. Commit `1132 step 3`.

### Step 4: sidebar CSS, rail, tab bar breakpoint, docs (at most 8 calls)
All in `app2.css`, scoped `body.v2`; append one block `/* 1132 sidebar */` at the end, then fix the two old rules named below.
- Laptop 1024+: `.side{width:240px}` (keep sticky/full height). `.side .nav{min-height:48px;border-radius:12px;gap:12px;padding:0 14px;font-size:16px;font-weight:500;color:var(--ink2);display:flex;align-items:center}`; svg/`.ui-icon` 22 px, `stroke-width:1.8`. `.side .nav.on{background:var(--coral-red-soft);color:var(--coral-red-deep);font-weight:600}` and its icon `stroke-width:2.1`. `.side .nav-group+.nav-group{margin-top:16px}` (small gap, no divider); `.side .nav+.nav{margin-top:4px}`. `.side .search{width:auto;min-height:48px;border-radius:12px;margin-bottom:16px;background:var(--side2);font-size:16px;gap:12px;padding:0 14px}`. `.side-sep{border:0;border-top:1px solid var(--line);margin:12px 0}`. `.side .me-menu > summary.me{display:flex;align-items:center;gap:12px;min-height:48px}`, `.me i` 32 px circle (initial) on `--coral-red-soft`, ink `--coral-red-deep`; `.me-name{flex:1;font-weight:600;font-size:16px}`. Logo mark and wordmark in `--coral-red`/`--ink`.
- Tablet 768-1023 px (`@media (min-width:768px) and (max-width:1023px)`): `.side` is a visible rail, `width:88px`, `align-items:stretch`, padding `16px 8px`. Hide `.ui-brand span` (keep mark), `.search span`, `.me-name`, `.me .ui-icon:last-child`. Each `.nav` and the search button: `flex-direction:column;justify-content:center;gap:4px;min-height:64px;padding:8px 4px;font-size:12px;font-weight:500;text-align:center;white-space:normal` (label 12 px under the 24 px icon: set icon to 24 px here); active = `coral-red-soft` pill, radius 12. No label may be cut: check "Properties" and "Stay fees" fit in 72 px at 12 px (if not, allow two lines, never ellipsis). `.app` stays a row; `.main` padding handled by 1133. The me-menu list opens to the right of the rail (`left:calc(100% + 8px);bottom:0`).
- Tab bar: split `@media (max-width:1023px)` so `body.v2 .side{display:none}` and `body.v2 .tabs{display:flex;position:fixed;left:0;right:0;bottom:0;height:84px;background:#fff;border-top:1px solid var(--line);padding:6px 4px 22px;padding-bottom:calc(22px + env(safe-area-inset-bottom));z-index:5}` move into a new `@media (max-width:767px)` block (keep every following `.tabs .tab` rule in that block unchanged). Laptop/tablet 768-1023 keeps `.side` visible (rail CSS above). The phone rules at 88-102 and line 2379 already target 767 px and stay.
- `docs/design/MASTER.md` section 2 (anchor `## 2. Tokens`): add one line under the semantic layer listing the new tokens from step 1 and a note "page background cream `--page-cream`, host pages, light mode". Do not edit other docs here (1134 does the rest).
Run from `App/`:
`.venv/bin/python -m pytest tests/test_0705_v2_shell_browser.py tests/test_0895_sidebar_inert_heal_browser.py tests/test_host_account_navigation.py tests/test_icons_nav_1060.py -q --tb=short -x -rs 2>&1 | tail -30`. Fix test assertions only where they name removed items (section 3 last row). Commit `1132 step 4`.

## 5. Do not touch

- The phone layout: `dash-phone` markup, `ph-*` rules and the phone tab bar structure (only icons and the 768 px breakpoint change, as listed in section 4).
- Guest pages, admin pages, login and auth forms.
- Routes and templates for Smart locks and Invoices (they only move into the account menu).
- Migrations, `db.py`, any SQL, any new dependency, any new outbound request.
- Anything not listed in section 3 Files.

## 6. Commands (from `App/`, each ends `| tail -30`)

```
.venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py -q --tb=short -x -rs 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_0710_v2_mockup_match_browser.py -q --tb=short -x -rs 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_design_*.py tests/test_host_i18n.py -q --tb=short -x 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x -rs 2>&1 | tail -30
```
Rows used (test-map): host pages and host CSS, any host template/CSS/JS, v2 pages, static files and cache keys, design system, copy and translations. Browser files 0 skipped (`-rs`); a skip is a fail. No full suite.

## 7. Acceptance

- Host pages have the cream background; cards stay white; `grep -n "#faf6f0\|#d0452d" App/app/templates/*.html | wc -l` is 0 (tokens only).
- Laptop 1280 sidebar: no name box, search without `Ctrl K`, groups [Dashboard, Stays, Properties, Cleaning] [Stay fees, Payments, Booking site], bottom Ask Havel (only with `havel_on`), Help, Settings, hairline, avatar row with first name; no Smart locks or Invoices link in the sidebar, both in the account menu and routes `/smart-locks`, `/invoices` still 200.
- Items 48 px high, radius 12, icon 22, label 16/500, active 600 coral-red-deep on coral-red-soft, no count badge.
- Tablet 820: 88 px rail, 24 px icon with 12 px label under it, active pill; no horizontal scroll; no bottom tab bar between 768 and 1023; phone (390) unchanged.
- Icons: Cleaning brush-cleaning, Stay fees coins, Payments wallet in the sidebar, phone tab bar and `/menu`.
- UX gate (AGENTS rule 10, you do it, never ask the owner): screenshots at 390, 768, 1280 of `/` (dashboard) and one other host page (`/reservations`); write per page in the PR what you see at each width (390, 768, 1280); tick the [design-system checklist](../design/design-system.md) in the PR body; never silence a lint finding.
- Section 5 green, 0 skipped.

## 8. Stop and ask

Stop and report if: an anchor is missing; the tab bar and rail cannot coexist without touching phone markup; a contrast ratio is below 4.5; `data-command-shortcut` is needed by JS; `test_layout_lint_browser.py` flags something you cannot fix in 2 tries; more than 25 tool calls.

## 9. Report

Write `docs/tasks/1132-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations (`Done: steps 1 to k. Left: steps k+1 to 4.` if you hit the cap).
5. Questions.
6. Owner steps left.

Do not edit `docs/context/status.md`, `docs/context/decisions.md` or `docs/context/known-issues.md`. Push only to the PR branch; never push to `main`.

## Risk list (for the reviewer)

Read the full diff for: `App/app/templates/_shell_v2.html`, `App/app/static/app2.css` (the `/* 1132 sidebar */` block and the tab-bar media-query split), `App/app/static/tokens.css`, and any test assertion changes in `test_0705_v2_shell_browser.py`.

## Owner steps

1. Open the draft PR for branch `claude/great-fermi-lw5ogs` on GitHub and leave it in draft until 1134 ships.
2. After the executor report, review the UX gate screenshot notes in the PR body and the design-system checklist.
3. Merge 1132, then stack or merge 1133 and 1134 in order, only with `scripts/merge-pr-on-green.sh` when CI is green.
4. If contrast check or layout lint fails twice, read the executor report Questions before asking for a re-run.
