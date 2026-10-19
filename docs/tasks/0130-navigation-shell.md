# 0130: Navigation shell: desktop sidebar, phone top bar, bottom tab bar and More sheet

Status: todo
Depends on: 0129 | Base commit: df8b842 | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit each step as `0130 step k`. Never push, never open a PR. Runs after 0129 (both touch `host2.css`).

## 1. Objective

Replace the slide-out menu and the mixed-weight hand-drawn icons with the v2 shell: a 240 px sidebar with Lucide icons on desktop, and on phone a 52 px top bar plus a five-tab bottom bar (Dashboard, Stays, Properties, Cleaning, More) whose More opens a bottom sheet (MASTER 6). Every host page gets it at once through `base.html`; the account menu, environment badge, command palette and shortcuts stay.

## 2. Context

Rules: MASTER 6.1 to 6.3, 4.2 (active item is tint only), 9.2 (44 px), owner defaults in MASTER 14 (More tab; Stay fees and Smart locks always visible). Tests that read the old chrome: `tests/test_signed_in_chrome.py` expects `<div class="host-rail-bottom">…</aside>` with the account menu, the `mailto:` support line, `href="/settings"` and the language buttons exactly as today; `tests/test_cleaning_browser.py` line 126 expects `.sidebar-nav a[href="/cleaning"] svg` to count 1; `tests/test_property_navigation_browser.py` line 457 clicks `.sidebar-nav a[href="/reservations"]`; `tests/test_host_fit_browser.py`, `test_host_wide_geometry_browser.py` and `test_property_navigation_browser.py` click `button[data-sidebar-collapse]` and read `body.sidebar-collapsed`. The new shell keeps those hooks, so no test changes.

Anchor A, `App/app/templates/base.html` (start of the old chrome):

```
{% if show_nav | default(true) %}
<header class="appbar">
  <button class="nav-toggle" type="button" data-nav-toggle aria-controls="app-sidebar" aria-label="{{ t('a11y.open_menu') }}" aria-expanded="false">
```

Anchor B, `App/app/templates/base.html` (end of the old chrome):

```
  </div>
  {% endif %}
</aside>
{% endif %}

<main id="main-content" class="wrap {{ wrap_class | default('') }} {{ 'with-sidebar' if show_nav | default(true) }}">
```

Anchor C, `App/app/templates/base.html`:

```
{% if (show_nav | default(true)) and passkeys_enabled() %}<script src="/static/passkeys.js?v=20261006a" defer></script>{% endif %}
```

Anchor D, `App/app/host_i18n.py` (English block):

```
        "nav.stays": "Stays",
```

Anchor E, `App/app/host_i18n.py` (Czech block):

```
        "nav.stays": "Pobyty",
```

The account footer markup below is copied from today's `base.html` lines 76 to 107 and must stay byte-identical inside the new sidebar.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/_shell_sidebar.html` | create | desktop sidebar |
| `App/app/templates/_shell_topbar.html` | create | phone top bar |
| `App/app/templates/_shell_tabbar.html` | create | phone tab bar and the More sheet |
| `App/app/templates/base.html` | edit | replace the old chrome with the three includes; load `shell.js` |
| `App/app/static/shell.js` | create | opens and closes the More sheet |
| `App/app/static/host2.css` | edit | append the shell rules |
| `App/app/host_i18n.py` | edit | `nav.cleaning`, `nav.more`, `nav.admin`, `nav.smart_locks` in both languages |
| `App/tests/test_design_shell.py` | create | markup and i18n |
| `App/tests/test_design_shell_browser.py` | create | geometry at 390 and 1280 |

No other file may change.

## 4. Steps

1. In `App/app/host_i18n.py`, replace Anchor D with:

```
        "nav.stays": "Stays",
        "nav.cleaning": "Cleaning",
        "nav.more": "More",
        "nav.admin": "Admin",
        "nav.smart_locks": "Smart locks",
```

   and Anchor E with:

```
        "nav.stays": "Pobyty",
        "nav.cleaning": "Úklid",
        "nav.more": "Další",
        "nav.admin": "Administrace",
        "nav.smart_locks": "Chytré zámky",
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -30` (if `test_host_i18n.py` does not exist, use `-k i18n`). Expected: passed.

