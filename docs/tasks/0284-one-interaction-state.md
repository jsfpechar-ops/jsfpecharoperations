# 0284: One hover and press state for everything clickable; "What needs you" lines

Status: todo
Depends on: none | Base commit: 4883510 | Branch: claude/project-thread-futwgu (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The owner loves how a Properties row reacts to the mouse (grey surface, coral name) and wants that same state on every clickable row, card and button, defined once. Today the button and Stays-row hover colour resolves to white on host pages (host.css rebinds `--surface-2` to the white canvas), so they never react; and on the dashboard "What needs you" card the buttons do not line up (the dismiss x shifts some) and only the button itself is clickable.

## 2. Context

- MASTER 7.1 / 7.3: secondary buttons hover grey, whole row is clickable, primary text is a real link. Lint (`scripts/design_lint.py`) on host2.css: no raw colours, no bare px except 0 and 1. Primitives (`--sand-*`, `--coral-*`) are used only inside tokens.css.
- `App/app/static/tokens.css` line in the "2.2 semantic" block: `  --canvas-2: var(--sand-100); --surface-2: var(--sand-150); --surface-3: var(--sand-200);`
- `App/app/templates/dashboard.html`: `    {% if line.href %}{{ ui_button(line.action, 'secondary', href=line.href) }}{% endif %}`
- `App/app/static/workflow.css` ends with the 0244 health block; the "What needs you" rules are lines 68-93.
- Cache keys (`/static/*?v=` is immutable): any changed static file needs a new key in every template that references it, then `tests/test_static_versions.py --write`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/static/tokens.css | edit | three state tokens |
| App/app/static/host2.css | append | the shared state block |
| App/app/static/workflow.css | append | needs-you line: stretched link, x slot |
| App/app/templates/dashboard.html | edit | `attrs='data-needs-you-go'` on the line button |
| App/app/templates/*.html (only the `tokens.css?v=` references) and App/app/templates/base.html | edit | new keys |
| App/tests/static_versions.json | regenerate | `--write` |
| App/tests/test_0284_states_browser.py | new | guard test |

No other file may change.

## 4. Steps

1. tokens.css: after the anchor line `  --canvas-2: var(--sand-100); --surface-2: var(--sand-150); --surface-3: var(--sand-200);` insert this new line:

```
  --state-hover: var(--sand-100); --state-press: var(--sand-200); --state-ink: var(--coral-600);
```

2. host2.css: append at the very end of the file:

```css

/* 0284: one interaction state for everything clickable (owner 2026-10-22: the
   Properties row is the model). Hover greys the surface and turns the name or
   label coral; pressing greys it one step more; keyboard focus keeps its ring.
   Pages add no hover CSS of their own: extend these lists instead. */
@media (hover: hover) {
  .host-workspace :is(tbody tr.clickable-row, .ui-table .ui-row, .ui-card, .host-property-card, .host-task, .needs-you-item:has([data-needs-you-go])):hover,
  .host-workspace .ui-table .ui-row:hover > td { background: var(--state-hover); }
  .host-workspace :is(.ui-card, .host-property-card, .host-task, .needs-you-item:has([data-needs-you-go])):hover { border-color: var(--line-strong); }
  .host-workspace :is(tbody tr.clickable-row, .ui-table .ui-row, .ui-card, .host-property-card, .host-task, .needs-you-item):hover :is(.row-primary-link, .ui-card-l1, .host-property-card-link, .needs-you-copy strong),
  .host-workspace a.host-property-card:hover strong { color: var(--state-ink); }
  .host-workspace :is(tbody tr.clickable-row, .ui-table .ui-row, .host-property-card, .needs-you-item):hover :is(.row-open, .host-property-card-open, [data-needs-you-go]) { border-color: var(--ink); }
  .host-workspace :is(.ui-btn-secondary, .ui-btn-quiet, .btn-icon, .ui-menu-item, .row-menu-item, .ui-chip:not([aria-current="true"])):hover { background: var(--state-hover); color: var(--state-ink); }
  .host-workspace :is(.ui-btn-secondary, .btn-icon):hover { border-color: var(--ink); }
}
.host-workspace :is(tbody tr.clickable-row, .ui-table .ui-row, .ui-card, .host-property-card, .host-task, .ui-btn-secondary, .ui-btn-quiet, .btn-icon, .ui-menu-item, .row-menu-item):active,
.host-workspace .ui-table .ui-row:active > td,
.host-workspace .needs-you-item:has([data-needs-you-go]):active { background: var(--state-press); }
.host-workspace :is(tbody tr.clickable-row, .ui-table .ui-row):focus-within,
.host-workspace .ui-table .ui-row:focus-within > td { background: var(--state-hover); }
```

3. workflow.css: append at the very end of the file:

```css

/* 0284: the whole line opens its fix: the button is the link, stretched over
   the line; the dismiss x and the "how" toggle sit above it. The x keeps its
   slot on every line, so the buttons line up. */
.host-workspace .needs-you-item:has([data-needs-you-go]) { position: relative; cursor: pointer; transition: background-color var(--motion-1) var(--ease-standard), border-color var(--motion-1) var(--ease-standard); }
.host-workspace .needs-you-actions > [data-needs-you-go] { position: static; }
.host-workspace .needs-you-actions > [data-needs-you-go]::before { content: ""; position: absolute; inset: 0; border-radius: var(--radius-md); }
.host-workspace .needs-you-dismiss, .host-workspace .needs-you-item > .needs-you-more { position: relative; z-index: 1; }
@media (min-width: 720px) {
  .needs-you-actions { display: grid; grid-template-columns: auto var(--control-h); justify-items: end; }
  .needs-you-actions > .ui-btn { grid-column: 1; }
  .needs-you-dismiss { grid-column: 2; justify-self: center; }
}
```

4. dashboard.html: replace the anchor line with

```
    {% if line.href %}{{ ui_button(line.action, 'secondary', href=line.href, attrs='data-needs-you-go') }}{% endif %}
```

5. Cache keys. From the repo root:

```
grep -rl 'tokens.css?v=20261022-0283"' App/app/templates | xargs sed -i 's/tokens.css?v=20261022-0283"/tokens.css?v=20261022-0284"/'
sed -i 's/host2.css?v=20261022-0283m"/host2.css?v=20261022-0284"/; s/workflow.css?v=20261022-0246"/workflow.css?v=20261022-0284"/' App/app/templates/base.html
grep -rho 'tokens.css?v=[^"]*\|host2.css?v=[^"]*\|workflow.css?v=[^"]*' App/app/templates | sort | uniq -c
cd App && .venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5
```

Expected: only `20261022-0284` keys for the three files.

6. Create `App/tests/test_0284_states_browser.py` with exactly:

```python
"""0284: one hover/press state for every clickable row, card and button, and
the "What needs you" lines: buttons line up and the whole line opens its fix."""
from __future__ import annotations

import secrets

from fastapi.testclient import TestClient

from app import auth, db, demo
from app.main import app
from tests.conftest import login_as
from tests.test_property_navigation_browser import base, chromium_launch_kwargs, sync_api  # noqa: F401

STYLE = "e => { const c = getComputedStyle(e); return [c.backgroundColor, c.color, c.borderTopColor].join('|'); }"
WHITE = "rgb(255, 255, 255)"


def _session(base):
    db.init_db()
    user = f"states-{secrets.token_hex(3)}"
    owner = auth.create_account(f"{user}@example.test", "States Host", role="host", username=user)
    demo.seed(owner)
    client = TestClient(app)
    login_as(client, user, url="/login?lang=en")
    flat = db.query_one("SELECT id FROM apartment WHERE owner_user_id = ? ORDER BY id", (owner,))["id"]
    return client.cookies.get(auth.SESSION_COOKIE), flat


def _page(playwright, base, cookie, width=1280):
    browser = playwright.chromium.launch(**chromium_launch_kwargs())
    context = browser.new_context(viewport={"width": width, "height": 900})
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
    return browser, context.new_page()


def test_hover_changes_every_clickable_thing(base):
    cookie, flat = _session(base)
    targets = [
        ("/apartments", "table.properties-table tbody tr.clickable-row"),
        ("/reservations?range=all", "tbody tr.clickable-row"),
        ("/", ".needs-you-item:has([data-needs-you-go])"),
        ("/", "[data-needs-you-go]"),
        (f"/apartments/{flat}?view=overview", "a.host-property-card"),
        ("/reservations?range=all", "a.ui-chip:not([aria-current])"),
    ]
    problems = []
    with sync_api.sync_playwright() as playwright:
        browser, page = _page(playwright, base, cookie)
        for path, selector in targets:
            page.goto(base + path + ("&" if "?" in path else "?") + "lang=en")
            element = page.locator(selector + ":visible").first
            assert element.count(), (path, selector)
            page.mouse.move(1, 1)
            page.wait_for_timeout(250)
            before = element.evaluate(STYLE)
            element.hover()
            page.wait_for_timeout(250)
            after = element.evaluate(STYLE)
            if before == after or after.split("|")[0] == WHITE:
                problems.append((path, selector, before, after))
        browser.close()
    assert not problems, problems


def test_needs_you_buttons_line_up_and_the_line_opens(base):
    cookie, _flat = _session(base)
    with sync_api.sync_playwright() as playwright:
        browser, page = _page(playwright, base, cookie)
        page.goto(base + "/?lang=en")
        rights = page.evaluate(
            "() => [...document.querySelectorAll('.needs-you-list > .needs-you-item [data-needs-you-go]')]"
            ".filter(e => e.offsetParent).map(e => Math.round(e.getBoundingClientRect().right))"
        )
        assert rights, "no What needs you line with a button"
        assert max(rights) - min(rights) <= 1, rights
        dismiss = page.locator(".needs-you-list .needs-you-dismiss button:visible")
        if dismiss.count():
            hit = dismiss.first.evaluate(
                "e => { const r = e.getBoundingClientRect(); const h = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2); return !!(h && h.closest('.needs-you-dismiss')); }"
            )
            assert hit, "the dismiss x is covered by the stretched link"
        item = page.locator(".needs-you-list > .needs-you-item:has([data-needs-you-go])").first
        href = item.locator("[data-needs-you-go]").get_attribute("href")
        box = item.locator(".needs-you-copy").bounding_box()
        page.mouse.click(box["x"] + 10, box["y"] + box["height"] / 2)
        page.wait_for_url("**" + href.split("#")[0].split("?")[0] + "*")
        browser.close()
```

Commands for steps 1-6 are in section 6. Commit after each step: `0284 step k`.

## 5. Do not touch

Everything not in section 3. No raw colours or bare px in host2.css. Do not edit host.css, app.css or host-controls.css (the new block overrides them by order and specificity). AGENTS.md hard rules 6 and 7.

## 6. Commands (from `App/`, with `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome`)

```
.venv/bin/python -m pytest tests/test_0284_states_browser.py tests/test_static_versions.py -q --tb=short -x -rs -p no:cacheprovider 2>&1 | tail -30
cd .. && python3 scripts/design_lint.py 2>&1 | tail -5 && python3 scripts/context_lint.py 2>&1 | tail -5
```

Expected: all pass, 0 skipped; design lint reports no finding.

## 7. Acceptance

- [ ] test_0284 passes, 0 skipped.
- [ ] design_lint and context_lint clean.
- [ ] New keys `20261022-0284` for tokens.css, host2.css, workflow.css; static_versions.json regenerated.

## 8. Stop and ask

As in docs/tasks/TEMPLATE.md section 8. If test_0284 fails twice, stop and paste the assertion message in the report.

## 9. Report

`docs/tasks/0284-report.md` (600 tokens at most), set `Status: review`. Do not push; the orchestrator pushes.
