# 0142: Stay fees (list and period detail) on the v2 template

Status: todo
Depends on: 0141 | Base commit: df8b842 | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit each step as `0142 step k`. Never push, never open a PR. Page file: `docs/design/pages/fees.md`.

## 1. Objective

Move `stay_fees.html` (list kind, no section tabs) and `stay_fee_detail.html` (detail kind, back link to the month) onto `host_page.html`. The month filter partial is already v2 (0141). Fee maths, the finalize form, CSV and PDF routes, QR payment block and the adjustment form keep their names and ids; only the shell and classes change. One primary per page: on the detail it is Save period (or Download PDF once the period is frozen); the scope save, the second PDF link and the adjustment save become secondary.

## 2. Context

Rules: MASTER 5 (list and detail kinds), 4 (one primary), 7.4, `docs/design/pages/fees.md`. `app.js` keys on `[data-filter-panel]`, `[data-month-picker]`, `[data-copy]`, `.clickable-row`, never on `.btn` or `.pill`. `stay-metrics detail-hero`, `copyrow`, `fee-*` and `filters fee-scope-form` classes stay as legacy (they carry layout rules in `host.css`).

Anchor A, `App/app/templates/stay_fees.html` lines 1 to 8 (verbatim):

```
{% extends "base.html" %}
{% set nav = 'stay_fees' %}
{% block title %}{{ t('stay_fees.title') }}{% endblock %}
{% block content %}
{% from "_components.html" import row_menu_begin, row_menu_end, list_page_header, empty_state with context %}
{#- 0099: no sub-page tabs: fee settings live per property (Settings,
    Reporting & fees); there is no one fee-settings page to link. -#}
{{ list_page_header(t('stay_fees.title')) }}
```

Anchor B, `App/app/templates/stay_fee_detail.html` lines 1 to 5 (verbatim):

```
{% extends "base.html" %}
{% set nav = 'stay_fees' %}
{% block title %}{{ apartment.internal_name }} ({{ ui_period }}){% endblock %}
{% block content %}
{% from "_components.html" import page_header, copy_button, field_label with context %}
```

Anchor C, same file, lines 27 and 28 (verbatim):

```
<a class="back-link" href="/stay-fees?month={{ month_key }}"> {{ t('stay_fees.back') }}</a>
{% include "_list_filter.html" %}
```