2. Create `App/app/templates/_shell_sidebar.html`:

```
{#- Design v2 desktop sidebar (MASTER 6.3). Hidden below 1024 px by host2.css.
    Keeps id="app-sidebar", .sidebar-nav and data-sidebar-collapse for app.js and the browser tests. -#}
{% from "_icons.html" import icon with context %}
{% set stays_nav = nav in ('reservations', 'submissions', 'housebook') %}
{% set properties_nav = nav in ('apartments', 'guest_links', 'automation', 'entities', 'smart_locks') %}
<aside class="ui-sidebar" id="app-sidebar">
  <div class="ui-brand">
    <a class="brand plain" href="/" aria-label="UbyHost"><img class="brand-logo" src="/static/ubyhost-mark.png?v=20261004a" alt=""><span class="brand-word">UbyHost</span></a>
    <button class="ui-btn ui-btn-quiet ui-btn-icon ui-btn-compact sidebar-collapse" type="button" data-sidebar-collapse aria-expanded="true" aria-label="{{ t('a11y.hide_menu') }}">{{ icon('panel-left', 16) }}</button>
  </div>
  <span class="env-badge ui-env {{ ubyport_env }}" title="{{ t('env.where_reports_go') }}">{{ t('env.' ~ ubyport_env) }}</span>
  <button class="ui-search-row" type="button" data-command-open>{{ icon('search', 16) }}<span>{{ t('host.search') }}</span><kbd data-command-shortcut>Ctrl K</kbd></button>
  <nav class="ui-nav sidebar-nav" aria-label="{{ t('a11y.main_navigation') }}">
    {% for href, icon_name, label, active in [
        ('/', 'layout-dashboard', t('nav.overview'), nav == 'dashboard'),
        ('/reservations', 'calendar-days', t('nav.stays'), stays_nav),
        ('/apartments', 'house', t('nav.properties'), properties_nav),
        ('/invoices', 'receipt', t('nav.invoices'), nav == 'invoices'),
        ('/cleaning', 'brush-cleaning', t('nav.cleaning'), nav == 'cleaning'),
        ('/stay-fees', 'coins', t('nav.stay_fees'), nav == 'stay_fees')] %}
    <a href="{{ href }}" title="{{ label }}" {% if active %}aria-current="page"{% endif %}>{{ icon(icon_name, 20) }}<span>{{ label }}</span>{% if href == '/' and nav_action_count is defined and nav_action_count %}<span class="ui-nav-count">{{ nav_action_count if nav_action_count < 10 else '9+' }}</span>{% endif %}</a>
    {% endfor %}
    <span class="ui-nav-gap" aria-hidden="true"></span>
    <a href="/smart-locks" title="{{ t('nav.smart_locks') }}" {% if nav == 'smart_locks' %}aria-current="page"{% endif %}>{{ icon('key-round', 20) }}<span>{{ t('nav.smart_locks') }}</span></a>
    <a href="/settings" title="{{ t('nav.settings') }}" {% if nav == 'settings' %}aria-current="page"{% endif %}>{{ icon('settings', 20) }}<span>{{ t('nav.settings') }}</span></a>
  </nav>
  {% if current_user %}
  <div class="host-rail-bottom">
    <nav class="ui-nav ui-nav-bottom" aria-label="{{ t('nav.guide') }}">
      <a class="host-help" href="/guide">{{ icon('book-open', 20) }}<span>{{ t('nav.guide') }}</span></a>
      {% if current_user.role == 'admin' %}<a href="/admin/users" {% if nav == 'admin' %}aria-current="page"{% endif %}>{{ icon('shield', 20) }}<span>{{ t('nav.admin') }}</span></a>{% endif %}
    </nav>
    <details class="host-account" data-host-account>
      <summary aria-label="{{ t('nav.account') }}: {{ workspace_user.display_name or workspace_user.username }}">
        <span class="sidebar-user-avatar" aria-hidden="true">{{ (workspace_user.display_name or workspace_user.username)[:1] | upper }}</span>
        <span class="host-account-name">{{ workspace_user.display_name or workspace_user.username }}<small>{{ t('nav.account') }}</small></span>
      </summary>
      <div class="host-account-menu">
        <a href="/settings">{{ t('nav.settings') }}</a>
        {% if operator().email %}
        <a class="host-menu-support" href="mailto:{{ operator().email }}">{{ t('nav.support') }}<small>{{ operator().email }}</small></a>
        {% endif %}
        <div class="host-menu-rule"></div>
        <a href="/settings/archived">{{ t('settings.nav.archive') }}</a>
        <a href="/privacy-requests">{{ t('nav.privacy_requests') }}</a>
        {% if current_user.role == 'admin' %}
        <a href="/admin/users">{{ t('nav.users') }}</a>
        <a href="/admin/incidents">{{ t('users.incidents_link') }}</a>
        <a href="/admin/operations">{{ t('ops.title') }}</a>
        <a href="/admin/funnel">{{ t('funnel.title') }}</a>
        {% endif %}
        <div class="host-menu-rule"></div>
        <form method="post" action="/language" class="lang-switch compact">
          <input type="hidden" name="next" value="{{ request.url.path }}">
          <button type="submit" name="lang" value="en" class="{{ 'is-active' if lang == 'en' }}">{{ t('lang.en') }}</button>
          <button type="submit" name="lang" value="cs" class="{{ 'is-active' if lang == 'cs' }}">{{ t('lang.cs') }}</button>
        </form>
        <button class="nav-button" type="button" data-shortcuts-open>{{ t('shortcuts.open') }}</button>
        <form method="post" action="/logout"><button class="nav-button" type="submit">{{ t('nav.logout') }}</button></form>
      </div>
    </details>
  </div>
  {% endif %}
</aside>
```

   Command: `cd App && .venv/bin/python -c "from app.templating import templates; templates.get_template('_shell_sidebar.html'); print('compiles')"`. Expected: `compiles`.

