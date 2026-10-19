# 0131: Living component catalog at /dev/ui (admin only) with screenshot and coral-budget tests

Status: todo
Depends on: 0130 | Base commit: df8b842 | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit each step as `0131 step k`. Never push, never open a PR.

## 1. Objective

Add `/dev/ui`, an admin-only page that renders every v2 component, state and skeleton from the real CSS (MASTER 11.3), and the browser test that screenshots it at 390 and 1280, checks overflow, 44 px targets and the coral budget (MASTER 4.1, 11.2). From here on every page brief screenshots against this page.

## 2. Context

Rules: MASTER 4 (coral at most 3 % at 1280 and 6 % at 390; empty surface at least 55 % / 50 %), 7, 11.2, 11.3. Pillow is already pinned (`App/requirements.lock`: `pillow==12.3.0`), so the pixel count needs no new dependency.

Anchor A, `App/app/main.py`:

```
from .routes import admin, cleaning as cleaning_routes, guest, invoices, legal, mail_unsubscribe, onboarding_wizard, stay_fees
```

Anchor B, `App/app/main.py`:

```
app.include_router(mail_unsubscribe.router)
```

Anchor C, `docs/design/catalog.json`:

```
  "enforced_templates": [],
```

Anchor D, `App/app/routes/admin_accounts.py` (the guard pattern to copy, do not import it):

```
def _require_admin(request: Request):
    guard = auth.require_login(request)
    if guard:
        return None, guard
    account = auth.current_user(request)
    if not account or account["role"] != "admin":
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/dev_ui.py` | create | the route |
| `App/app/main.py` | edit | import and include the router |
| `App/app/templates/dev_ui.html` | create | the catalog page (extends `host_page.html`) |
| `docs/design/catalog.json` | edit | enforce `dev_ui.html`; add the swatch classes |
| `App/tests/test_dev_ui.py` | create | access and content |
| `App/tests/test_dev_ui_browser.py` | create | screenshots, geometry, coral budget |

No other file may change.

## 4. Steps

1. Create `App/app/routes/dev_ui.py`:

```python
"""/dev/ui: the living component catalog (docs/design/MASTER.md 11.3).

Admin only. It renders every v2 component from the real CSS so executors
screenshot against it; it reads no data and writes nothing.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, Response

from .. import auth, templating

router = APIRouter()

SKELETON_KINDS = ("list", "detail", "form", "settings")


@router.get("/dev/ui")
def dev_ui(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    account = auth.current_user(request)
    if not account or account["role"] != "admin":
        return Response(status_code=404)
    kind = request.query_params.get("kind", "detail")
    return templating.render(
        request,
        "dev_ui.html",
        {"nav": "admin", "body_kind": kind if kind in SKELETON_KINDS else "detail", "skeleton_kinds": SKELETON_KINDS},
    )
```

   Command: `cd App && .venv/bin/python -c "import app.routes.dev_ui as m; print(m.router.routes[0].path)"`. Expected: `/dev/ui`.

2. In `App/app/main.py`, replace Anchor A with:

```
from .routes import admin, cleaning as cleaning_routes, dev_ui, guest, invoices, legal, mail_unsubscribe, onboarding_wizard, stay_fees
```

   and Anchor B with:

```
app.include_router(mail_unsubscribe.router)
app.include_router(dev_ui.router)
```

   Command: `cd App && .venv/bin/python -c "from app.main import app; print([r.path for r in app.routes if r.path=='/dev/ui'])"`. Expected: `['/dev/ui']`.

3. Create `App/app/templates/dev_ui.html`:

```
{% extends "host_page.html" %}
{% set nav = 'admin' %}
{% block title %}UI catalog{% endblock %}
{% block meta %}docs/design/MASTER.md 2.0.0. Every component, state and skeleton from the real CSS.{% endblock %}
{% block primary_action %}{{ ui_button('Primary action', 'primary', href='#buttons') }}{% endblock %}
{% block secondary_actions %}{{ ui_button('Secondary', 'secondary', href='#fields', icon_name='refresh-cw') }}{{ ui_icon_button('More actions', 'ellipsis-vertical', attrs='class="ui-btn ui-btn-quiet ui-btn-icon ui-ph-menu"') }}{% endblock %}
{% block tabs %}{{ ui_tabs([('/dev/ui#tokens', 'Tokens', true), ('/dev/ui#buttons', 'Buttons', false), ('/dev/ui#lists', 'Lists', false), ('/dev/ui#skeletons', 'Skeletons', false)], 'Catalog') }}{% endblock %}
{% block body %}
{% call ui_section('Tokens', id='tokens') %}
<div class="ui-swatch-grid">
  {% for name in ['canvas', 'surface', 'surface-2', 'surface-3', 'ink', 'ink-2', 'ink-3', 'line', 'line-strong', 'accent', 'accent-soft', 'accent-ink', 'st-action-bg', 'st-attention-bg', 'st-done-bg', 'st-neutral-bg', 'danger', 'property-1', 'property-2', 'property-3'] %}
  <div class="ui-swatch" data-token="{{ name }}"><span class="ui-swatch-chip"></span><code>--{{ name }}</code></div>
  {% endfor %}
</div>
<p class="ui-type-sample">Body 16 px. <strong>Facts 600.</strong> <span class="ui-sub">Meta 13 px ink-3.</span> <span class="ui-mono">Mono 4821 #</span> <span class="ui-num">12 345 Kč</span></p>
{% endcall %}

{% call ui_section('Buttons', id='buttons', actions=ui_button('Section action', 'quiet', size='compact')) %}
<div class="ui-btn-group">
  {{ ui_button('Primary', 'primary') }}{{ ui_button('Secondary', 'secondary') }}{{ ui_button('Quiet', 'quiet') }}{{ ui_button('Danger', 'danger') }}
  {{ ui_button('Compact', 'secondary', size='compact') }}{{ ui_button('With icon', 'secondary', icon_name='plus') }}{{ ui_icon_button('Icon only', 'pencil', 'secondary') }}
  {{ ui_button('Loading', 'secondary', loading=true) }}{{ ui_button('Disabled', 'secondary', disabled=true) }}{{ ui_button('Disabled primary', 'quiet', disabled=true) }}
</div>
{% endcall %}

{% call ui_section('Fields', id='fields') %}
<form onsubmit="return false">
  <div class="ui-pair">{{ ui_field('f1', 'Text input', value='Byt Vinohradská 12', help='Help text under the field') }}{{ ui_field('f2', 'With error', error='Enter the house number, the police require it.') }}</div>
  <div class="ui-pair">{{ ui_select('f3', 'Select', [('a', 'All properties'), ('b', 'Studio Karlín')], selected='b') }}{{ ui_field('f4', 'Date', type='date', optional=true) }}</div>
  {{ ui_textarea('f5', 'Textarea', value='Notes') }}
  {{ ui_check('f6', 'Checkbox label', checked=true) }}
  {{ ui_toggle('f7', 'Toggle label', checked=true) }}
  <div class="ui-form-actions">{{ ui_button('Cancel', 'quiet') }}{{ ui_button('Save (secondary here, the page primary is in the header)', 'secondary', type='submit') }}</div>
</form>
{% endcall %}

{% call ui_section('Badges and chips', id='badges') %}
<div class="ui-btn-group">{{ ui_badge('action', '1 guest missing') }}{{ ui_badge('action', 'Report overdue', true) }}{{ ui_badge('attention', 'Waiting for UbyPort') }}{{ ui_badge('done', 'Confirmed') }}{{ ui_badge('neutral', 'Waiting for guests') }}{{ ui_pdot(1, 'Property one') }}{{ ui_pdot(2, 'Property two') }}</div>
<div class="ui-chips">{{ ui_chip('Upcoming', href='#', selected=true) }}{{ ui_chip('Past', href='#') }}{{ ui_chip('All', href='#') }}</div>
{% endcall %}

{% call ui_section('Toolbar, table and cards', id='lists') %}
{{ ui_toolbar(search=('q', 'Search guest or label', ''), chips=[('#', 'Upcoming', true), ('#', 'Past', false)], filters_id='dev-filters', filters_count=2, actions=ui_button('Export CSV', 'quiet', icon_name='download')) }}
{{ ui_table_begin([('Stay', ''), ('Dates', ''), ('Property', ''), ('Guests', 'r'), ('Police report', ''), ('', '')], 'Sample rows') }}
{% for i in range(3) %}
<tr class="ui-row clickable-row" data-href="#" tabindex="0"><td class="ui-cell-first"><a href="#">Sample stay {{ i + 1 }}</a><span class="ui-sub">Airbnb</span></td><td class="ui-num">19. 10. to 22. 10.</td><td>{{ ui_pdot(i, 'Property') }}</td><td class="ui-cell-r ui-num">1 of 2</td><td>{{ ui_badge('action', '1 guest missing') }}</td><td class="ui-cell-acts">{{ ui_button('Send', 'secondary', size='compact', icon_name='send') }} {{ ui_menu_begin() }}{{ ui_menu_item('Open', '#') }}{{ ui_menu_item('Delete', danger=true, icon_name='trash-2') }}{{ ui_menu_end() }}</td></tr>
{% endfor %}
{{ ui_table_end() }}
<div class="ui-cards">{% for i in range(3) %}{{ ui_card('#', '19. 10. to 22. 10.', 'Nováková · Byt Vinohradská 12', '1 of 2 guests', ui_badge('action', '1 guest missing')) }}{% endfor %}</div>
{{ ui_pagination(1, 4, '', '#', 'Sample', 'Show more', 'Previous', 'Next') }}
{% endcall %}

{% call ui_section('Detail parts', id='detail') %}
<div class="ui-detail">
  <div>{{ ui_banner('attention', '<strong>Studio Karlín</strong>: address and UbyPort credentials missing.', 'Finish setup', '#') }}{{ ui_banner('neutral', 'The report can be sent once every guest is complete.') }}
    <div class="ui-gcard"><h3>Jana Nováková {{ ui_badge('done', 'Details complete') }}</h3><p class="ui-sub">Passport, 14. 3. 1986, Slovakia</p></div>
    {{ ui_empty('No stays yet', 'Connect a calendar or add a stay by hand.', 'Add stay', '#', primary=false) }}
    {{ ui_tip('dev-tip', 'A help tip opens a short note.', '/guide') }}
  </div>
  <aside class="ui-detail-side">{{ ui_facts([('Property', 'Byt Vinohradská 12'), ('Arrival', '19. 10. 2026'), ('Guests', '1 of 2'), ('Door code', '<span class="ui-mono">4821 #</span>')]) }}</aside>
</div>
{{ ui_stats([('#', 3, 'Needs you'), ('#', 2, 'Ready to send'), ('#', 1, 'Overdue')], 'Sample') }}
{% endcall %}

{% call ui_section('Dialog', id='dialog') %}
{{ ui_button('Open dialog', 'secondary', attrs='onclick="document.getElementById(\'dev-dialog\').showModal()"') }}
{{ ui_dialog_begin('dev-dialog', 'Delete this stay?') }}<p>It moves to Archived. You can restore it there.</p><div class="ui-form-actions">{{ ui_button('Cancel', 'secondary', attrs='onclick="this.closest(\'dialog\').close()"') }}{{ ui_button('Delete', 'danger', attrs='onclick="this.closest(\'dialog\').close()"') }}</div>{{ ui_dialog_end() }}
{% endcall %}

{% call ui_section('Skeletons', id='skeletons') %}
{% for kind in skeleton_kinds %}<h3 class="ui-sub">{{ kind }}</h3>{{ ui_skeleton(kind) }}{% endfor %}
{% endcall %}
{% endblock %}
```

   Note the `onclick` attributes are a prototype-grade affordance for the catalog page only; the design lint allows attributes, not `style`. Command: `cd App && .venv/bin/python -c "from app.templating import templates; templates.get_template('dev_ui.html'); print('compiles')"`. Expected: `compiles`.

