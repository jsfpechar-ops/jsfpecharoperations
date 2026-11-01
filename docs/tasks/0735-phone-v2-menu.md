# 0735 brief: phone v2 Menu (Airbnb style)

Status: todo (run after 0729 is committed on the same branch)
Executor: Haiku 5.5, alone, in a worktree of branch `claude/project-thread-50hyv5` that already has the 0729 commit.

## 1. Objective

`/menu` looks like screen `menu` of `docs/design/mockup/ubyhost-phone-v2.html`: "Menu" title with an initial avatar,
two tiles (guests this month, police reports this month), one soft "Add a property" card, plain rows with outline
icons and chevrons (no icon boxes, no second lines), a divider, then "Log out". It replaces the 0728 menu look.

## 2. Context

- Approved design: `docs/design/mockup/ubyhost-phone-v2.html` (do not edit it). Josef approved it app-wide on 2026-11-01 21:15.
- 0729 already added `PHONE_MOCKUP_V2`, `phone_url(mockup)` and the `phone_mockup` PAGES key in `App/tests/v2_mockup.py`.
- `reporting.month_summary(owner_user_id, today)` returns `{"guests", "nights", "reported"}` for the calendar month (one query).
- Standing rule: you may rewrite `App/tests/test_0728_menu_geometry_browser.py` and the `/menu` assertions in `App/tests/test_0718_menu_page.py` to the new design. Change no other test; if one fails, stop and ask.

## 3. Files

- `App/app/templates/menu.html`, `App/app/routes/admin.py` (`menu_view` only)
- `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`
- `App/app/static/app2.css`, `App/app/templates/base.html` (css key), `App/tests/static_versions.json`
- `App/tests/v2_mockup.py`, `App/tests/test_0728_menu_geometry_browser.py`, `App/tests/test_0718_menu_page.py`
- new: `docs/tasks/0735-phone-v2-menu-report.md`, `docs/tasks/screenshots-0735/`

## 4. Steps

1. `App/app/routes/admin.py`, `menu_view`: replace the body from `from .. import claim, cleaning` down to the closing `)` of `return render(...)` with:
   ```python
    from .. import claim, cleaning

    owner = access.owner_id(request)
    today = claim.prague_today()
    cleaning_today = None
    try:
        events = cleaning.schedule(owner, today, today)["events"]
        cleaning_today = sum(
            1 for e in events if e.get("kind") == "cleaning" and str(e.get("start", ""))[:10] == today.isoformat()
        )
    except Exception:
        cleaning_today = None
    return render(
        request,
        "menu.html",
        {
            "cleaning_today": cleaning_today,
            "month": reporting.month_summary(owner, today),
        },
    )
   ```
   Check `reporting` is imported at the top of `admin.py` (`grep -n "^from .. import\|^from \.\. import\|import reporting" App/app/routes/admin.py | head`); it is used by `dashboard()`, so it should be. `apartments` is no longer passed: confirm with `grep -n "apartments" App/app/templates/menu.html` after step 3 that the template does not use it.
2. i18n. In `App/app/host_i18n.py`, English dict: delete the 7 lines `"menu.sub.cleaning_live"` … `"menu.sub.admin"` and put in their place:
   ```python
        "menu.tile.guests": "Guests",
        "menu.tile.police": "Police reports",
        "menu.tile.when": "This month",
        "menu.add_property_sub": "Get it ready for guests",
        "menu.help": "Get help",
   ```
   Czech dict: delete the 7 `"menu.sub.*"` lines and put:
   ```python
        "menu.tile.guests": "Hosté",
        "menu.tile.police": "Hlášení policii",
        "menu.tile.when": "Tento měsíc",
        "menu.add_property_sub": "Připravte ho pro hosty",
        "menu.help": "Pomoc",
   ```
   `App/app/host_vi_i18n.py`: delete the 7 `"menu.sub.*"` lines and put:
   ```python
    "menu.tile.guests": "Khách",
    "menu.tile.police": "Khai báo công an",
    "menu.tile.when": "Tháng này",
    "menu.add_property_sub": "Chuẩn bị cho khách",
    "menu.help": "Trợ giúp",
   ```
   Then `grep -rn "menu\.sub\." App/app App/tests | head` must print nothing (fix any test that still uses them per the standing rule).
