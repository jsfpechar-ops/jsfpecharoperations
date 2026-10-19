# 0135: Stay detail on the v2 template (detail kind)

Status: todo
Depends on: 0134 | Base commit: df8b842 | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit each step as `0135 step k`. Never push, never open a PR. Page file: `docs/design/pages/stays.md` (detail section).

## 1. Objective

Move `reservation_detail.html` onto `host_page.html` as a detail page: v2 header (back link, stay name, the dates and source line as meta), the four in-page jump links styled as tabs, v2 banners, badges and buttons. The one coral button stays the UbyPort step in the `#now` panel (Fix, Send, Send again, Download receipt, View reports); every other button becomes secondary. Section order, ids, forms, the send controls and the claim logic do not change.

## 2. Context

Rules: MASTER 5 (detail kind), 4 (one primary), 7.5 (badges), 7.9 (banner), `docs/UBYPORT_CORE.md` (the CTA copy and gating are correctness, not design). Tests read `id="now"`, `class="panel stay-command-panel"`, `stay-command-panel outcome-*`, `class="stay-metrics detail-hero`, `nav.stay-jump a` (4 links), `.guest-card .guest-facts`, `#now > .stay-command-main > .stay-command-actions`, so those class strings stay (legacy list). The CTA class is written once as a variable so the five exclusive branches render the same class and the template text holds no literal `ui-btn-primary`.

Anchor A, `App/app/templates/reservation_detail.html`, lines 1 to 13:

```
{% extends "base.html" %}
{% set nav = 'reservations' %}
{% block title %}{{ reservation.internal_name }} · {{ reservation.date_from | date_cz }}{% endblock %}
{% block content %}
{# 0080: local primitive (the shared _components.html belongs to another lane).
   In-page jump links so the four groups are reachable without folding any. #}
{% macro stay_jump_nav(items) %}
<nav class="stay-jump" aria-label="{{ t('stay.detail.nav.label') }}">
  {% for href, label in items %}<a href="{{ href }}">{{ label }}</a>{% endfor %}
</nav>
{% endmacro %}
{% from "_components.html" import page_header, field_label, help_tip, progress_pill, submission_pill, row_menu_begin, row_menu_end, guest_count, deadline_badge, source_badge with context %}
<input class="sr-only" type="text" id="stay-link" readonly value="{{ guest_link }}">
```

Line 14 (`{% set stay_lede %}...{% endset %}`) stays where it is. Anchor B, lines 15 to 21:

```
{{ page_header(
  reservation.internal_name,
  stay_lede,
  return_to,
  t('stay.detail.back'),
  ''
) }}
```

Anchor C, line 101:

```
            <button class="btn{% if send_controls.rejected_edited %} accent primary{% endif %}" type="submit">
```

