# 0322: Havel (AI): "Ask Havel" in the command palette and on the Help page

Status: todo
Depends on: 0324 | Base commit: 92646d3 (check `git rev-parse --short origin/main` first; if it differs, write the current one here) | Branch: task/0322-havel-palette
Executor: Haiku 5.5 | Fits one session: 22 tool calls, 45k tokens

## 1. Objective

Two more ways in (plan section 17a): when a search in the command palette finds nothing, its only row reads "Ask Havel (AI): <what you typed>" and opens the Havel panel with the text filled in; and the Help page has an "Ask Havel (AI)" button at the top. Both appear only while Havel is switched on.

## 2. Context

Today (`grep -nF` 2026-10-24):

- `App/app/routes/api.py` line 15 `from .. import access, auth, config, db, guest_slug, host_i18n, ttlock`; `command_palette` builds `items` (dicts with `label`, `group`, `url`, `keywords`, optional `method`, `meta`, `tone`, `copy`) and ends `    return JSONResponse({"items": items})`; `t = lambda key, **kwargs: ...` is defined in it.
- `App/app/static/app.js`, function `render(query)` (line 1596): the items are matched with

```js
      visible = items.map(function (item) {
        var haystack = [item.label, item.meta, item.group, item.keywords].join(" ").toLocaleLowerCase();
```

  and the empty case is

```js
      if (!visible.length) {
        var empty = document.createElement("p");
        empty.className = "command-empty";
        empty.textContent = results.getAttribute("data-empty") || "";
        results.appendChild(empty);
        return;
      }
```

  `function runItem(item) {` (line 1562) starts with `      var recentId = item.url || item.label;`; the dialog object is `command` (`command.open`, `command.close()`). `App/app/templates/base.html` line 244 `<script src="/static/app.js?v=20261022-0251"></script>`; palette openers are `[data-command-open]`, the input `[data-command-input]`, rows `.command-option`.
- `App/app/templates/guide.html` starts `{% extends "host_page.html" %}` and has no `ui_button` import; `host_page.html` line 49 has `{% block primary_action %}{% endblock %}{% block secondary_actions %}{% endblock %}`. `cleaning.html` line 3 imports with `{% from "_ui.html" import ui_button with context %}` and fills `{% block secondary_actions %}`.

From 0312/0324: `havel.launcher` is "Ask Havel (AI)" (en), "Zeptat se Havla (AI)" (cs), and vi; launchers are links `href="/havel" data-sheet-open="havel-sheet" data-havel-launcher`; `havel.js` sets `window.UbyHavel = { open: function (text) {...} }` (opens `#havel-sheet`, fills its message textarea), only when the panel is on the page. `ai.enabled(havel.FEATURE)`. Browser harness: `tests/test_havel_browser.py` fixture `origin`, helper `_context(pw, origin, width, js=True)`.

No new copy keys: both use `havel.launcher`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/routes/api.py | edit | the Havel item |
| App/app/static/app.js | edit | render and runItem |
| App/app/templates/base.html | edit | app.js cache key |
| App/app/templates/guide.html | edit | button |
| App/tests/test_havel_palette.py | new | API and page tests, browser test |

## 4. Steps

1. **API.** In `routes/api.py` change line 15 to `from .. import access, ai, auth, config, db, guest_slug, havel, host_i18n, ttlock` and replace the last line of `command_palette` with:

```python
    if ai.enabled(havel.FEATURE):
        # 0322: app.js shows this row only when nothing else matches, as "Ask Havel (AI): <query>".
        items.append({"label": t("havel.launcher"), "group": t("havel.name"), "url": "/havel", "havel": True})
    return JSONResponse({"items": items})
```

   Check: `.venv/bin/python -c "import app.routes.api"` prints nothing.

2. **Palette.** In `app.js` `render(query)` replace

```js
      visible = items.map(function (item) {
        var haystack = [item.label, item.meta, item.group, item.keywords].join(" ").toLocaleLowerCase();
```

   with

```js
      var askHavel = null;
      visible = items.map(function (item) {
        if (item.havel) { askHavel = item; return null; }
        var haystack = [item.label, item.meta, item.group, item.keywords].join(" ").toLocaleLowerCase();
```

   and replace the empty case of section 2 with

```js
      if (!visible.length && askHavel && words.length) {
        var asked = String(query || "").trim();
        visible = [{ label: askHavel.label + ": " + asked, group: askHavel.group, url: askHavel.url, havel: true, query: asked }];
      }
      if (!visible.length) {
        var empty = document.createElement("p");
        empty.className = "command-empty";
        empty.textContent = results.getAttribute("data-empty") || "";
        results.appendChild(empty);
        return;
      }
```

   In `runItem(item)` insert as its first lines, before `      var recentId = item.url || item.label;`:

```js
      if (item.havel) {
        if (command.open) command.close();
        if (window.UbyHavel && window.UbyHavel.open) window.UbyHavel.open(item.query || "");
        else window.location.assign(item.url);
        return;
      }
```

   The label is set with `textContent` by the existing row code (check: `grep -n 'innerHTML' app/static/app.js | sed -n 1,5p` shows no line inside `render`). Bump the key: in `base.html` replace `app.js?v=20261022-0251` with `app.js?v=20261024-0322`, then `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -3`.

3. **Help page button.** In `guide.html`, after the first line `{% extends "host_page.html" %}`, add:

