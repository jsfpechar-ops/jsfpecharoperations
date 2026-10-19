# 0132: Shared macros to v2 (badges, row menu, copy, sync, send, empty state, identity)

Status: todo
Depends on: 0131 | Base commit: df8b842 | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit each step as `0132 step k`. Never push, never open a PR.

## 1. Objective

Convert the macros in `_components.html` that every host page renders (status pills, deadline badge, submission pill, row menu, copy buttons, sync and send buttons, CSV export, empty state, property identity, guest count) to the v2 catalog classes and Lucide icons, so the page briefs that follow inherit the right badges and menus without touching each macro again (MASTER 7.5, 7.8, 7.11, migration-map section 3). Status meanings do not change; the colour family does: red and amber and blue host-action tones become `action`, teal and grey become `neutral`, green stays `done`. Each badge keeps a `data-tone` attribute with the old tone name so tests keep checking the same semantics.

## 2. Context

Rules: MASTER 7.5 (fixed badge kinds, overdue mark), 10.9 (a status always has a word), UbyPort copy unchanged (labels and tips stay exactly as today). Anchors are in `App/app/templates/_components.html` unless stated.

Anchor A (end of `progress_pill`):

```
  <span class="pill {{ tone }}" {% if tip %}title="{{ tip }}"{% endif %}>{{ label }}</span>
{% endmacro %}
```

Anchor B (end of `submission_pill`):

```
  <span class="pill {{ tones.get(state, 'red') }}">{{ labels.get(state, state) }}</span>
{% endmacro %}
```

Anchor C (`deadline_badge`, whole macro from `{% macro deadline_badge(cell, tag='span', extra_class='') -%}` to its `{%- endmacro %}`; the first and last lines are the anchors):

```
{% macro deadline_badge(cell, tag='span', extra_class='') -%}
  {%- set classes = (' ' ~ extra_class) if extra_class else '' -%}
```

Anchor D (`guest_count`, the svg line):

```
      <svg viewBox="0 0 16 16" fill="none" aria-hidden="true"><circle cx="8" cy="5.5" r="2.5" stroke="currentColor" stroke-width="1.4"/><path d="M3.5 13.5c0-2.4 2-3.8 4.5-3.8s4.5 1.4 4.5 3.8" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>
```

Anchor E (`row_reporting_actions`):

```
      <button class="btn small row-action-send{% if controls.get('send_enabled') %} accent{% endif %}" type="submit"
```

Anchor F (`bulk_send_ready`):

```
    <button class="btn send-all" type="submit"
            {% if not count %}disabled{% endif %}
            title="{{ t('send.all_ready_hint') }}">
      {{ t('send.all_ready') }}{% if count %} ({{ count }}){% endif %}
    </button>
```

Anchor G (`sync_calendars_button`):

```
      <button class="btn{% if primary %} primary{% endif %} sync-btn" type="submit">
        <span class="sync-btn-icon" aria-hidden="true">{{ nav_icon('calendar') }}</span>
        <span>{{ t(label_key) }}</span>
      </button>
```

Anchor H (`csv_actions_menu`):

```
<button class="btn{% if compact %} small csv-in-filter{% endif %}" type="button"
        data-csv-export="/reservations.csv" data-csv-params="{{ export_params }}"
```

Anchor I (`empty_state`):

```
  <div class="panel empty empty-state" data-empty-state>
    {% if title %}<h2>{{ title }}</h2>{% endif %}
    {% if body %}<p>{{ body }}</p>{% endif %}
    {% if action_url %}<div class="empty-state-action"><a class="btn{{ ' primary' if primary }}" href="{{ action_url }}">{{ action_label }}</a></div>{% endif %}
```

Anchor J (`property_identity`):

```
  <span class="property-identity{{ ' truncate' if truncate }}"{% if truncate %} title="{{ name }}"{% endif %}>
    <span class="property-mark property-tone-{{ id % 10 }}" aria-hidden="true">{{ name[:1] }}</span>
```

Anchor K (`copy_button`):

```
  <button class="btn-icon" type="button" data-copy="{{ target_id }}"
          data-copy-label="{{ t('common.copy') }}" data-copied-label="{{ t('common.copied') }}"
          aria-label="{{ t('common.copy') }}">{{ copy_icon() }}<span class="btn-icon-label" data-copy-label-slot hidden></span></button>
```

Anchor L (`row_menu_begin`):