Anchor D, `App/tests/test_send_controls.py` lines 730, 735 and 741 (three assertions on `class="btn accent primary"`). Anchor E, `App/tests/test_wp28_ui_sweep.py` line 154: `assert '<span class="pill grey">Cancelled</span>' in reporting`. Anchor F, `App/tests/test_onboarding_followup_browser.py` line 67: `(".page-header", ".stay-property-line", ".stay-jump", "#now")`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/reservation_detail.html` | edit | head, jump nav, CTA class, controls, badges, banners |
| `docs/design/catalog.json` | edit | enforce the template; its legacy list |
| `App/tests/test_send_controls.py` | edit | three CTA assertions (Anchor D) |
| `App/tests/test_wp28_ui_sweep.py` | edit | Anchor E |
| `App/tests/test_onboarding_followup_browser.py` | edit | Anchor F |
| `App/tests/test_design_stay_detail.py` | create | slots, one coral CTA, hooks |

No other file may change.

## 4. Steps

1. Replace Anchor A with:

```
{% extends "host_page.html" %}
{% set nav = 'reservations' %}
{% set body_kind = 'detail' %}
{% from "_components.html" import field_label, help_tip, progress_pill, submission_pill, row_menu_begin, row_menu_end, guest_count, deadline_badge, source_badge with context %}
{% from "_ui.html" import ui_button with context %}
{# The UbyPort step is the page's one coral button; the branches below are exclusive. #}
{% set cta = 'ui-btn ui-btn-primary' %}
{% block title %}{{ reservation.internal_name }} · {{ reservation.date_from | date_cz }}{% endblock %}
{% block page_title %}{{ reservation.internal_name }}{% endblock %}
{% block back_url %}{{ return_to }}{% endblock %}
{% block back_label %}{{ t('stay.detail.back') }}{% endblock %}
{% macro stay_jump_nav(items) %}
<nav class="ui-tabs stay-jump" aria-label="{{ t('stay.detail.nav.label') }}">
  {% for href, label in items %}<a class="ui-tab" href="{{ href }}">{{ label }}</a>{% endfor %}
</nav>
{% endmacro %}
```

   Replace Anchor B with:

```
{% block meta %}{{ stay_lede }}{% endblock %}
{% block body %}
<input class="sr-only" type="text" id="stay-link" readonly value="{{ guest_link }}">
```

   Replace Anchor C with:

```
            <button class="{{ cta if send_controls.rejected_edited else 'ui-btn ui-btn-secondary' }}" type="submit">
```

   Command: `cd App && .venv/bin/python -c "from app.templating import templates; templates.env.get_template('reservation_detail.html')" && echo compiled`. Expected: `compiled`.

2. Mechanical replacements, from `App/`:

```
.venv/bin/python - <<'EOF'
import pathlib
p = pathlib.Path("app/templates/reservation_detail.html"); s = p.read_text(encoding="utf-8")
PAIRS = [
 ('class="btn accent primary"', 'class="{{ cta }}"', 5),
 ('class="btn primary"', 'class="ui-btn ui-btn-secondary"', 2),
 ('class="btn small"', 'class="ui-btn ui-btn-secondary ui-btn-compact"', 10),
 ('class="btn"', 'class="ui-btn ui-btn-secondary"', 4),
 ('class="pill grey no-dot"', 'class="ui-badge ui-badge-neutral" data-tone="grey"', 1),
 ('class="pill grey"', 'class="ui-badge ui-badge-neutral" data-tone="grey"', 2),
 ('class="pill green"', 'class="ui-badge ui-badge-done" data-tone="green"', 2),
 ('class="pill amber"', 'class="ui-badge ui-badge-action" data-tone="amber"', 3),
 ('class="pill red"', 'class="ui-badge ui-badge-action" data-tone="red"', 2),
 ('class="pill blue"', 'class="ui-badge ui-badge-action" data-tone="blue"', 1),
 ('class="table-cards"', 'class="ui-table ui-table-stack"', 1),
 ('class="section-heading"', 'class="ui-section-h"', 4),
 ('class="small muted"', 'class="ui-sub"', 7),
 ('class="actions settings-actions"', 'class="ui-form-actions"', 2),
 ('class="actions"', 'class="ui-form-actions"', 1),
 ('class="banner critical"', 'class="ui-banner ui-banner-attention"', 1),
 ('class="banner warning"', 'class="ui-banner ui-banner-attention"', 1),
 ('class="banner info stay-demo-banner"', 'class="ui-banner ui-banner-neutral stay-demo-banner"', 1),
 ('class="banner info"', 'class="ui-banner ui-banner-neutral"', 1),
 ('class="field"', 'class="ui-field"', 5),
 ('class="mono small"', 'class="ui-mono ui-sub"', 1),
 ('class="nowrap small"', 'class="nowrap ui-sub"', 1),
 ('class="muted"', 'class="ui-sub"', 1),
 ('class="small"', 'class="ui-sub"', 3),
 ('class="mono"', 'class="ui-mono"', 1),
 ('class="panel stay-settings"', 'class="ui-section stay-settings"', 1),
 ('class="panel"', 'class="ui-section"', 2),
]
for old, new, n in PAIRS:
    assert s.count(old) == n, (old, s.count(old)); s = s.replace(old, new)
assert 'style="' not in s and 'class="btn' not in s and 'class="pill' not in s and 'ui-btn-primary"' not in s.replace("{% set cta = 'ui-btn ui-btn-primary' %}", "")
p.write_text(s, encoding="utf-8"); print("ok")
EOF
```

   Expected: `ok`.

3. In `docs/design/catalog.json` add `"App/app/templates/reservation_detail.html"` to `enforced_templates`; run `python3 scripts/design_lint.py 2>&1 | grep reservation_detail.html | sed 's/.*catalog: //' | sort -u | tr '\n' ' '` and put every token into `legacy["App/app/templates/reservation_detail.html"]` (expected among them: `host-stay-detail stay-property-line stay-jump stay-command-panel stay-command-main stay-command-actions stay-command-note eyebrow inline guest-cards guest-card guest-card-head guest-card-who guest-card-state guest-card-note guest-card-action guest-facts guest-facts-identity guest-facts-stay fact-extra fact-wide verify-form stay-claim-line stay-claim-label stay-metrics detail-hero inactive detail-metric metric-label metric-value metric-note small-value field-label-row settings-grid stay-settings stay-demo-banner inline-edit-bar inline-edit-title inline-edit-status nowrap scroll-x tight placeholder critical err-text row-menu-form`). Command: `python3 scripts/design_lint.py`. Expected: OK.

4. Tests. In `App/tests/test_send_controls.py` replace every `class="btn accent primary"` (three lines) with `class="ui-btn ui-btn-primary"`. In `App/tests/test_wp28_ui_sweep.py` replace Anchor E's string with `'<span class="ui-badge ui-badge-neutral" data-tone="grey">Cancelled</span>'`. In `App/tests/test_onboarding_followup_browser.py` replace `".page-header"` in Anchor F with `".ui-ph"`. Create `App/tests/test_design_stay_detail.py`:

```python
"""0135: the stay detail renders on host_page; the UbyPort step is the one coral button."""
from __future__ import annotations

import re

from tests.test_signed_in_chrome import host_with_property  # noqa: F401


def _first_stay(client):
    page = client.get("/reservations?range=all&lang=en").text
    match = re.search(r'data-href="(/reservations/\d+)"', page)
    assert match, "no stay on the list"
    return client.get(match.group(1) + "?lang=en").text


def test_stay_detail_has_the_v2_header_jump_tabs_and_one_coral_button(host_with_property):
    page = _first_stay(host_with_property)
    assert page.count("<h1") == 1 and 'data-body-kind="detail"' in page
    assert 'class="ui-ph-back"' in page
    assert '<nav class="ui-tabs stay-jump"' in page and page.count('class="ui-tab"') == 4
    assert page.count('class="ui-btn ui-btn-primary"') <= 1
    assert 'class="panel stay-command-panel" id="now"' in page
    assert page.index('id="now"') < page.index('id="guests"') < page.index('id="reports"') < page.index('id="stay-quick-edit"')
    assert "page-header" not in page


def test_no_raw_style_or_legacy_control_in_the_template():
    text = open("app/templates/reservation_detail.html", encoding="utf-8").read()
    assert 'style="' not in text and 'class="btn' not in text and 'class="pill' not in text
    assert text.count("ui-btn-primary") == 1
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_design_stay_detail.py tests/test_send_controls.py tests/test_wp28_ui_sweep.py tests/test_overhaul.py tests/test_wp25_reported_bugs.py tests/test_deadline_after_reporting.py tests/test_design_lint.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed.

5. Browser and screenshots: `cd App && UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/ubyhost-shots .venv/bin/python -m pytest tests/test_host_stay_detail_layout_browser.py tests/test_onboarding_followup_browser.py tests/test_host_geometry.py -q --tb=short 2>&1 | tail -30`. Expected: passed, 0 skipped. Attach a stay detail at 390 and 1280 (`stay-detail-390.png`, `stay-detail-1280.png`).

6. Commit: `git add App/app/templates/reservation_detail.html docs/design/catalog.json App/tests && git commit -m "0135 step 6: stay detail on host_page (detail kind)"`.

## 5. Do not touch

`app/send_controls.py`, `app/reporting.py`, `routes/reservations.py`, the CTA copy keys, the claim and hand-filing forms, `_components.html`; hard rules 1, 3, 8.

## 6. Commands

- `python3 scripts/design_lint.py` expected: OK.
- Step 4 and step 5 commands, 0 skipped.

## 7. Acceptance

- [ ] Back link, name, dates line; four jump tabs; one coral button, and only in `#now`.
- [ ] 390 px and 1280 px screenshots attached.
- [ ] Lint passes with `reservation_detail.html` enforced.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a count in step 2 differs; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a new dependency seems needed; a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0135-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/templates/reservation_detail.html` (UbyPort CTA branches, hard rule 1).

## Owner steps

None.
