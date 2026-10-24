# 0291: Soft-coral "Open" buttons on rows and cards, What-needs-you button at the edge

Status: todo
Depends on: none | Base commit: 92646d3 | Branch: claude/project-thread-1am307 (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The owner (2026-10-24) wants every row and card to show a plain, highlighted "Open" text button instead of the round arrow pill, and the "What needs you" action button to sit at the card's right edge. The owner chose a **soft coral** look (light coral fill, coral border and text), so the one solid coral primary of each group still stands out.

## 2. Context

- MASTER 7.1 now has the `open` variant: fill `--accent-soft`, 1 px `--coral-200` border, text `--accent-ink`; hover fill `--coral-200`. No arrow icon.
- `row_open()` in `App/app/templates/_components.html` (line ~502) is today:

```jinja
{% macro row_open() -%}
<span class="row-open" aria-hidden="true"><span class="row-open-text">{{ t('common.open') }}</span>{{ icon('chevron-right', 16) }}</span>
{%- endmacro %}
```

- The property cards use the same pill: `App/app/templates/_property_overview.html` line ~38 (`open_pill`) and `App/app/templates/settings.html` line 14, both ending `{{ icon('chevron-right', 16) }}</span>`.
- `App/app/templates/dashboard.html` line 78: `{% if line.href %}{{ ui_button(line.action, 'secondary', href=line.href, attrs='data-needs-you-go') }}{% endif %}`
- `App/app/static/workflow.css` lines ~123-127: at ≥720 px `.needs-you-actions` is a grid `auto var(--control-h)` so an empty slot for the dismiss "x" sits right of every button. That empty slot is the "weird placement" the owner saw.
- `App/app/templates/cleaning_properties.html` line 9: each property is `<a class="cleaning-panel" ...><strong>{{ home.internal_name }}</strong><span>{{ ct('settings') }} →</span></a>`; the name runs into the repeated page title. It becomes a row with the name and an "Open" button.
- host2.css lint: no raw colours, no bare px except 0 and 1 (use tokens: `--control-h-compact`, `--space-*`, `--size-13`, `--radius-md`).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/_components.html | edit | step 1 |
| App/app/templates/_property_overview.html | edit | step 2 |
| App/app/templates/settings.html | edit | step 2 |
| App/app/templates/dashboard.html | edit | step 3 |
| App/app/templates/cleaning_properties.html | edit | step 4 |
| App/app/static/host2.css | append + one-line edit | step 5 |
| App/app/static/workflow.css | edit | step 6 |
| App/app/static/cleaning.css | append | step 4 |
| App/app/templates/base.html | edit | `?v=` keys, step 7 |
| App/app/templates/cleaning_shared.html | edit only if it references a changed file's key | step 7 |
| App/tests/static_versions.json | regenerate | step 7 |
| App/tests/test_0291_open_buttons.py | new | step 8 |

No other file may change, except a test assertion that pinned the old arrow/`secondary` look (report each one).

## 4. Steps

1. `_components.html`: replace the `row_open` macro body with
   `<span class="row-open" aria-hidden="true"><span class="row-open-text">{{ t('common.open') }}</span></span>` (drop the icon; keep both classes).
2. `_property_overview.html` and `settings.html`: delete `{{ icon('chevron-right', 16) }}` inside the `host-property-card-open` span. Nothing else.
3. `dashboard.html` line 78: change `'secondary'` to `'open'` (gives `class="ui-btn ui-btn-open"`).
4. `cleaning_properties.html` line 9: replace the `<a class="cleaning-panel" …>…</a>` with
   `<a class="cleaning-panel cleaning-property-row" href="/cleaning/properties/{{ home.id }}"><strong>{{ home.internal_name }}</strong><span class="ui-btn ui-btn-open ui-btn-compact" aria-hidden="true">{{ t('common.open') }}</span></a>`
   and append to `cleaning.css`:
   ```css
   /* 0291: one row per property: the name left, a visible Open right. */
   body.host-workspace .cleaning-property-links { grid-template-columns: minmax(0, 1fr); gap: var(--space-3); }
   body.host-workspace .cleaning-page .cleaning-property-row { display: flex; flex-direction: row; align-items: center; justify-content: space-between; gap: var(--space-4); margin: 0; }
   body.host-workspace .cleaning-property-row strong { font-size: var(--size-16); font-weight: 600; min-width: 0; overflow-wrap: anywhere; }
   body.host-workspace .cleaning-property-row .ui-btn { flex: 0 0 auto; }
   ```
5. host2.css: in the 0284 block, change the line
   `.host-workspace :is(tbody tr.clickable-row, .ui-table .ui-row, .host-property-card, .needs-you-item):hover :is(.row-open, .host-property-card-open, [data-needs-you-go]) { border-color: var(--ink); }`
   to
   `.host-workspace :is(tbody tr.clickable-row, .ui-table .ui-row, .host-property-card, .needs-you-item, .cleaning-property-row):hover :is(.row-open, .host-property-card-open, .ui-btn-open) { background: var(--coral-200); border-color: var(--accent); }`
   Then append at the end of host2.css:
   ```css
   /* 0291: the soft-coral "Open" (MASTER 7.1 `open`): a text button on every
      row and card, never a bare arrow (owner 2026-10-24). */
   .ui-btn-open,
   .host-workspace .row-open,
   .host-workspace .host-property-card-open { display: inline-flex; align-items: center; justify-content: center; width: auto; height: auto; min-height: var(--control-h-compact); padding: 0 var(--space-3); border: 1px solid var(--coral-200); border-radius: var(--radius-md); background: var(--accent-soft); color: var(--accent-ink); font-size: var(--size-13); font-weight: 600; line-height: 1.2; white-space: nowrap; text-decoration: none; }
   .host-workspace :is(.row-open-text, .host-property-card-open-text) { position: static; display: inline; width: auto; height: auto; overflow: visible; clip: auto; }
   @media (hover: hover) { .ui-btn-open:hover { background: var(--coral-200); border-color: var(--accent); color: var(--accent-ink); } }
   .ui-btn-open:active { background: var(--coral-200); }
   .ui-btn-open:focus-visible { outline: 3px solid var(--focus-ring); outline-offset: 2px; }
   ```
   If `--focus-ring` is not defined in tokens.css, use the token the other `:focus-visible` rules in host2.css use.
6. workflow.css: replace
   `  .needs-you-actions { display: grid; grid-template-columns: auto var(--control-h); justify-items: end; }`
   with
   ```css
     .needs-you-actions { display: grid; grid-template-columns: auto; justify-items: end; }
     /* 0291: the x slot only exists when a line in this list can be dismissed; otherwise the button sits on the card's right edge. */
     .needs-you-list:has(.needs-you-dismiss) .needs-you-actions { grid-template-columns: auto var(--control-h); }
   ```
7. Bump keys in base.html: host2.css → `?v=20261024-0291`, workflow.css → `?v=20261024-0291`, cleaning.css → `?v=20261024-0291`. Then `.venv/bin/python tests/test_static_versions.py --write`.
8. New `App/tests/test_0291_open_buttons.py` using the `host_with_property` fixture (import as in `tests/test_design_dashboard.py`):
   - `/apartments?lang=en`: the page has `class="row-open"` and no `chevron-right` inside any `row-open` span (split on `class="row-open"` and check the next 200 chars).
   - `/cleaning/properties?lang=en`: has `ui-btn ui-btn-open` and does not contain `→</span>`.
   - `App/app/static/workflow.css` text contains `.needs-you-list:has(.needs-you-dismiss)`.

## 5. Do not touch

Python routes, i18n files, any other template. AGENTS hard rules 6 (light mode), 7 (screenshots), 8 (no push to main).

## 6. Commands

From `App/`:
```
.venv/bin/python -m pytest tests/test_0291_open_buttons.py tests/test_design_dashboard.py tests/test_design_cleaning.py tests/test_static_versions.py tests/test_0285_rows_browser.py tests/test_0252_touch_sweep_browser.py tests/test_host_list_layouts_browser.py tests/test_onboarding_followup_browser.py tests/test_host_stay_actions_browser.py tests/test_design_guardrails_browser.py -q --tb=short 2>&1 | tail -30
```
A geometry test that fails only because the Open button is now wider than 28 px: report it, do not loosen it (the orchestrator decides).

## 7. Acceptance

- [ ] No `chevron-right` inside `row-open` / `host-property-card-open`.
- [ ] Dashboard needs-you button is `ui-btn ui-btn-open`; with no dismissable line it ends at the line's right padding.
- [ ] Cleaning properties page shows name left, Open right.
- [ ] Keys bumped, static_versions.json regenerated.
- [ ] Commands above run; failures listed in the report.

## 8. Stop and ask

As in TEMPLATE §8.

## 9. Report

Write `docs/tasks/0291-report.md` (600 tokens at most), `Status: review`. Commit with message `0291: soft-coral Open buttons, needs-you button at the edge`.

## Risk list (for the reviewer)

host2.css 0284 line, workflow.css, _components.html.

## Owner steps

None (part of the PR).
