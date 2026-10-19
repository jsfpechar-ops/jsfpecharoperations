# 0145: Smart locks and the admin pages (users, incidents, operations, funnel) on the v2 template

Status: todo
Depends on: 0144 | Base commit: df8b842 | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit each step as `0145 step k`. Never push, never open a PR. Page files: `docs/design/pages/properties.md` (smart locks), `docs/design/pages/admin.md`.

## 1. Objective

Move `smart_locks.html` (settings kind, inside the Properties section tabs), `users.html`, `admin_incidents.html`, `admin_operations.html` and `admin_funnel.html` onto `host_page.html`; v2 controls, badges, tables, fields; no inline styles. TTLock setup, refresh and remove forms, user management forms and incident review forms keep their actions, names and confirms.

## 2. Context

Rules: MASTER 5 (settings and list kinds), 7.3 (badges), 7.4, 4. `smart_locks.html` has three `btn primary` buttons in exclusive branches (connect, setup, refresh): the page uses a `cta` variable so the template text holds one literal `ui-btn-primary`. `app.js` keys on `data-copy`, `data-confirm`, `.row-menu-trigger`, never on `.btn` or `.pill`. No test under `App/tests/test_admin*.py`, `test_users*.py` or `test_smart_locks*.py` asserts a legacy class (checked 2026-10-19 with `grep -n 'class="btn\|class="pill\|\.btn\b\|page-header' App/tests/test_admin*.py App/tests/test_users*.py App/tests/test_smart_lock*.py`; run it again before step 1 and stop if it prints anything).

Anchor A, `App/app/templates/smart_locks.html` lines 1 to 7 (verbatim; line 6 is empty):

```
{% extends "base.html" %}
{% set nav = 'smart_locks' %}
{% block title %}{{ t('smart_locks.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header, help_tip, copy_button with context %}

{{ page_header(t('smart_locks.title'), t('smart_locks.lede')) }}
```

Anchor B, `App/app/templates/users.html` lines 1 to 9 (verbatim):

```
{% extends "base.html" %}
{% set nav = 'users' %}
{% block title %}{{ t('users.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header, row_menu_begin, row_menu_end with context %}
{{ page_header(
  t('users.title'),
  t('users.lede')
) }}
```

Anchor C, `App/app/templates/admin_incidents.html` lines 1 to 6 (verbatim):

```
{% extends "base.html" %}
{% set nav = 'incidents' %}
{% block title %}{{ t('incidents.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header with context %}
{{ page_header(t('incidents.title'), t('incidents.lede')) }}
```

Anchor D, `App/app/templates/admin_operations.html` lines 1 to 5 (verbatim), followed by two macros (`age`, `workspace_link`) and then line 17 `{{ page_header(t('ops.title'), t('ops.lede')) }}`:

```
{% extends "base.html" %}
{% set nav = 'operations' %}
{% block title %}{{ t('ops.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header with context %}
```

Anchor E, `App/app/templates/admin_funnel.html` lines 1 to 6 (verbatim):

```
{% extends "base.html" %}
{% set nav = 'funnel' %}
{% block title %}{{ t('funnel.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header with context %}
{{ page_header(t('funnel.title')) }}
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/smart_locks.html` | edit | head, classes, 12 styles |
| `App/app/templates/users.html` | edit | head, classes, 1 style |
| `App/app/templates/admin_incidents.html` | edit | head, classes, 2 styles |
| `App/app/templates/admin_operations.html` | edit | head, badges, classes, 6 styles |
| `App/app/templates/admin_funnel.html` | edit | head, one button |
| `docs/design/catalog.json` | edit | enforce the five templates; legacy lists |
| `App/tests/test_design_admin.py` | create | shells, no styles, one primary |

No other file may change.

## 4. Steps

1. Heads. Replace Anchor A with:

```
{% extends "host_page.html" %}
{% set nav = 'smart_locks' %}
{% set body_kind = 'settings' %}
{% set cta = 'ui-btn ui-btn-primary' %}
{% block title %}{{ t('smart_locks.title') }}{% endblock %}
{% block page_title %}{{ t('smart_locks.title') }}{% endblock %}
{% block meta %}{{ t('smart_locks.lede') }}{% endblock %}
{% block tabs %}{{ ui_section_tabs(t('nav.properties')) }}{% endblock %}
{% block body %}
{% from "_components.html" import help_tip, copy_button with context %}
```

   and insert `{% from "_ui_layout.html" import ui_section_tabs with context %}` as a new line right after `{% set cta = ... %}` (top level, so the `tabs` block sees it). If `page_tabs()` returns no tabs for `nav == 'smart_locks'` (check: `grep -n "smart_locks" App/app/templating.py App/app/routes/admin.py | head -5`), drop the `tabs` block and the import and say so in the report.

   Replace Anchor B with:

```
{% extends "host_page.html" %}
{% set nav = 'users' %}
{% set body_kind = 'list' %}
{% block title %}{{ t('users.title') }}{% endblock %}
{% block page_title %}{{ t('users.title') }}{% endblock %}
{% block meta %}{{ t('users.lede') }}{% endblock %}
{% block body %}
{% from "_components.html" import row_menu_begin, row_menu_end with context %}
```

   Replace Anchor C with:

```
{% extends "host_page.html" %}
{% set nav = 'incidents' %}
{% set body_kind = 'list' %}
{% block title %}{{ t('incidents.title') }}{% endblock %}
{% block page_title %}{{ t('incidents.title') }}{% endblock %}
{% block meta %}{{ t('incidents.lede') }}{% endblock %}
{% block body %}
```

   Replace Anchor D with:

```
{% extends "host_page.html" %}
{% set nav = 'operations' %}
{% set body_kind = 'list' %}
{% block title %}{{ t('ops.title') }}{% endblock %}
{% block page_title %}{{ t('ops.title') }}{% endblock %}
{% block meta %}{{ t('ops.lede') }}{% endblock %}
```

   then move the two macro definitions (`{% macro age(minutes) -%}` ... `{%- endmacro %}` and `{% macro workspace_link(row) -%}` ... `{%- endmacro %}`) so they follow the `meta` block unchanged, and replace the line `{{ page_header(t('ops.title'), t('ops.lede')) }}` with `{% block body %}`. Macros defined at top level of a child template are visible in its blocks.

   Replace Anchor E with:

```
{% extends "host_page.html" %}
{% set nav = 'funnel' %}
{% set body_kind = 'list' %}
{% block title %}{{ t('funnel.title') }}{% endblock %}
{% block page_title %}{{ t('funnel.title') }}{% endblock %}
{% block body %}
```

   Compile: `cd App && .venv/bin/python -c "from app.templating import templates; [templates.env.get_template(n) for n in ('smart_locks.html','users.html','admin_incidents.html','admin_operations.html','admin_funnel.html')]; print('compiled')"`. Expected: `compiled`.

2. Styles and classes, from `App/`:

```
.venv/bin/python - <<'EOF'
import pathlib, re
T = pathlib.Path("app/templates")
def run(name, exact, pairs, primaries, regex=()):
    p = T / name; s = p.read_text(encoding="utf-8")
    for pat, rep, n in regex:
        assert len(re.findall(pat, s)) == n, (name, pat, len(re.findall(pat, s))); s = re.sub(pat, rep, s)
    for old, new in exact:
        assert s.count(old) == 1, (name, old, s.count(old)); s = s.replace(old, new)
    for old, new, n in pairs:
        assert s.count(old) == n, (name, old, s.count(old)); s = s.replace(old, new)
    assert 'style="' not in s, (name, re.findall(r' style="[^"]*"', s))
    assert 'class="btn' not in s and 'class="pill' not in s, name
    assert s.count("ui-btn-primary") == primaries, (name, s.count("ui-btn-primary"))
    p.write_text(s, encoding="utf-8")
run("smart_locks.html", [
 ('<div class="action-group" style="margin-top:28px">', '<div class="action-group">'),
 ('<div class="smart-lock-row" style="margin-bottom:16px">', '<div class="smart-lock-row">'),
 ('<p class="small muted" style="margin-top:20px">', '<p class="ui-sub">'),
 ('<p class="small" style="margin-top:16px">', '<p class="ui-sub">'),
 ('<p style="margin-bottom:6px">', '<p>'),
], [
 ('<h2 style="margin-top:0">', '<h2>', 3),
 ('<p style="margin-top:0">', '<p>', 1),
 ('<form method="post" action="/smart-locks/refresh" style="margin-top:20px">', '<form method="post" action="/smart-locks/refresh">', 1),
 (' style="display:inline"', ' class="inline"', 2),
 ('class="btn primary"', 'class="{{ cta }}"', 3),
 ('class="btn danger"', 'class="ui-btn ui-btn-danger"', 1),
 ('class="small muted"', 'class="ui-sub"', 2),
 ('class="small"', 'class="ui-sub"', 4),
 ('class="panel"', 'class="ui-section"', 5),
], 1)
run("users.html", [
 ('<h2 style="margin-top:0">', '<h2>'),
], [
 ('class="btn primary"', 'class="ui-btn ui-btn-primary"', 1),
 ('class="btn small"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 1),
 ('class="btn"', 'class="ui-btn ui-btn-secondary"', 1),
 ('class="pill amber"', 'class="ui-badge ui-badge-action" data-tone="amber"', 3),
 ('class="pill green"', 'class="ui-badge ui-badge-done" data-tone="green"', 1),
 ('class="pill grey"', 'class="ui-badge ui-badge-neutral" data-tone="grey"', 1),
 ('class="table-cards user-table"', 'class="ui-table ui-table-stack user-table"', 1),
 ('class="panel tight scroll-x"', 'class="ui-section scroll-x"', 1),
 ('class="panel"', 'class="ui-section"', 2),
 ('class="field"', 'class="ui-field"', 2),
 ('class="small muted mono"', 'class="ui-sub ui-mono"', 1),
 ('class="small muted"', 'class="ui-sub"', 8),
 ('class="small"', 'class="ui-sub"', 1),
 ('class="mono"', 'class="ui-mono"', 1),
], 1)
run("admin_incidents.html", [], [
 ('<h2 style="margin-top:0">', '<h2>', 2),
 ('class="btn primary"', 'class="ui-btn ui-btn-primary"', 1),
 ('class="btn ghost"', 'class="ui-btn ui-btn-quiet"', 1),
 ('class="btn"', 'class="ui-btn ui-btn-secondary"', 1),
 ('class="field"', 'class="ui-field"', 9),
 ('class="actions"', 'class="ui-form-actions"', 2),
 ('class="grid"', 'class="ui-pair"', 2),
 ('class="panel"', 'class="ui-section"', 3),
 ('class="small muted"', 'class="ui-sub"', 3),
 ('class="muted small"', 'class="ui-sub"', 1),
 ('class="small"', 'class="ui-sub"', 1),
 ('class="muted"', 'class="ui-sub"', 1),
], 1)
run("admin_operations.html", [], [
 ('<h2 style="margin-top:0">', '<h2>', 6),
 ('class="pill red"', 'class="ui-badge ui-badge-action" data-tone="red"', 2),
 ('class="pill amber"', 'class="ui-badge ui-badge-action" data-tone="amber"', 1),
 ('class="pill green"', 'class="ui-badge ui-badge-done" data-tone="green"', 1),
 ('class="table-cards"', 'class="ui-table ui-table-stack"', 6),
 ('class="panel tight scroll-x"', 'class="ui-section scroll-x"', 6),
 ('class="small muted"', 'class="ui-sub"', 6),
 ('class="small"', 'class="ui-sub"', 1),
 ('class="muted"', 'class="ui-sub"', 5),
 ('class="mono"', 'class="ui-mono"', 7),
], 0, regex=[
 (r'class="pill \{\{ \'(red|amber)\' if (.+?) else \'green\' \}\}"',
  r'class="ui-badge ui-badge-{{ \'action\' if \2 else \'done\' }}" data-tone="{{ \'\1\' if \2 else \'green\' }}"', 6),
])
run("admin_funnel.html", [], [
 ('class="btn"', 'class="ui-btn ui-btn-secondary"', 1),
], 0)
print("ok")
EOF
```

   Expected: `ok`. The regex turns `<span class="pill {{ 'red' if ops.filings.count else 'green' }}">` into `<span class="ui-badge ui-badge-{{ 'action' if ops.filings.count else 'done' }}" data-tone="{{ 'red' if ops.filings.count else 'green' }}">` (six headings: filings, feeds, jobs, mail, ttlock, alerts). If the regex count is not 6, print `grep -n "pill {{" App/app/templates/admin_operations.html` and stop.