3. Create `App/app/templates/_shell_topbar.html`:

```
{#- Design v2 phone top bar (MASTER 6.2.5). Shown below 1024 px only. Not sticky. -#}
{% from "_icons.html" import icon with context %}
<header class="ui-topbar">
  <a class="brand plain" href="/" aria-label="UbyHost"><img class="brand-logo" src="/static/ubyhost-mark.png?v=20261004a" alt=""></a>
  <span class="env-badge ui-env {{ ubyport_env }}" title="{{ t('env.where_reports_go') }}">{{ t('env.' ~ ubyport_env) }}</span>
  <span class="grow"></span>
  <button class="ui-btn ui-btn-quiet ui-btn-icon" type="button" data-command-open aria-label="{{ t('command.open') }}">{{ icon('search', 20) }}</button>
</header>
```

4. Create `App/app/templates/_shell_tabbar.html`:

```
{#- Design v2 phone bottom tab bar and More sheet (MASTER 6.2). Shown below 1024 px only.
    More is a real link to Settings; shell.js turns it into the sheet. -#}
{% from "_icons.html" import icon with context %}
{% set stays_nav = nav in ('reservations', 'submissions', 'housebook') %}
{% set properties_nav = nav in ('apartments', 'guest_links', 'automation', 'entities', 'smart_locks') %}
{% set more_nav = nav in ('invoices', 'stay_fees', 'settings', 'admin', 'guide') %}
<nav class="ui-tabbar" aria-label="{{ t('a11y.main_navigation') }}">
  <a href="/" {% if nav == 'dashboard' %}aria-current="page"{% endif %}><span class="ui-tabbar-ic">{{ icon('layout-dashboard', 24) }}</span><span>{{ t('nav.overview') }}</span>{% if nav_action_count is defined and nav_action_count %}<span class="ui-nav-count">{{ nav_action_count if nav_action_count < 10 else '9+' }}</span>{% endif %}</a>
  <a href="/reservations" {% if stays_nav %}aria-current="page"{% endif %}><span class="ui-tabbar-ic">{{ icon('calendar-days', 24) }}</span><span>{{ t('nav.stays') }}</span></a>
  <a href="/apartments" {% if properties_nav %}aria-current="page"{% endif %}><span class="ui-tabbar-ic">{{ icon('house', 24) }}</span><span>{{ t('nav.properties') }}</span></a>
  <a href="/cleaning" {% if nav == 'cleaning' %}aria-current="page"{% endif %}><span class="ui-tabbar-ic">{{ icon('brush-cleaning', 24) }}</span><span>{{ t('nav.cleaning') }}</span></a>
  <a href="/settings" data-sheet-open="more-sheet" {% if more_nav %}aria-current="page"{% endif %}><span class="ui-tabbar-ic">{{ icon('ellipsis', 24) }}</span><span>{{ t('nav.more') }}</span></a>
</nav>
<dialog id="more-sheet" class="ui-dialog" aria-label="{{ t('nav.more') }}">
  <div class="ui-sheet">
    <span class="ui-sheet-handle" aria-hidden="true"></span>
    <nav class="ui-menu-panel ui-sheet-list" aria-label="{{ t('nav.more') }}">
      <button class="ui-menu-item" type="button" data-command-open>{{ icon('search', 16) }}{{ t('host.search') }}</button>
      <a class="ui-menu-item" href="/invoices">{{ icon('receipt', 16) }}{{ t('nav.invoices') }}</a>
      <a class="ui-menu-item" href="/stay-fees">{{ icon('coins', 16) }}{{ t('nav.stay_fees') }}</a>
      <a class="ui-menu-item" href="/smart-locks">{{ icon('key-round', 16) }}{{ t('nav.smart_locks') }}</a>
      <a class="ui-menu-item" href="/settings">{{ icon('settings', 16) }}{{ t('nav.settings') }}</a>
      <a class="ui-menu-item" href="/guide">{{ icon('book-open', 16) }}{{ t('nav.guide') }}</a>
      {% if current_user and current_user.role == 'admin' %}<a class="ui-menu-item" href="/admin/users">{{ icon('shield', 16) }}{{ t('nav.admin') }}</a>{% endif %}
      <a class="ui-menu-item" href="/settings/archived">{{ icon('archive', 16) }}{{ t('settings.nav.archive') }}</a>
      <a class="ui-menu-item" href="/privacy-requests">{{ icon('file-lock', 16) }}{{ t('nav.privacy_requests') }}</a>
      <form method="post" action="/language" class="lang-switch compact ui-sheet-lang">
        <input type="hidden" name="next" value="{{ request.url.path }}">
        <button type="submit" name="lang" value="en" class="{{ 'is-active' if lang == 'en' }}">{{ t('lang.en') }}</button>
        <button type="submit" name="lang" value="cs" class="{{ 'is-active' if lang == 'cs' }}">{{ t('lang.cs') }}</button>
      </form>
      <form method="post" action="/logout"><button class="ui-menu-item" type="submit">{{ icon('log-out', 16) }}{{ t('nav.logout') }}</button></form>
    </nav>
    <button class="ui-btn ui-btn-secondary" type="button" data-sheet-close>{{ t('common.close') }}</button>
  </div>
</dialog>
```