```
<div class="row-menu">
  <button class="btn-icon row-menu-trigger" type="button" aria-label="{{ label or t('common.more_actions') }}" aria-expanded="false" aria-haspopup="true">
    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <circle cx="3.25" cy="8" r="1.25"/><circle cx="8" cy="8" r="1.25"/><circle cx="12.75" cy="8" r="1.25"/>
    </svg>
  </button>
  <div class="row-menu-panel" role="menu" hidden>
```

Anchor M, first line of the file:

```
{#- 0093 help: one contextual "?" tip beside a field label. Place it OUTSIDE the <label> tag.
```

Anchor N, `App/tests/test_status_colours.py`:

```
PILL = re.compile(
    r'<span class="pill ([a-z]+)"(?: title="([^"]*)")?>([^<]*)</span>',
)
```

Anchor O, `App/tests/test_deadline_after_reporting.py`:

```
DEADLINE_SPAN = re.compile(r'class="deadline(?: [a-z-]+)* ([a-z]+)"[^>]*>([^<]*)<')
```

Anchor P, `App/tests/test_host_quiet_dashboard_browser.py`:

```
                assert page.locator(".dashboard-row-task .pill.amber").count() >= 1
                ready_row = page.locator(f'.dashboard-row[data-stay-id="{dashboard_rich_host["ready"]}"]')
                assert ready_row.locator(".dashboard-row-task .pill.blue").count() == 1
```

Anchor Q, `docs/design/catalog.json`:

```
  "hooks": [
```