3. Replace the whole content of `App/app/templates/menu.html` with:
   ```jinja
{% extends "host_page.html" %}
{% set v2 = true %}
{% from "_icons.html" import icon with context %}
{% set nav = 'menu' %}
{% block title %}{{ t('nav.menu') }}{% endblock %}
{% block page_title %}{% endblock %}
{% block body %}
{#- 0735: phone v2 Menu (docs/design/mockup/ubyhost-phone-v2.html, screen menu). -#}
<div class="mh"><h1 class="big">{{ t('nav.menu') }}</h1><a class="me-av" href="/settings" aria-label="{{ t('nav.account') }}">{{ (workspace_user.display_name or workspace_user.username)[:1] | upper }}</a></div>
<div class="tiles">
  <a class="tile" href="/reservations"><b>{{ t('menu.tile.guests') }}</b><small>{{ t('menu.tile.when') }}</small><span class="v">{{ month.guests }}</span></a>
  <a class="tile" href="/submissions"><b>{{ t('menu.tile.police') }}</b><small>{{ t('menu.tile.when') }}</small><span class="v">{{ month.reported }}</span></a>
</div>
<a class="promo" href="/apartments/new"><span class="pi" aria-hidden="true">{{ icon('plus', 24) }}</span><span><b>{{ t('apartments.add') }}</b><small>{{ t('menu.add_property_sub') }}</small></span></a>
<nav class="list plain" aria-label="{{ t('nav.menu') }}">
  <a class="row" href="/cleaning">{{ icon('brush-cleaning', 26) }}<span class="t">{{ t('nav.cleaning') }}</span>{% if cleaning_today %}<span class="badge">{{ cleaning_today }}</span>{% endif %}{{ icon('chevron-right', 20, 'chev') }}</a>
  <a class="row" href="/stay-fees">{{ icon('receipt', 26) }}<span class="t">{{ t('nav.stay_fees') }}</span>{{ icon('chevron-right', 20, 'chev') }}</a>
  <a class="row" href="/payments">{{ icon('credit-card', 26) }}<span class="t">{{ t('nav.payments') }}</span>{{ icon('chevron-right', 20, 'chev') }}</a>
  <a class="row" href="/settings">{{ icon('settings', 26) }}<span class="t">{{ t('nav.settings') }}</span>{{ icon('chevron-right', 20, 'chev') }}</a>
  <a class="row" href="/guide">{{ icon('circle-help', 26) }}<span class="t">{{ t('menu.help') }}</span>{{ icon('chevron-right', 20, 'chev') }}</a>
  {% if current_user.role == 'admin' %}<a class="row" href="/admin">{{ icon('shield', 26) }}<span class="t">{{ t('nav.admin') }}</span>{{ icon('chevron-right', 20, 'chev') }}</a>{% endif %}
</nav>
<form method="post" action="/logout" class="list plain menu-logout"><button class="row" type="submit">{{ icon('log-out', 26) }}<span class="t">{{ t('nav.logout') }}</span></button></form>
{% endblock %}
   ```
   Check the icon macro's signature first (`sed -n 1,8p App/app/templates/_icons.html`); if it does not take `(name, size, class)` in that order, adapt the calls and say so in the report. If `t('apartments.add')` or `t('nav.account')` is missing in en/cs/vi, stop and ask.