5. In `App/app/templates/base.html`: delete everything from Anchor A's second line (`<header class="appbar">`) through the `</aside>` line of Anchor B inclusive, and put the includes in their place, so the region reads:

```
{% if show_nav | default(true) %}
{% include "_shell_topbar.html" %}
{% include "_shell_sidebar.html" %}
{% endif %}

<main id="main-content" class="wrap {{ wrap_class | default('') }} {{ 'with-sidebar' if show_nav | default(true) }}">
```

   Then replace Anchor C with:

```
{% if (show_nav | default(true)) and passkeys_enabled() %}<script src="/static/passkeys.js?v=20261006a" defer></script>{% endif %}
{% if show_nav | default(true) %}{% include "_shell_tabbar.html" %}<script src="/static/shell.js?v=20261019-v2a" defer></script>{% endif %}
```

   Command: `grep -c 'nav-toggle\|nav-backdrop\|sidebar-expand\|class="appbar"' App/app/templates/base.html`. Expected: `0`. Then `cd App && .venv/bin/python -m pytest tests/test_signed_in_chrome.py tests/test_skeleton_loaders.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed.

6. Create `App/app/static/shell.js`:

```
/* Design v2 shell: the More tab opens a bottom sheet (MASTER 6.2.4).
   Without JavaScript the tab is a plain link to Settings. */
