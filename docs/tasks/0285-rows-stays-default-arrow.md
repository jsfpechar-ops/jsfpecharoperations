# 0285: Properties rows look like Stays rows; Stays opens on "Upcoming & current"; Guest links arrow gap

Status: todo
Depends on: 0284 | Base commit: the 0284 commits | Branch: claude/project-thread-futwgu (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

On wide screens the Properties, Guest links and Business tables become separate bordered, rounded rows with a gap, exactly like the Stays rows (owner, 2026-10-22). The Stays page opens on "Upcoming & current" instead of "All dates" (explicit choices and saved views still win), and the Open arrow in the Guest links table sits on the name's line with a clear gap instead of tight under it.

## 2. Context

- Stays rows (host2.css, 0181): `border-spacing: 0 var(--space-2)`, 1 px `--line` borders on the cells, `--card-radius` on the outer cells, header with no bottom border.
- Properties (`apartments.html`) and Business (`entities.html`) tables live in `.list-cards.lc-properties` / `.lc-entities` containers (container name `list-cards`); below 800 px (properties) and 950 px (entities) they are already separate cards (0281). This brief covers the wide case only.
- `App/app/routes/admin.py`, in `reservations_list`:
  `        date_range = "custom" if (date_from or date_to or (archive_scope and date_range == "custom")) else "all"`
  The comment above it reads `        # Explicit dates win; an empty date query is the unbounded default.`
- `App/tests/test_query_budget.py`: `_LIST_QUERY_BUDGET = {"/": 20, "/reservations": 25}`. Its comment says WP33 merges overdue unfinished stays into the default list, which costs reads on /reservations; with "upcoming" as the default the page now makes exactly 25 queries (measured), so the budget becomes 26.
- Guest links name cell (`apartments.html`): `<a class="row-primary-link" href="{{ base_url }}">{{ property_identity(...) }}</a> {{ row_open() }}`; a long name wraps and pushes the 28 px arrow onto the next line, almost touching the name.
- Lint on host2.css: no raw colours, no bare px except 0 and 1.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/static/host2.css | append | wide bordered rows, arrow gap |
| App/app/routes/admin.py | edit | default range `upcoming` |
| App/tests/test_query_budget.py | edit | budget 26 for /reservations |
| App/app/templates/base.html | edit | host2.css key |
| App/tests/static_versions.json | regenerate | `--write` |
| App/tests/test_0285_rows_browser.py | new | guard test |

No other file may change.

## 4. Steps

1. host2.css: append at the very end:

```css

/* 0285: on wide screens Properties, Guest links and Business rows are the same
   separate bordered cards as the Stays rows (0181); below their card switch
   point 0281 already makes them cards. */
@container list-cards (min-width: 800px) {
  .host-workspace .lc-properties > table { border-collapse: separate; border-spacing: 0 var(--space-2); }
  .host-workspace .lc-properties thead th { border-bottom: 0; }
  .host-workspace .lc-properties tbody tr { border: 0; }
  .host-workspace .lc-properties tbody td { border: 0; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
  .host-workspace .lc-properties tbody td:first-child { border-left: 1px solid var(--line); border-top-left-radius: var(--card-radius); border-bottom-left-radius: var(--card-radius); }
  .host-workspace .lc-properties tbody td:last-child { border-right: 1px solid var(--line); border-top-right-radius: var(--card-radius); border-bottom-right-radius: var(--card-radius); }
}
@container list-cards (min-width: 950px) {
  .host-workspace .lc-entities > table { border-collapse: separate; border-spacing: 0 var(--space-2); }
  .host-workspace .lc-entities thead th { border-bottom: 0; }
  .host-workspace .lc-entities tbody tr { border: 0; }
  .host-workspace .lc-entities tbody td { border: 0; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
  .host-workspace .lc-entities tbody td:first-child { border-left: 1px solid var(--line); border-top-left-radius: var(--card-radius); border-bottom-left-radius: var(--card-radius); }
  .host-workspace .lc-entities tbody td:last-child { border-right: 1px solid var(--line); border-top-right-radius: var(--card-radius); border-bottom-right-radius: var(--card-radius); }
}
@media (hover: hover) {
  .host-workspace :is(.lc-properties, .lc-entities) tbody tr.clickable-row:hover > td { background: var(--state-hover); }
}
.host-workspace :is(.lc-properties, .lc-entities) tbody tr.clickable-row:focus-within > td { background: var(--state-hover); }
.host-workspace :is(.lc-properties, .lc-entities) tbody tr.clickable-row:active > td { background: var(--state-press); }

/* 0285: the Guest links Open arrow stays on the name's line with a clear gap. */
.host-workspace .property-summary-table td:first-child .row-primary-link { display: inline-block; max-width: calc(100% - var(--space-12)); vertical-align: middle; }
.host-workspace .property-summary-table td:first-child .row-primary-link + .row-open { margin-left: var(--space-3); }
```

2. admin.py: replace the two context lines with

```python
        # Explicit dates win; with no range the host sees what is coming and who is in now (owner 2026-10-22).
        date_range = "custom" if (date_from or date_to or (archive_scope and date_range == "custom")) else "upcoming"
```

3. test_query_budget.py: replace `_LIST_QUERY_BUDGET = {"/": 20, "/reservations": 25}` with `_LIST_QUERY_BUDGET = {"/": 20, "/reservations": 26}`.

4. Cache key, from the repo root:

```
sed -i 's/host2.css?v=20261022-0284"/host2.css?v=20261022-0285"/' App/app/templates/base.html
grep -c 'host2.css?v=20261022-0285"' App/app/templates/base.html
cd App && .venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5
```

5. Create `App/tests/test_0285_rows_browser.py` with exactly:

```python
"""0285: Properties rows are bordered cards like Stays rows; Stays opens on
Upcoming & current; the Guest links arrow keeps a gap from the name."""
from __future__ import annotations

import secrets

from fastapi.testclient import TestClient

from app import auth, db, demo
from app.main import app
from tests.conftest import login_as
from tests.test_property_navigation_browser import base, chromium_launch_kwargs, sync_api  # noqa: F401

ROW = """sel => { const tr = document.querySelector(sel); const tds = [...tr.children];
  const first = getComputedStyle(tds[0]), last = getComputedStyle(tds[tds.length - 1]);
  return {left: first.borderLeftStyle, right: last.borderRightStyle, radius: parseFloat(first.borderTopLeftRadius),
          spacing: getComputedStyle(tr.closest('table')).borderSpacing}; }"""


def _client():
    db.init_db()
    user = f"rows-{secrets.token_hex(3)}"
    owner = auth.create_account(f"{user}@example.test", "Rows Host", role="host", username=user)
    demo.seed(owner)
    client = TestClient(app)
    login_as(client, user, url="/login?lang=en")
    return client


def test_stays_open_on_upcoming_and_current():
    client = _client()
    page = client.get("/reservations?lang=en").text
    assert 'aria-current="true">Upcoming &amp; current<' in page or 'aria-current="true">Upcoming & current<' in page
    page = client.get("/reservations?range=all&lang=en").text
    assert 'aria-current="true">All dates<' in page


def test_properties_rows_match_stays_rows(base):
    client = _client()
    cookie = client.cookies.get(auth.SESSION_COOKIE)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for width in (1280, 2000):
            context = browser.new_context(viewport={"width": width, "height": 900})
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
            page = context.new_page()
            page.goto(base + "/reservations?range=all&lang=en")
            stays = page.evaluate(ROW, "table.ui-table tbody tr")
            page.goto(base + "/apartments?lang=en")
            for selector in ("table.properties-table tbody tr", "table.property-summary-table tbody tr"):
                row = page.evaluate(ROW, selector)
                assert row == stays, (width, selector, row, stays)
            gap = page.evaluate(
                """() => { const a = document.querySelector('.property-summary-table tbody tr .row-primary-link');
                const o = a.parentElement.querySelector('.row-open'); const ra = a.getBoundingClientRect(), ro = o.getBoundingClientRect();
                return {gap: ro.left - ra.right, sameLine: ro.top < ra.bottom && ro.bottom > ra.top}; }"""
            )
            assert gap["sameLine"] and gap["gap"] >= 11, (width, gap)
            context.close()
        browser.close()
```

Commit after each step: `0285 step k`.

## 5. Do not touch

Everything not in section 3. Do not change the phone/tablet card rules (0281) or apartments.html/entities.html. AGENTS.md hard rules 6 and 7.

## 6. Commands (from `App/`, with `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome`)

```
.venv/bin/python -m pytest tests/test_0285_rows_browser.py tests/test_query_budget.py tests/test_static_versions.py tests/test_archive_stays_on_page.py tests/test_stays_empty_workspace.py tests/test_design_stays.py -q --tb=short -x -rs -p no:cacheprovider 2>&1 | tail -30
cd .. && python3 scripts/design_lint.py 2>&1 | tail -5
```

Expected: all pass, 0 skipped; lint clean. If a non-browser test fails only because a bare `/reservations` request no longer lists past stays, change that request to `/reservations?range=all` (that test file then joins section 3) and note it under Deviations; any other failure: stop.

## 7. Acceptance

- [ ] test_0285 passes at 1280 and 2000, 0 skipped.
- [ ] `/reservations` with no query shows "Upcoming & current" selected.
- [ ] host2.css key `20261022-0285`; static_versions.json regenerated; design lint clean.

## 8. Stop and ask

As in docs/tasks/TEMPLATE.md section 8.

## 9. Report

`docs/tasks/0285-report.md` (600 tokens at most), set `Status: review`. Do not push.