```jinja
{% from "_ui.html" import ui_button with context %}
{% block secondary_actions %}{% if havel_on %}{{ ui_button(t('havel.launcher'), 'secondary', href='/havel', icon_name='message-circle-question', attrs='data-sheet-open="havel-sheet" data-havel-launcher') }}{% endif %}{% endblock %}
```

   The `/guide` route is `App/app/routes/admin.py` line 513, `    return render(request, "guide.html", {"demo_available": config.UBYPORT_ENV == "mock"})`. Change it to `    return render(request, "guide.html", {"demo_available": config.UBYPORT_ENV == "mock", "havel_on": ai.enabled(havel.FEATURE)})` and add `    ai,` and `    havel,` to the file's `from .. import (` block (line 25, one module per line, alphabetical).
   Check: `.venv/bin/python -c "from app.main import app"` prints nothing.

4. **Tests.** Create `App/tests/test_havel_palette.py`:

```python
"""0322: "Ask Havel (AI)" in the command palette and on the Help page."""
from pathlib import Path

from playwright import sync_api

from app import config
from tests.test_havel_browser import _context, origin  # noqa: F401
from tests.test_submission_retry_cap import host  # noqa: F401

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0322"


def _actions(html):
    """The page-header actions of /guide (the sidebar and top-bar launchers of 0324 are left out)."""
    head = html.split('class="guide-layout"')[0]
    return head.split("ui-ph-acts", 1)[1] if "ui-ph-acts" in head else ""


def test_palette_carries_the_havel_row_only_when_on(host, monkeypatch):
    monkeypatch.setattr(config, "AI_FEATURES", frozenset())
    assert not [i for i in host.get("/api/command-palette").json()["items"] if i.get("havel")]
    assert "data-havel-launcher" not in _actions(host.get("/guide").text)
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"havel"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "k")
    rows = [i for i in host.get("/api/command-palette").json()["items"] if i.get("havel")]
    assert rows == [{"label": "Ask Havel (AI)", "group": "Havel (AI)", "url": "/havel", "havel": True}]
    assert 'data-sheet-open="havel-sheet"' in _actions(host.get("/guide").text)


def test_no_match_opens_havel_with_the_query(origin):
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as pw:
        for width in (390, 1280):
            browser, context = _context(pw, origin, width)
            page = context.new_page()
            page.goto(f"{origin[0]}/guide")
            page.locator("[data-command-open]:visible").first.click()
            page.fill("[data-command-input]", "how do i zzqx")
            option = page.locator(".command-option").first
            option.wait_for()
            assert "Ask Havel (AI): how do i zzqx" in option.inner_text()
            if width == 390:
                page.screenshot(path=str(SHOTS / "palette-ask-390.png"))
                page.keyboard.press("Escape")
                page.locator(".ui-ph-acts [data-havel-launcher]").wait_for()
                page.screenshot(path=str(SHOTS / "guide-ask-390.png"))
                page.locator("[data-command-open]:visible").first.click()
                page.fill("[data-command-input]", "how do i zzqx")
                option = page.locator(".command-option").first
                option.wait_for()
            option.click()
            page.wait_for_function("(() => { const t = document.querySelector('#havel-sheet textarea[name=message]');"
                                   " return t && t.value === 'how do i zzqx'; })()")
            assert page.evaluate("document.documentElement.scrollWidth") <= width
            browser.close()
```

   The `origin` fixture of 0324 switches Havel on. `host_page.html` renders the page actions in `<div class="ui-ph-acts" data-list-actions>`. Command in section 6 (first). Expected: 2 passed, 0 skipped, two PNGs; look at both once (the palette row reads as a normal row; the button sits with the page title, secondary style).

## 5. Do not touch

`havel.js`, `shell.js`, the palette's other items and its matching, `guide_i18n.py`.

## 6. Commands (from `App/`, `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome UBYHOST_REQUIRE_BROWSER=1`)

- `.venv/bin/python -m pytest tests/test_havel_palette.py tests/test_havel_browser.py -q --tb=short -x -rs 2>&1 | tail -10`
- `.venv/bin/python -m pytest tests/test_host_redesign.py tests/test_stay_fee_list.py tests/test_signed_in_chrome.py tests/test_guide.py tests/test_guide_browser.py tests/test_static_versions.py -q --tb=short -x -rs 2>&1 | tail -10`
- `.venv/bin/python -m pytest tests/test_design_guardrails_browser.py -q --tb=short -rs 2>&1 | tail -10` and `.venv/bin/python -m pytest tests/test_host_geometry.py -q --tb=short -rs 2>&1 | tail -10` (0 skipped)
- From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -3` and `python3 scripts/context_lint.py | tail -5`

## 7. Acceptance

- [ ] With Havel off: no palette row, no Help button.
- [ ] With Havel on: a search with no match shows one row "Ask Havel (AI): <query>"; choosing it closes the palette and opens the panel with the query typed in; without the panel it goes to `/havel`.
- [ ] A search that matches something shows only the normal rows.
- [ ] Help page shows "Ask Havel (AI)" as a secondary action; screenshots `docs/tasks/screenshots-0322/palette-ask-390.png`, `guide-ask-390.png`.
- [ ] All section 6 commands pass, browser 0 skipped.

## 8. Stop and ask

- `window.UbyHavel` is missing on `/guide` (the panel is not included there).

## 9. Report

Write `docs/tasks/0322-report.md` (400 tokens at most) and set `Status: review`: files changed, each command's last 5 lines, section 7 ticked, both screenshots.

## Risk list (for the reviewer)

- The query goes into the textarea only; nothing is sent until the host presses Send, so no call is spent on a mistyped search.
- `textContent` keeps the query from being read as HTML.

## Owner steps

None.