(function () {
  "use strict";
  function sheetFor(trigger) {
    return document.getElementById(trigger.getAttribute("data-sheet-open"));
  }
  document.addEventListener("click", function (event) {
    var opener = event.target.closest ? event.target.closest("[data-sheet-open]") : null;
    if (opener) {
      var sheet = sheetFor(opener);
      if (sheet && typeof sheet.showModal === "function") {
        event.preventDefault();
        if (!sheet.open) sheet.showModal();
      }
      return;
    }
    var closer = event.target.closest ? event.target.closest("[data-sheet-close]") : null;
    if (closer) {
      var dialog = closer.closest("dialog");
      if (dialog) dialog.close();
      return;
    }
    var open = event.target.closest ? event.target.closest("dialog.ui-dialog[open]") : null;
    if (open && event.target === open) open.close();
  });
  document.addEventListener("click", function (event) {
    var palette = event.target.closest ? event.target.closest("#more-sheet [data-command-open]") : null;
    if (palette) { var s = document.getElementById("more-sheet"); if (s && s.open) s.close(); }
  }, true);
})();
```

7. Append to `App/app/static/host2.css`:

```

/* ---- 6 shell: sidebar, top bar, tab bar ---- */
.host-workspace .ui-sidebar { position: fixed; inset: 0 auto 0 0; width: var(--nav-w); box-sizing: border-box; background: var(--surface); border-right: 1px solid var(--line); padding: var(--space-3); display: flex; flex-direction: column; gap: var(--space-1); overflow-y: auto; z-index: var(--z-drawer); transform: none; }
.host-workspace .wrap.with-sidebar { margin-left: var(--nav-w); padding: var(--space-8) var(--gutter) var(--space-12); }
.host-workspace .ui-brand { display: flex; align-items: center; justify-content: space-between; height: var(--topbar-h); padding: 0 var(--space-2); }
.host-workspace .ui-brand .brand { display: inline-flex; align-items: center; gap: var(--space-3); font-weight: 700; font-size: var(--size-16); color: var(--ink); text-decoration: none; }
.host-workspace .ui-env { display: inline-flex; align-items: center; height: var(--badge-h); padding: 0 var(--badge-px); border-radius: var(--radius-pill); background: var(--st-neutral-bg); color: var(--st-neutral-ink); font-size: var(--size-12); font-weight: 600; margin: 0 var(--space-2) var(--space-2); width: fit-content; }
.host-workspace .ui-search-row { display: flex; align-items: center; gap: var(--space-3); height: calc(var(--control-h) - var(--space-1)); padding: 0 var(--space-3); border-radius: var(--radius-2); background: var(--surface-2); color: var(--ink-3); font: inherit; font-size: var(--size-14); border: 0; width: 100%; cursor: pointer; margin: 0 0 var(--space-2); }
.host-workspace .ui-search-row kbd { margin-left: auto; font: inherit; font-size: var(--size-12); color: var(--ink-3); border: 1px solid var(--line); border-radius: var(--radius-1); padding: 0 var(--space-1); background: var(--surface); }
.host-workspace .ui-nav { display: flex; flex-direction: column; gap: var(--space-1); }
.host-workspace .ui-nav a { display: flex; align-items: center; gap: var(--space-3); min-height: var(--nav-item-h); height: var(--nav-item-h); padding: 0 var(--space-3); border-radius: var(--radius-2); color: var(--ink-2); text-decoration: none; font-size: var(--size-14); font-weight: 550; box-shadow: none; background: transparent; }
.host-workspace .ui-nav a:hover { background: var(--surface-2); color: var(--ink); }
.host-workspace .ui-nav a[aria-current="page"] { background: var(--accent-soft); color: var(--accent-ink); font-weight: 600; }
.host-workspace .ui-nav a[aria-current="page"] .ui-icon { color: var(--accent); stroke-width: 2.25; }
.host-workspace .ui-nav-count { margin-left: auto; min-width: var(--size-18); height: var(--size-18); padding: 0 var(--space-1); border-radius: var(--radius-pill); background: var(--accent); color: var(--on-accent); font-size: var(--size-11); font-weight: 600; display: grid; place-items: center; }
.host-workspace .ui-nav-gap { display: block; height: var(--space-4); }
.host-workspace .host-rail-bottom { margin-top: auto; }
.host-workspace .ui-topbar, .host-workspace .ui-tabbar { display: none; }
body.host-workspace.sidebar-collapsed .ui-sidebar { width: var(--nav-w-collapsed); padding: var(--space-3) var(--space-2); }
body.host-workspace.sidebar-collapsed .wrap.with-sidebar { margin-left: var(--nav-w-collapsed); }
body.host-workspace.sidebar-collapsed .ui-sidebar :is(.brand-word, .ui-env, .ui-search-row span, .ui-search-row kbd, .ui-nav a > span:not(.ui-nav-count), .host-account-name) { display: none; }
body.host-workspace.sidebar-collapsed .ui-sidebar .ui-nav a, body.host-workspace.sidebar-collapsed .ui-sidebar .ui-search-row { justify-content: center; padding: 0; }
body.host-workspace.sidebar-collapsed .ui-brand { flex-direction: column; height: auto; gap: var(--space-2); }