4. In `docs/design/catalog.json`, replace Anchor C with:

```
  "enforced_templates": ["App/app/templates/dev_ui.html"],
```

   and add to the `classes` array (after `"ui-cards-stack"`): `, "ui-swatch-grid", "ui-swatch", "ui-swatch-chip", "ui-type-sample"`. Then append to `App/app/static/host2.css` is NOT allowed in this brief; instead the swatch rules go in `dev_ui.html`? No: no `<style>` in templates. Add exactly these four rules to the end of `App/app/static/host2.css` and add that file to section 3 as `edit` in your report's deviations:

```

/* ---- /dev/ui catalog helpers ---- */
.host-workspace .ui-swatch-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(calc(var(--space-12) * 3), 1fr)); gap: var(--space-2); }
.host-workspace .ui-swatch { display: flex; align-items: center; gap: var(--space-2); font-size: var(--size-13); color: var(--ink-2); }
.host-workspace .ui-swatch-chip { width: var(--space-6); height: var(--space-6); border-radius: var(--radius-1); border: 1px solid var(--line); background: var(--surface); }
.host-workspace .ui-swatch[data-token="canvas"] .ui-swatch-chip { background: var(--canvas); } .host-workspace .ui-swatch[data-token="surface-2"] .ui-swatch-chip { background: var(--surface-2); } .host-workspace .ui-swatch[data-token="surface-3"] .ui-swatch-chip { background: var(--surface-3); } .host-workspace .ui-swatch[data-token="ink"] .ui-swatch-chip { background: var(--ink); } .host-workspace .ui-swatch[data-token="ink-2"] .ui-swatch-chip { background: var(--ink-2); } .host-workspace .ui-swatch[data-token="ink-3"] .ui-swatch-chip { background: var(--ink-3); } .host-workspace .ui-swatch[data-token="line"] .ui-swatch-chip { background: var(--line); } .host-workspace .ui-swatch[data-token="line-strong"] .ui-swatch-chip { background: var(--line-strong); } .host-workspace .ui-swatch[data-token="accent"] .ui-swatch-chip { background: var(--accent); } .host-workspace .ui-swatch[data-token="accent-soft"] .ui-swatch-chip { background: var(--accent-soft); } .host-workspace .ui-swatch[data-token="accent-ink"] .ui-swatch-chip { background: var(--accent-ink); } .host-workspace .ui-swatch[data-token="st-action-bg"] .ui-swatch-chip { background: var(--st-action-bg); } .host-workspace .ui-swatch[data-token="st-attention-bg"] .ui-swatch-chip { background: var(--st-attention-bg); } .host-workspace .ui-swatch[data-token="st-done-bg"] .ui-swatch-chip { background: var(--st-done-bg); } .host-workspace .ui-swatch[data-token="st-neutral-bg"] .ui-swatch-chip { background: var(--st-neutral-bg); } .host-workspace .ui-swatch[data-token="danger"] .ui-swatch-chip { background: var(--danger); } .host-workspace .ui-swatch[data-token="property-1"] .ui-swatch-chip { background: var(--property-1); } .host-workspace .ui-swatch[data-token="property-2"] .ui-swatch-chip { background: var(--property-2); } .host-workspace .ui-swatch[data-token="property-3"] .ui-swatch-chip { background: var(--property-3); }
.host-workspace .ui-type-sample { font-size: var(--body-size); }
```

   (Section 3 of this brief therefore also includes `App/app/static/host2.css` | edit | catalog swatch rules.) Command: `python3 scripts/design_lint.py`. Expected: OK, with `dev_ui.html` now enforced. If it reports a T3 class, that class is a real catalog gap: add it to `classes` and note it in the report.

