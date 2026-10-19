# 0135: Stay detail on the v2 template (detail kind)

Status: todo
Depends on: 0134 | Base commit: 5b10d6a (refreshed 2026-10-19 against 0133 to 0150; every anchor re-verified) | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit each step as `0135 step k`. Never push, never open a PR. Page file: `docs/design/pages/stays.md` (detail section).

## 1. Objective

Move `reservation_detail.html` onto `host_page.html` as a detail page: v2 header (back link, stay name, the dates and source line as meta), the four in-page jump links styled as tabs, v2 banners, badges and buttons. The one coral button is the UbyPort step in the `#now` panel (Fix, Send, Send again, Download receipt, View reports); every other button becomes secondary. Section order, ids, forms, the send controls and the claim logic do not change.

## 2. Context

Rules: MASTER 5 (detail kind), 4 (one primary), 7.3 and 7.4 (one DOM: a table is restyled as cards through `data-card` roles, never rendered twice), 7.5 (badges), 7.9 (banner), `docs/UBYPORT_CORE.md` (the CTA copy and gating are correctness, not design). Settled rules for every v2 brief:

- One DOM: the page never renders its rows twice; card roles via `data-card="primary|secondary|meta|badge|actions|hide"` on each `<td>` (MASTER 7.3, 7.4).
- Never `class=` inside a ui macro's `attrs`; use `extra_class`. (This brief uses no macro `attrs`.)
- v2 controls are 40 px at 768 px and up, 44 px below (`.ui-btn` tokens). A test expecting 42 is updated to 40, never weakened. No test expects 42 on this page.
- A hook or text the old page rendered and the new page lacks is a regression: restore it. Tests that read old markup are updated to v2 markup, keeping what they assert. Never skip or weaken a test.
- No raw colours or bare px in CSS (`scripts/design_lint.py`); this brief adds no CSS, it deletes four dead `host.css` rules.
- "Clear demo data" and "Delete demo stay" stay (owner decision).

`host_page.html` imports every `_ui.html` and `_ui_layout.html` macro into the context, so the child template imports none of them (same as `dashboard.html`). Tests read `id="now"`, `class="panel stay-command-panel"`, `stay-command-panel outcome-*`, `class="stay-metrics detail-hero`, `nav.stay-jump a` (4 links), `.guest-card .guest-facts`, `#now > .stay-command-main > .stay-command-actions`, `.stay-property-line`, so those class strings stay (legacy list). The CTA class is written once as a variable so the exclusive branches render the same class and the template text holds no literal `ui-btn-primary`. In the refusal branch, Fix and Send again swap: Fix is coral until the refused guest was edited, then Send again is coral and Fix secondary (one coral button at a time; `test_send_controls.py` lines 730 and 741 already assert exactly this).

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

Anchor C, lines 97 to 101 (the refusal branch, Fix then Send again):

```
          <a class="btn accent primary" href="#guests">{{ t('stay.detail.cta.fix') }}</a>
          <form method="post" action="/reservations/{{ reservation.id }}/submit" class="inline">
            <input type="hidden" name="_csrf" value="{{ csrf_token }}">
            <input type="hidden" name="return_to" value="/reservations/{{ reservation.id }}">
            <button class="btn{% if send_controls.rejected_edited %} accent primary{% endif %}" type="submit">
```