4. `App/app/static/app2.css`:
   a. Delete these now-unused rules (exact text; each is part of a longer line, delete only the named rule):
      - `body.v2 .menu-logout{margin-top:16px}body.v2 .menu-logout .row{width:100%;border:0;background:none;font:inherit;text-align:left;cursor:pointer}body.v2 .menu-logout .ic{background:#efefeb;color:var(--ink2)}`
      - the whole line `  body.v2 .me{display:flex;gap:14px;align-items:center}`
      - the whole line `  body.v2 .me .av{width:60px;height:60px;font-size:24px}`
      - the whole line starting `  body.v2 .card.me{margin-top:12px;`
      - the whole line `  body.v2 .menu-list .row .t{flex:1}`
      - the whole lines starting `  body.v2 .card.me .me-link`, `  body.v2 .card.me b{`, `  body.v2 .card.me .who b{` (0719 block)
      - the whole line `@media (min-width:1024px){body.v2 .menu-list .row{display:flex;align-items:center;gap:14px;min-height:48px;padding:12px 0;border-bottom:1px solid var(--line)}}`
      - the last line of the file before 0729's block: `body.v2 .menu-list .row .t small{display:block;color:var(--ink3);font-size:14px;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}`
      After deleting, `grep -n "card\.me\|menu-list\|\.me-link\|body.v2 \.me[ {]" App/app/static/app2.css` must print nothing.
   b. Append at the end of the file (all widths: the Menu page is reached from the phone tab bar, and must not look broken if opened wide):
   ```css
/* 0735 phone v2 Menu (Airbnb style); values from docs/design/mockup/ubyhost-phone-v2.html, screen menu */
body.v2 .mh{display:flex;align-items:center;justify-content:space-between;margin:6px 0 24px}
body.v2 .mh .big{font-size:30px;font-weight:800;letter-spacing:-.02em;line-height:1.15;margin:0}
body.v2 .me-av{width:44px;height:44px;border-radius:50%;background:var(--accs);color:var(--acc-text);display:grid;place-items:center;font-weight:800;text-decoration:none}
body.v2 .tiles{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:16px}
body.v2 .tile{background:#fff;border-radius:20px;box-shadow:0 6px 24px rgba(0,0,0,.08),0 0 0 1px rgba(0,0,0,.03);padding:16px 16px 18px;height:150px;display:flex;flex-direction:column;color:inherit;text-decoration:none}
body.v2 .tile b{font-size:16px}body.v2 .tile small{color:var(--ink3);font-size:14px;margin-top:2px}
body.v2 .tile .v{margin-top:auto;font-size:32px;font-weight:800;letter-spacing:-.02em}
body.v2 .promo{background:#f4f3ef;border-radius:20px;padding:18px;display:flex;gap:14px;align-items:center;margin-bottom:10px;color:inherit;text-decoration:none}
body.v2 .promo .pi{width:44px;height:44px;border-radius:12px;background:#fff;display:grid;place-items:center;color:var(--acc);flex:none}
body.v2 .promo b{font-size:17px;display:block}body.v2 .promo small{color:var(--ink3);font-size:14px}
body.v2 .list.plain .row{display:flex;align-items:center;gap:18px;min-height:56px;padding:15px 0;border:0;font:inherit;font-size:17px;font-weight:500;color:var(--ink);text-decoration:none;width:100%;text-align:left;background:none;cursor:pointer}
body.v2 .list.plain .row > svg:first-child{width:26px;height:26px;stroke-width:1.6;flex:none}
body.v2 .list.plain .row .t{flex:1;min-width:0}
body.v2 .list.plain .badge{background:var(--acc);color:#fff;font-size:12px;font-weight:800;border-radius:999px;min-width:22px;height:22px;display:grid;place-items:center;padding:0 6px}
body.v2 .list.plain .chev{width:20px;height:20px;color:var(--ink3);flex:none}
body.v2 .menu-logout{margin-top:8px;border-top:1px solid var(--line);padding-top:8px}
   ```