Anchor D, same file, lines 29 to 50: starts with `{% set actions %}`, ends with `{% endset %}` followed by the line `{{ page_header(apartment.internal_name ~ ' (' ~ ui_period ~ ')', '', '', '', t('nav.stay_fees'), actions) }}`. Inside it, `class="btn accent primary"` appears twice (the PDF link at line 33, the Save period button at line 44).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/stay_fees.html` | edit | head, classes |
| `App/app/templates/stay_fee_detail.html` | edit | head, header actions, classes |
| `docs/design/catalog.json` | edit | enforce both templates; legacy lists |
| `App/tests/test_host_wide_geometry_browser.py` | edit | three selectors |
| `App/tests/test_host_fee_navigation.py` | edit | one selector |
| `App/tests/test_design_fees.py` | create | shells, one primary |

No other file may change.

## 4. Steps

1. `stay_fees.html`: replace Anchor A with:

```
{% extends "host_page.html" %}
{% set nav = 'stay_fees' %}
{% set body_kind = 'list' %}
{% block title %}{{ t('stay_fees.title') }}{% endblock %}
{% block page_title %}{{ t('stay_fees.title') }}{% endblock %}
{#- 0099: no sub-page tabs: fee settings live per property (Settings,
    Reporting & fees); there is no one fee-settings page to link. -#}
{% block body %}
{% from "_components.html" import row_menu_begin, row_menu_end, empty_state with context %}
```

   Then, from `App/`:

```
.venv/bin/python - <<'EOF'
import pathlib
p = pathlib.Path("app/templates/stay_fees.html"); s = p.read_text(encoding="utf-8")
PAIRS = [
 ('class="btn small primary"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 2),
 ('class="pill green"', 'class="ui-badge ui-badge-done" data-tone="green"', 2),
 ('class="pill teal"', 'class="ui-badge ui-badge-neutral" data-tone="teal"', 1),
 ('class="pill amber"', 'class="ui-badge ui-badge-action" data-tone="amber"', 1),
 ('class="pill blue"', 'class="ui-badge ui-badge-action" data-tone="blue"', 2),
 ('class="panel tight scroll-x list-cards lc-fees fee-periods', 'class="list-cards lc-fees fee-periods', 1),
 ('class="table-cards{% if fee_list.all_unset %} fee-periods-table-unset{% endif %}"', 'class="ui-table ui-table-stack{% if fee_list.all_unset %} fee-periods-table-unset{% endif %}"', 1),
 ('class="num"', 'class="ui-num"', 9),
 ('class="small muted"', 'class="ui-sub"', 2),
]
for old, new, n in PAIRS:
    assert s.count(old) == n, (old, s.count(old)); s = s.replace(old, new)
assert 'class="btn' not in s and 'class="pill' not in s and 'style="' not in s and "ui-btn-primary" not in s
p.write_text(s, encoding="utf-8"); print("ok")
EOF
```

   Expected: `ok`. Compile: `cd App && .venv/bin/python -c "from app.templating import templates; templates.env.get_template('stay_fees.html'); templates.env.get_template('stay_fee_detail.html'); print('compiled')"` (run again after step 2). Expected: `compiled`.

2. `stay_fee_detail.html`: replace Anchor B with:

```
{% extends "host_page.html" %}
{% set nav = 'stay_fees' %}
{% set body_kind = 'detail' %}
{% set cta = 'ui-btn ui-btn-primary' %}
{% block title %}{{ apartment.internal_name }} ({{ ui_period }}){% endblock %}
{% block page_title %}{{ apartment.internal_name }} ({{ ui_period }}){% endblock %}
{% block back_url %}/stay-fees?month={{ month_key }}{% endblock %}
{% block back_label %}{{ t('stay_fees.back') }}{% endblock %}
{% block toolbar %}{% include "_list_filter.html" %}{% endblock %}
{% block primary_action %}
```

   Delete Anchor C (both lines). In Anchor D delete the final `{{ page_header(...) }}` line and put after `{% endset %}`:

```
{{ actions }}
{% endblock %}
{% block body %}
{% from "_components.html" import copy_button, field_label with context %}
```

   Then, from `App/`:

```
.venv/bin/python - <<'EOF'
import pathlib
p = pathlib.Path("app/templates/stay_fee_detail.html"); s = p.read_text(encoding="utf-8")
head, body = s.split("{% block body %}", 1)
assert head.count('class="btn accent primary"') == 2 and body.count('class="btn accent primary"') == 2
head = head.replace('class="btn accent primary"', 'class="{{ cta }}"')
body = body.replace('class="btn accent primary"', 'class="ui-btn ui-btn-secondary"')
s = head + "{% block body %}" + body
PAIRS = [
 ('class="btn primary"', 'class="ui-btn ui-btn-secondary"', 1),
 ('class="btn small"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 6),
 ('class="btn"', 'class="ui-btn ui-btn-secondary"', 5),
 ('class="pill green"', 'class="ui-badge ui-badge-done" data-tone="green"', 2),
 ('class="pill grey no-dot"', 'class="ui-badge ui-badge-neutral" data-tone="grey"', 1),
 ('class="pill amber"', 'class="ui-badge ui-badge-action" data-tone="amber"', 1),
 ('class="section-heading"', 'class="ui-section-h"', 2),
 ('class="panel tight"', 'class="ui-section"', 1),
 ('class="panel fee-blockers"', 'class="ui-section fee-blockers"', 1),
 ('class="panel"', 'class="ui-section"', 4),
 ('class="field fee-adjust-reason"', 'class="ui-field fee-adjust-reason"', 1),
 ('class="field"', 'class="ui-field"', 15),
 ('class="small muted mono"', 'class="ui-sub ui-mono"', 1),
 ('class="small muted fee-qr-help"', 'class="ui-sub fee-qr-help"', 1),
 ('class="small muted fee-hint"', 'class="ui-sub fee-hint"', 1),
 ('class="small muted"', 'class="ui-sub"', 3),
 ('class="warn-text small"', 'class="ui-sub warn-text"', 1),
 ('class="small warn-text"', 'class="ui-sub warn-text"', 1),
 ('class="small"', 'class="ui-sub"', 3),
 ('class="muted"', 'class="ui-sub"', 1),
 ('class="metric-value small-value mono"', 'class="metric-value small-value ui-mono"', 1),
]
for old, new, n in PAIRS:
    assert s.count(old) == n, (old, s.count(old)); s = s.replace(old, new)
assert 'class="btn' not in s and 'class="pill' not in s and 'style="' not in s and "ui-btn-primary" not in s.split("{% set cta")[1].split("%}")[1]
assert "back-link" not in s and "page_header" not in s
p.write_text(s, encoding="utf-8"); print("ok")
EOF
```

   Expected: `ok`. The two `class="{{ cta }}"` sit in exclusive branches of the header (frozen: PDF; otherwise: Save period), so one primary renders at a time.

3. Catalog: add both templates to `enforced_templates`; for each run `python3 scripts/design_lint.py 2>&1 | grep <name> | sed 's/.*catalog: //' | sort -u | tr '\n' ' '` and put the tokens into its `legacy` list. Command: `python3 scripts/design_lint.py`. Expected: OK.

4. Tests. `App/tests/test_host_wide_geometry_browser.py`: line 720 `page.locator(".page-header").bounding_box()` → `page.locator(".ui-ph").bounding_box()`; line 721 `page.locator("main.wrap.with-sidebar > a.back-link").bounding_box()` → `page.locator(".ui-ph-back").bounding_box()`; line 733 `page.locator(".page-header").first.bounding_box()` → `page.locator(".ui-ph").first.bounding_box()`. `App/tests/test_host_fee_navigation.py` line 198: `page.locator(".page-header").bounding_box()` → `page.locator(".ui-ph").bounding_box()`. If any of these lines has already been changed by 0129 step 8 (it widened some selectors), skip that line and say so in the report. Create `App/tests/test_design_fees.py`:

```python
"""0142: stay fee pages render on host_page; one primary on the period detail."""
from __future__ import annotations

import re

from tests.test_signed_in_chrome import host_with_property  # noqa: F401


def test_fee_list_and_detail_have_the_v2_shells(host_with_property):
    listing = host_with_property.get("/stay-fees?lang=en").text
    assert listing.count("<h1") == 1 and 'data-body-kind="list"' in listing
    assert 'class="ui-toolbar"' in listing and "ui-btn-primary filter-apply" in listing
    assert listing.count("ui-btn-primary") == 1
    match = re.search(r'href="(/stay-fees/\d+\?month=\d{4}-\d{2})"', listing)
    if match:
        detail = host_with_property.get(match.group(1) + "&lang=en").text
        assert 'data-body-kind="detail"' in detail and 'class="ui-ph-back"' in detail
        assert detail.count('class="ui-btn ui-btn-primary"') <= 1


def test_templates_have_no_raw_style_or_legacy_control():
    for name in ("stay_fees.html", "stay_fee_detail.html"):
        text = open(f"app/templates/{name}", encoding="utf-8").read()
        assert 'style="' not in text and 'class="btn' not in text, name
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_design_fees.py tests/test_stay_fee*.py tests/test_host_fee_navigation.py tests/test_design_lint.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed.

5. Browser and screenshots: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-shots .venv/bin/python -m pytest tests/test_host_fee_navigation.py tests/test_host_wide_geometry_browser.py tests/test_host_filter_panels_browser.py -q --tb=short 2>&1 | tail -30`. Expected: passed, 0 skipped. Attach `fees-390.png`, `fees-1280.png`, `fee-detail-390.png`, `fee-detail-1280.png`.

6. Commit: `git add App/app/templates docs/design/catalog.json App/tests && git commit -m "0142 step 6: stay fees list and period detail on host_page"`.

## 5. Do not touch

`routes/stay_fees.py`, fee maths, `_list_filter.html` (done in 0141), `host.css`; hard rules 1, 2, 3, 8.

## 6. Commands

- `python3 scripts/design_lint.py` expected: OK.
- Step 4 and step 5 commands, 0 skipped.

## 7. Acceptance

- [ ] Fees list: title, month toolbar, v2 table, no header primary (Apply in the collapsed filter is the only one).
- [ ] Period detail: back link to the month, header with Save period or Download PDF as the one primary, metrics and sections unchanged in content.
- [ ] Screenshots attached; lint OK with both templates enforced.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a count differs; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0142-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/templates/stay_fee_detail.html` (finalize form inputs must stay inside the header form; check the hidden `collected_*` inputs still post).

## Owner steps

None.