@media (max-width: 1279px) and (min-width: 1024px) {
  .host-workspace .ui-sidebar { width: var(--nav-w-collapsed); padding: var(--space-3) var(--space-2); }
  .host-workspace .wrap.with-sidebar { margin-left: var(--nav-w-collapsed); }
  .host-workspace .ui-sidebar :is(.brand-word, .ui-env, .ui-search-row span, .ui-search-row kbd, .ui-nav a > span:not(.ui-nav-count), .host-account-name) { display: none; }
  .host-workspace .ui-sidebar .ui-nav a, .host-workspace .ui-sidebar .ui-search-row { justify-content: center; padding: 0; }
  .host-workspace .ui-brand { flex-direction: column; height: auto; gap: var(--space-2); }
}
@media (max-width: 1023px) {
  .host-workspace .ui-sidebar, .host-workspace .sidebar-expand { display: none; }
  .host-workspace .wrap.with-sidebar, body.host-workspace.sidebar-collapsed .wrap.with-sidebar { margin-left: 0; padding: var(--space-6) var(--space-4) calc(var(--tabbar-h) + env(safe-area-inset-bottom) + var(--space-6)); }
  .host-workspace .ui-topbar { display: flex; align-items: center; gap: var(--space-2); height: var(--topbar-h); padding: 0 var(--space-2) 0 var(--space-4); background: var(--surface); border-bottom: 1px solid var(--line); }
  .host-workspace .ui-topbar .ui-env { margin: 0; }
  .host-workspace .ui-tabbar { position: fixed; inset: auto 0 0 0; display: grid; grid-template-columns: repeat(5, 1fr); height: calc(var(--tabbar-h) + env(safe-area-inset-bottom)); padding-bottom: env(safe-area-inset-bottom); background: var(--surface); border-top: 1px solid var(--line); z-index: var(--z-sticky); }
  .host-workspace .ui-tabbar a { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px; min-height: var(--control-h-phone); color: var(--ink-2); text-decoration: none; font-size: var(--size-11); font-weight: 500; position: relative; }
  .host-workspace .ui-tabbar-ic { display: grid; place-items: center; width: var(--control-h-phone); height: calc(var(--space-6) + var(--space-1)); border-radius: var(--radius-pill); }
  .host-workspace .ui-tabbar a[aria-current="page"] { color: var(--accent-ink); font-weight: 600; }
  .host-workspace .ui-tabbar a[aria-current="page"] .ui-tabbar-ic { background: var(--accent-soft); }
  .host-workspace .ui-tabbar a[aria-current="page"] .ui-icon { color: var(--accent); stroke-width: 2.25; }
  .host-workspace .ui-tabbar .ui-nav-count { position: absolute; top: var(--space-1); left: calc(50% + var(--space-1)); margin: 0; min-width: var(--space-4); height: var(--space-4); }
  .host-workspace #more-sheet .ui-menu-panel { position: static; display: flex; box-shadow: none; border: 0; padding: 0; margin: 0 0 var(--space-3); }
  .host-workspace #more-sheet .ui-sheet-lang { display: flex; gap: var(--space-2); padding: var(--space-2) var(--space-3); }
  .host-workspace #more-sheet .ui-btn { width: 100%; }
}
```

   Command: `python3 scripts/design_lint.py`. Expected: OK. If `ui-sheet-list` or `ui-sheet-lang` triggers T3 later when shell partials are enforced, they are not enforced; still add both to `classes` in `docs/design/catalog.json` now (one array edit; add that file to your report as a deviation).

8. Create `App/tests/test_design_shell.py`:

```python
"""Design v2 shell (MASTER 6): sidebar, top bar, tab bar, More sheet."""
import re

