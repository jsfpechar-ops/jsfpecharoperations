# 0093a report: shared help-tip foundation

Scope: macro, CSS, JS, one proof use. The host-wide pass (rest of 0093) is not done; 0093 stays `todo`.

## Macros (App/app/templates/_components.html)

```jinja
{% macro help_tip(id, text, guide_href='') %}
{% macro field_label(for, text, help_text='', optional=false, guide_href='') %}
```

- `help_tip` renders a `<button type="button" class="help-tip-btn" aria-label="Help|Nápověda" aria-expanded aria-controls=id>?</button>` and a `role="tooltip"` span with that `id`. `id` must be unique per page. `text` is escaped. `guide_href` (e.g. `/guide#housebook`) adds a "Read more" link inside the tip.
- `field_label` renders `<div class="field-label-row"><label for>...</label>` plus the tip (id = `<for>-help`) when `help_text` is given. The `?` sits outside the `<label>` tag.
- Import with context (they call `t()`): `{% from "_components.html" import field_label, help_tip with context %}`

Usage (apartment_form.html):

```jinja
{{ field_label('permalink_window_days', t('apartment.form.guest_link.window_label'), t('apartment.form.guest_link.window_hint')) }}
<input type="number" id="permalink_window_days" ...>
```

Standalone: `{{ help_tip('pin-help', t('...'), '/guide#guests') }}` next to a label.

## Behaviour

- JS (`initHelpTips` in app.js, called on DOMContentLoaded): mouse hover and keyboard focus (focus-visible) open; click/tap pins open and toggles; Esc and outside click close; Esc returns focus to the `?`. The tip is `position: fixed`, clamped 8px inside the viewport, flips above when short of room, repositions on scroll/resize.
- No JS: CSS `:hover` / `:focus-within` shows the tip (it is absolutely positioned under the label row).
- CSS lives in one block `/* 0093 help */` at the end of host.css. 22px visual button with a 44px hit area.
- i18n keys added in host_i18n.py: `help.tip.label`, `help.tip.more` (EN and CS).

## Gotchas for copiers

- Esc is also handled by host.js (closes `.host-tools` and `[data-host-account]` menus and focuses their summary); irrelevant unless one is open.
- The tip is a tooltip role, not interactive; a Guide link inside is still tabbable.

## Verification

- tests/test_host_help_browser.py: 2 tests (hover, focus, tap, Esc, outside click, aria, unique ids, no form submit, fit at 360/390/1280, EN/CS, 44px target, no-JS reachability). Pass.
- Also green: test_host_property_controls_browser.py, test_host_i18n.py, test_privacy_first.py; context_lint OK. No test referenced `guest_link.window_hint`.
- Evidence: docs/tasks/0093-evidence/help-{360,390,1280}-{en,cs}.png.