(the full hooks line starts with that text; edit the array it opens).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/_components.html` | edit | the macros above |
| `App/app/static/host2.css` | edit | append styles for the legacy menu hooks and the old empty-state block |
| `docs/design/catalog.json` | edit | hooks for legacy functional classes |
| `App/tests/test_status_colours.py` | edit | regex (Anchor N) |
| `App/tests/test_deadline_after_reporting.py` | edit | regex (Anchor O) |
| `App/tests/test_host_quiet_dashboard_browser.py` | edit | selectors (Anchor P) |
| `App/tests/test_design_shared_macros.py` | create | badge mapping and markup |

No other file may change. If another test fails only because it matches `class="pill …"` or `.pill.<tone>` on output of one of these macros, change that assertion to `data-tone="<tone>"` or `[data-tone="<tone>"]` in the same way, list the file in the report, and never delete the assertion. Do not touch tests that read a `pill` written literally in a page template (`reservations.html`, `_property_calendars.html`, `guide.html`, setup wizard): those move with their page briefs.

## 4. Steps

1. In `_components.html`, replace Anchor M with:

```
{% from "_icons.html" import icon with context %}
{#- Status tones map to the four v2 badge kinds (docs/design/MASTER.md 7.5):
    red, amber and blue are things the host must do; teal and grey wait; green is verified done.
    data-tone keeps the old tone name for tests and for anyone reading the markup. -#}
{% set UI_KINDS = {'red': 'action', 'amber': 'action', 'blue': 'action', 'teal': 'neutral', 'green': 'done', 'grey': 'neutral'} %}
{% set UI_SUBMISSION_KINDS = {'red': 'action', 'amber': 'attention', 'blue': 'action', 'teal': 'neutral', 'green': 'done', 'grey': 'neutral'} %}
{% set UI_DEADLINE_KINDS = {'overdue': 'action', 'urgent': 'attention', 'soon': 'attention', 'done': 'done', 'late': 'neutral'} %}
{#- 0093 help: one contextual "?" tip beside a field label. Place it OUTSIDE the <label> tag.
```

2. Replace Anchor A with:

```
  <span class="ui-badge ui-badge-{{ UI_KINDS.get(tone, 'neutral') }}{{ ' ui-badge-overdue' if tone == 'red' }}" data-tone="{{ tone }}"{% if tip %} title="{{ tip }}"{% endif %}>{% if tone == 'red' %}! {% endif %}{{ label }}</span>
{% endmacro %}
```

3. Replace Anchor B with:

```
  {% set stone = tones.get(state, 'red') %}
  <span class="ui-badge ui-badge-{{ UI_SUBMISSION_KINDS.get(stone, 'neutral') }}{{ ' ui-badge-overdue' if stone == 'red' }}" data-tone="{{ stone }}">{% if stone == 'red' %}! {% endif %}{{ labels.get(state, state) }}</span>
{% endmacro %}
```

4. Replace the whole `deadline_badge` macro (Anchor C through its `{%- endmacro %}`) with:

```
{% macro deadline_badge(cell, tag='span', extra_class='') -%}
  {%- set classes = (' ' ~ extra_class) if extra_class else '' -%}
  {%- if cell.by_hand and cell.state in ('filed_on_time', 'filed_late') -%}
    <{{ tag }} class="ui-badge ui-badge-{{ UI_DEADLINE_KINDS.get(cell.level, 'neutral') }}{{ classes }}" data-deadline="{{ cell.level }}">{{ t('deadline.filed_by_hand', when=cell.filed_at.strftime('%d.%m. %H:%M')) }}</{{ tag }}>
  {%- elif cell.state == 'filed_on_time' -%}
    <{{ tag }} class="ui-badge ui-badge-done{{ classes }}" data-deadline="done">{{ t('deadline.filed_at', when=cell.filed_at.strftime('%d.%m. %H:%M')) }}</{{ tag }}>
  {%- elif cell.state == 'filed_late' -%}
    <{{ tag }} class="ui-badge ui-badge-neutral{{ classes }}" data-deadline="neutral" title="{{ t('deadline.filed_at', when=cell.filed_at.strftime('%d.%m. %H:%M')) }}">
      {%- if cell.late_hours < 48 %}{{ t('deadline.filed_late_hours', n=cell.late_hours) }}
      {%- else %}{{ tp('deadline.filed_late_days', cell.late_hours // 24) }}{% endif -%}
    </{{ tag }}>
  {%- elif cell.state == 'countdown' -%}
    <{{ tag }} class="ui-badge ui-badge-{{ UI_DEADLINE_KINDS.get(cell.level, 'neutral') }}{{ ' ui-badge-overdue' if cell.level == 'overdue' }}{{ classes }}" data-deadline="{{ cell.level }}">{% if cell.level == 'overdue' %}! {% endif %}{{ describe_time_left(cell.check_in) if cell.check_in else '—' }}</{{ tag }}>
  {%- endif -%}
{%- endmacro %}
```

   Keep the `'—'` placeholder exactly (it is an empty-cell dash, allowed by `test_no_em_dashes`).

5. Replace Anchor D with `      {{ icon('users', 16) }}`.

6. Replace Anchor E with:

```
      <button class="ui-btn ui-btn-secondary ui-btn-compact row-action-send" type="submit"
```

7. Replace Anchor F with:

```
    <button class="ui-btn ui-btn-secondary send-all" type="submit"
            {% if not count %}disabled{% endif %}
            title="{{ t('send.all_ready_hint') }}">
      {{ icon('send', 16) }}<span>{{ t('send.all_ready') }}{% if count %} ({{ count }}){% endif %}</span>
    </button>
```

8. Replace Anchor G with:

```
      <button class="ui-btn ui-btn-{{ 'primary' if primary else 'secondary' }} sync-btn" type="submit">
        {{ icon('refresh-cw', 16) }}
        <span>{{ t(label_key) }}</span>
      </button>
```

9. Replace Anchor H with:

```
<button class="ui-btn ui-btn-quiet{% if compact %} ui-btn-compact csv-in-filter{% endif %}" type="button"
        data-csv-export="/reservations.csv" data-csv-params="{{ export_params }}"
```

10. Replace Anchor I with:

```
  <div class="ui-empty" data-empty-state>
    {% if title %}<h2>{{ title }}</h2>{% endif %}
    {% if body %}<p>{{ body }}</p>{% endif %}
    {% if action_url %}<div class="ui-btn-group"><a class="ui-btn ui-btn-{{ 'primary' if primary else 'secondary' }}" href="{{ action_url }}">{{ action_label }}</a></div>{% endif %}
```

    Then run `cd App && .venv/bin/python -m pytest tests/test_first_property_step.py tests/test_stays_empty_workspace.py tests/test_properties_table_chips.py -q --tb=short 2>&1 | tail -30`. Those three files match `<div class="panel empty empty-state" data-empty-state>(.*?)\n  </div>`; change each such regex to `<div class="ui-empty" data-empty-state>(.*?)\n  </div>` and, inside those tests only, `class="btn primary"` to `class="ui-btn ui-btn-primary"` and `class="btn"` to `class="ui-btn ui-btn-secondary"` where the assertion reads the empty state's button. Add the three files to section 3 in your report. Expected after the edits: the empty-state tests pass; any failure about `btn primary sync-btn` or `filter-apply` belongs to the page briefs and is reported, not fixed.

11. Replace Anchor J with:

```
  <span class="property-identity ui-pdot{{ ' truncate' if truncate }}" data-property="{{ (id % 4) + 1 }}"{% if truncate %} title="{{ name }}"{% endif %}>
```

    (the letter mark span is deleted; the `ui-pdot` dot replaces it.)

12. Replace Anchor K with:

```
  <button class="ui-btn ui-btn-quiet ui-btn-icon ui-btn-compact" type="button" data-copy="{{ target_id }}"
          data-copy-label="{{ t('common.copy') }}" data-copied-label="{{ t('common.copied') }}"
          aria-label="{{ t('common.copy') }}">{{ icon('copy', 16) }}<span class="btn-icon-label" data-copy-label-slot hidden></span></button>
```

13. Replace Anchor L with:

```
<div class="row-menu ui-menu">
  <button class="ui-btn ui-btn-quiet ui-btn-icon ui-btn-compact row-menu-trigger" type="button" aria-label="{{ label or t('common.more_actions') }}" aria-expanded="false" aria-haspopup="true">{{ icon('ellipsis-vertical', 16) }}</button>
  <div class="row-menu-panel ui-menu-panel" role="menu" hidden>
```

14. Append to `App/app/static/host2.css`:

```

/* ---- legacy functional hooks rendered by _components.html macros ---- */
.host-workspace .ui-menu-panel .row-menu-item { display: flex; align-items: center; gap: var(--space-3); min-height: var(--control-h); padding: 0 var(--space-3); border-radius: var(--radius-2); color: var(--ink); text-decoration: none; font: inherit; font-size: var(--body-size); background: transparent; border: 0; width: 100%; text-align: left; cursor: pointer; white-space: nowrap; }
.host-workspace .ui-menu-panel .row-menu-item:hover { background: var(--surface-2); }
.host-workspace .ui-menu-panel .row-menu-form { margin: 0; }
.host-workspace .guest-count { display: inline-flex; align-items: center; gap: var(--space-1); font-variant-numeric: tabular-nums; }
.host-workspace .sync-cta { display: inline-flex; flex-direction: column; gap: var(--space-1); }
.host-workspace .sync-cta-meta { margin: 0; font-size: var(--size-13); color: var(--ink-3); }
```

15. In `docs/design/catalog.json`, extend the `hooks` array with: `"row-menu-item", "row-menu-form", "row-action-send", "row-action-form", "send-all", "send-all-form", "sync-btn", "sync-cta", "sync-cta-form", "sync-cta-meta", "has-meta", "csv-in-filter", "btn-icon-label", "property-identity", "truncate", "guest-count", "inline", "source-badge"`. Command: `python3 scripts/design_lint.py`. Expected: OK.

16. Test edits. Replace Anchor N with:

```
PILL = re.compile(
    r'<span class="ui-badge ui-badge-[a-z]+(?: ui-badge-overdue)?" data-tone="([a-z]+)"(?: title="([^"]*)")?>(?:! )?([^<]*)</span>',
)
```

    Replace Anchor O with:

```
DEADLINE_SPAN = re.compile(r'data-deadline="([a-z_]+)"[^>]*>(?:! )?([^<]*)<')
```

    Replace Anchor P with:

```
                assert page.locator('.dashboard-row-task [data-tone="amber"]').count() >= 1
                ready_row = page.locator(f'.dashboard-row[data-stay-id="{dashboard_rich_host["ready"]}"]')
                assert ready_row.locator('.dashboard-row-task [data-tone="blue"]').count() == 1
```

    Command: `cd App && .venv/bin/python -m pytest tests/test_status_colours.py tests/test_deadline_after_reporting.py tests/test_send_controls.py tests/test_source_badge.py tests/test_overhaul.py -q --tb=short 2>&1 | tail -30`. Expected: passed, except assertions in `test_send_controls.py` lines 730 to 741 about `btn accent primary` in the stay detail, which belong to 0135 (report them, do not change them).

17. Create `App/tests/test_design_shared_macros.py`:

```python
"""_components.html badges and menus render the v2 catalog (MASTER 7.5, 7.8)."""
import re

from app.templating import templates


def _render(src, **ctx):
    env = templates.env
    ctx.setdefault("t", lambda key, **kw: key)
    ctx.setdefault("tp", lambda key, n, **kw: f"{key}:{n}")
    return env.from_string('{% from "_components.html" import progress_pill, submission_pill, row_menu_begin, row_menu_end, copy_button, bulk_send_ready, empty_state with context %}' + src).render(**ctx)


def test_progress_pill_maps_tones_to_kinds_and_keeps_the_tone():
    cases = {"failed": ("action", "red", "! "), "incomplete": ("action", "amber", ""), "ready": ("action", "blue", ""),
             "awaiting_guest": ("neutral", "teal", ""), "reported": ("done", "green", ""), "not_required": ("neutral", "grey", "")}
    for status, (kind, tone, mark) in cases.items():
        html = _render("{{ progress_pill(status) }}", status=status)
        assert f'class="ui-badge ui-badge-{kind}' in html and f'data-tone="{tone}"' in html, status
        assert (">" + mark) in html
    assert "ui-badge-overdue" in _render("{{ progress_pill('failed') }}")


def test_submission_pill_uses_attention_for_amber_and_overdue_for_red():
    assert 'ui-badge-attention' in _render("{{ submission_pill('partial') }}")
    assert 'ui-badge-action ui-badge-overdue' in _render("{{ submission_pill('error') }}")
    assert 'ui-badge-done' in _render("{{ submission_pill('ok') }}")


def test_row_menu_and_copy_button_use_catalog_classes_and_lucide():
    html = _render("{{ row_menu_begin() }}{{ row_menu_end() }}{{ copy_button('x') }}")
    assert 'class="ui-btn ui-btn-quiet ui-btn-icon ui-btn-compact row-menu-trigger"' in html
    assert 'data-icon="ellipsis-vertical"' in html and 'data-icon="copy"' in html
    assert 'class="row-menu-panel ui-menu-panel" role="menu" hidden' in html
    assert "<circle cx=\"3.25\"" not in html


def test_bulk_send_and_empty_state_are_secondary_and_v2():
    html = _render("{{ bulk_send_ready(2, '/') }}{{ empty_state('T', 'B', '/a', 'Go') }}")
    assert 'class="ui-btn ui-btn-secondary send-all"' in html and "(2)" in html
    assert '<div class="ui-empty" data-empty-state>' in html and 'class="ui-btn ui-btn-primary" href="/a"' in html
    assert re.search(r"<h2>T</h2>", html)
```

    Command: `cd App && .venv/bin/python -m pytest tests/test_design_shared_macros.py -q --tb=short -x 2>&1 | tail -30`. Expected: `4 passed`. If `templates.env` lacks `describe_time_left` or `source_mark` for a rendered macro, those macros are not rendered here; keep the test as written.

18. Commit: `git add App/app/templates/_components.html App/app/static/host2.css docs/design/catalog.json App/tests && git commit -m "0132 step 18: shared macros render v2 badges, menus and buttons"`.

## 5. Do not touch

`page_header`, `list_page_header`, `list_toolbar`, `onboarding_*`, `settings_*`, `nav_icon`, `help_tip`, `field_label` (they go with their pages or with 0143); any page template; status labels and tips (UbyPort copy); hard rules 1, 2, 3, 8.

## 6. Commands

- `python3 scripts/design_lint.py` expected: OK.
- `cd App && .venv/bin/python -m pytest tests/test_design_shared_macros.py tests/test_status_colours.py tests/test_deadline_after_reporting.py tests/test_first_property_step.py tests/test_stays_empty_workspace.py tests/test_properties_table_chips.py tests/test_signed_in_chrome.py -q --tb=short 2>&1 | tail -30` expected: passed except the page-owned assertions named in steps 10 and 16 (report them).
- `cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_quiet_dashboard_browser.py tests/test_host_stay_actions_browser.py tests/test_host_list_layouts_browser.py tests/test_host_geometry.py -q --tb=short 2>&1 | tail -30` expected: passed, 0 skipped.

## 7. Acceptance

- [ ] No `class="pill` remains in `_components.html`: `grep -c 'class="pill' App/app/templates/_components.html` prints `0`.
- [ ] No hand-drawn `<svg` remains in the edited macros: `grep -c '<svg' App/app/templates/_components.html` is lower than before and `nav_icon` is the only macro still holding svg markup.
- [ ] The listed tests pass with their regexes updated; no test deleted or skipped.
- [ ] One 390 px screenshot of the Stays list showing the new badges (via `UBYHOST_SHOTS_DIR` on `test_host_list_layouts_browser.py` or a manual Playwright shot).

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a test fails twice for a reason other than the page-owned assertions named above; you reach 25 tool calls or about 50k tokens (report as `blocked`); a new dependency seems needed; a file outside section 3 (plus the three empty-state test files) needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0132-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/templates/_components.html` (status mapping tables), the three regex edits in tests.

## Owner steps

None.