Anchor D, `App/tests/test_send_controls.py` lines 730, 735 and 741 (three assertions on `class="btn accent primary"`). Anchor E, `App/tests/test_wp28_ui_sweep.py` line 154: `assert '<span class="pill grey">Cancelled</span>' in reporting`. Anchor F, `App/tests/test_onboarding_followup_browser.py` line 67: `(".page-header", ".stay-property-line", ".stay-jump", "#now")`. Anchor G, `App/tests/test_wp28_geometry.py` line 155 `card.querySelectorAll('.btn')` and line 158 `'.guest-card .verify-form .btn'` (the stay page's guest cards; after this brief their buttons are `.ui-btn`). Anchor H, `App/app/static/host.css` lines 703 to 705 and 716, the four `.stay-jump` rules (they out-rank `.ui-tab`, so the tabs would still render as pills):

```
.host-workspace .stay-jump { display: flex; flex-wrap: wrap; gap: 6px 8px; margin: 0 auto 18px; }
.host-workspace .stay-jump a { display: inline-flex; align-items: center; min-height: 36px; padding: 0 12px; border: 1px solid var(--line); border-radius: 999px; background: white; color: var(--ink); font-size: 13px; font-weight: 600; text-decoration: none; }
.host-workspace .stay-jump a:hover, .host-workspace .stay-jump a:focus-visible { border-color: var(--brand); }
```

and, inside the `@media (max-width: 600px)` block, `  .host-workspace .stay-jump a { min-height: 44px; }`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/reservation_detail.html` | edit | head, jump nav, CTA class, controls, badges, banners, reporting table roles |
| `App/app/static/host.css` | edit | Anchor H: delete the four `.stay-jump` rules |
| `docs/design/catalog.json` | edit | enforce the template; its legacy list |
| `App/tests/test_send_controls.py` | edit | three CTA assertions (Anchor D) |
| `App/tests/test_wp28_ui_sweep.py` | edit | Anchor E |
| `App/tests/test_onboarding_followup_browser.py` | edit | Anchor F |
| `App/tests/test_wp28_geometry.py` | edit | Anchor G |
| `App/tests/test_design_stay_detail.py` | create | slots, one coral CTA, hooks |

No other file may change.

## 4. Steps

1. Head and CTA, run from `App/` (one script; each anchor must occur exactly once):

```
.venv/bin/python - <<'EOF'
import pathlib
p = pathlib.Path("app/templates/reservation_detail.html"); s = p.read_text(encoding="utf-8")
A_OLD = """{% extends "base.html" %}
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
"""
A_NEW = """{% extends "host_page.html" %}
{% set nav = 'reservations' %}
{% set body_kind = 'detail' %}
{% from "_components.html" import field_label, help_tip, progress_pill, submission_pill, row_menu_begin, row_menu_end, guest_count, deadline_badge, source_badge with context %}
{# The UbyPort step is the page's one coral button; the branches below are exclusive. #}
{% set cta = 'ui-btn ui-btn-primary' %}
{% block title %}{{ reservation.internal_name }} · {{ reservation.date_from | date_cz }}{% endblock %}
{% block page_title %}{{ reservation.internal_name }}{% endblock %}
{% block back_url %}{{ return_to }}{% endblock %}
{% block back_label %}{{ t('stay.detail.back') }}{% endblock %}
{# 0080: in-page jump links so the four groups are reachable without folding any; 0135: styled as tabs. #}
{% macro stay_jump_nav(items) %}
<nav class="ui-tabs stay-jump" aria-label="{{ t('stay.detail.nav.label') }}">
  {% for href, label in items %}<a class="ui-tab" href="{{ href }}">{{ label }}</a>{% endfor %}
</nav>
{% endmacro %}
"""
B_OLD = """{{ page_header(
  reservation.internal_name,
  stay_lede,
  return_to,
  t('stay.detail.back'),
  ''
) }}
"""
B_NEW = """{% block meta %}{{ stay_lede }}{% endblock %}
{% block body %}
<input class="sr-only" type="text" id="stay-link" readonly value="{{ guest_link }}">
"""
C_OLD = """          <a class="btn accent primary" href="#guests">{{ t('stay.detail.cta.fix') }}</a>
          <form method="post" action="/reservations/{{ reservation.id }}/submit" class="inline">
            <input type="hidden" name="_csrf" value="{{ csrf_token }}">
            <input type="hidden" name="return_to" value="/reservations/{{ reservation.id }}">
            <button class="btn{% if send_controls.rejected_edited %} accent primary{% endif %}" type="submit">
"""
C_NEW = """          <a class="{{ 'ui-btn ui-btn-secondary' if send_controls.rejected_edited else cta }}" href="#guests">{{ t('stay.detail.cta.fix') }}</a>
          <form method="post" action="/reservations/{{ reservation.id }}/submit" class="inline">
            <input type="hidden" name="_csrf" value="{{ csrf_token }}">
            <input type="hidden" name="return_to" value="/reservations/{{ reservation.id }}">
            <button class="{{ cta if send_controls.rejected_edited else 'ui-btn ui-btn-secondary' }}" type="submit">
"""
for old, new in ((A_OLD, A_NEW), (B_OLD, B_NEW), (C_OLD, C_NEW)):
    assert s.count(old) == 1, old[:60]; s = s.replace(old, new)
p.write_text(s, encoding="utf-8"); print("ok")
EOF
```

   Expected: `ok`. Command: `cd App && .venv/bin/python -c "from app.templating import templates; templates.env.get_template('reservation_detail.html')" && echo compiled`. Expected: `compiled`. (The file's last line `{% endblock %}` now closes `block body`.)

2. Mechanical replacements, from `App/` (the reporting table gets its `data-card` roles here, MASTER 7.3):

```
.venv/bin/python - <<'EOF'
import pathlib
p = pathlib.Path("app/templates/reservation_detail.html"); s = p.read_text(encoding="utf-8")
PAIRS = [
 ("""<td class="nowrap small" data-label="{{ t('stay.detail.reports.when') }}">""", '<td class="ui-cell-first nowrap" data-card="primary">', 1),
 ("""<td data-label="{{ t('stay.detail.reports.outcome') }}">""", '<td data-card="badge">', 1),
 ("""<td class="mono small" data-label="{{ t('stay.detail.reports.stamp') }}">""", '<td class="ui-mono ui-sub" data-card="meta">', 1),
 ('<td class="nowrap row-actions" data-label="">', '<td class="ui-cell-acts row-actions" data-card="actions">', 1),
 ('class="btn accent primary"', 'class="{{ cta }}"', 4),
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
 ('class="muted"', 'class="ui-sub"', 1),
 ('class="small"', 'class="ui-sub"', 3),
 ('class="mono"', 'class="ui-mono"', 1),
 ('class="panel stay-settings"', 'class="ui-section stay-settings"', 1),
 ('class="panel"', 'class="ui-section"', 2),
]
for old, new, n in PAIRS:
    assert s.count(old) == n, (old, s.count(old)); s = s.replace(old, new)
assert 'style="' not in s and 'class="btn' not in s and 'class="pill' not in s and 'data-label=' not in s
assert s.count("ui-btn-primary") == 1 and s.count('data-card="') == 4
p.write_text(s, encoding="utf-8"); print("ok")
EOF
```

   Expected: `ok`. (The tone-to-kind map is the one `_components.html` line 5 uses: red, amber, blue are `action`; green `done`; grey `neutral`. `data-tone` is what `test_status_colours.py` reads.)

3. Catalog and CSS. In `docs/design/catalog.json` add `"App/app/templates/reservation_detail.html"` to `enforced_templates`; run `python3 scripts/design_lint.py 2>&1 | grep reservation_detail.html | sed 's/.*catalog: //' | sort -u | tr '\n' ' '` and put every token into `legacy["App/app/templates/reservation_detail.html"]` (expected among them: `host-stay-detail stay-property-line stay-jump stay-command-panel stay-command-main stay-command-actions stay-command-note eyebrow guest-cards guest-card guest-card-head guest-card-who guest-card-state guest-card-note guest-card-action guest-facts guest-facts-identity guest-facts-stay fact-extra fact-wide verify-form stay-claim-line stay-claim-label stay-metrics detail-hero inactive detail-metric metric-label metric-value metric-note small-value field-label-row settings-grid stay-settings stay-demo-banner inline-edit-bar inline-edit-title inline-edit-status nowrap row-actions scroll-x tight empty panel placeholder opt err-text`; take the lint's list, not this one). Then delete Anchor H from `App/app/static/host.css`: the three whole lines 703 to 705 and the one line 716 (`grep -c 'stay-jump' App/app/static/host.css` prints `0` afterwards; `host.css` is not lint-enforced, nothing else changes in it). Command: `python3 scripts/design_lint.py | tail -3`. Expected: OK.

4. Tests, from `App/` (one script, then one new file):

```
.venv/bin/python - <<'EOF'
import pathlib
def patch(path, pairs):
    p = pathlib.Path(path); s = p.read_text(encoding="utf-8")
    for old, new, n in pairs:
        assert s.count(old) == n, (path, old[:60], s.count(old)); s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")
patch("tests/test_send_controls.py", [('class="btn accent primary"', 'class="ui-btn ui-btn-primary"', 3)])
patch("tests/test_wp28_ui_sweep.py", [("'<span class=\"pill grey\">Cancelled</span>'", "'<span class=\"ui-badge ui-badge-neutral\" data-tone=\"grey\">Cancelled</span>'", 1)])
patch("tests/test_onboarding_followup_browser.py", [('(".page-header", ".stay-property-line", ".stay-jump", "#now")', '(".ui-ph", ".stay-property-line", ".stay-jump", "#now")', 1)])
patch("tests/test_wp28_geometry.py", [
 ("card.querySelectorAll('.btn')", "card.querySelectorAll('.ui-btn')", 1),
 ("'.guest-card .verify-form .btn'", "'.guest-card .verify-form .ui-btn'", 1),
])
print("ok")
EOF
```

   Expected: `ok`. Create `App/tests/test_design_stay_detail.py` (the `host` fixture of `test_status_colours.py` seeds one stay with one guest; `host_with_property` has no stay):

```python
"""0135: the stay detail renders on host_page; the UbyPort step is the one coral button."""
from __future__ import annotations

from tests.test_status_colours import host  # noqa: F401


def test_stay_detail_has_the_v2_header_jump_tabs_and_one_coral_button(host):
    client, _, reservation_id = host
    page = client.get(f"/reservations/{reservation_id}?lang=en").text
    assert page.count("<h1") == 1 and 'data-body-kind="detail"' in page
    assert 'class="ui-ph-back"' in page
    assert '<nav class="ui-tabs stay-jump"' in page and page.count('class="ui-tab"') == 4
    assert page.count('class="ui-btn ui-btn-primary"') <= 1
    assert 'class="panel stay-command-panel" id="now"' in page
    assert page.index('id="now"') < page.index('id="guests"') < page.index('id="reports"') < page.index('id="stay-quick-edit"')
    assert 'class="page-header' not in page and 'class="btn' not in page and 'class="pill' not in page


def test_no_raw_style_or_legacy_control_in_the_template():
    text = open("app/templates/reservation_detail.html", encoding="utf-8").read()
    assert 'style="' not in text and 'class="btn' not in text and 'class="pill' not in text
    assert text.count("ui-btn-primary") == 1
    # One DOM (MASTER 7.4): the reporting table restyles as cards through data-card roles.
    assert 'class="ui-table ui-table-stack"' in text and text.count('data-card="') == 4
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_design_stay_detail.py tests/test_send_controls.py tests/test_wp28_ui_sweep.py tests/test_status_colours.py tests/test_overhaul.py tests/test_wp25_reported_bugs.py tests/test_deadline_after_reporting.py tests/test_design_lint.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed.

5. Browser and screenshots, from `App/` with `UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_SHOTS_DIR=/tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0135 UBYHOST_CAPTURE_0080=1`: `.venv/bin/python -m pytest tests/test_host_stay_detail_layout_browser.py tests/test_onboarding_followup_browser.py tests/test_host_geometry.py tests/test_wp28_geometry.py -q --tb=short -rs 2>&1 | tail -30`. Expected: passed, 0 skipped. `UBYHOST_CAPTURE_0080=1` makes the first test overwrite the tracked `docs/tasks/0080-evidence/stay-detail-*.png`; copy two and restore the rest: `mkdir -p /tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0135 && cp docs/tasks/0080-evidence/stay-detail-en-390.png docs/tasks/0080-evidence/stay-detail-en-1280.png /tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0135/ && git checkout -- docs/tasks/0080-evidence && git status --short docs/tasks/0080-evidence | head -3` (prints nothing). Open both and write what you see (back link, title, meta line, four tabs under the property line, one coral button, no pill-shaped jump links).

6. Lint and commit: `python3 scripts/design_lint.py | tail -3 && App/.venv/bin/ruff check --select E9,F63,F7,F82,F401,F841 App/ | tail -3`, then `git add App/app/templates/reservation_detail.html App/app/static/host.css docs/design/catalog.json App/tests && git commit -m "0135 step 6: stay detail on host_page (detail kind)"`.

## 5. Do not touch

`app/reporting.py`, `routes/reservations.py`, `routes/admin.py`, the CTA copy keys, the claim and hand-filing forms, `_components.html`, `host2.css`, `docs/tasks/0080-evidence/` (restore it, never add it); hard rules 1, 3, 8.

## 6. Commands

- `python3 scripts/design_lint.py` expected: OK.
- Step 4 and step 5 commands, 0 skipped.
- Known local failures elsewhere (not in this brief's runs; if you see one, note it and move on, never fix it here): `test_host_i18n` language endpoint run alone, `test_property_navigation_browser.py`, `test_host_properties_navigation` fit test, `test_host_fit_browser`, `test_host_invoice_items_browser`, `test_host_property_controls_browser`, `test_host_ux_acceptance` rail-cards test, `test_host_list_page_layout_browser` properties `[40, 42]`, `test_onboarding_wizard_browser.py:1518` skeleton flake (passes on rerun).

## 7. Acceptance

- [ ] Back link, name, dates line; four jump tabs (no pills); one coral button, and only in `#now`; 40 px controls at 768+, 44 below.
- [ ] Reporting table rows carry the four `data-card` roles; no `data-label`, no `style=`, no `btn`, no `pill` in the template.
- [ ] 390 px and 1280 px screenshots in the shots folder and described in the report.
- [ ] Lint passes with `reservation_detail.html` enforced; `host.css` has no `stay-jump` rule.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a count in step 1, 2 or 4 differs; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a new dependency seems needed; a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0135-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left, screenshot paths and what they show.

## Risk list (for the reviewer)

`App/app/templates/reservation_detail.html` (UbyPort CTA branches, hard rule 1; the Fix / Send again swap in the refusal branch).

## Owner steps

None.
