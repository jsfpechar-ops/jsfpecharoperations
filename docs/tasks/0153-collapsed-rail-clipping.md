# 0153: content clipped behind the collapsed rail (stale tokens.css in the browser cache)

Status: todo
Depends on: none | Base commit: 79252fd | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 25 tool calls, 50k tokens

## 1. Objective

On staging the host pages render with the content lane under the sidebar rail (about 34 px of the Overview and onboarding under the collapsed rail, the whole left edge under the expanded one), the header buttons unstyled (`+ Add stay` as plain text, `+ Add cleaning` as an outlined link) and the table headers run together. Root cause (reproduced locally, see §2): the browser still holds the **old `tokens.css`**, because the redesign (#397 follow-ups on this branch) added the shell tokens (`--nav-w`, `--nav-w-collapsed`, `--lane`, `--gutter`, `--control-h`, `--accent`, ...) to `tokens.css` but left its cache key at `?v=20261002a`, and `/static/*?v=` is served `public, max-age=31536000, immutable` (`App/app/main.py` line 294). With the old file every `var(--nav-w-collapsed)` in `host2.css` is invalid at computed-value time, so `margin-left` falls back to `0`, `max-width: var(--lane)` to `none`, `background: var(--accent)` to transparent. This brief bumps the stale keys, adds a unit test that fails whenever a versioned static file changes without a new key, and adds a browser test that pins the lane geometry and header button styles at 1280 and 2000 px, collapsed and expanded.

## 2. Context

**Reproduction (orchestrator, local, this branch).** Chromium 2000 px, `/` with one property, `tokens.css` served from `origin/main` (what a returning browser has cached):

| page, rail | wrap margin-left | wrap padding-left | elements of `#main-content` left of the rail's right edge | `+ Add stay` background, height |
|---|---|---|---|---|
| `/` collapsed, old tokens | 0px | 34px | 54 | transparent, 17 px |
| `/` expanded, old tokens | 0px | 0px | 63 | transparent, 17 px |
| `/reservations` collapsed, old tokens | 0px | 34px | 17 | transparent, 17 px |
| `/` collapsed, current tokens | 64px | 34px | 0 | rgb(173, 73, 66), 40 px |
| `/` expanded, current tokens | 240px | 32px | 0 | rgb(173, 73, 66), 40 px |

`document.scrollingElement.scrollLeft` is 0 and `scrollWidth == innerWidth` in every case: nothing overflows, the page is not scrolled sideways. The 34 px padding in the collapsed case is the pre-redesign `padding-left: 34px` from `App/app/static/host.css` line 227, which is why the owner's screenshots show the rail covering roughly 30 px of text (`DO THIS NOW`, `ant to learn`, `all setup steps`, `servations`), not the full rail width. Same cause on `/onboarding`, `/reservations`, stay detail, `/invoices`, `/settings`: every page under `base.html`.

**Files changed on this branch without a new key** (`git diff origin/main HEAD --stat -- App/app/static`): `tokens.css` (+39), `app.js` (+3), `skeleton.js` (+14). `host2.css`, `shell.js` and `dashboard-calendar.css` already carry `20261019-*` keys.

**Rule (WP07, `App/app/main.py` lines 289-293):** every `/static` URL in a template carries `?v=<key>` and the key is bumped whenever the file changes. There is no test for the second half of that sentence; step 3 adds one.

**Pre-existing, not fixed here (for the orchestrator):** `components.css`, `passkeys.js` and `cleaning.css` are referenced with two to four different keys across live templates (e.g. `components.css?v=20261002a` in `auth_base.html`, `?v=20261014-0102c` in `base.html`). The manifest test records the newest key per file; a later brief can unify them.

**MASTER 6.2 (docs/design/MASTER.md):** the shell owns the lane; `--nav-w: 240px; --nav-w-collapsed: 64px; --lane: 1080px` (`tokens.css` lines 153-154). No CSS changes in this brief: the selectors are right, the browser just never received the tokens.

**Button tokens for the test** (`tokens.css` line 126, `host2.css` lines 6-11): primary background `--accent` = `--coral-600` = `#ad4942` = `rgb(173, 73, 66)`; secondary border `--line-strong` = `--sand-400` = `#c9c9c2` = `rgb(201, 201, 194)`; height `--control-h` = 40 px at 1024 px and up.

**Collapse mechanics:** `App/app/static/app.js` line 824 adds `body.sidebar-collapsed` when `localStorage["ubyhost-sidebar-collapsed"] === "1"`; `app.css` line 312 animates `margin-left` for 0.26 s, so a test waits for the computed margin, not a fixed delay.

Anchors (verbatim, with line numbers; if one is not found at its line, STOP, §8):

- A1 `App/app/templates/base.html` line 12: `  <link rel="stylesheet" href="/static/tokens.css?v=20261002a">`
- A2 `App/app/templates/base.html` line 245: `<script src="/static/skeleton.js?v=20261014-0102c"></script>`
- A3 `App/app/templates/base.html` line 246: `<script src="/static/app.js?v=20261016-0123-refresh1"></script>`
- A4 `App/app/templates/auth_base.html` line 12: `  <link rel="stylesheet" href="/static/tokens.css?v=20261002a">`
- A5 `App/app/templates/public_legal_base.html` line 24: `  <link rel="stylesheet" href="/static/tokens.css?v=20261002a">`
- A6 `App/app/templates/cleaning_shared.html` line 4 contains the fragment `/static/tokens.css?v=20261002a`
- A7 `App/app/templates/guest/base.html` line 13: `  <link rel="stylesheet" href="/static/tokens.css?v=20261003a">`
- A8 `App/app/templates/guest/base.html` line 67: `<script src="/static/skeleton.js?v=20261014-0102c"></script>`
- A9 `App/app/templates/landing.html` line 26, `public_guide.html` line 23, `product.html` line 24, `pricing.html` line 24, each: `  <link rel="stylesheet" href="/static/tokens.css?v=20260914d">`
- A10 `docs/context/test-map.md`, the row: `| Design system, catalog page, design lint | `test_design_*.py test_dev_ui*.py` |`

`App/app/templates/guest/archive/**` is a reference copy no route renders (see `test_wp07_cache_heartbeats.py` line 55): leave it alone.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/base.html | edit | A1, A2, A3 |
| App/app/templates/auth_base.html | edit | A4 |
| App/app/templates/public_legal_base.html | edit | A5 |
| App/app/templates/cleaning_shared.html | edit | A6 |
| App/app/templates/guest/base.html | edit | A7, A8 |
| App/app/templates/landing.html, public_guide.html, product.html, pricing.html | edit | A9 |
| App/tests/test_static_versions.py | new | step 3 |
| App/tests/static_versions.json | new | step 3 (generated) |
| App/tests/test_shell_lane_browser.py | new | step 4 |
| docs/context/test-map.md | edit | A10, one row |

No other file may change. `App/app/static/` is not touched.

## 4. Steps

1. **Bump the stale keys.** The new key everywhere is `20261019-0153`.
   - A1, A4, A5, A7 and the four A9 lines become `  <link rel="stylesheet" href="/static/tokens.css?v=20261019-0153">` (keep each file's indentation as it is).
   - A6: in `cleaning_shared.html` line 4 replace the fragment `/static/tokens.css?v=20261002a` with `/static/tokens.css?v=20261019-0153` and nothing else on that line.
   - A2 and A8 become `<script src="/static/skeleton.js?v=20261019-0153"></script>`.
   - A3 becomes `<script src="/static/app.js?v=20261019-0153"></script>`.
   Check: from the repo root `grep -rn "tokens.css?v=\|skeleton.js?v=\|app.js?v=" App/app/templates | grep -v archive | grep -v "20261019-0153" | tail -5` prints nothing. Commit `0153 step 1: bump tokens.css, app.js, skeleton.js cache keys` with `git add App/app/templates`.

2. **Confirm the fix in the browser the way the owner sees it.** From `App/`: `UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_wp07_cache_heartbeats.py -k static -q --tb=short -x 2>&1 | tail -5`. Expected: 5 passed. (The owner-side check, a hard reload on staging, is in Owner steps.)

3. **Unit guard: a changed static file needs a new key.** Create `App/tests/test_static_versions.py`:

```python
"""WP07, second half: a versioned static file that changes must get a new ``?v=`` key.

``/static/*?v=`` is served immutable for a year (app/main.py). On 2026-10-19 the
redesign added the shell tokens to tokens.css without a new key, so returning
browsers kept the old file and rendered the lane under the rail (task 0153).

``tests/static_versions.json`` records, for every static file the live templates
reference with ``?v=``, the key and the file's sha256. When you change a static
file: bump its key in every template that references it, then run from ``App/``
``.venv/bin/python tests/test_static_versions.py --write`` and commit the json.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
TEMPLATES = APP / "templates"
STATIC = APP / "static"
MANIFEST = Path(__file__).resolve().parent / "static_versions.json"
REF = re.compile(r'(?:src|href)="/static/([^"?]+)\?v=([^"&]+)"')


def references() -> dict[str, dict[str, set[str]]]:
    """{static path: {key: {template, ...}}} for every live template."""
    found: dict[str, dict[str, set[str]]] = {}
    for path in sorted(TEMPLATES.rglob("*.html")):
        if "archive" in path.relative_to(TEMPLATES).parts:
            continue
        for name, key in REF.findall(path.read_text(encoding="utf-8")):
            found.setdefault(name, {}).setdefault(key, set()).add(str(path.relative_to(TEMPLATES)))
    return found


def current_manifest() -> dict[str, dict[str, str]]:
    out = {}
    for name, keys in references().items():
        file = STATIC / name
        if not file.is_file():
            continue
        # Some files carry several keys across templates (pre-existing, see 0153 §2); the newest one is recorded.
        out[name] = {"v": sorted(keys)[-1], "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
    return out


def test_a_changed_static_file_has_a_new_key():
    recorded = json.loads(MANIFEST.read_text(encoding="utf-8"))
    stale, unrecorded = [], []
    for name, entry in current_manifest().items():
        if name not in recorded:
            unrecorded.append(name)
        elif recorded[name]["sha256"] != entry["sha256"] and recorded[name]["v"] == entry["v"]:
            stale.append(f"{name} changed but still has ?v={entry['v']}")
    assert not stale, stale + ["bump the key in the templates, then: .venv/bin/python tests/test_static_versions.py --write"]
    assert not unrecorded, unrecorded + ["new versioned file: .venv/bin/python tests/test_static_versions.py --write"]


def test_the_manifest_is_current():
    recorded = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert recorded == current_manifest(), "run: .venv/bin/python tests/test_static_versions.py --write"


if __name__ == "__main__":
    if sys.argv[1:] == ["--write"]:
        MANIFEST.write_text(json.dumps(current_manifest(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {MANIFEST} ({len(current_manifest())} files)")
    else:
        print("usage: tests/test_static_versions.py --write")
```

   Then from `App/`: `.venv/bin/python tests/test_static_versions.py --write | tail -2`, then `.venv/bin/python -m pytest tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -5`. Expected: 2 passed. Ruff: `.venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 tests/test_static_versions.py | tail -3`. Commit `0153 step 3: static version manifest test` with `git add App/tests/test_static_versions.py App/tests/static_versions.json`.

4. **Browser guard: lane inside the rail, header buttons styled.** Create `App/tests/test_shell_lane_browser.py`:

```python
"""0153: the content lane starts right of the rail and the header buttons keep
their v2 styles, collapsed and expanded, at 1280 and 2000 px (MASTER 6.2)."""
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

PAGES = ("/", "/onboarding", "/reservations", "/invoices", "/settings")
HAS_PRIMARY = ("/", "/reservations")  # migrated page headers with a primary action; the rest are checked when present
PRIMARY_BG = "rgb(173, 73, 66)"  # --accent = --coral-600 #ad4942
SECONDARY_BORDER = "rgb(201, 201, 194)"  # --line-strong = --sand-400 #c9c9c2
GEOMETRY = """(() => {
  const rail = document.querySelector('.ui-sidebar').getBoundingClientRect();
  const main = document.querySelector('#main-content');
  const under = [];
  for (const el of main.querySelectorAll('*')) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    if (r.left < rail.right - 0.5) under.push(el.tagName + '.' + String(el.className).slice(0, 40) + '@' + Math.round(r.left));
    if (under.length >= 5) break;
  }
  const btn = (sel) => [...document.querySelectorAll(sel)].filter(b => b.getBoundingClientRect().height > 0).map(b => {
    const c = getComputedStyle(b); return {bg: c.backgroundColor, border: c.borderTopWidth + ' ' + c.borderTopColor, h: Math.round(b.getBoundingClientRect().height)}; });
  return {railRight: rail.right, mainLeft: main.getBoundingClientRect().left, under,
          scrollLeft: document.scrollingElement.scrollLeft, scrollWidth: document.documentElement.scrollWidth, innerWidth: innerWidth,
          primary: btn('.ui-ph-acts .ui-btn-primary'), secondary: btn('.ui-ph-acts .ui-btn-secondary')};
})()"""


def _account():
    username = f"lane{secrets.token_hex(3)}"
    owner = auth.create_account(f"{username}@example.test", "Lane", role="host", username=username)
    entity = db.insert("legal_entity", {"name": "Lane s.r.o.", "owner_user_id": owner, "created_at": db.utcnow()})
    db.insert("apartment", {"internal_name": "Lane flat", "owner_user_id": owner, "legal_entity_id": entity,
                            "permalink_token": f"ln{secrets.token_hex(4)}", "active": 1, "created_at": db.utcnow()})
    return username


@pytest.mark.parametrize("width", [1280, 2000])
@pytest.mark.parametrize("collapsed", [False, True])
def test_main_starts_right_of_the_rail_and_header_buttons_keep_v2_styles(base, width, collapsed):
    username = _account()
    cookie = _browser_session_cookie(username)
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception as exc:
            if REQUIRE_BROWSER:
                raise
            pytest.skip(f"Chromium is not available: {exc}")
        context = browser.new_context(viewport={"width": width, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
        if collapsed:
            context.add_init_script("try { localStorage.setItem('ubyhost-sidebar-collapsed', '1'); } catch (e) {}")
        page = context.new_page()
        rail_w = 64 if collapsed else 240
        for path in PAGES:
            page.goto(base + path + "?lang=en")
            page.wait_for_selector("#main-content", timeout=30000)
            assert page.evaluate("document.body.classList.contains('sidebar-collapsed')") is collapsed, path
            page.wait_for_function(  # app.css animates margin-left for 0.26 s
                "w => getComputedStyle(document.querySelector('.wrap.with-sidebar')).marginLeft === w + 'px'", arg=rail_w, timeout=3000)
            g = page.evaluate(GEOMETRY)
            assert round(g["railRight"]) == rail_w, (path, g["railRight"])
            assert g["scrollLeft"] == 0 and g["scrollWidth"] <= g["innerWidth"], (path, g)
            assert g["mainLeft"] >= g["railRight"], (path, g["mainLeft"], g["railRight"])
            assert g["under"] == [], (path, width, collapsed, g["under"])
            if path in HAS_PRIMARY:
                assert g["primary"], (path, "no visible primary header button")
            for b in g["primary"]:
                assert b["bg"] == PRIMARY_BG and b["h"] == 40, (path, b)
            for b in g["secondary"]:
                assert b["border"] == f"1px {SECONDARY_BORDER}" and b["h"] == 40, (path, b)
        browser.close()
```

   Run from `App/`: `UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_shell_lane_browser.py -q --tb=short -x 2>&1 | tail -15`. Expected: 4 passed, 0 skipped. If `/` or `/reservations` has no visible `.ui-ph-acts .ui-btn-primary` (assertion `no visible primary header button`), do not loosen the test: paste the failing page and STOP (§8). Ruff as in step 3 on the new file. Commit `0153 step 4: shell lane browser test` with `git add App/tests/test_shell_lane_browser.py`.

5. **Test map and screenshots.** In `docs/context/test-map.md` insert after A10 the row:
   `| Static files under App/app/static (any), cache keys | `test_static_versions.py test_wp07_cache_heartbeats.py` plus the row of the page the file styles |`
   From the repo root: `python3 scripts/context_lint.py | tail -2`. Expected: `context lint: OK`.
   Then run the three browser files together, from `App/`: `UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_shell_lane_browser.py tests/test_design_shell_browser.py tests/test_onboarding_wizard_browser.py -q --tb=short 2>&1 | tail -15`. Expected: all passed, 0 skipped. Known flake, not yours: `test_phone_guest_sharing_and_clear_setup_actions` can fail on `assert skeleton.is_hidden()` (K-T02, fixed by 0152 if that brief has run); if it is the only failure, rerun that test id once and paste both outputs.
   Screenshots: with the small script below saved as `/tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0153/shoot.py` (outside the repo), run from `App/`: `UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest -p tests.conftest /tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0153/shoot.py -q -s 2>&1 | tail -3`. It writes `dashboard-1280-collapsed.png`, `dashboard-2000-collapsed.png`, `onboarding-1280-collapsed.png`, `onboarding-2000-collapsed.png` next to itself. Look at each: the rail is 64 px, the lane starts right of it with a visible gutter, `+ Add stay` is a coral button, the step numbers 1-5 are whole.

```python
import secrets
from pathlib import Path
import playwright.sync_api as sync_api
from app import auth, db
from tests.browser_support import chromium_launch_kwargs
from tests.test_host_geometry import _browser_session_cookie, base  # noqa: F401
OUT = Path(__file__).resolve().parent

def test_shoot(base):  # noqa: F811
    u = f"shot{secrets.token_hex(3)}"
    owner = auth.create_account(f"{u}@example.test", "Shot", role="host", username=u)
    db.insert("apartment", {"internal_name": "Shot flat", "owner_user_id": owner, "permalink_token": f"sh{secrets.token_hex(4)}", "active": 1, "created_at": db.utcnow()})
    cookie = _browser_session_cookie(u)
    with sync_api.sync_playwright() as pw:
        browser = pw.chromium.launch(**chromium_launch_kwargs())
        for width in (1280, 2000):
            for path, name in (("/", "dashboard"), ("/onboarding", "onboarding")):
                ctx = browser.new_context(viewport={"width": width, "height": 900})
                ctx.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
                ctx.add_init_script("try { localStorage.setItem('ubyhost-sidebar-collapsed', '1'); } catch (e) {}")
                page = ctx.new_page()
                page.goto(base + path + "?lang=en")
                page.wait_for_selector("#main-content")
                page.wait_for_timeout(500)
                page.screenshot(path=str(OUT / f"{name}-{width}-collapsed.png"))
                ctx.close()
        browser.close()
```

   Commit `0153 step 5: test-map row` with `git add docs/context/test-map.md`. Then write the report (§9).

## 5. Do not touch

`App/app/static/**` (no CSS or JS change is needed; the selectors are right), `App/app/main.py`, `App/app/templates/guest/archive/**`, `docs/design/**`, `docs/tasks/0138*` to `0141*` and `0151*`, `0152*` (other briefs in flight). Hard rules 3, 7, 8: no secrets, screenshots in the report, no push.

## 6. Commands

As in steps 1 to 5, every one ending `| tail -N`. Never the full suite.

## 7. Acceptance

- [ ] Step 1: no live template references `tokens.css`, `app.js` or `skeleton.js` with a key other than `20261019-0153`; `git diff 79252fd --stat -- App/app/static` is empty.
- [ ] Step 3: `test_static_versions.py` 2 passed; `static_versions.json` committed; the test fails when a static file is edited without a key bump (the executor may verify by appending a blank line to `App/app/static/tokens.css`, running the test, then `git checkout -- App/app/static/tokens.css`).
- [ ] Step 4: `test_shell_lane_browser.py` 4 passed, 0 skipped, at 1280 and 2000, collapsed and expanded, on the five pages.
- [ ] Step 5: the three browser files all pass, 0 skipped (one allowed rerun of the K-T02 flake); `context lint: OK`; four screenshots looked at and their paths in the report.

## 8. Stop and ask

Stop, and write the report as `blocked`, if an anchor is not found verbatim at its line, if a test fails twice (quote the assertion with the test id, page, width and rail state), if a screenshot still shows the rail over text, or if you reach 25 tool calls.

## 9. Report

Write `docs/tasks/0153-report.md` (600 tokens at most) and set `Status: review`: files changed (`git diff 79252fd --stat`), each command with its last 5 lines, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/tests/static_versions.json` (every entry's `v` must match the templates), `App/tests/test_static_versions.py`, `App/tests/test_shell_lane_browser.py`, the ten template lines.

## Owner steps

1. After the merge and the staging deploy, open staging and press Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows) once on the Overview. The lane now starts right of the rail and `+ Add stay` is a coral button. A normal reload is enough on every later visit: the new `?v=20261019-0153` URL is a different cache entry.
2. Production gets the same fix with the next manual deploy; tell hosts nothing, their browsers pick up the new URL on the first page load after the deploy.
3. Note for the future (already enforced by the new test): any change under `App/app/static/` needs a new `?v=` key in the templates that reference the file, and `.venv/bin/python tests/test_static_versions.py --write`.
