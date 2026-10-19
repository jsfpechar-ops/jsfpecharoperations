# 0138: Reports list, report detail and house book on the v2 template

Status: todo
Depends on: 0137 | Base commit: 79252fd (refreshed 2026-10-19 against 0130-0137 and 0147-0152; every anchor count below was asserted on a scratch copy of this head and the result compiled and tested) | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit each step as `0138 step k`. Never push, never open a PR. Page file: `docs/design/pages/stays.md` (reports and register are the section's tabs).

**How to run this brief.** Every step is one command, run from `App/` (`cd App` first; the scripts use paths relative to `App/`). Each script asserts the count of every anchor before it writes anything and prints `ok` at the end; if it prints an `AssertionError` tuple instead (the anchor text and the count it found), nothing was written: stop and put the tuple in the report. Do not retype the scripts and do not edit the files by hand. Known-failing tests are named per step; a failure not named there is yours to report, not to fix by weakening the test.

## 1. Objective

Move `submissions.html` (list), `submission_detail.html` (detail) and `housebook.html` (list) onto `host_page.html` with v2 header, tabs, controls, badges and tables, one DOM per list (MASTER 7.4) with `data-card` roles (MASTER 7.3). Receipts, the report grammar (`#now` command panel, technical fold), the house-book filter form (its JS hooks) and the CSV and PDF exports do not change.

## 2. Context

Rules: MASTER 4 (controls 40 px at 1024 and above, 44 below), 5, 7.3, 7.4, 7.5, `docs/design/pages/stays.md` (`date_short` for list date columns). Tests read `class="panel stay-command-panel outcome-*"` and `<details class="panel technical">` on the report detail (`test_wp25_reported_bugs.py`, `test_report_detail_polish.py`): those two class strings stay. Settled since the first version of this brief:

- `.ui-form-actions` is `display: none` below 1024 px (the sticky-bar pattern), so a plain action row becomes `ui-btn-group`, never `ui-form-actions`.
- `.panel` to `ui-section` loses the box; where the page needs a boxed look (the empty state, the PDF dialog) it is `ui-section ui-card` (0135 fix 1).
- `.ui-sub` is `display: block`: it goes on `<p>`/`<span>` copy, never on a `<td>`. Table cells carry `ui-mono`, `ui-num`, `ui-cell-r`, `ui-cell-first`, `ui-cell-acts` instead.
- Phone card roles: property or guest is `primary`, dates `secondary`, counts and small facts `meta` (the badge sits under the primary line per the 0151 MASTER edit), status `badge`, the actions cell `actions`, register columns that only fit a desktop (`nationality`, `document`, `residence`, `purpose`, `signed`) `hide` (they stay in the desktop table, the CSV and the PDF).
- The receipts download was a header secondary action; `.ui-ph-acts` secondaries are hidden on phones, so it is a neutral `ui_banner` with the hint as its text (the old header button and the hint paragraph go).
- `host2.css` gets two small rules (script 2): `td[data-card="meta"] ~ td[data-card="meta"]` (the `+` sibling rule missed a meta cell that follows a hidden one) and `.ui-field .err/.hint` (the legacy rule lives under `.field` in app.css).
- `test_host_list_cards_browser.py` keeps its assertion but learns v2 lists (phone cards below 1024 px, roles instead of `::before` labels); `test_host_filter_panels_browser.py` measures `.ui-btn` as well as `.btn`; `test_zz_review.py` and the wide-lane capture read the v2 badge and wrappers.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/submissions.html` | edit | head (script 1), cells and badges (script 2) |
| `App/app/templates/submission_detail.html` | edit | head, CTA variable, cells, banner, action rows |
| `App/app/templates/housebook.html` | edit | head, filter controls, cells, dialog |
| `App/app/static/host2.css` | edit | meta sibling rule; `.ui-field .err/.hint` (script 2) |
| `docs/design/catalog.json` | edit | enforce the three templates; legacy lists (script 3) |
| `App/tests/test_report_detail_next_step.py` | edit | v2 action row and link class (script 4) |
| `App/tests/test_wp25_reported_bugs.py` | edit | v2 table, wrapper and reported-column strings |
| `App/tests/test_host_list_cards_browser.py` | edit | v2-aware card expectation |
| `App/tests/test_host_filter_panels_browser.py` | edit | `.ui-btn` in the clipped-text selector |
| `App/tests/test_zz_review.py` | edit | v2 green badge string |
| `App/tests/test_host_wide_geometry_browser.py` | edit | result-lane selectors of `/submissions` and `/housebook` |
| `App/tests/test_design_reports.py` | create | header, tabs, roles, no legacy control |

No other file may change.

## 4. Steps

1. Heads (the three templates extend `host_page.html`; the blocks `title`, `meta`, `back_url`, `back_label`, `tabs`, `body`; the receipts banner):

```
.venv/bin/python - <<'EOF'
import pathlib
def patch(path, pairs):
    p = pathlib.Path(path); s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, (path, old[:70], s.count(old)); s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")
patch("app/templates/submissions.html", [("""{% extends "base.html" %}
{% set nav = 'submissions' %}
{% block title %}{{ t('reports.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import row_menu_begin, row_menu_end, page_header, submission_pill, empty_state, property_identity with context %}
{% set header_actions %}
  {% if receipt_count %}
    <a class="btn" href="/submissions/receipts.zip">{{ t('reports.download_receipts') }}</a>
  {% endif %}
{% endset %}
{{ page_header(
  t('reports.title'),
  t('reports.lede'),
  actions=header_actions if receipt_count else ''
) }}
{% if receipt_count %}
  <p class="small muted">{{ t('reports.download_receipts_hint') }}</p>
{% endif %}
""", """{% extends "host_page.html" %}
{% set nav = 'submissions' %}
{% set body_kind = 'list' %}
{% from "_components.html" import row_menu_begin, row_menu_end, submission_pill, empty_state, property_identity with context %}
{% from "_ui_layout.html" import ui_section_tabs with context %}
{% block title %}{{ t('reports.title') }}{% endblock %}
{% block meta %}{{ t('reports.lede') }}{% endblock %}
{% block tabs %}{{ ui_section_tabs() }}{% endblock %}
{% block body %}
{# 0138: the receipts download and its hint are one neutral banner with one secondary action
   (rule 9, one explanation in one place); a header secondary would be hidden on phone. #}
{% if receipt_count %}{{ ui_banner('neutral', t('reports.download_receipts_hint'), t('reports.download_receipts'), '/submissions/receipts.zip') }}{% endif %}
""")])
patch("app/templates/submission_detail.html", [("""{% extends "base.html" %}
{% set nav = 'submissions' %}
{% block title %}{{ t('reports.detail.title', id=submission.id) }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header, submission_pill, row_menu_begin, row_menu_end, copy_button with context %}
""", """{% extends "host_page.html" %}
{% set nav = 'submissions' %}
{% set body_kind = 'detail' %}
{% from "_components.html" import submission_pill, row_menu_begin, row_menu_end, copy_button with context %}
{# The next step is the page's one coral button; the two branches below are exclusive. #}
{% set cta = 'ui-btn ui-btn-primary' %}
{% block title %}{{ t('reports.detail.title', id=submission.id) }}{% endblock %}
"""), ("""{{ page_header(
  t('reports.detail.title', id=submission.id),
  submission.internal_name ~ ' · ' ~ report_mode_label(submission.mode),
  '/submissions',
  t('reports.detail.back')
) }}
""", """{% block meta %}{{ submission.internal_name ~ ' · ' ~ report_mode_label(submission.mode) }}{% endblock %}
{% block back_url %}/submissions{% endblock %}
{% block back_label %}{{ t('reports.detail.back') }}{% endblock %}
{% block body %}
""")])
patch("app/templates/housebook.html", [("""{% extends "base.html" %}
{% set nav = 'housebook' %}
{% block title %}{{ t('housebook.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header, row_menu_begin, row_menu_end, housebook_csv_menu, property_identity with context %}
{% set housebook_csv_params = 'apartment=' ~ (apartment_id or '') %}
{{ page_header(
  t('housebook.title'),
  ''
) }}
""", """{% extends "host_page.html" %}
{% set nav = 'housebook' %}
{% set body_kind = 'list' %}
{% from "_components.html" import row_menu_begin, row_menu_end, housebook_csv_menu, property_identity with context %}
{% from "_ui_layout.html" import ui_section_tabs with context %}
{% set housebook_csv_params = 'apartment=' ~ (apartment_id or '') %}
{% block title %}{{ t('housebook.title') }}{% endblock %}
{% block tabs %}{{ ui_section_tabs() }}{% endblock %}
{% block body %}
""")])
print("ok")
EOF
```

   Expected: `ok`. Then `.venv/bin/python -c "from app.templating import templates; templates.env.get_template('submissions.html'); templates.env.get_template('submission_detail.html'); templates.env.get_template('housebook.html'); print('compiled')"`. Expected: `compiled`. Commit `0138 step 1`.

2. Cells, badges, controls, the two `host2.css` rules:

```
.venv/bin/python - <<'EOF'
import pathlib
def patch(name, pairs, forbid=('style="', 'class="btn', 'class="pill', 'class="small', 'class="mono', 'class="num"', 'class="actions"')):
    p = pathlib.Path("app/templates/" + name); s = p.read_text(encoding="utf-8")
    for old, new, n in pairs:
        assert s.count(old) == n, (name, old[:70], s.count(old)); s = s.replace(old, new)
    for f in forbid:
        assert f not in s, (name, f)
    p.write_text(s, encoding="utf-8")
B = {"grey": ("neutral", "grey"), "green": ("done", "green"), "teal": ("neutral", "teal"),
     "amber": ("action", "amber"), "red": ("action", "red")}
def pill(tone): return f'class="ui-badge ui-badge-{B[tone][0]}" data-tone="{B[tone][1]}"'
CPT = 'class="ui-btn ui-btn-secondary ui-btn-compact"'
SEC = 'class="ui-btn ui-btn-secondary"'
QUIET = 'class="ui-btn ui-btn-quiet"'
ACTS = '<td class="ui-cell-acts row-actions" data-card="actions" data-label="">'
patch("submissions.html", [
 ('<div class="panel tight scroll-x list-cards lc-reports">', '<div class="list-cards lc-reports">', 1),
 ('<table class="table-cards">', '<table class="ui-table ui-table-stack">', 1),
 ("<th>{{ t('reports.guests') }}</th>", "<th class=\"ui-cell-r\">{{ t('reports.guests') }}</th>", 1),
 ("<td class=\"nowrap small\" data-label=\"{{ t('reports.when') }}\">", "<td class=\"nowrap\" data-card=\"secondary\" data-label=\"{{ t('reports.when') }}\">", 1),
 ("<td data-label=\"{{ t('reports.property') }}\">", "<td class=\"ui-cell-first\" data-card=\"primary\" data-label=\"{{ t('reports.property') }}\">", 1),
 ("<td class=\"small\" data-label=\"{{ t('reports.mode') }}\">", "<td data-card=\"meta\" data-label=\"{{ t('reports.mode') }}\">", 1),
 ("<td class=\"num\" data-label=\"{{ t('reports.guests') }}\">", "<td class=\"ui-num ui-cell-r\" data-card=\"meta\" data-label=\"{{ t('reports.guests') }}\">", 1),
 ("<td data-label=\"{{ t('reports.outcome') }}\">", "<td data-card=\"badge\" data-label=\"{{ t('reports.outcome') }}\">", 1),
 ("<td class=\"mono small\" data-label=\"{{ t('reports.stamp') }}\">", "<td class=\"ui-mono\" data-card=\"hide\" data-label=\"{{ t('reports.stamp') }}\">", 1),
 ('<td class="nowrap row-actions" data-label="">', ACTS, 1),
 ('<a class="btn small primary" href="/submissions/{{ submission.id }}/receipt.pdf">{{ t(\'reports.receipt\') }}</a>',
  '<span class="row-action-form"><a ' + CPT + ' href="/submissions/{{ submission.id }}/receipt.pdf">{{ t(\'reports.receipt\') }}</a></span>', 1),
])
patch("submission_detail.html", [
 ('<p class="small muted report-receipt-missing" data-receipt-missing>', '<p class="ui-sub report-receipt-missing" data-receipt-missing>', 1),
 ('<div class="actions">', '<div class="ui-btn-group">', 1),
 ('class="btn primary"', 'class="{{ cta }}"', 2),
 ('class="btn"', SEC, 1),
 ('<div class="banner err" style="margin:0; border-radius:0; border-left:0; border-right:0">', '<div class="ui-banner ui-banner-attention">', 1),
 ('<ul class="small">', '<ul class="ui-sub">', 1),
 ('<p class="small muted">', '<p class="ui-sub">', 2),
 ('<span class="mono report-stamp"', '<span class="ui-mono report-stamp"', 1),
 ('<div class="panel tight scroll-x">', '<div class="ui-section scroll-x">', 1),
 ('<table class="table-cards">', '<table class="ui-table ui-table-stack">', 1),
 ('<td class="num" data-label="#">', '<td class="ui-num" data-card="hide" data-label="#">', 1),
 ("<td data-label=\"{{ t('reports.detail.guest') }}\">", "<td class=\"ui-cell-first\" data-card=\"primary\" data-label=\"{{ t('reports.detail.guest') }}\">", 1),
 ("<td data-label=\"{{ t('reports.detail.result') }}\">", "<td data-card=\"badge\" data-label=\"{{ t('reports.detail.result') }}\">", 1),
 ('<td class="nowrap row-actions" data-label="">', ACTS, 1),
 ('<td colspan="4" class="small muted">', '<td colspan="4">', 1),
 ('<div class="small muted">', '<div class="ui-sub">', 3),
 ('<div class="small err-text">', '<div class="ui-sub err-text">', 1),
 ('class="pill amber"', pill("amber"), 2), ('class="pill green"', pill("green"), 1),
 ('class="pill red"', pill("red"), 2), ('class="pill grey"', pill("grey"), 1),
 ('<dd class="mono small">', '<dd class="ui-mono">', 1),
 ('class="btn small"', CPT, 2),
 ('<pre class="mono small code-block">', '<pre class="ui-mono code-block">', 1),
])
patch("housebook.html", [
 ('class="btn filter-toggle"', 'class="ui-btn ui-btn-secondary filter-toggle"', 1),
 ('<div class="field">', '<div class="ui-field">', 4),
 ('class="btn primary filter-apply"', 'class="ui-btn ui-btn-primary filter-apply"', 1),
 ('class="btn ghost"', QUIET, 2),
 ('class="filters panel host-filter-panel"', 'class="filters ui-section host-filter-panel"', 1),
 ('<div class="panel tight scroll-x housebook-scroll"', '<div class="ui-section scroll-x housebook-scroll"', 1),
 ('<table class="table-cards housebook-table">', '<table class="ui-table ui-table-stack housebook-table">', 1),
 # register rows: MASTER 7.3 roles; the phone card shows guest, stay dates, property, birth date and the report badge
 ("<td class=\"nowrap small\" data-label=\"{{ t('housebook.stay') }}\">{{ row.stay_from | date_cz }}<br>{{ row.stay_to | date_cz }}</td>",
  "<td class=\"nowrap\" data-card=\"secondary\" data-label=\"{{ t('housebook.stay') }}\">{{ row.stay_from | date_short }} – {{ row.stay_to | date_short }}</td>", 2),
 ("<td class=\"small col-property\" data-label=\"{{ t('housebook.apartment') }}\">", "<td class=\"col-property\" data-card=\"meta\" data-label=\"{{ t('housebook.apartment') }}\">", 1),
 ("<td class=\"col-name\" data-label=\"{{ t('housebook.guest') }}\"><strong>{{ row.surname }}</strong><br>", "<td class=\"ui-cell-first col-name\" data-card=\"primary\" data-label=\"{{ t('housebook.guest') }}\"><strong>{{ row.surname }}</strong><br>", 1),
 ('<span class="small">{{ row.first_name }}</span>', '<span class="ui-sub">{{ row.first_name }}</span>', 1),
 ("<td class=\"nowrap small\" data-label=\"{{ t('housebook.born') }}\">", "<td class=\"nowrap\" data-card=\"meta\" data-label=\"{{ t('housebook.born') }}\">", 1),
 ("<td class=\"small\" data-label=\"{{ t('housebook.nationality') }}\">", "<td data-card=\"hide\" data-label=\"{{ t('housebook.nationality') }}\">", 1),
 ("<td class=\"mono small\" data-label=\"{{ t('housebook.document') }}\">", "<td class=\"ui-mono\" data-card=\"hide\" data-label=\"{{ t('housebook.document') }}\">", 1),
 ("<td class=\"small col-address\" data-label=\"{{ t('housebook.residence') }}\">", "<td class=\"col-address\" data-card=\"hide\" data-label=\"{{ t('housebook.residence') }}\">", 1),
 ("<td class=\"small col-purpose\" data-label=\"{{ t('housebook.purpose') }}\">", "<td class=\"col-purpose\" data-card=\"hide\" data-label=\"{{ t('housebook.purpose') }}\">", 1),
 ("<td class=\"small nowrap\" data-label=\"{{ t('housebook.signed') }}\">", "<td class=\"nowrap\" data-card=\"hide\" data-label=\"{{ t('housebook.signed') }}\">", 1),
 ("<td class=\"small col-reported\" data-label=\"{{ t('housebook.reported') }}\">", "<td class=\"col-reported\" data-card=\"badge\" data-label=\"{{ t('housebook.reported') }}\">", 1),
 ('<div class="small muted">{{ row.reported_at[:10] }}</div>', '<div class="ui-sub">{{ row.reported_at[:10] }}</div>', 1),
 ('<td class="nowrap row-actions" data-label="">', ACTS, 1),
 ('class="pill grey"', pill("grey"), 1), ('class="pill green"', pill("green"), 2), ('class="pill teal"', pill("teal"), 1),
 ('class="pill amber"', pill("amber"), 1), ('class="pill red"', pill("red"), 2),
 ('<p class="small muted">', '<p class="ui-sub">', 3),
 ('<div class="panel empty">', '<div class="ui-section ui-card empty">', 1),
 # archived rows
 ('<div class="panel tight scroll-x">', '<div class="ui-section scroll-x">', 1),
 ('<table class="table-cards">', '<table class="ui-table ui-table-stack">', 1),
 ("<td data-label=\"{{ t('housebook.apartment') }}\">", "<td data-card=\"meta\" data-label=\"{{ t('housebook.apartment') }}\">", 1),
 ("<td data-label=\"{{ t('housebook.guest') }}\">", "<td class=\"ui-cell-first\" data-card=\"primary\" data-label=\"{{ t('housebook.guest') }}\">", 1),
 ("<td class=\"small muted\" data-label=\"{{ t('housebook.archived') }}\">", "<td data-card=\"meta\" data-label=\"{{ t('housebook.archived') }}\">", 1),
 ('<td class="nowrap" data-label="">', ACTS, 1),
 ('<form method="post" action="/guests/{{ row._guest_id }}/unarchive" class="inline">', '<form method="post" action="/guests/{{ row._guest_id }}/unarchive" class="inline row-action-form">', 1),
 ('<button class="btn small" type="submit">{{ t(\'common.restore\') }}</button>', '<button ' + CPT + ' type="submit">{{ t(\'common.restore\') }}</button>', 1),
 ('<p class="small" style="margin-top:16px">', '<p class="ui-sub">', 1),
 # PDF export dialog
 ('<h2 style="margin-top:0">', '<h2>', 1),
 ('<p class="small muted housebook-pdf-warn">', '<p class="ui-sub housebook-pdf-warn">', 1),
 ('<div class="grid two">', '<div class="ui-pair">', 1),
 ('<div class="actions" style="margin-top:14px">', '<div class="ui-btn-group">', 1),
 ('<button class="btn" type="button" data-housebook-pdf-cancel>', '<button ' + SEC + ' type="button" data-housebook-pdf-cancel>', 1),
 ('<button class="btn primary" type="submit">{{ t(\'data.export_csv_download\') }}</button>', '<button ' + SEC + ' type="submit">{{ t(\'data.export_csv_download\') }}</button>', 1),
])
# host2.css: the second phone meta may follow the first after a hidden cell (general sibling), and the
# inline field messages keep their colour under ui-field (app.css styles .err/.hint under .field only).
p = pathlib.Path("app/static/host2.css"); s = p.read_text(encoding="utf-8")
old = '.host-workspace .ui-table td[data-card="meta"] + td[data-card="meta"] { grid-column: 2; justify-self: end; }'
assert s.count(old) == 1, s.count(old)
s = s.replace(old, old.replace(" + td", " ~ td"))
assert "0138: field messages" not in s
s = s.rstrip("\n") + """

/* 0138: field messages under ui-field (the legacy rule lives under .field in app.css) */
.host-workspace .ui-field .err { font-size: var(--size-13); color: var(--danger); font-weight: 550; }
.host-workspace .ui-field .hint { font-size: var(--size-13); color: var(--ink-3); }
"""
p.write_text(s, encoding="utf-8")
print("ok")
EOF
```

   Expected: `ok`. Commit `0138 step 2`.

3. Catalog (enforce the three templates; their legacy tokens were collected with the lint on this head):

```
.venv/bin/python - <<'EOF'
import json, pathlib
p = pathlib.Path("../docs/design/catalog.json"); s = p.read_text(encoding="utf-8")
LEGACY = {
 "submissions.html": ["lc-reports", "list-cards", "nowrap", "row-actions"],
 "submission_detail.html": ["code-block", "detail-hero", "detail-metric", "err-text", "eyebrow", "help-dot", "kv", "metric-label", "metric-value", "outcome-", "panel", "report-header-problems", "report-metrics", "report-receipt-missing", "report-stamp", "report-stamp-value", "row-actions", "scroll-x", "small-value", "stay-command-actions", "stay-command-main", "stay-command-note", "stay-command-panel", "stay-metrics", "technical", "technical-download", "technical-downloads"],
 "housebook.html": ["col-address", "col-born", "col-doc", "col-name", "col-property", "col-purpose", "col-reported", "col-stay", "csv-export-dialog", "empty", "filter-applied-summary", "filter-apply", "filter-fields", "filter-panel-actions", "filter-toggle", "filter-toolbar", "filter-toolbar-actions", "filters", "host-filter-panel", "housebook-pdf-warn", "housebook-scroll", "housebook-table", "nowrap", "row-actions", "scroll-x"],
}
old = '"App/app/templates/reservation_detail.html"],\n  "legacy": {\n'
assert s.count(old) == 1, s.count(old)
new = ('"App/app/templates/reservation_detail.html", ' + ", ".join(f'"App/app/templates/{n}"' for n in LEGACY) + '],\n  "legacy": {\n'
       + "".join(f'    "App/app/templates/{n}": {json.dumps(t)},\n' for n, t in LEGACY.items()))
s = s.replace(old, new); json.loads(s); p.write_text(s, encoding="utf-8"); print("ok")
EOF
```

   Expected: `ok`. Then `cd .. && python3 scripts/design_lint.py && cd App`. Expected: `design lint: OK`. Commit `0138 step 3`.

4. Tests:

```
.venv/bin/python - <<'EOF'
import pathlib
def patch(path, pairs):
    p = pathlib.Path(path); s = p.read_text(encoding="utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, (path, old[:70], s.count(old)); s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")
patch("tests/test_report_detail_next_step.py", [
 ("""    match = re.search(r'<div class="actions">(.*?)</div>', page, re.S)""", """    match = re.search(r'<div class="ui-btn-group">(.*?)</div>', page, re.S)"""),
 ("""            f'<a class="btn primary" href="/reservations/{reservation["id"]}#guests">'""", """            f'<a class="ui-btn ui-btn-primary" href="/reservations/{reservation["id"]}#guests">'"""),
 ("""        assert actions.count("<a class=\\"btn") == 1""", """        assert actions.count("<a class=\\"ui-btn") == 1"""),
])
patch("tests/test_wp25_reported_bugs.py", [
 ("""    assert 'class="table-cards housebook-table"' in page""", """    assert 'class="ui-table ui-table-stack housebook-table"' in page"""),
 ("""    assert 'class="panel tight scroll-x housebook-scroll"' in page""", """    assert 'class="ui-section scroll-x housebook-scroll"' in page"""),
 ("""    assert 'class="small col-reported"' in page""", """    assert 'class="col-reported" data-card="badge"' in page"""),
])
# 0084 list-cards test, moved to v2 where a list is on host_page (MASTER 7.4: cards below 1024, one DOM with
# data-card roles instead of ::before labels); legacy lists keep the 0084 rules until their brief lands.
patch("tests/test_host_list_cards_browser.py", [
 ("""  const acts = [...panel.querySelectorAll('tbody td.row-actions a.btn, tbody td.row-actions .row-menu-trigger')]""",
  """  const acts = [...panel.querySelectorAll('tbody td.row-actions a.btn, tbody td.row-actions .ui-btn, tbody td.row-actions .row-menu-trigger')]"""),
 ("""          panelWidth: Math.round(pr.width), cards, acts, labels, rows: panel.querySelectorAll('tbody tr').length};""",
  """          panelWidth: Math.round(pr.width), cards, acts, labels, rows: panel.querySelectorAll('tbody tr').length,
          v2: !!panel.querySelector('.ui-table'), roles: panel.querySelectorAll('tbody tr:first-child td[data-card="primary"]').length};"""),
 ("""                if result["cards"] != (result["panelWidth"] < THRESHOLDS[name]):
                    failures.append((label, "layout does not follow the panel width", result["panelWidth"], result["cards"]))""",
  """                # v2 lists (MASTER 7.4) switch at the 1024 px viewport; legacy lists at their panel threshold.
                expected_cards = width < 1024 if result["v2"] else result["panelWidth"] < THRESHOLDS[name]
                if result["cards"] != expected_cards:
                    failures.append((label, "layout does not follow the panel width", result["panelWidth"], result["cards"]))"""),
 ("""                    if not any(text not in ('none', 'normal', '""') for text in result["labels"]):
                        failures.append((label, "cards without labels", result["labels"]))""",
  """                    # v2 cards name their cells through data-card roles (one DOM); legacy cards through ::before labels.
                    if not result["roles"] and not any(text not in ('none', 'normal', '""') for text in result["labels"]):
                        failures.append((label, "cards without labels", result["labels"]))"""),
])
patch("tests/test_host_filter_panels_browser.py", [
 ("""                            clipped: [...document.querySelectorAll('[data-filter-toolbar] .btn')].some((button) => button.scrollWidth > button.clientWidth + 1),""",
  """                            clipped: [...document.querySelectorAll('[data-filter-toolbar] .btn, [data-filter-toolbar] .ui-btn')].some((button) => button.scrollWidth > button.clientWidth + 1),"""),
])
pathlib.Path("tests/test_design_reports.py").write_text('''"""0138: reports list, report detail and house book render on host_page."""
from __future__ import annotations

from pathlib import Path

from tests.test_signed_in_chrome import host_with_property  # noqa: F401

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"


def test_reports_and_housebook_have_the_v2_header_and_tabs(host_with_property):
    for path in ("/submissions?lang=en", "/housebook?lang=en"):
        page = host_with_property.get(path).text
        assert page.count("<h1") == 1 and 'data-body-kind="list"' in page, path
        assert 'class="ui-tabs" data-sub-tabs' in page, path
        assert 'class="page-header' not in page and 'class="sub-tabs' not in page, path


def test_no_raw_style_or_legacy_control_in_the_three_templates():
    for name in ("submissions.html", "submission_detail.html", "housebook.html"):
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        assert 'style="' not in text and 'class="btn' not in text and 'class="pill' not in text, name
        assert text.count("ui-btn-primary") <= 1, name
        # one DOM per list: the rows carry MASTER 7.3 roles instead of a second phone markup
        assert 'data-card="primary"' in text and 'data-card="actions"' in text, name
''', encoding="utf-8")
patch("tests/test_zz_review.py", [
 ('        refused_row = "pill green" in page', '        refused_row = \'ui-badge-done" data-tone="green"\' in page'),
])
# wide lanes: the result lane of the two lists is the v2 list wrapper (or the v2 empty state)
patch("tests/test_host_wide_geometry_browser.py", [
 ('    "housebook": ("/housebook?apartment={unconfigured_apartment}&from={today}&to={housebook_end}", ".housebook-page, .panel"),',
  '    "housebook": ("/housebook?apartment={unconfigured_apartment}&from={today}&to={housebook_end}", ".housebook-scroll, .ui-card.empty"),'),
 ('    "submissions": ("/submissions", ".panel.tight.scroll-x, .panel.empty"),', '    "submissions": ("/submissions", ".lc-reports, .ui-empty"),'),
])
print("ok")
EOF
```

   Expected: `ok`. Then `.venv/bin/python -m pytest tests/test_design_reports.py tests/test_report_detail_next_step.py tests/test_report_detail_polish.py tests/test_wp25_reported_bugs.py tests/test_submission_*.py tests/test_report_*.py tests/test_zz_review.py tests/test_design_lint.py -q --tb=short 2>&1 | tail -30`. Expected: all passed. Commit `0138 step 4`.

5. Browser: `UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_host_list_cards_browser.py tests/test_host_filter_panels_browser.py tests/test_host_geometry.py tests/test_host_wide_geometry_browser.py -q --tb=short 2>&1 | tail -30`. Expected: passed, 0 skipped (`test_host_geometry.py` still expects the legacy 42 px month stepper here; it moves to 40 px in 0141).

6. Screenshots (390 and 1280 of each changed page, from `App/`): `UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers SHOT_TASK=0138 SHOT_PAGES="reports housebook report-detail" .venv/bin/python -m pytest -p tests.conftest /tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shoot_pages.py -q -s 2>&1 | tail -8`. Files land in `/tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0138/`. The fixture seeds no submission, so `report-detail` prints "nothing to show"; if it does, rerun with `SHOT_PAGES="reports housebook"` and say in the report that the detail was not captured. Name the files in the report. Then `git status --short | head -20`: the only changes must be the files in section 3. If a tracked evidence folder changed (for example `docs/tasks/0087-evidence/`), `git checkout -- <that folder>` before committing.

7. Commit: `git add App/app/templates/submissions.html App/app/templates/submission_detail.html App/app/templates/housebook.html App/app/static/host2.css docs/design/catalog.json App/tests && git commit -m "0138 step 7: reports, report detail and house book on host_page"`.

## 5. Do not touch

Routes, receipt and export code, `_components.html`, `_date_range.html`, the house-book filter behaviour (`data-filter-*` hooks); hard rules 1, 3, 8.

## 6. Commands

- `python3 scripts/design_lint.py` (repo root) expected: OK.
- Step 4 and step 5 commands, 0 skipped.

## 7. Acceptance

- [ ] Three pages on host_page with one h1 each; reports and register tabs under the title; badges, controls and tables in v2 classes; one DOM per list with roles.
- [ ] Screenshots attached (390 and 1280 for the two lists; the detail if the fixture allowed it).
- [ ] Lint passes with the three templates enforced.

## 8. Stop and ask

Stop, and write the report, if: a script prints an `AssertionError` instead of `ok`; a test not named as known-failing fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0138-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, the known failures seen (one line each, with the message), deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/templates/submission_detail.html` (report grammar, receipt links); `App/app/templates/housebook.html` (register columns hidden on phone cards: nationality, document, residence, purpose, signed).

## Owner steps

None.