from app import host_i18n
from tests.test_signed_in_chrome import host_with_property  # noqa: F401  (fixture reuse)


def test_signed_in_pages_carry_the_v2_shell_and_not_the_drawer(host_with_property):
    page = host_with_property.get("/?lang=en").text
    assert 'class="ui-sidebar" id="app-sidebar"' in page
    assert 'class="ui-topbar"' in page
    assert "data-nav-toggle" not in page and 'class="appbar"' not in page and "nav-backdrop" not in page
    tabbar = re.search(r'<nav class="ui-tabbar".*?</nav>', page, re.S).group(0)
    assert tabbar.count("<a ") == 5
    assert 'data-sheet-open="more-sheet"' in tabbar
    assert '<dialog id="more-sheet" class="ui-dialog"' in page
    for href in ("/invoices", "/stay-fees", "/smart-locks", "/settings", "/guide", "/settings/archived", "/privacy-requests"):
        assert f'class="ui-menu-item" href="{href}"' in page, href


def test_the_sidebar_lists_every_destination_with_a_lucide_icon(host_with_property):
    page = host_with_property.get("/?lang=en").text
    sidebar = re.search(r'<aside class="ui-sidebar".*?</aside>', page, re.S).group(0)
    for href, icon in (("/", "layout-dashboard"), ("/reservations", "calendar-days"), ("/apartments", "house"), ("/invoices", "receipt"),
                       ("/cleaning", "brush-cleaning"), ("/stay-fees", "coins"), ("/smart-locks", "key-round"), ("/settings", "settings"), ("/guide", "book-open")):
        assert re.search(rf'href="{re.escape(href)}"[^>]*>\s*<svg class="ui-icon"[^>]*data-icon="{icon}"', sidebar), href
    assert sidebar.count('aria-current="page"') == 1
    assert "<path" in sidebar and "hand-drawn" not in sidebar
    assert 'data-sidebar-collapse' in sidebar and 'class="ui-nav sidebar-nav"' in sidebar


def test_navigation_labels_exist_in_both_languages():
    for key in ("nav.cleaning", "nav.more", "nav.admin", "nav.smart_locks"):
        assert host_i18n.STRINGS["en"][key] and host_i18n.STRINGS["cs"][key]
    assert host_i18n.STRINGS["cs"]["nav.more"] == "Další"
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_design_shell.py tests/test_signed_in_chrome.py -q --tb=short -x 2>&1 | tail -30`. Expected: all passed.

9. Create `App/tests/test_design_shell_browser.py`:

```python
"""Shell geometry (MASTER 6.2, 6.3): 240 px sidebar at 1280, 56 px tab bar with 44 px tabs at 390."""
import os
import secrets

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, db
from tests.browser_support import chromium_launch_kwargs
from tests.test_host_geometry import _browser_session_cookie, base  # noqa: F401


def _open(playwright, base, width):
    username = f"shell{secrets.token_hex(3)}"
    owner = auth.create_account(f"{username}@example.test", "Shell", role="host", username=username)
    db.insert("apartment", {"internal_name": "Shell flat", "owner_user_id": owner, "permalink_token": f"sh{secrets.token_hex(4)}", "active": 1, "created_at": db.utcnow()})
    try:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
    except Exception as exc:
        if REQUIRE_BROWSER:
            raise
        pytest.skip(f"Chromium is not available: {exc}")
    context = browser.new_context(viewport={"width": width, "height": 900 if width >= 1024 else 844})
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": _browser_session_cookie(username), "url": base + "/"}])
    page = context.new_page()
    page.goto(base + "/reservations?lang=en")
    page.wait_for_selector("#main-content", timeout=30000)
    return browser, page