3. Catalog: add the five templates to `enforced_templates`; for each run `python3 scripts/design_lint.py 2>&1 | grep <name> | sed 's/.*catalog: //' | sort -u | tr '\n' ' '` and put the tokens into its `legacy` list. Command: `python3 scripts/design_lint.py`. Expected: OK.

4. Create `App/tests/test_design_admin.py`:

```python
"""0145: smart locks and admin pages render on host_page without inline styles."""
from __future__ import annotations

from tests.test_signed_in_chrome import host_with_property  # noqa: F401

TEMPLATES = ("smart_locks.html", "users.html", "admin_incidents.html", "admin_operations.html", "admin_funnel.html")


def test_smart_locks_has_the_v2_shell_and_one_primary(host_with_property):
    page = host_with_property.get("/smart-locks?lang=en").text
    assert page.count("<h1") == 1 and 'data-body-kind="settings"' in page
    assert page.count('class="ui-btn ui-btn-primary"') == 1
    assert 'style="' not in page.split("<main", 1)[1]


def test_templates_have_no_raw_style_or_legacy_control():
    for name in TEMPLATES:
        text = open(f"app/templates/{name}", encoding="utf-8").read()
        assert 'style="' not in text and 'class="btn' not in text and 'class="pill' not in text, name
        assert text.count("ui-btn-primary") <= 1, name
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_design_admin.py tests/test_smart_lock*.py tests/test_users*.py tests/test_admin*.py tests/test_design_lint.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed.

5. Browser and screenshots: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-shots .venv/bin/python -m pytest tests/test_host_geometry.py tests/test_host_wide_geometry_browser.py -q --tb=short 2>&1 | tail -30`. Expected: passed, 0 skipped. Attach `smart-locks-390.png`, `smart-locks-1280.png`, `admin-operations-1280.png` (sign in as the admin fixture from `tests/test_admin_operations*.py` if one exists; otherwise attach `users-1280.png` from the host fixture and say so).

6. Commit: `git add App/app/templates docs/design/catalog.json App/tests && git commit -m "0145 step 6: smart locks and admin pages on host_page"`.

## 5. Do not touch

`routes/admin.py`, `ttlock.py`, `_components.html`; hard rules 2, 3, 8.

## 6. Commands

- `python3 scripts/design_lint.py` expected: OK.
- Step 4 and step 5 commands, 0 skipped.

## 7. Acceptance

- [ ] Smart locks: header, section tabs (if any), one primary per state, forms post as before.
- [ ] Users, incidents, operations, funnel: v2 shells, badges with tones, v2 tables, no inline styles.
- [ ] Screenshots attached; lint OK with the five templates enforced.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a count differs; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0145-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/templates/admin_operations.html` (filing backlog counters are the owner's UbyPort watch panel; badge tones must still read red when `ops.filings.count` is positive).

## Owner steps

None.
