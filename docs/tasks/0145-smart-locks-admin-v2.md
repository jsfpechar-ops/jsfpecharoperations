# 0145: Smart locks and the admin pages (users, incidents, operations, funnel) on the v2 template

Status: done
Depends on: 0144 | Base commit: c340b7f | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Never push, never open a PR. One commit at the end (step 8). Page file: `docs/design/pages/properties.md` section "Smart locks" (a Properties tab). The admin pages have no page file; this brief is their spec.

Reconciled 2026-10-19 against c340b7f: every replacement count below was dry-run on a copy of the tree and passes; the lint, the new test and the browser tests in step 7 passed on that copy.

## 1. Objective

Move `smart_locks.html`, `users.html`, `admin_incidents.html`, `admin_operations.html` and `admin_funnel.html` from `base.html` + `page_header` onto `host_page.html`, with v2 buttons, badges, tables, fields and no inline styles. TTLock setup, refresh and remove forms, user management forms and incident forms keep their actions, field names and confirms.

## 2. Context

Rules: MASTER 5 (page template, body kinds), 7.1 (buttons), 7.4 (table), 7.5 (badges), 4 (one coral button per screen). Hard rules 2, 3, 8.

How the migrated pages do it (copy this, nothing else): `reservations.html` sets `nav` and `body_kind` at the top, imports `ui_section_tabs` at top level from `_ui_layout.html`, fills `title`, `meta`, `tabs` (`{{ ui_section_tabs() }}`) and `body`. `host_page.html` renders the `<h1>` from the `title` block (no `page_title` block needed) and the meta line from `meta`. The old `page_header()` showed the section tabs automatically (`page_tabs()` in `App/app/templating.py` lines 440 to 471 returns Properties tabs for `smart_locks` and Settings tabs for `users`, `incidents`, `operations`, `funnel`), so every page here fills the `tabs` block or it would lose its tabs.

Decisions taken while reconciling (do not change them):

- Body kinds follow the migration map: smart locks `list` (keeps the same wide lane as its sibling Properties tabs), users and incidents `list`, operations and funnel `detail`.
- Badges use the four v2 kinds only (MASTER 7.5): `pill red` -> `ui-badge ui-badge-action`, `pill amber` -> `ui-badge-attention`, `pill green` -> `ui-badge-done`, `pill grey` -> `ui-badge-neutral`. There is no `data-tone` attribute in v2; do not add one. The six live counters on Operations keep their condition: e.g. `class="ui-badge {{ 'ui-badge-action' if ops.filings.count else 'ui-badge-done' }}"` (coral when filings are pending).
- Smart locks has one coral button per state, through `{% set cta = 'ui-btn ui-btn-primary' %}`: Connect (no account), the share block's Check (account, no locks), the list's Check (locks). When locks exist the "add more" share block is also on the page, so its Check button is `ui-btn-secondary` there (`{{ cta if section == 'share' else 'ui-btn ui-btn-secondary' }}`).
- `class="actions"` in incidents becomes `ui-btn-group`, not `ui-form-actions`: `host2.css` hides `.ui-form-actions` below 1024 px (sticky bar pattern), which would remove the only submit button on phone.
- `&#10003;` in smart_locks becomes the literal character `✓`: the design lint reads `#10003` as a raw colour.
- `app.js` keys on `data-copy`, `data-confirm`, `.row-menu-trigger`, never on `.btn` or `.pill`.

Stale facts removed from the old brief: the anchors are now matched by the script in step 2 (it stops on any miss); the admin_operations `page_header` line is line 15, not 17; `admin.md` does not exist; `test_admin*.py`/`test_users*.py` globs are replaced by real files; the `/smart-locks` geometry entry has to change because its `.panel` selector disappears (see step 5).

Existing tests that render these pages and must stay green (none asserts the old classes; checked 2026-10-19): `tests/test_smart_locks_page.py`, `tests/test_users_disable_confirm.py`, `tests/test_admin_funnel.py`, `tests/test_admin_operations.py`, `tests/test_incident_register.py`, `tests/test_lock_navigation_browser.py` (keeps `#smart-locks-share .help-tip-btn`), `tests/test_host_wide_geometry_browser.py` (line 68, edited in step 5).

