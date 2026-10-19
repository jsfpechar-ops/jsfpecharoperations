# 0138: Reports list, report detail and house book on the v2 template

Status: todo
Depends on: 0137 | Base commit: c340b7f | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). One commit at the end (step 8). Never push, never open a PR. Page file: `docs/design/pages/stays.md`, sections "Police reports list", "Police report detail" and "Guest register" (already written; do not edit it).

## 1. Objective

Move `submissions.html` (list), `submission_detail.html` (detail) and `housebook.html` (list) onto `host_page.html` with v2 buttons, badges and tables, the way `reservations.html` and `reservation_detail.html` already do. Receipts, the report grammar (`#now` command panel, technical fold), the house-book filter form, its two legacy tables, and the CSV and PDF exports keep their markup.

## 2. Context

Rules: MASTER 5, 7.3, 7.4, 7.5, 4. How migrated pages do it: `{% extends "host_page.html" %}`, `nav`, `body_kind`, then only the blocks `title`, `meta`, `back_url`, `back_label`, `primary_action`, `secondary_actions`, `tabs`, `toolbar`, `body`. Section tabs come from `ui_section_tabs()` in `_ui_layout.html`. Badges are `<span class="ui-badge ui-badge-<kind>" data-tone="<old colour>">` (amber and red: `action`, green: `done`, grey and teal: `neutral`). Stacked tables are `<table class="ui-table ui-table-stack">` with `<tr class="ui-row clickable-row">` and `data-card` roles on each `td` (primary, secondary, badge, meta, hide, actions).

Keep these strings, tests read them: `class="panel stay-command-panel outcome-...` and `<details class="panel technical">` on the report detail (`test_wp25_reported_bugs.py`, `test_report_detail_polish.py`); on the house book `class="table-cards housebook-table"`, `class="panel tight scroll-x housebook-scroll"` and `class="small col-reported"` (`test_wp25_reported_bugs.py` lines 349 to 352). That is why the house-book register and archived tables stay on the legacy `table-cards` markup.

Do not put `ui-sub` on a `<td>`: `.ui-sub` is `display: block` and breaks the desktop table. It goes on a `p`, `div`, `ul` or `span`.

Anchors (all checked verbatim at c340b7f; the step 2 script asserts each one and its count):

- `App/app/templates/submission_detail.html` lines 1 to 5 (`{% extends "base.html" %}` to the `{% from "_components.html" import page_header, ...` line) and lines 20 to 25 (the `{{ page_header(` call).
- `App/app/templates/housebook.html` lines 1 to 10 (`{% extends "base.html" %}` to the `) }}` closing `page_header(`).
- `App/tests/test_report_detail_next_step.py` lines 77, 113, 116; `App/tests/test_host_list_cards_browser.py` lines 29 and 32; `App/tests/test_host_wide_geometry_browser.py` line 61.

`submissions.html` (51 lines) is replaced whole in step 1.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/submissions.html` | replace | host_page, stacked table, receipt in the row menu |
| `App/app/templates/submission_detail.html` | edit | head, CTA variable, classes, banner, guests table |
| `App/app/templates/housebook.html` | edit | head, buttons, badges, fields, three style attributes |
| `docs/design/catalog.json` | edit | enforce the three templates; their legacy lists |
| `App/tests/test_report_detail_next_step.py` | edit | v2 action classes (lines 77, 113, 116) |
| `App/tests/test_host_list_cards_browser.py` | edit | drop the `reports` list (lines 29, 32) |
| `App/tests/test_host_wide_geometry_browser.py` | edit | submissions result lane selector (line 61) |
| `App/tests/test_design_reports.py` | create | header, tabs, hooks, no legacy controls |

No other file may change.

## 4. Steps

All commands run from `App/` unless they say otherwise.

1. Replace `App/app/templates/submissions.html` in full (Write tool) with:

```
{% extends "host_page.html" %}
{% set nav = 'submissions' %}
{% set body_kind = 'list' %}
{% from "_components.html" import row_menu_begin, row_menu_end, submission_pill, empty_state, property_identity with context %}
{% from "_ui.html" import ui_button with context %}
{% from "_ui_layout.html" import ui_section_tabs with context %}
{% block title %}{{ t('reports.title') }}{% endblock %}
{% block meta %}{{ t('reports.lede') }}{% endblock %}
{% block secondary_actions %}{% if receipt_count %}{{ ui_button(t('reports.download_receipts'), 'secondary', href='/submissions/receipts.zip', icon_name='download') }}{% endif %}{% endblock %}
{% block tabs %}{{ ui_section_tabs() }}{% endblock %}
{% block body %}
{% if receipt_count %}
  <p class="ui-sub">{{ t('reports.download_receipts_hint') }}</p>
{% endif %}