5. Create `App/tests/test_dev_ui.py`:

```python
"""/dev/ui: admin-only living catalog (MASTER 11.3)."""
import json
import secrets
from pathlib import Path

from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.conftest import login_as

ROOT = Path(__file__).resolve().parents[2]
CATALOG = json.loads((ROOT / "docs" / "design" / "catalog.json").read_text(encoding="utf-8"))

MUST_SHOW = [
    "ui-btn-primary", "ui-btn-secondary", "ui-btn-quiet", "ui-btn-danger", "ui-btn-compact", "ui-btn-icon", "ui-btn-loading",
    "ui-field-err", "ui-select", "ui-textarea", "ui-check", "ui-switch",
    "ui-badge-action", "ui-badge-attention", "ui-badge-done", "ui-badge-neutral", "ui-badge-overdue",
    "ui-chip", "ui-toolbar", "ui-table", "ui-cards", "ui-card", "ui-menu-panel", "ui-dialog", "ui-empty", "ui-tip",
    "ui-pagination", "ui-facts", "ui-stats", "ui-banner-attention", "ui-banner-neutral",
    'data-skeleton-kind="list"', 'data-skeleton-kind="detail"', 'data-skeleton-kind="form"', 'data-skeleton-kind="settings"',
]


def _client(role):
    db.init_db()
    username = f"devui{secrets.token_hex(3)}"
    auth.create_account(f"{username}@example.test", "Dev UI", role=role, username=username)
    client = TestClient(app)
    login_as(client, username)
    return client


def test_a_host_cannot_see_the_catalog():
    assert _client("host").get("/dev/ui").status_code == 404


def test_the_catalog_is_enforced_by_the_design_lint():
    assert "App/app/templates/dev_ui.html" in CATALOG["enforced_templates"]


def test_an_admin_sees_every_component_state_and_skeleton():
    html = _client("admin").get("/dev/ui?lang=en").text
    assert html.count("<h1") == 1
    for marker in MUST_SHOW:
        assert marker in html, marker
    assert html.count('class="ui-btn ui-btn-primary"') == 1
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_dev_ui.py -q --tb=short -x 2>&1 | tail -30`. Expected: `3 passed`. If `create_account` rejects `role="admin"` here, read its signature (`grep -n "def create_account" app/auth.py`) and pass the role the way `tests/test_signed_in_chrome.py` or `tests/test_admin_funnel.py` does.