def test_desktop_sidebar_is_240_wide_and_main_starts_after_it(base):
    with sync_api.sync_playwright() as playwright:
        browser, page = _open(playwright, base, 1280)
        side = page.evaluate("document.querySelector('.ui-sidebar').getBoundingClientRect().width")
        main_left = page.evaluate("document.querySelector('#main-content').getBoundingClientRect().left")
        assert round(side) == 240 and main_left >= 240
        assert page.evaluate("getComputedStyle(document.querySelector('.ui-tabbar')).display") == "none"
        page.click("button[data-sidebar-collapse]")
        page.wait_for_function("document.body.classList.contains('sidebar-collapsed')")
        assert round(page.evaluate("document.querySelector('.ui-sidebar').getBoundingClientRect().width")) == 64
        browser.close()


def test_phone_tab_bar_is_fixed_at_the_bottom_with_five_44px_tabs(base):
    with sync_api.sync_playwright() as playwright:
        browser, page = _open(playwright, base, 390)
        assert page.evaluate("getComputedStyle(document.querySelector('.ui-sidebar')).display") == "none"
        bar = page.evaluate("(() => { const r = document.querySelector('.ui-tabbar').getBoundingClientRect(); return {top: r.top, bottom: r.bottom, h: r.height}; })()")
        assert round(bar["bottom"]) == 844 and bar["h"] >= 56
        heights = page.evaluate("[...document.querySelectorAll('.ui-tabbar a')].map(a => a.getBoundingClientRect().height)")
        assert len(heights) == 5 and min(heights) >= 44
        assert page.evaluate("document.documentElement.scrollWidth") <= 390
        page.click('[data-sheet-open="more-sheet"]')
        page.wait_for_selector("#more-sheet[open]")
        assert page.locator('#more-sheet a[href="/invoices"]').is_visible()
        browser.close()
```

   Command: `cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_design_shell_browser.py -q --tb=short -x 2>&1 | tail -30`. Expected: `2 passed`.

10. Commit: `git add App/app/templates/_shell_sidebar.html App/app/templates/_shell_topbar.html App/app/templates/_shell_tabbar.html App/app/templates/base.html App/app/static/shell.js App/app/static/host2.css App/app/host_i18n.py App/tests/test_design_shell.py App/tests/test_design_shell_browser.py docs/design/catalog.json && git commit -m "0130 step 10: v2 navigation shell"`.

## 5. Do not touch

`app.js` (its `initNavigation` tolerates the missing toggles: every lookup is null-guarded); page templates; `_components.html`; old stylesheets (their `.sidebar` rules no longer match anything); hard rules 2, 3, 6, 8.

## 6. Commands

- `cd App && .venv/bin/python -m pytest tests/test_design_shell.py tests/test_signed_in_chrome.py tests/test_skeleton_loaders.py -q --tb=short -x 2>&1 | tail -30` expected: all passed.
- `cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_design_shell_browser.py tests/test_host_geometry.py tests/test_cleaning_browser.py tests/test_property_navigation_browser.py tests/test_download_skeleton_browser.py -q --tb=short -x 2>&1 | tail -30` expected: all passed, 0 skipped.
- `python3 scripts/design_lint.py` expected: OK.
- Screenshots: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-shots .venv/bin/python -m pytest tests/test_dashboard_calendar_browser.py -q --tb=short -x 2>&1 | tail -30` expected: passed; attach one 390 px shot showing the tab bar.

## 7. Acceptance

- [ ] No `nav-toggle`, `appbar` or `nav-backdrop` in a signed-in page; the drawer is gone.
- [ ] Sidebar 240 px at 1280 and 64 px collapsed; tab bar 5 tabs at 390, each at least 44 px, More opens the sheet.
- [ ] `test_signed_in_chrome.py` unchanged and passing.
- [ ] One 390 px screenshot in the report.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a new dependency seems needed; a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy. Known pre-existing failures that this brief need not fix: `test_host_fit_browser.py`, `test_host_property_controls_browser.py` (360 px cases); report them if they still fail, do not edit them.

## 9. Report

Write `docs/tasks/0130-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/templates/base.html` (chrome replaced), `App/app/static/host2.css` shell block (layout offsets), `App/app/static/shell.js`.

## Owner steps

None.
