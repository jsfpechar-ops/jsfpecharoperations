# 0402: Guide card tables line up

Status: todo
Depends on: none | Base commit: a759eb6 | Branch: task/0402-guide-table-align
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

On the host Guest guide page (`/apartments/{id}/guide`) every topic is its own `ui-table` with auto column widths, so the STATE header and the badges sit at a different x in every section at desktop width (measured at 1280 px: badge left edges from 743 to 951 px). Right-align the STATE column in these tables so header and badges share one edge in every section; phone (cards) stays as it is.

## 2. Context

`ui_table_begin` already takes an align flag per column (App/app/templates/_ui_layout.html):

```
<table class="ui-table" aria-label="{{ label }}"><thead><tr>{% for text, align in columns %}<th scope="col"{% if align == 'r' %} class="ui-cell-r"{% endif %}>{{ text }}</th>{% endfor %}</tr></thead><tbody>
```

`.ui-cell-r { text-align: right; }` exists in App/app/static/host2.css. Under 1024 px the table becomes cards and `td` gets `text-align: left`, so phone layout does not change. No CSS change and no new class are needed (design lint stays green).

Excerpts to change (verbatim):

App/app/templates/guest_guide.html
```
{{ ui_table_begin([(t('guest_guide.col.card'), ''), (t('guest_guide.col.state'), '')], label=t('guest_guide.topic.' ~ topic)) }}
```
```
  <td data-card="badge">{% if card.state == 'done' %}
```

App/app/templates/guest_guide_quick_done.html
```
{{ ui_table_begin([(t('guest_guide.col.card'), ''), (t('guest_guide.col.state'), '')], label=t('guest_guide.quick.missing_title')) }}
```
```
  <td data-card="badge">{% if card.state == 'check' %}
```

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/guest_guide.html | edit | STATE column right-aligned in the topic tables only (the import section is being moved by 0403; do not touch it) |
| App/app/templates/guest_guide_quick_done.html | edit | same |
| App/tests/test_guest_guide_table_browser.py | new | alignment test + screenshots |
| docs/tasks/0402-report.md | new | report |

No other file may change.

## 4. Steps

1. In both templates, change each STATE column tuple from `(..., '')` to `(..., 'r')` (second tuple of the two `ui_table_begin` calls above), and each `<td data-card="badge">` shown above to `<td class="ui-cell-r" data-card="badge">`.
2. Create App/tests/test_guest_guide_table_browser.py:

```python
"""0402: the STATE column of every guide topic table shares one right edge at desktop width."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth
from tests.browser_support import chromium_launch_kwargs
from test_host_wide_geometry_browser import (  # noqa: F401  (fixtures)
    _dismiss_optional_security_prompt,
    _wait_for_host_layout,
    wide_base,
    wide_host,
)

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0402"
EDGES = """(selector) => [...document.querySelectorAll(selector)]
  .map(e => Math.round(e.getBoundingClientRect().right))"""


@pytest.mark.parametrize("width", [1280, 390])
def test_guide_state_column_lines_up(wide_host, wide_base, width):  # noqa: F811
    apartment_id = wide_host["apartments"][0]
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": width, "height": 900}, device_scale_factor=2)
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": wide_host["cookie"], "url": wide_base + "/"}])
        page = context.new_page()
        page.goto(f"{wide_base}/apartments/{apartment_id}/guide?lang=en")
        _wait_for_host_layout(page)
        _dismiss_optional_security_prompt(page)
        assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")
        if width >= 1024:
            # th and td have different side padding, so headers and badges are checked as two groups.
            for selector in ("[id^=topic-] td[data-card=badge] .ui-badge", "[id^=topic-] th:last-child"):
                edges = page.evaluate(EDGES, selector)
                assert len(edges) > 4
                assert max(edges) - min(edges) <= 2, (selector, edges)
        page.locator("[id^=topic-]").nth(1).scroll_into_view_if_needed()
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"guide-table-{width}.png"))
        context.close()
        browser.close()
```

## 5. Do not touch

CSS files, `_ui_layout.html`, the design catalog, any other template. AGENTS.md rules 7 and 8 apply: browser tests 0 skipped; never push to main.

## 6. Commands

From `App/`:

- `.venv/bin/python -m pytest tests/test_guest_guide_table_browser.py -q --tb=short 2>&1 | tail -30` → 2 passed, 0 skipped (set `UBYHOST_REQUIRE_BROWSER=1`; if Chromium is not bundled, also `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium`).
- `.venv/bin/python -m pytest tests/test_guest_guide.py tests/test_guest_guide_pages.py tests/test_guest_guide_browser.py tests/test_design_guardrails_browser.py -q --tb=short 2>&1 | tail -30` → all pass.
- `.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 2>&1 | tail -5` → clean.
- From repo root: `python3 scripts/design_lint.py 2>&1 | tail -5` and `python3 scripts/context_lint.py 2>&1 | tail -5` → clean.
- `git checkout -- docs/tasks/screenshots-*` for any folder other than screenshots-0402 that a browser run rewrote.

## 7. Acceptance

- [ ] At 1280 px the right edges of all badges differ by at most 2 px, and those of all STATE headers too (test above).
- [ ] At 390 px the cards look as before (badge on its own line, left).
- [ ] Screenshots docs/tasks/screenshots-0402/guide-table-1280.png and -390.png.

## 8. Stop and ask

Stop, and write the report, if an excerpt is not found, a test fails twice, a file outside §3 needs a change, or you reach 25 tool calls.

## 9. Report

Write `docs/tasks/0402-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, §7 ticked, deviations.
