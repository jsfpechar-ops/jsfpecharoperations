# 0138: Reports list, report detail and house book on the v2 template

Status: todo
Depends on: 0137 | Base commit: df8b842 | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit each step as `0138 step k`. Never push, never open a PR. Page file: `docs/design/pages/stays.md` (reports and register are the section's tabs).

## 1. Objective

Move `submissions.html` (list), `submission_detail.html` (detail) and `housebook.html` (list) onto `host_page.html` with v2 controls, badges and tables. Receipts, the report grammar (`#now` command panel, technical fold), the house-book filter form and the CSV and PDF exports do not change. The house-book toolbar keeps its own markup (JS hooks) and goes on the legacy list.

## 2. Context

Rules: MASTER 5, 7.4, 7.5, 4. Tests read `class="panel stay-command-panel outcome-*"` and `<details class="panel technical">` on the report detail (`test_wp25_reported_bugs.py`, `test_report_detail_polish.py`), so those two class strings stay. The report detail's two coral links sit in exclusive branches, so their class is a variable (`cta`), as on the stay detail.

Anchor A, `App/app/templates/submissions.html` lines 1 to 15 (from `{% extends "base.html" %}` to the `) }}` that closes `page_header(`). Anchor B, `App/app/templates/submission_detail.html` lines 1 to 5:

```
{% extends "base.html" %}
{% set nav = 'submissions' %}
{% block title %}{{ t('reports.detail.title', id=submission.id) }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header, submission_pill, row_menu_begin, row_menu_end, copy_button with context %}
```

Anchor C, same file, lines 20 to 25:

```
{{ page_header(
  t('reports.detail.title', id=submission.id),
  submission.internal_name ~ ' · ' ~ report_mode_label(submission.mode),
  '/submissions',
  t('reports.detail.back')
) }}
```

Anchor D, `App/app/templates/housebook.html` lines 1 to 10 (from `{% extends "base.html" %}` to the `) }}` after `page_header(`).

Anchor E, `App/tests/test_report_detail_next_step.py`: line 77 `    match = re.search(r'<div class="actions">(.*?)</div>', page, re.S)`, line 113 `            f'<a class="btn primary" href="/reservations/{reservation["id"]}#guests">'`, line 116 `        assert actions.count("<a class=\"btn") == 1`. Anchor F, `App/tests/test_wp25_reported_bugs.py` lines 349 and 350: `    assert 'class="table-cards housebook-table"' in page` and `    assert 'class="panel tight scroll-x housebook-scroll"' in page`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/submissions.html` | edit | head, classes |
| `App/app/templates/submission_detail.html` | edit | head, CTA variable, classes, banner style |
| `App/app/templates/housebook.html` | edit | head, classes, three style attributes |
| `docs/design/catalog.json` | edit | enforce the three templates; legacy lists |
| `App/tests/test_report_detail_next_step.py` | edit | Anchor E |
| `App/tests/test_wp25_reported_bugs.py` | edit | Anchor F |
| `App/tests/test_design_reports.py` | create | slots and hooks |

No other file may change.

## 4. Steps

1. Replace Anchor A with:

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
```

   Replace Anchor B with:

```
{% extends "host_page.html" %}
{% set nav = 'submissions' %}
{% set body_kind = 'detail' %}
{% from "_components.html" import submission_pill, row_menu_begin, row_menu_end, copy_button with context %}
{% set cta = 'ui-btn ui-btn-primary' %}
{% block title %}{{ t('reports.detail.title', id=submission.id) }}{% endblock %}
```

   Replace Anchor C with:

```
{% block meta %}{{ submission.internal_name ~ ' · ' ~ report_mode_label(submission.mode) }}{% endblock %}
{% block back_url %}/submissions{% endblock %}
{% block back_label %}{{ t('reports.detail.back') }}{% endblock %}
{% block body %}
```

   Replace Anchor D with:

```
{% extends "host_page.html" %}
{% set nav = 'housebook' %}
{% set body_kind = 'list' %}
{% from "_components.html" import row_menu_begin, row_menu_end, housebook_csv_menu, property_identity with context %}
{% from "_ui_layout.html" import ui_section_tabs with context %}
{% set housebook_csv_params = 'apartment=' ~ (apartment_id or '') %}
{% block title %}{{ t('housebook.title') }}{% endblock %}
{% block tabs %}{{ ui_section_tabs() }}{% endblock %}
{% block body %}
```

   Command: `cd App && .venv/bin/python -c "
from app.templating import templates
for n in ('submissions.html','submission_detail.html','housebook.html'): templates.env.get_template(n)
print('compiled')"`. Expected: `compiled`.

2. Mechanical replacements, from `App/`:

```
.venv/bin/python - <<'EOF'
import pathlib
def patch(name, pairs, forbid=('style="', 'class="btn', 'class="pill')):
    p = pathlib.Path("app/templates/" + name); s = p.read_text(encoding="utf-8")
    for old, new, n in pairs:
        assert s.count(old) == n, (name, old[:60], s.count(old)); s = s.replace(old, new)
    for f in forbid:
        assert f not in s, (name, f)
    p.write_text(s, encoding="utf-8")
B = {"grey": ("neutral", "grey"), "green": ("done", "green"), "teal": ("neutral", "teal"),
     "amber": ("action", "amber"), "red": ("action", "red"), "blue": ("action", "blue")}
def pill(tone): return f'class="ui-badge ui-badge-{B[tone][0]}" data-tone="{B[tone][1]}"'
patch("submissions.html", [
 ('class="btn small primary"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 1),
 ('class="panel tight scroll-x list-cards lc-reports"', 'class="list-cards lc-reports"', 1),
 ('class="table-cards"', 'class="ui-table ui-table-stack"', 1),
 ('class="small muted"', 'class="ui-sub"', 1),
 ('class="mono small"', 'class="ui-mono ui-sub"', 1),
 ('class="nowrap small"', 'class="nowrap ui-sub"', 1),
 ('class="small"', 'class="ui-sub"', 1),
 ('class="num"', 'class="ui-num"', 1),
])
patch("submission_detail.html", [
 ('class="btn primary"', 'class="{{ cta }}"', 2),
 ('class="btn small"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 2),
 ('class="btn"', 'class="ui-btn ui-btn-secondary"', 1),
 ('class="pill grey"', pill("grey"), 1), ('class="pill green"', pill("green"), 1),
 ('class="pill amber"', pill("amber"), 2), ('class="pill red"', pill("red"), 2),
 ('class="table-cards"', 'class="ui-table ui-table-stack"', 1),
 ('class="panel tight scroll-x"', 'class="ui-section scroll-x"', 1),
 ('class="small muted"', 'class="ui-sub"', 6),
 ('class="actions"', 'class="ui-form-actions"', 1),
 ('<div class="banner err" style="margin:0; border-radius:0; border-left:0; border-right:0">', '<div class="ui-banner ui-banner-attention">', 1),
 ('class="mono small"', 'class="ui-mono ui-sub"', 1),
 ('class="small"', 'class="ui-sub"', 1),
 ('class="num"', 'class="ui-num"', 1),
])
patch("housebook.html", [
 ('<p class="small" style="margin-top:16px">', '<p class="ui-sub">', 1),
 ('<h2 style="margin-top:0">', '<h2>', 1),
 ('<div class="actions" style="margin-top:14px">', '<div class="ui-form-actions">', 1),
 ('class="btn primary filter-apply"', 'class="ui-btn ui-btn-primary filter-apply"', 1),
 ('class="btn primary"', 'class="ui-btn ui-btn-secondary"', 1),
 ('class="btn small"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 1),
 ('class="btn ghost"', 'class="ui-btn ui-btn-quiet"', 2),
 ('class="btn filter-toggle"', 'class="ui-btn ui-btn-secondary filter-toggle"', 1),
 ('class="btn"', 'class="ui-btn ui-btn-secondary"', 0),
 ('class="pill grey"', pill("grey"), 1), ('class="pill green"', pill("green"), 2), ('class="pill teal"', pill("teal"), 1),
 ('class="pill amber"', pill("amber"), 1), ('class="pill red"', pill("red"), 2),
 ('class="table-cards housebook-table"', 'class="ui-table ui-table-stack housebook-table"', 1),
 ('class="panel tight scroll-x housebook-scroll"', 'class="ui-section scroll-x housebook-scroll"', 1),
 ('class="filters panel host-filter-panel"', 'class="filters ui-section host-filter-panel"', 1),
 ('class="small muted"', 'class="ui-sub"', 5),
 ('class="field"', 'class="ui-field"', 4),
 ('class="mono small"', 'class="ui-mono ui-sub"', 1),
 ('class="nowrap small"', 'class="nowrap ui-sub"', 3),
 ('class="small"', 'class="ui-sub"', 2),
 ('class="grid two"', 'class="ui-pair"', 1),
])
print("ok")
EOF
```

   Expected: `ok`. The housebook `class="btn"` pair has count 0 after the filter-toggle pair (the only bare `btn` was the toggle); if the assertion names another count, read that line and report.

3. Catalog: add the three templates to `enforced_templates`; run `python3 scripts/design_lint.py 2>&1 | grep -E 'submissions.html|submission_detail.html|housebook.html' | sed 's/.*catalog: //' | sort -u | tr '\n' ' '` and put the tokens into each template's `legacy` list (expected for submissions: `list-cards lc-reports nowrap row-actions`; for submission_detail: `stay-command-panel outcome-* stay-command-main stay-command-actions stay-command-note eyebrow detail-hero detail-metric metric-label metric-value metric-note small-value stay-metrics kv report-* technical technical-download technical-downloads code-block help-dot panel scroll-x nowrap row-actions report-stamp report-stamp-value`; for housebook: `filter-toolbar filter-toggle filter-applied-summary filter-toolbar-actions filters host-filter-panel filter-fields filter-panel-actions filter-apply housebook-scroll housebook-table housebook-pdf-warn csv-export-dialog col-* nowrap row-actions row-menu-form inline empty`). `outcome-{{ ... }}` renders as `outcome-` after the lint strips Jinja; list `outcome-` too. Command: `python3 scripts/design_lint.py`. Expected: OK.

4. Tests. Anchor E: line 77 regex -> `r'<div class="ui-form-actions">(.*?)</div>'`; line 113 -> `f'<a class="ui-btn ui-btn-primary" href="/reservations/{reservation["id"]}#guests">'`; line 116 -> `assert actions.count("<a class=\"ui-btn") == 1`. Anchor F: `'class="ui-table ui-table-stack housebook-table"'` and `'class="ui-section scroll-x housebook-scroll"'`. Create `App/tests/test_design_reports.py`:

```python
"""0138: reports list, report detail and house book render on host_page."""
from __future__ import annotations

from pathlib import Path

from tests.test_signed_in_chrome import host_with_property  # noqa: F401

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"


def test_reports_and_housebook_have_the_v2_header_and_tabs(host_with_property):
    for path, kind in (("/submissions?lang=en", "list"), ("/housebook?lang=en", "list")):
        page = host_with_property.get(path).text
        assert page.count("<h1") == 1 and f'data-body-kind="{kind}"' in page, path
        assert 'class="ui-tabs" data-sub-tabs' in page, path
        assert "page-header" not in page, path


def test_no_raw_style_or_legacy_control_in_the_three_templates():
    for name in ("submissions.html", "submission_detail.html", "housebook.html"):
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        assert 'style="' not in text and 'class="btn' not in text and 'class="pill' not in text, name
        assert text.count('class="ui-btn ui-btn-primary') <= 1, name
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_design_reports.py tests/test_report_detail_next_step.py tests/test_report_detail_polish.py tests/test_wp25_reported_bugs.py tests/test_housebook*.py tests/test_submission_*.py tests/test_design_lint.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed.

5. Browser and screenshots: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-shots .venv/bin/python -m pytest tests/test_host_filter_panels_browser.py tests/test_host_list_page_layout_browser.py tests/test_host_geometry.py -q --tb=short 2>&1 | tail -30`. Expected: passed, 0 skipped. Attach `/submissions` and `/housebook` at 390 and 1280 and one report detail at 390.

6. Commit: `git add App/app/templates/submissions.html App/app/templates/submission_detail.html App/app/templates/housebook.html docs/design/catalog.json App/tests && git commit -m "0138 step 6: reports, report detail and house book on host_page"`.

## 5. Do not touch

Routes, receipt and export code, `_components.html`, `_date_range.html`, the house-book filter behaviour; hard rules 1, 3, 8.

## 6. Commands

- `python3 scripts/design_lint.py` expected: OK.
- Step 4 and step 5 commands, 0 skipped.

## 7. Acceptance

- [ ] Three pages on host_page with one h1 each; reports and register tabs under the title; badges and tables in v2 classes.
- [ ] Screenshots attached (390 and 1280 for the two lists, 390 for the detail).
- [ ] Lint passes with the three templates enforced.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a count in step 2 differs; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0138-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/templates/submission_detail.html` (report grammar, receipt links).

## Owner steps

None.