Known failures that are NOT yours (they fail on c340b7f before this brief too; do not run or fix them): `test_host_ux_acceptance.py::test_page_families_through_rail_cards_search_and_back`, `test_host_ux_acceptance.py::test_keyboard_reaches_rail_tabs_and_editor_with_visible_focus`, `test_host_properties_navigation.py::test_properties_page_fits_every_width_and_both_languages`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/smart_locks.html` | edit | head, classes, 12 styles (step 2 script) |
| `App/app/templates/users.html` | edit | head, classes, badges, 1 style |
| `App/app/templates/admin_incidents.html` | edit | head, classes, 2 styles |
| `App/app/templates/admin_operations.html` | edit | head, badges, tables, 6 styles |
| `App/app/templates/admin_funnel.html` | edit | head, one button |
| `docs/design/catalog.json` | edit | enforce the five templates; their legacy lists (step 4 script) |
| `App/tests/test_host_wide_geometry_browser.py` | edit | one line: the `smart-locks` selector |
| `App/tests/test_design_admin.py` | create | v2 shell, one primary per smart-lock state, no styles |

No other file may change. No file under `App/app/static/` changes, so there is no static version bump.

## 4. Steps

All commands run from `App/` unless they say otherwise.

1. Check you start clean: `git status --short App/app/templates docs/design/catalog.json App/tests | head -20`. Expected: no line for any file in section 3. If one is listed, stop.

2. Rewrite the five templates. Run exactly:

```
cd App && .venv/bin/python - <<'PYEOF'
import pathlib, re
T = pathlib.Path("app/templates")
def run(name, exact, pairs, primaries):
    p = T / name; s = p.read_text(encoding="utf-8")
    for old, new in exact:
        assert s.count(old) == 1, (name, old[:60], s.count(old)); s = s.replace(old, new)
    for old, new, n in pairs:
        assert s.count(old) == n, (name, old, s.count(old)); s = s.replace(old, new)
    assert 'style="' not in s, (name, re.findall(r' style="[^"]*"', s))
    assert 'class="btn' not in s and 'class="pill' not in s and 'page_header' not in s, name
    assert s.count("ui-btn-primary") == primaries, (name, s.count("ui-btn-primary"))
    assert s.count("{% block body %}") == 1 and "{% block content %}" not in s, name
    p.write_text(s, encoding="utf-8")
# The six live counters: red becomes action (coral), amber becomes attention, green stays done.
OLD = '''class="pill {{ 'TONE' if COND else 'green' }}"'''
NEW = '''class="ui-badge {{ 'ui-badge-KIND' if COND else 'ui-badge-done' }}"'''
OPS_BADGES = [(OLD.replace("TONE", tone).replace("COND", cond), NEW.replace("KIND", kind).replace("COND", cond))
    for tone, kind, cond in [("red", "action", "ops.filings.count"), ("amber", "attention", "ops.feeds.count"),
        ("red", "action", "ops.jobs.count"), ("amber", "attention", "ops.mail.count"),
        ("amber", "attention", "ops.ttlock.used >= ops.ttlock.limit * 0.8"), ("amber", "attention", "ops.alerts.count")]]
