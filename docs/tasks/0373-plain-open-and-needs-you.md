# 0373: Plain bordered Open on rows; "What needs you" lines with one look and equal buttons

Status: todo
Depends on: none | Base commit: a49cdaf | Branch: claude/project-thread-1am307 (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 25 tool calls, 50k tokens

## 1. Objective

Owner, 2026-10-25: he rejects the soft-coral `Open` from 0291 ("bring back the simple open button"). Every row/card Open becomes a plain bordered button (white, grey border, dark text), still with the word "Open", no arrow.
On the dashboard "What needs you" card the action buttons (Open the stay, Send the report, Send the guest link) have uneven widths and look plain. New line design: a round tinted icon on the left that shows urgency, the text, and a right-hand button. All buttons are the same width from 720 px up and full width on phones. Only the **first** line's button is solid coral (the next thing to do). The others are bordered secondary.

## 2. Context

- `App/app/static/host2.css`, the 0291 block starts with the comment `/* 0291: the soft-coral "Open"`. Its rule `.ui-btn-open, .host-workspace .row-open, .host-workspace .host-property-card-open { ... border: 1px solid var(--coral-500); ... background: var(--accent-soft); color: var(--accent-ink); ... }`, then hover/active lines using `--coral-200`.
- host2.css (~line 738), inside `@media (hover: hover)`, there is a line ending `:hover :is(.row-open, .host-property-card-open, .ui-btn-open) { background: var(--coral-200); border-color: var(--accent); }`.
- `App/app/templates/dashboard.html`: `{% macro needs_you_line(line) %}` renders `<li class="needs-you-item" ...>`, then `<div class="needs-you-copy">`, then the actions with `{{ ui_button(line.action, 'open', href=line.href, attrs='data-needs-you-go') }}`. It is called in two loops: `{% for line in ny_lines[:5] %}{{ needs_you_line(line) }}{% endfor %}` and `{% for line in ny_lines[5:] %}{{ needs_you_line(line) }}{% endfor %}`.
- `App/app/static/workflow.css` has the needs-you rules (lines ~68-130).
- Icons available through `icon(name, size)`: `triangle-alert`, `info`.

## 3. Files

| Path | Action |
|---|---|
| App/app/static/host2.css | edit the 0291 block + the hover line |
| App/app/templates/dashboard.html | edit the macro and the first loop |
| App/app/static/workflow.css | append one block |
| App/app/templates/base.html | keys: host2 `?v=20261025-0373`, workflow `?v=20261025-0373` |
| App/tests/static_versions.json | `--write` |
| App/tests/test_0373_needs_you_and_open.py | new |
| App/tests/test_design_dashboard.py | only if step 6 says so |

## 4. Steps

1. host2.css 0291 block: change the comment's first line to `/* 0291 + 0373: the plain "Open" (MASTER 7.1 `open`): a bordered text button on every`. In the main rule, set `border: 1px solid var(--line-strong);` `background: var(--surface);` `color: var(--ink);` (leave every other property alone). Change the hover line to `@media (hover: hover) { .ui-btn-open:hover { background: var(--state-hover); border-color: var(--ink); color: var(--ink); } }` and the active line to `.ui-btn-open:active { background: var(--state-press); }`.
2. host2.css ~738: change that line's declarations to `{ background: var(--state-hover); border-color: var(--ink); }`.
3. dashboard.html: macro signature becomes `{% macro needs_you_line(line, first=False) %}`. Directly after the `<li ...>` opening tag insert `<span class="needs-you-icon" aria-hidden="true">{{ icon('triangle-alert' if line.tone == 'red' else 'info', 18) }}</span>`. Change the button variant from `'open'` to `('primary' if first else 'secondary')`. In the first loop only, call `needs_you_line(line, loop.first)`.
4. Append to workflow.css:
```css
/* 0373: one look per line (owner 2026-10-25): a tinted icon says how urgent,
   the sentence says why, every button has the same width; only the top
   line's button is solid coral. */
.needs-you-item { grid-template-columns: auto minmax(0, 1fr); column-gap: var(--space-3); }
.needs-you-icon { display: inline-flex; align-items: center; justify-content: center; width: 36px; height: 36px; border-radius: 50%; background: var(--amber-100); color: var(--amber-700); }
.needs-you-item[data-tone="red"] .needs-you-icon { background: var(--red-100); color: var(--red-700); }
.needs-you-item[data-tone="grey"] .needs-you-icon { background: var(--surface-2); color: var(--ink-secondary); }
.needs-you-item > .needs-you-more { grid-column: 2 / -1; }
.needs-you-item > .needs-you-actions { grid-column: 1 / -1; }
.needs-you-actions > .ui-btn { width: 100%; justify-content: center; }
@media (min-width: 720px) {
  .needs-you-item { grid-template-columns: auto minmax(0, 1fr) auto; }
  .needs-you-item > .needs-you-actions { grid-column: 3; grid-row: 1; }
  .needs-you-actions > .ui-btn { width: auto; min-width: 14rem; }
}
```
5. Bump both keys, run `.venv/bin/python tests/test_static_versions.py --write` from `App/`.
6. Write `tests/test_0373_needs_you_and_open.py` with:
   - a test that `app/static/host2.css` no longer contains `var(--accent-soft)` inside the 0291 rule (read the file, take the text between `/* 0291 + 0373` and `/* 0292`, assert `accent-soft` and `coral-500` not in it).
   - a test that `app/templates/dashboard.html` contains `needs_you_line(line, loop.first)`, `needs-you-icon` and `'primary' if first else 'secondary'`, and does not contain `ui_button(line.action, 'open'`.
   Then run §6. If `tests/test_design_dashboard.py` fails only on `page.count('class="ui-btn ui-btn-primary"') == 1` because the needs-you card now adds a primary, change that assertion to `<= 2` and add the comment `# 0373: the page header and the top "What needs you" line may each have one.`

## 5. Do not touch

Everything outside §3. Do not rename classes. No new colours or tokens.

## 6. Commands

From `App/` (the env var makes browser tests run instead of skip):
```
UBYHOST_REQUIRE_BROWSER=1 UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests/test_0373_needs_you_and_open.py tests/test_0291_open_buttons.py tests/test_design_dashboard.py tests/test_needs_you_dashboard_0241.py tests/test_dashboard_phone_browser.py tests/test_host_quiet_dashboard_browser.py tests/test_0284_states_browser.py tests/test_0285_rows_browser.py tests/test_0252_touch_sweep_browser.py tests/test_static_versions.py -q --tb=short 2>&1 | tail -30
cd .. && python3 scripts/design_lint.py 2>&1 | tail -5
```
If a test fails, put its first assertion line in the report and stop (do not try other CSS).

## 7. Acceptance

- [ ] The §6 commands pass, or the failure is in the report.

## 8. Stop and ask

As in TEMPLATE §8.

## 9. Report

`docs/tasks/0373-report.md` (200 tokens), `Status: review`. One commit `0373: plain Open, even What needs you buttons`. Do not push.