{% if rows %}
{# 0138: the stay detail's report table grammar (MASTER 7.3, 7.4): one DOM, cards under 1024 px; the receipt is a row-menu item. #}
<table class="ui-table ui-table-stack" aria-label="{{ t('reports.title') }}">
  <thead>
    <tr><th>{{ t('reports.when') }}</th><th>{{ t('reports.property') }}</th><th>{{ t('reports.mode') }}</th><th class="ui-cell-r">{{ t('reports.guests') }}</th><th>{{ t('reports.outcome') }}</th>
      <th>{{ t('reports.stamp') }}</th><th><span class="sr-only">{{ t('common.actions') }}</span></th></tr>
  </thead>
  <tbody>
  {% for submission in rows %}
    <tr class="ui-row clickable-row" data-href="/submissions/{{ submission.id }}" tabindex="0" role="link"
        aria-label="{{ t('reports.open', id=submission.id) }}">
      <td class="ui-cell-first nowrap" data-card="primary" data-label="{{ t('reports.when') }}">{{ submission.created_at | datetime_local }}</td>
      <td data-card="secondary" data-label="{{ t('reports.property') }}">{{ property_identity(submission.apartment_id, submission.internal_name, true) }}</td>
      <td data-card="meta" data-label="{{ t('reports.mode') }}">{{ report_mode_label(submission.mode) }}</td>
      <td class="ui-num ui-cell-r" data-card="meta" data-label="{{ t('reports.guests') }}">{{ (submission.guest_ids | from_json | length) if submission.guest_ids else 0 }}</td>
      <td data-card="badge" data-label="{{ t('reports.outcome') }}">{{ submission_pill(submission.state) }}</td>
      <td class="ui-mono" data-card="hide" data-label="{{ t('reports.stamp') }}">{{ submission.pseudo_stamp or '—' }}</td>
      <td class="ui-cell-acts row-actions" data-card="actions" data-label="">
        {{ row_menu_begin() }}
          <a class="row-menu-item" href="/submissions/{{ submission.id }}" role="menuitem">{{ t('reports.details') }}</a>
          {% if submission.has_receipt %}
            <a class="row-menu-item" href="/submissions/{{ submission.id }}/receipt.pdf" role="menuitem">{{ t('reports.receipt') }}</a>
          {% endif %}
        {{ row_menu_end() }}
      </td>
    </tr>
  {% endfor %}
  </tbody>
</table>
{% else %}
  {{ empty_state(t('reports.empty_title'), t('reports.empty_body'), '/reservations', t('reports.empty_action')) }}
{% endif %}
{% endblock %}
```

   Command: none (step 3 compiles it).

2. Save this script as `/tmp/patch_0138.py` and run `cd App && .venv/bin/python /tmp/patch_0138.py`. Expected: `ok`. If an assertion fires, it names the file, the string, the expected and the found count: stop and report (do not guess).

```
import pathlib
ROOT = pathlib.Path("app/templates")
def patch(name, pairs, forbid=('style="', 'class="btn', 'class="pill')):
    p = ROOT / name; s = p.read_text(encoding="utf-8")
    for old, new, n in pairs:
        assert s.count(old) == n, (name, old[:70], n, s.count(old)); s = s.replace(old, new)
    for f in forbid:
        assert f not in s, (name, f)
    p.write_text(s, encoding="utf-8")
B = {"grey": ("neutral", "grey"), "green": ("done", "green"), "teal": ("neutral", "teal"),
     "amber": ("action", "amber"), "red": ("action", "red")}
def pill(tone): return f'class="ui-badge ui-badge-{B[tone][0]}" data-tone="{B[tone][1]}"'
DETAIL_HEAD_OLD = '''{% extends "base.html" %}
{% set nav = 'submissions' %}
{% block title %}{{ t('reports.detail.title', id=submission.id) }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header, submission_pill, row_menu_begin, row_menu_end, copy_button with context %}
'''
DETAIL_HEAD_NEW = '''{% extends "host_page.html" %}
{% set nav = 'submissions' %}
{% set body_kind = 'detail' %}
{% from "_components.html" import submission_pill, row_menu_begin, row_menu_end, copy_button with context %}
{# The two coral links below sit in exclusive branches (failed vs receipt), as on the stay detail. #}
{% set cta = 'ui-btn ui-btn-primary' %}
{% block title %}{{ t('reports.detail.title', id=submission.id) }}{% endblock %}
'''
DETAIL_HEADER_OLD = '''{{ page_header(
  t('reports.detail.title', id=submission.id),
  submission.internal_name ~ ' · ' ~ report_mode_label(submission.mode),
  '/submissions',
  t('reports.detail.back')
) }}
'''
DETAIL_HEADER_NEW = '''{% block meta %}{{ submission.internal_name ~ ' · ' ~ report_mode_label(submission.mode) }}{% endblock %}
{% block back_url %}/submissions{% endblock %}
{% block back_label %}{{ t('reports.detail.back') }}{% endblock %}
{% block body %}
'''
patch("submission_detail.html", [
 (DETAIL_HEAD_OLD, DETAIL_HEAD_NEW, 1),
 (DETAIL_HEADER_OLD, DETAIL_HEADER_NEW, 1),
 ('class="btn primary"', 'class="{{ cta }}"', 2),
 ('class="btn small"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 2),
 ('class="btn"', 'class="ui-btn ui-btn-secondary"', 1),
 ('class="pill grey"', pill("grey"), 1), ('class="pill green"', pill("green"), 1),
 ('class="pill amber"', pill("amber"), 2), ('class="pill red"', pill("red"), 2),
 ('<div class="actions">', '<div class="ui-form-actions">', 1),
 ('<div class="banner err" style="margin:0; border-radius:0; border-left:0; border-right:0">', '<div class="ui-banner ui-banner-attention">', 1),
 ("<h2>{{ t('reports.detail.guests') }}</h2>\n<div class=\"panel tight scroll-x\">\n  <table class=\"table-cards\">",
  "<section class=\"ui-section\">\n<div class=\"ui-section-h\"><h2>{{ t('reports.detail.guests') }}</h2></div>\n  <table class=\"ui-table ui-table-stack\" aria-label=\"{{ t('reports.detail.guests') }}\">", 1),
 ("  </table>\n</div>\n\n<details class=\"panel technical\">", "  </table>\n</section>\n\n<details class=\"panel technical\">", 1),
 ('<tr class="clickable-row" data-href="/guests/', '<tr class="ui-row clickable-row" data-href="/guests/', 1),
 ('<td class="num" data-label="#">', '<td class="ui-num" data-card="hide" data-label="#">', 1),
 ("<td data-label=\"{{ t('reports.detail.guest') }}\">", "<td class=\"ui-cell-first\" data-card=\"primary\" data-label=\"{{ t('reports.detail.guest') }}\">", 1),
 ("<td data-label=\"{{ t('reports.detail.result') }}\">", "<td data-card=\"badge\" data-label=\"{{ t('reports.detail.result') }}\">", 1),
 ('<td class="nowrap row-actions" data-label="">', '<td class="ui-cell-acts row-actions" data-card="actions" data-label="">', 1),
 ('<td colspan="4" class="small muted">', '<td colspan="4" data-card="primary">', 1),
 ('class="small muted report-receipt-missing"', 'class="ui-sub report-receipt-missing"', 1),
 ('class="small muted"', 'class="ui-sub"', 5),
 ('class="small err-text"', 'class="ui-sub err-text"', 1),
 ('<ul class="small">', '<ul class="ui-sub">', 1),
 ('class="mono report-stamp"', 'class="ui-mono report-stamp"', 1),
 ('class="mono small code-block"', 'class="ui-mono code-block"', 1),
 ('class="mono small"', 'class="ui-mono"', 1),
])
HB_HEAD_OLD = '''{% extends "base.html" %}
{% set nav = 'housebook' %}
{% block title %}{{ t('housebook.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header, row_menu_begin, row_menu_end, housebook_csv_menu, property_identity with context %}
{% set housebook_csv_params = 'apartment=' ~ (apartment_id or '') %}
{{ page_header(
  t('housebook.title'),
  ''
) }}
'''
HB_HEAD_NEW = '''{% extends "host_page.html" %}
{% set nav = 'housebook' %}
{% set body_kind = 'list' %}
{% from "_components.html" import row_menu_begin, row_menu_end, housebook_csv_menu, property_identity with context %}
{% from "_ui_layout.html" import ui_section_tabs with context %}
{% set housebook_csv_params = 'apartment=' ~ (apartment_id or '') %}
{% block title %}{{ t('housebook.title') }}{% endblock %}
{% block tabs %}{{ ui_section_tabs() }}{% endblock %}
{% block body %}
'''
patch("housebook.html", [
 (HB_HEAD_OLD, HB_HEAD_NEW, 1),
 ('<p class="small" style="margin-top:16px">', '<p class="ui-sub">', 1),
 ('<h2 style="margin-top:0">', '<h2>', 1),
 ('<div class="actions" style="margin-top:14px">', '<div class="ui-form-actions">', 1),
 ('class="btn filter-toggle"', 'class="ui-btn ui-btn-secondary filter-toggle"', 1),
 ('class="btn primary filter-apply"', 'class="ui-btn ui-btn-primary filter-apply"', 1),
 ('class="btn primary"', 'class="ui-btn ui-btn-secondary"', 1),
 ('class="btn small"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 1),
 ('class="btn ghost"', 'class="ui-btn ui-btn-quiet"', 2),
 ('class="btn"', 'class="ui-btn ui-btn-secondary"', 1),
 ('class="pill grey"', pill("grey"), 1), ('class="pill green"', pill("green"), 2), ('class="pill teal"', pill("teal"), 1),
 ('class="pill amber"', pill("amber"), 1), ('class="pill red"', pill("red"), 2),
 ('class="filters panel host-filter-panel"', 'class="filters ui-section host-filter-panel"', 1),
 ('<p class="small muted">', '<p class="ui-sub">', 3),
 ('<div class="small muted">', '<div class="ui-sub">', 1),
 ('class="small muted housebook-pdf-warn"', 'class="ui-sub housebook-pdf-warn"', 1),
 ('<div class="field">', '<div class="ui-field">', 4),
 ('class="grid two"', 'class="ui-pair"', 1),
])
print("ok")
```

3. Compile: `cd App && .venv/bin/python -c "
from app.templating import templates
for n in ('submissions.html','submission_detail.html','housebook.html'): templates.env.get_template(n)
print('compiled')"`. Expected: `compiled`.

4. Catalog. Save as `/tmp/catalog_0138.py` and run from the repo root: `python3 /tmp/catalog_0138.py && python3 scripts/design_lint.py 2>&1 | tail -5`. Expected: `catalog ok`, then `design lint: OK`. The script edits by key name (it works whatever earlier briefs added) and keeps the file's compact layout.

```
import json, pathlib
p = pathlib.Path("docs/design/catalog.json"); text = p.read_text(encoding="utf-8"); c = json.loads(text)
T = "App/app/templates/"
LEGACY = {
 T + "submissions.html": ["nowrap", "row-actions"],
 T + "submission_detail.html": ["code-block", "detail-hero", "detail-metric", "err-text", "eyebrow", "help-dot", "kv", "metric-label", "metric-value", "outcome-", "panel", "report-header-problems", "report-metrics", "report-receipt-missing", "report-stamp", "report-stamp-value", "row-actions", "small-value", "stay-command-actions", "stay-command-main", "stay-command-note", "stay-command-panel", "stay-metrics", "technical", "technical-download", "technical-downloads"],
 T + "housebook.html": ["col-address", "col-born", "col-doc", "col-name", "col-property", "col-purpose", "col-reported", "col-stay", "csv-export-dialog", "empty", "filter-applied-summary", "filter-apply", "filter-fields", "filter-panel-actions", "filter-toggle", "filter-toolbar", "filter-toolbar-actions", "filters", "host-filter-panel", "housebook-pdf-warn", "housebook-scroll", "housebook-table", "mono", "muted", "nowrap", "panel", "row-actions", "scroll-x", "small", "table-cards", "tight"],
}
want = json.loads(text)
for name, tokens in LEGACY.items():
    if name not in want["enforced_templates"]:
        want["enforced_templates"].append(name)
    want["legacy"][name] = tokens
# Keep the file's compact layout: rewrite the enforced_templates line and add one line per legacy entry.
lines = text.split("\n")
i = next(k for k, l in enumerate(lines) if l.lstrip().startswith('"enforced_templates":'))
if lines[i].rstrip().endswith("],"):
    lines[i] = '  "enforced_templates": ' + json.dumps(want["enforced_templates"], ensure_ascii=False) + ","
    j = next(k for k, l in enumerate(lines) if l.strip() == '"legacy": {')
    new = ['    ' + json.dumps(n) + ': ' + json.dumps(t) + ',' for n, t in LEGACY.items() if n not in c["legacy"]]
    lines[j + 1:j + 1] = new
    out = "\n".join(lines)
else:
    out = json.dumps(want, indent=2, ensure_ascii=False) + "\n"
assert json.loads(out) == want, "catalog edit did not produce the intended JSON"
p.write_text(out, encoding="utf-8")
print("catalog ok")
```

5. Test edits. Save as `/tmp/tests_0138.py` and run `cd App && .venv/bin/python /tmp/tests_0138.py`. Expected: `tests ok`.

```
import pathlib
def edit(path, pairs):
    p = pathlib.Path(path); s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, (path, old[:70], s.count(old)); s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")
edit("tests/test_report_detail_next_step.py", [
 ("""    match = re.search(r'<div class="actions">(.*?)</div>', page, re.S)""",
  """    match = re.search(r'<div class="ui-form-actions">(.*?)</div>', page, re.S)"""),
 ("""            f'<a class="btn primary" href="/reservations/{reservation["id"]}#guests">'""",
  """            f'<a class="ui-btn ui-btn-primary" href="/reservations/{reservation["id"]}#guests">'"""),
 ("""        assert actions.count("<a class=\\"btn") == 1""",
  """        assert actions.count("<a class=\\"ui-btn") == 1"""),
])
# The reports list is a v2 stacked table now (cards under 1024 px, like the stays list), not a .list-cards panel.
edit("tests/test_host_list_cards_browser.py", [
 ('    "reports": "/submissions",\n', ''),
 ('"fees": 940, "reports": 850}', '"fees": 940}'),
])
edit("tests/test_host_wide_geometry_browser.py", [
 ('    "submissions": ("/submissions", ".panel.tight.scroll-x, .panel.empty"),',
  '    "submissions": ("/submissions", ".ui-table, .ui-empty"),'),
])
print("tests ok")
```

6. Create `App/tests/test_design_reports.py`:

```python
"""0138: reports list, report detail and house book render on host_page."""
from __future__ import annotations

from pathlib import Path

from tests.test_signed_in_chrome import host_with_property  # noqa: F401

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"


def test_reports_and_housebook_have_the_v2_header_and_tabs(host_with_property):
    for path in ("/submissions?lang=en", "/housebook?lang=en"):
        page = host_with_property.get(path).text
        assert page.count("<h1") == 1 and 'data-body-kind="list"' in page, path
        assert 'class="ui-tabs" data-sub-tabs' in page, path
        assert "page-header" not in page, path


def test_the_house_book_keeps_its_filter_and_export_hooks(host_with_property):
    page = host_with_property.get("/housebook?lang=en").text
    assert 'id="housebook-filter-panel"' in page and "data-filter-toggle" in page
    assert 'class="filters ui-section host-filter-panel"' in page
    assert 'id="housebook-pdf-dialog" class="csv-export-dialog"' in page


def test_no_raw_style_or_legacy_control_in_the_three_templates():
    for name in ("submissions.html", "submission_detail.html", "housebook.html"):
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        assert 'style="' not in text and 'class="btn' not in text and 'class="pill' not in text, name
        assert text.count('class="ui-btn ui-btn-primary') <= 1, name
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_design_reports.py tests/test_report_detail_next_step.py tests/test_report_detail_polish.py tests/test_wp25_reported_bugs.py tests/test_design_lint.py tests/test_skeleton_loaders.py tests/test_host_redesign.py tests/test_zz_review.py -q --tb=short -x 2>&1 | tail -30`. Expected: all passed.

7. Browser tests, 0 skipped. Chromium needs `UBYHOST_BROWSER_EXECUTABLE` (Playwright's own bundle is not installed here). Run the two commands separately (each takes 1 to 3 minutes; give the Bash call a 600000 ms timeout):

   a. `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_host_list_page_layout_browser.py tests/test_host_filter_panels_browser.py tests/test_host_geometry.py tests/test_shell_lane_browser.py tests/test_host_list_cards_browser.py tests/test_download_skeleton_browser.py --deselect tests/test_host_list_page_layout_browser.py::test_list_pages_share_order_edges_and_rhythm -q --tb=short 2>&1 | tail -30`. Expected: passed, 0 skipped. (The deselected rhythm test already fails at c340b7f on the stays and properties pages, which this brief does not touch.)

   b. `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/test_host_wide_geometry_browser.py -q --tb=short 2>&1 | tail -30`. Expected: 6 passed, 0 skipped.

   The orchestrator takes the screenshots; the executor attaches none.

8. Commit (no static file changes in this brief, so no `?v=` bump): `git add App/app/templates/submissions.html App/app/templates/submission_detail.html App/app/templates/housebook.html docs/design/catalog.json App/tests/test_report_detail_next_step.py App/tests/test_host_list_cards_browser.py App/tests/test_host_wide_geometry_browser.py App/tests/test_design_reports.py && git commit -m "0138: reports, report detail and house book on host_page"`.

## 5. Do not touch

Routes, receipt and export code, `_components.html`, `_date_range.html`, `host_page.html`, every file under `App/app/static/`, the house-book filter behaviour and its two tables' structure; hard rules 1, 3, 8.

## 6. Commands

- `python3 scripts/design_lint.py` (repo root) expected: `design lint: OK`.
- Step 6 and step 7 commands: passed, 0 skipped.

## 7. Acceptance

- [ ] Three pages on host_page with one h1 each; reports and register show the section tabs under the title (`test_design_reports.py`).
- [ ] No `style="`, `class="btn` or `class="pill` in the three templates; at most one `ui-btn-primary` per template (lint T4 and `test_design_reports.py`).
- [ ] Lint passes with the three templates enforced.
- [ ] Step 7 browser runs: passed, 0 skipped (no screenshots needed from the executor).

## 8. Stop and ask

Stop, and write the report, if: an assertion in steps 2, 4 or 5 fires; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0138-report.md` (600 tokens at most) and set `Status: review`: files changed (`git diff --stat HEAD~1`), each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/templates/submission_detail.html` (report grammar, receipt links), `App/app/templates/submissions.html` (receipt moved from a row button into the row menu, like the stay detail's report rows).

## Owner steps

None.