run("smart_locks.html", [
 ('''{% extends "base.html" %}
{% set nav = 'smart_locks' %}
{% block title %}{{ t('smart_locks.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header, help_tip, copy_button with context %}

{{ page_header(t('smart_locks.title'), t('smart_locks.lede')) }}
''', '''{% extends "host_page.html" %}
{% set nav = 'smart_locks' %}
{% set body_kind = 'list' %}
{# One coral button per state: setup (no account), share check (no locks yet), list check (locks). #}
{% set cta = 'ui-btn ui-btn-primary' %}
{% from "_ui_layout.html" import ui_section_tabs with context %}
{% block title %}{{ t('smart_locks.title') }}{% endblock %}
{% block meta %}{{ t('smart_locks.lede') }}{% endblock %}
{% block tabs %}{{ ui_section_tabs() }}{% endblock %}
{% block body %}
{% from "_components.html" import help_tip, copy_button with context %}
'''),
 ('<div class="action-group"><button class="btn primary" type="submit">{{ t(\'smart_locks.check\') }}</button></div></form>',
  '<div class="action-group"><button class="{{ cta if section == \'share\' else \'ui-btn ui-btn-secondary\' }}" type="submit">{{ t(\'smart_locks.check\') }}</button></div></form>'),
 ('<div class="action-group" style="margin-top:28px">', '<div class="action-group">'),
 ('<div class="smart-lock-row" style="margin-bottom:16px">', '<div class="smart-lock-row">'),
 ('<p class="small muted" style="margin-top:20px">', '<p class="ui-sub">'),
 ('<p class="small" style="margin-top:16px">', '<p class="ui-sub">'),
 ('<p style="margin-bottom:6px">', '<p>'),
 ('<p class="small">&#10003; {{', '<p class="small">\u2713 {{'),
], [
 ('<h2 style="margin-top:0">', '<h2>', 3),
 ('<p style="margin-top:0">', '<p>', 1),
 ('<form method="post" action="/smart-locks/refresh" style="margin-top:20px">', '<form method="post" action="/smart-locks/refresh">', 1),
 (' style="display:inline"', ' class="inline"', 2),
 ('class="btn primary"', 'class="{{ cta }}"', 2),
 ('class="btn danger"', 'class="ui-btn ui-btn-danger"', 1),
 ('class="small muted"', 'class="ui-sub"', 2),
 ('class="small"', 'class="ui-sub"', 4),
 ('class="panel"', 'class="ui-section"', 5),
], 1)
run("users.html", [
 ('''{% extends "base.html" %}
{% set nav = 'users' %}
{% block title %}{{ t('users.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header, row_menu_begin, row_menu_end with context %}
{{ page_header(
  t('users.title'),
  t('users.lede')
) }}
''', '''{% extends "host_page.html" %}
{% set nav = 'users' %}
{% set body_kind = 'list' %}
{% from "_ui_layout.html" import ui_section_tabs with context %}
{% block title %}{{ t('users.title') }}{% endblock %}
{% block meta %}{{ t('users.lede') }}{% endblock %}
{% block tabs %}{{ ui_section_tabs() }}{% endblock %}
{% block body %}
{% from "_components.html" import row_menu_begin, row_menu_end with context %}
'''),
 ('<h2 style="margin-top:0">', '<h2>'),
 ('<td class="row-actions" data-label="">', '<td class="ui-cell-acts" data-card="actions">'),
 ('<div class="hint">', '<div class="ui-help">'),
], [
 ('class="btn primary"', 'class="ui-btn ui-btn-primary"', 1),
 ('class="btn small"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 1),
 ('class="btn"', 'class="ui-btn ui-btn-secondary"', 1),
 ('class="pill amber"', 'class="ui-badge ui-badge-attention"', 3),
 ('class="pill green"', 'class="ui-badge ui-badge-done"', 1),
 ('class="pill grey"', 'class="ui-badge ui-badge-neutral"', 1),
 ('class="table-cards user-table"', 'class="ui-table ui-table-stack user-table"', 1),
 ('class="panel tight scroll-x"', 'class="ui-section"', 1),
 ('class="panel"', 'class="ui-section"', 2),
 ('class="field"', 'class="ui-field"', 2),
 ('class="small muted mono"', 'class="ui-sub ui-mono"', 1),
 ('class="small muted"', 'class="ui-sub"', 8),
 ('class="small"', 'class="ui-sub"', 1),
 ('class="mono"', 'class="ui-mono"', 1),
], 1)
run("admin_incidents.html", [
 ('''{% extends "base.html" %}
{% set nav = 'incidents' %}
{% block title %}{{ t('incidents.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header with context %}
{{ page_header(t('incidents.title'), t('incidents.lede')) }}
''', '''{% extends "host_page.html" %}
{% set nav = 'incidents' %}
{% set body_kind = 'list' %}
{% from "_ui_layout.html" import ui_section_tabs with context %}
{% block title %}{{ t('incidents.title') }}{% endblock %}
{% block meta %}{{ t('incidents.lede') }}{% endblock %}
{% block tabs %}{{ ui_section_tabs() }}{% endblock %}
{% block body %}
'''),
], [
 ('<h2 style="margin-top:0">', '<h2>', 2),
 ('class="btn primary"', 'class="ui-btn ui-btn-primary"', 1),
 ('class="btn ghost"', 'class="ui-btn ui-btn-quiet"', 1),
 ('class="btn"', 'class="ui-btn ui-btn-secondary"', 1),
 ('class="field"', 'class="ui-field"', 9),
 ('class="actions"', 'class="ui-btn-group"', 2),
 ('class="grid"', 'class="ui-pair"', 2),
 ('class="panel"', 'class="ui-section"', 3),
 ('class="small muted"', 'class="ui-sub"', 3),
 ('class="muted small"', 'class="ui-sub"', 1),
 ('class="small"', 'class="ui-sub"', 1),
 ('class="muted"', 'class="ui-sub"', 1),
], 1)
run("admin_operations.html", [
 ('''{% extends "base.html" %}
{% set nav = 'operations' %}
{% block title %}{{ t('ops.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header with context %}
''', '''{% extends "host_page.html" %}
{% set nav = 'operations' %}
{% set body_kind = 'detail' %}
{% from "_ui_layout.html" import ui_section_tabs with context %}
{% block title %}{{ t('ops.title') }}{% endblock %}
{% block meta %}{{ t('ops.lede') }}{% endblock %}
{% block tabs %}{{ ui_section_tabs() }}{% endblock %}
{% block body %}
'''),
 ("{{ page_header(t('ops.title'), t('ops.lede')) }}\n", ""),
] + OPS_BADGES, [
 ('<h2 style="margin-top:0">', '<h2>', 6),
 ('class="pill red"', 'class="ui-badge ui-badge-action"', 2),
 ('class="pill amber"', 'class="ui-badge ui-badge-attention"', 1),
 ('class="pill green"', 'class="ui-badge ui-badge-done"', 1),
 ('class="table-cards"', 'class="ui-table ui-table-stack"', 6),
 ('class="panel tight scroll-x"', 'class="ui-section"', 6),
 ('class="small muted"', 'class="ui-sub"', 6),
 ('class="small"', 'class="ui-sub"', 1),
 ('class="muted"', 'class="ui-sub"', 5),
 ('class="mono"', 'class="ui-mono"', 7),
], 0)
run("admin_funnel.html", [
 ('''{% extends "base.html" %}
{% set nav = 'funnel' %}
{% block title %}{{ t('funnel.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header with context %}
{{ page_header(t('funnel.title')) }}
''', '''{% extends "host_page.html" %}
{% set nav = 'funnel' %}
{% set body_kind = 'detail' %}
{% from "_ui_layout.html" import ui_section_tabs with context %}
{% block title %}{{ t('funnel.title') }}{% endblock %}
{% block tabs %}{{ ui_section_tabs() }}{% endblock %}
{% block body %}
'''),
], [
 ('class="btn"', 'class="ui-btn ui-btn-secondary"', 1),
], 0)
print("ok")
PYEOF
```

   Expected: `ok`. Any `AssertionError` means an anchor or a count is off: stop and paste it in the report. Do not edit counts.

3. Compile: `cd App && .venv/bin/python -c "from app.templating import templates; [templates.env.get_template(n) for n in ('smart_locks.html','users.html','admin_incidents.html','admin_operations.html','admin_funnel.html')]; print('compiled')" 2>&1 | tail -5`. Expected: `compiled`.

4. Catalog (keyed on names, so it applies after earlier briefs edited the same file). From the repo root, run exactly:

```
python3 -I - <<'PYEOF'
import json, pathlib, subprocess, sys
ROOT = pathlib.Path(".").resolve()
cat_path = ROOT / "docs/design/catalog.json"
names = ["smart_locks.html", "users.html", "admin_incidents.html", "admin_operations.html", "admin_funnel.html"]
rels = [f"App/app/templates/{n}" for n in names]
cat = json.loads(cat_path.read_text(encoding="utf-8"))
for rel in rels:
    if rel not in cat["enforced_templates"]:
        cat["enforced_templates"].append(rel)
    cat["legacy"].setdefault(rel, [])
cat_path.write_text(json.dumps(cat, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
out = subprocess.run([sys.executable, "scripts/design_lint.py"], capture_output=True, text=True).stdout
other = []
for line in out.splitlines():
    if not line.startswith("DESIGN "):
        continue
    rel = line[len("DESIGN "):].split(":", 1)[0]
    if rel in rels and ": T3 class not in catalog: " in line:
        token = line.rsplit(": ", 1)[1]
        if token not in cat["legacy"][rel]:
            cat["legacy"][rel].append(token)
    else:
        other.append(line)
for rel in rels:
    cat["legacy"][rel].sort()
cat_path.write_text(json.dumps(cat, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("\n".join(other) or "no other findings")
print({r.split("/")[-1]: cat["legacy"][r] for r in rels})
PYEOF
python3 scripts/design_lint.py | tail -3
```

   Expected: `no other findings`, then the legacy lists, then `design lint: OK`. On the base commit the lists were: smart_locks `action-group, checkline, guide-steps, smart-lock-row, smart-locks-steps-title`; users `split, user-table, wide`; admin_incidents `checkline`; operations and funnel empty. If another finding is printed (not T3 for these five), stop.

5. Geometry entry. With the TTLock feature off (as in the test), `/smart-locks` redirects to `/apartments`; the entry must match that page before and after its own migration. Run exactly:

```
cd App && python3 -I - <<'PYEOF'
import pathlib
p = pathlib.Path("tests/test_host_wide_geometry_browser.py"); s = p.read_text(encoding="utf-8")
old = '    "smart-locks": ("/smart-locks", ".panel"),\n'
assert s.count(old) == 1, s.count(old)
p.write_text(s.replace(old, '    "smart-locks": ("/smart-locks", ".ui-body-list, .panel"),\n'), encoding="utf-8")
print("ok")
PYEOF
```

   Expected: `ok`.

6. Create `App/tests/test_design_admin.py` with exactly:

```python
"""0145: smart locks and the admin pages render on host_page without inline styles."""
from __future__ import annotations

import json
import re
from pathlib import Path

from app import db

from tests.test_smart_locks_page import _client, _connect, hosts, USERS  # noqa: F401

TEMPLATES = ("smart_locks.html", "users.html", "admin_incidents.html", "admin_operations.html", "admin_funnel.html")
LOCK = {"lock_id": "1", "alias": "Door A", "battery": 80, "tz_offset_ms": 3600000}


def _main(page: str) -> str:
    """The page lane only: from the v2 page wrapper to the first shared dialog of base.html."""
    return page.split('<div class="ui-page"', 1)[1].split("<dialog", 1)[0]


def test_smart_locks_has_the_v2_shell_and_one_primary_in_every_state(hosts):
    client = _client(USERS[0])
    states = [client.get("/smart-locks?lang=en").text]
    _connect(hosts[0], "hjhfa_uhaaaa")
    states.append(client.get("/smart-locks?lang=en").text)
    db.execute("UPDATE lock_account SET locks_json = ? WHERE owner_user_id = ?", (json.dumps([LOCK]), hosts[0]))
    states.append(client.get("/smart-locks?lang=en").text)
    for index, page in enumerate(states):
        main = _main(page)
        assert main.count("<h1") == 1 and main.startswith(' data-body-kind="list"'), index
        assert main.count("ui-btn ui-btn-primary") == 1, index
        assert 'style="' not in main and not re.search(r'class="(btn|pill)[ "]', main), index
        assert 'class="ui-tabs"' in main and 'href="/smart-locks" aria-current="page"' in main, index
    assert 'action="/smart-locks/remove"' in states[2] and "data-confirm" in states[2]


def test_templates_have_no_raw_style_or_legacy_control():
    root = Path(__file__).resolve().parents[1] / "app" / "templates"
    for name in TEMPLATES:
        text = (root / name).read_text(encoding="utf-8")
        assert text.startswith('{% extends "host_page.html" %}'), name
        assert 'style="' not in text and 'class="btn' not in text and 'class="pill' not in text, name
        assert "page_header" not in text and text.count("ui-btn-primary") <= 1, name
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_design_admin.py tests/test_smart_locks_page.py tests/test_users_disable_confirm.py tests/test_admin_funnel.py tests/test_admin_operations.py tests/test_incident_register.py tests/test_design_lint.py -q --tb=short -x 2>&1 | tail -30`. Expected: `49 passed` (the number may differ by a few if earlier briefs added lint tests), 0 failed.

7. Browser tests (no screenshots: the orchestrator takes them, so attach none). The browser is not found automatically; set its path:

   `cd App && UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_shell_lane_browser.py tests/test_host_wide_geometry_browser.py tests/test_lock_navigation_browser.py -q --tb=short -p no:warnings 2>&1 | tail -30`. Expected: `13 passed`, 0 skipped, 0 failed. It takes about 10 minutes; use a 900000 ms timeout. If `test_host_wide_lanes_align` fails on a route other than `smart-locks`, that comes from an earlier brief: stop and report it.

8. Commit: `git add App/app/templates/smart_locks.html App/app/templates/users.html App/app/templates/admin_incidents.html App/app/templates/admin_operations.html App/app/templates/admin_funnel.html docs/design/catalog.json App/tests/test_host_wide_geometry_browser.py App/tests/test_design_admin.py && git commit -m "0145: smart locks and admin pages on host_page" 2>&1 | tail -3`. Then `cd .. && python3 scripts/context_lint.py 2>&1 | tail -5`.

## 5. Do not touch

`App/app/routes/admin.py`, `App/app/ttlock.py`, `App/app/templating.py`, `_components.html`, `host_page.html`, `_ui*.html`, every file under `App/app/static/`; hard rules 2, 3, 8. Never push, never open a PR.

## 6. Commands

- Step 4: `python3 scripts/design_lint.py` -> `design lint: OK`.
- Step 6 and step 7 commands, 0 skipped.

## 7. Acceptance

- [ ] Step 2 prints `ok`; step 3 prints `compiled`; lint OK with the five templates in `enforced_templates`.
- [ ] Smart locks: `<h1>`, Properties tabs with Smart locks current, exactly one `ui-btn ui-btn-primary` in each of the three states (test_design_admin), forms post to `/smart-locks/setup`, `/smart-locks/refresh`, `/smart-locks/remove` as before.
- [ ] Users, incidents, operations, funnel: `host_page.html` shell with Settings tabs, v2 badges (four kinds only), `ui-table ui-table-stack` tables, no `style=""`, no `class="btn`, no `class="pill`.
- [ ] Step 6 and step 7 pass, 0 skipped. No screenshots needed from you.

## 8. Stop and ask

Stop, and write the report, if: an assert in a script fails; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0145-report.md` (600 tokens at most) and set `Status: review`: files changed (`git diff --stat HEAD~1`), each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

- `App/app/templates/admin_operations.html`: the filing backlog and stuck-submission counters are the owner's UbyPort watch panel; their badge must be `ui-badge-action` (coral) whenever `ops.filings.count` / `ops.stuck.count` / `ops.jobs.count` is positive.
- `App/app/templates/smart_locks.html`: one primary per state; the remove form keeps `data-confirm`.
- Phone (below 1024 px): `ui-table` rows stack as cards without `data-card` roles, so the admin tables show values without their column labels. Acceptable for admin-only pages for now; a later brief can add `data-card` roles.

## Owner steps

None.