5. Cache key: change the app2.css key in `App/app/templates/base.html` to `20261101-0735`, then from `App/` run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`.
6. `App/tests/v2_mockup.py`, `menu` PAGES entry: add `"phone_mockup": PHONE_MOCKUP_V2,`; set `"phone_selectors"` to
   `[".tabs", ".tab:not(.on)", ".tab.on", ".mh .big", ".me-av", ".tile", ".tile b", ".tile small", ".tile .v", ".promo", ".promo .pi", ".promo b", ".promo small", ".list.plain .row", ".list.plain .badge", ".menu-logout"]`;
   set `"missing_ok"` to `{".list.plain .badge": "the Cleaning badge shows only when a cleaning is planned for today"}`.
   In `BOX_OVERRIDES` delete the `.card.me`, `.card.me@320` and `.big` keys.
   Note: in the mockup `.tab.on` is Today and on `/menu` it is Menu; both use the same style, so the style comparison still holds.
7. Run `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -q --tb=short -x -k menu 2>&1 | tail -30`.
   Box failures that follow text length (`.tile small`, `.promo small`, `.promo b`, `.list.plain .row` height when a label wraps at 320) get a `"selector@width"` override with the app value under `# text-dependent: app copy vs phone v2 mockup demo copy (0735)`. Style failures mean the CSS is wrong: fix the CSS, never override a style.
8. Rewrite `App/tests/test_0728_menu_geometry_browser.py` for the new design (keep its fixtures, imports and widths 320, 360, 390, 768; update its docstring to "0728/0735"). Assert at each width:
   - `.mh`: `.big` font-size 30px; `.me-av` 44×44 and its right edge 20 px (±2) from the viewport's right edge;
   - `.tiles`: two `.tile`s of equal width (±1 px), each 150 px tall, side by side (same top), gap 14 px (±1), together spanning the content width;
   - `.promo` spans the content width; `.promo .pi` 44×44;
   - every `.list.plain .row` (menu rows and log-out) is at least 56 px tall and spans the content width; each row's first svg is 26×26; no row has a second line (no `small` inside `.list.plain`); menu rows have a `.chev` whose right edge is within 2 px of the row's right edge; the log-out row has no `.chev`;
   - `.menu-logout` has a 1 px top border and sits below the last menu row;
   - every text element is inside the viewport; no horizontal scroll; the log-out row ends above the `.tabs` top after scrolling to the bottom (skip this one at 768 if the tab bar is hidden there).
9. `App/tests/test_0718_menu_page.py`: update only what fails because of the new markup (links must all still be present: /cleaning, /stay-fees, /payments, /settings, /guide, /admin for admins, /apartments/new, /logout form).
10. Screenshots: `UBYHOST_SHOTS_V2=1 ... -k screenshots` as in 0729; copy the menu 390 and 320 phone shots to `docs/tasks/screenshots-0735/` (`menu-390.png`, `menu-320.png`); `git restore` every other tracked PNG the run changed.
11. Commit: `git add -A App docs && git commit -m "0735: phone v2 Menu (Airbnb style)"` with the Co-Authored-By trailer. Do not push.

## 5. Do not touch

- `docs/design/mockup/*.html`, `_shell_v2.html`, the tab bar, `dashboard.html`, the 0729 CSS block, other pages. No new dependencies, no JS.

## 6. Commands

From `App/`:
```
PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py tests/test_0728_menu_geometry_browser.py tests/test_0718_menu_page.py tests/test_0729_phone_today_geometry_browser.py tests/test_static_versions.py tests/test_0252_touch_sweep_browser.py -q --tb=short -rs 2>&1 | tail -30
.venv/bin/python -m ruff check app tests --select E9,F63,F7,F82,F401,F841 2>&1 | tail -5
```
From the repo root: `python3 scripts/design_lint.py | tail -5`, `python3 scripts/context_lint.py | tail -5`.

## 7. Acceptance

- [ ] `/menu` at 320, 360, 390 and 768 matches the mockup's menu screen (title + avatar, two tiles, promo card, plain rows, divider, Log out).
- [ ] No `menu.sub.*` keys, no `.card.me` / `.menu-list` CSS left.
- [ ] All listed tests pass with 0 skipped; lints OK; css key bumped.

## 8. Stop and ask

- A test outside the standing rule fails, a translation key named in step 3 is missing, or `reporting` is not importable in `admin.py`.
- 25 tool calls without green tests: commit what you have and report.

## 9. Report

Write `docs/tasks/0735-phone-v2-menu-report.md`: Status line, changed files, command tails, every override added with its value, deviations, screenshot paths.