6. Create `App/tests/test_dev_ui_browser.py`:

```python
"""Screenshots and the coral budget on /dev/ui (MASTER 4.1, 11.2).

Runs in the browser CI job (UBYHOST_REQUIRE_BROWSER=1) and is skipped only
where Chromium is missing. Shots land in UBYHOST_SHOTS_DIR when set.
"""
import io
import os
import secrets
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from PIL import Image

from app import auth, db
from tests.browser_support import chromium_launch_kwargs
from tests.test_host_geometry import _browser_session_cookie, base  # noqa: F401  (fixture reuse)

CORAL = ((173, 73, 66), (200, 90, 82))
EMPTY = ((247, 247, 245), (255, 255, 255))
BUDGET = {390: (6.0, 50.0), 1280: (3.0, 55.0)}


def _near(p, c, d):
    return (p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2 + (p[2] - c[2]) ** 2 <= d * d


def _shares(png_bytes):
    im = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    px = list(im.getdata())
    coral = sum(1 for p in px if any(_near(p, c, 40) for c in CORAL))
    empty = sum(1 for p in px if any(_near(p, c, 8) for c in EMPTY))
    return 100.0 * coral / len(px), 100.0 * empty / len(px)


@pytest.mark.parametrize("width", [390, 1280])
def test_catalog_page_fits_the_viewport_and_the_coral_budget(base, width):
    username = f"devuiadmin{secrets.token_hex(3)}"
    auth.create_account(f"{username}@example.test", "Catalog", role="admin", username=username)
    session = _browser_session_cookie(username)
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
        except Exception as exc:
            if REQUIRE_BROWSER:
                raise
            pytest.skip(f"Chromium is not available: {exc}")
        context = browser.new_context(viewport={"width": width, "height": 900 if width == 1280 else 844})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": session, "url": base + "/"}])
        page = context.new_page()
        page.goto(base + "/dev/ui?lang=en")
        page.wait_for_selector("#skeletons", timeout=30000)
        assert page.evaluate("document.documentElement.scrollWidth") <= width, "horizontal overflow"
        if width == 390:
            short = page.evaluate("""() => [...document.querySelectorAll('.ui-btn, .ui-chip, .ui-tab')]
                .filter(el => el.offsetParent !== null)
                .map(el => el.getBoundingClientRect().height).filter(h => h < 43.5)""")
            assert short == [], f"targets under 44 px at 390: {short}"
        lane = page.evaluate("document.querySelector('.ui-page').getBoundingClientRect().width")
        skel = page.evaluate("document.querySelector('[data-skeleton-kind=\"list\"]').getBoundingClientRect().width")
        assert abs(lane - skel) <= 8, "the skeleton must span the lane"
        shot = page.screenshot(full_page=False)
        shots = os.environ.get("UBYHOST_SHOTS_DIR")
        if shots:
            Path(shots).mkdir(parents=True, exist_ok=True)
            (Path(shots) / f"dev-ui-{width}.png").write_bytes(shot)
        coral, empty = _shares(shot)
        max_coral, min_empty = BUDGET[width]
        assert coral <= max_coral, f"coral {coral:.2f}% over {max_coral}% at {width}"
        assert empty >= min_empty, f"empty surface {empty:.1f}% under {min_empty}% at {width}"
        context.close()
        browser.close()
```

   Command: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-shots .venv/bin/python -m pytest tests/test_dev_ui_browser.py -q --tb=short -x 2>&1 | tail -30`. Expected: `2 passed`, and two PNGs in `/tmp/ubyhost-shots`. If the coral share fails, the cause is the catalog page itself (it shows the primary button, the overdue badge and the active nav): reduce nothing in the components; instead report the measured numbers and stop (section 8), because the budget is the owner's rule.

7. Commit: `git add App/app/routes/dev_ui.py App/app/main.py App/app/templates/dev_ui.html docs/design/catalog.json App/app/static/host2.css App/tests/test_dev_ui.py App/tests/test_dev_ui_browser.py && git commit -m "0131 step 7: /dev/ui living catalog with screenshot and coral budget tests"`.

## 5. Do not touch

Any page template; `_ui.html`, `_ui_layout.html`, `host_page.html`; the old stylesheets; hard rules 2, 3, 8. The route must never leak data: it reads no tables.

## 6. Commands

- `python3 scripts/design_lint.py` expected: OK.
- `cd App && .venv/bin/python -m pytest tests/test_dev_ui.py tests/test_design_lint.py -q --tb=short -x 2>&1 | tail -30` expected: all passed.
- `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-shots .venv/bin/python -m pytest tests/test_dev_ui_browser.py tests/test_host_geometry.py -q --tb=short -x 2>&1 | tail -30` expected: all passed, 0 skipped.
- `cd App && .venv/bin/ruff check app/routes/dev_ui.py tests/test_dev_ui.py tests/test_dev_ui_browser.py --select E9,F63,F7,F82,F401,F841` expected: clean (the fixture import carries `noqa: F401`).

## 7. Acceptance

- [ ] `/dev/ui` returns 404 for a host and 200 for an admin.
- [ ] Both screenshots exist; the report states the measured coral and empty percentages at 390 and 1280.
- [ ] Design lint passes with `dev_ui.html` enforced.
- [ ] `git diff df8b842 --stat` lists only section 3 files plus `host2.css`.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a new dependency seems needed; a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0131-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/routes/dev_ui.py` (admin guard), `App/tests/test_dev_ui_browser.py` (budget thresholds).

## Owner steps

1. After the branch is deployed to staging, open `/dev/ui` while signed in as admin to see the catalog.
