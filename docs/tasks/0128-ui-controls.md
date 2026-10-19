# 0128: v2 controls: button, field, badge, chip, menu, dialog, toast, empty state, tip, pagination

Status: todo
Depends on: 0127 | Base commit: df8b842 | Branch: claude/project-thread-td6fpc
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Part of [design-v2](../plans/design-v2.md). Commit each step as `0128 step k`. Never push, never open a PR.

## 1. Objective

Create `App/app/templates/_ui.html` (the v2 component macros) and the first half of `App/app/static/host2.css` (controls and small components, tokens only), and load `host2.css` last in `base.html`. No page uses them yet; the catalog page (0131) and the page briefs do. This replaces the 20 one-off button styles with four variants (MASTER 7.1, 7.2, 7.5, 7.7 to 7.13).

## 2. Context

Rules: MASTER 2 (tokens only), 7 (catalog), 9 (44 px targets below 1024, focus ring), 10. The design lint (0126) checks `host2.css` for raw values: every length comes from a token; `0` and `1px` borders are allowed. Old sheets still load before `host2.css`; v2 selectors are prefixed `.host-workspace .ui-` so they win.

Anchor A, `App/app/templates/base.html`:

```
  <link rel="stylesheet" href="/static/host-design0123.css?v=20261016-0123f">
  {% endif %}
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/_ui.html` | create | macros: `ui_button`, `ui_icon_button`, `ui_badge`, `ui_chip`, `ui_field`, `ui_select`, `ui_textarea`, `ui_check`, `ui_toggle`, `ui_menu_begin`, `ui_menu_end`, `ui_menu_item`, `ui_dialog_begin`, `ui_dialog_end`, `ui_empty`, `ui_tip`, `ui_pagination`, `ui_pdot` |
| `App/app/static/host2.css` | create | tokens-only rules for the classes above |
| `App/app/templates/base.html` | edit | load `host2.css` after `host-design0123.css` |
| `App/tests/test_design_ui_macros.py` | create | renders every macro and checks classes, states and the one-primary rule |

No other file may change.

## 4. Steps

1. Create `App/app/templates/_ui.html`:

```
{#- Design v2 component macros (docs/design/MASTER.md section 7). Every class
    here is in docs/design/catalog.json; a template may use nothing else. -#}
{% from "_icons.html" import icon with context %}

{#- 7.1 button. variant: primary | secondary | quiet | danger. size: regular | compact.
    href renders <a>, otherwise <button type=...>. attrs is raw attribute text. -#}
{% macro ui_button(label, variant='secondary', href='', type='button', size='regular', icon_name='', loading=false, disabled=false, attrs='', id='') -%}
{%- set classes = 'ui-btn ui-btn-' ~ variant ~ (' ui-btn-compact' if size == 'compact') ~ (' ui-btn-loading' if loading) -%}
{%- if href -%}
<a class="{{ classes }}" href="{{ href }}"{% if id %} id="{{ id }}"{% endif %}{% if disabled %} aria-disabled="true" tabindex="-1"{% endif %}{% if loading %} aria-busy="true"{% endif %} {{ attrs | safe }}>{% if icon_name %}{{ icon(icon_name, 16) }}{% endif %}<span>{{ label }}</span></a>
{%- else -%}
<button class="{{ classes }}" type="{{ type }}"{% if id %} id="{{ id }}"{% endif %}{% if disabled %} disabled{% endif %}{% if loading %} aria-busy="true"{% endif %} {{ attrs | safe }}>{% if icon_name %}{{ icon(icon_name, 16) }}{% endif %}<span>{{ label }}</span></button>
{%- endif -%}
{%- endmacro %}

{#- icon-only button: the label becomes aria-label and title. -#}
{% macro ui_icon_button(label, icon_name, variant='quiet', href='', type='button', size='regular', attrs='') -%}
{%- set classes = 'ui-btn ui-btn-' ~ variant ~ ' ui-btn-icon' ~ (' ui-btn-compact' if size == 'compact') -%}
{%- if href -%}<a class="{{ classes }}" href="{{ href }}" aria-label="{{ label }}" title="{{ label }}" {{ attrs | safe }}>{{ icon(icon_name, 16) }}</a>
{%- else -%}<button class="{{ classes }}" type="{{ type }}" aria-label="{{ label }}" title="{{ label }}" {{ attrs | safe }}>{{ icon(icon_name, 16) }}</button>{%- endif -%}
{%- endmacro %}

{#- 7.5 badge. kind: action | attention | done | neutral. overdue prefixes "!" and a border. -#}
{% macro ui_badge(kind, label, overdue=false) -%}
<span class="ui-badge ui-badge-{{ kind }}{{ ' ui-badge-overdue' if overdue }}">{% if overdue %}! {% endif %}{{ label }}</span>
{%- endmacro %}

{#- 7.7 chip: a link (href) or a button; selected is ink, never coral. -#}
{% macro ui_chip(label, href='', selected=false, remove_href='', attrs='') -%}
{%- if href -%}<a class="ui-chip" href="{{ href }}"{% if selected %} aria-current="true"{% endif %} {{ attrs | safe }}>{{ label }}</a>
{%- else -%}<button class="ui-chip" type="button" aria-pressed="{{ 'true' if selected else 'false' }}" {{ attrs | safe }}>{{ label }}{% if remove_href %}{% endif %}</button>{%- endif -%}
{%- endmacro %}

{#- 7.2 text input. error renders the message under the field with aria-describedby. -#}
{% macro ui_field(id, label, name='', value='', type='text', help='', error='', optional=false, attrs='', placeholder='') -%}
<div class="ui-field{{ ' ui-field-err' if error }}">
  <label class="ui-label" for="{{ id }}">{{ label }}{% if optional %} <span class="ui-opt">{{ t('common.optional') }}</span>{% endif %}</label>
  <input class="ui-input" id="{{ id }}" name="{{ name or id }}" type="{{ type }}" value="{{ value }}"{% if placeholder %} placeholder="{{ placeholder }}"{% endif %}{% if error %} aria-invalid="true" aria-describedby="{{ id }}-error"{% elif help %} aria-describedby="{{ id }}-help"{% endif %} {{ attrs | safe }}>
  {% if error %}<span class="ui-error" id="{{ id }}-error">{{ icon('triangle-alert', 16) }}{{ error }}</span>{% elif help %}<span class="ui-help" id="{{ id }}-help">{{ help }}</span>{% endif %}
</div>
{%- endmacro %}

{#- select: options is a list of (value, label); the caller passes the chosen value. -#}
{% macro ui_select(id, label, options, selected='', name='', help='', error='', optional=false, attrs='') -%}
<div class="ui-field{{ ' ui-field-err' if error }}">
  <label class="ui-label" for="{{ id }}">{{ label }}{% if optional %} <span class="ui-opt">{{ t('common.optional') }}</span>{% endif %}</label>
  <select class="ui-select" id="{{ id }}" name="{{ name or id }}"{% if error %} aria-invalid="true" aria-describedby="{{ id }}-error"{% elif help %} aria-describedby="{{ id }}-help"{% endif %} {{ attrs | safe }}>
    {% for value, text in options %}<option value="{{ value }}"{% if value | string == selected | string %} selected{% endif %}>{{ text }}</option>{% endfor %}
  </select>
  {% if error %}<span class="ui-error" id="{{ id }}-error">{{ icon('triangle-alert', 16) }}{{ error }}</span>{% elif help %}<span class="ui-help" id="{{ id }}-help">{{ help }}</span>{% endif %}
</div>
{%- endmacro %}

{% macro ui_textarea(id, label, value='', name='', help='', error='', optional=false, rows=3, attrs='') -%}
<div class="ui-field{{ ' ui-field-err' if error }}">
  <label class="ui-label" for="{{ id }}">{{ label }}{% if optional %} <span class="ui-opt">{{ t('common.optional') }}</span>{% endif %}</label>
  <textarea class="ui-textarea" id="{{ id }}" name="{{ name or id }}" rows="{{ rows }}"{% if error %} aria-invalid="true" aria-describedby="{{ id }}-error"{% elif help %} aria-describedby="{{ id }}-help"{% endif %} {{ attrs | safe }}>{{ value }}</textarea>
  {% if error %}<span class="ui-error" id="{{ id }}-error">{{ icon('triangle-alert', 16) }}{{ error }}</span>{% elif help %}<span class="ui-help" id="{{ id }}-help">{{ help }}</span>{% endif %}
</div>
{%- endmacro %}

{% macro ui_check(id, label, name='', checked=false, value='1', attrs='') -%}
<label class="ui-check" for="{{ id }}"><input class="ui-input" type="checkbox" id="{{ id }}" name="{{ name or id }}" value="{{ value }}"{% if checked %} checked{% endif %} {{ attrs | safe }}><span>{{ label }}</span></label>
{%- endmacro %}

{#- toggle: a real checkbox styled as a switch, so it works without JavaScript. -#}
{% macro ui_toggle(id, label, name='', checked=false, attrs='') -%}
<label class="ui-toggle" for="{{ id }}"><span>{{ label }}</span><input class="ui-input ui-switch" type="checkbox" role="switch" id="{{ id }}" name="{{ name or id }}" value="1"{% if checked %} checked{% endif %} {{ attrs | safe }}></label>
{%- endmacro %}

{#- 7.8 menu: trigger plus a panel of items. Reuses the row-menu JS hooks in app.js
    (row-menu-trigger / row-menu-panel are functional hooks listed in catalog.json). -#}
{% macro ui_menu_begin(label='') -%}
<span class="ui-menu row-menu" data-row-menu>
  <button class="ui-btn ui-btn-quiet ui-btn-icon ui-btn-compact row-menu-trigger" type="button" aria-haspopup="menu" aria-expanded="false" aria-label="{{ label or t('common.actions') }}" title="{{ label or t('common.actions') }}">{{ icon('ellipsis-vertical', 16) }}</button>
  <span class="ui-menu-panel row-menu-panel" role="menu" hidden>
{%- endmacro %}
{% macro ui_menu_end() -%}
  </span>
</span>
{%- endmacro %}
{% macro ui_menu_item(label, href='', danger=false, icon_name='', attrs='') -%}
{%- if href -%}<a class="ui-menu-item{{ ' ui-menu-danger' if danger }}" role="menuitem" href="{{ href }}" {{ attrs | safe }}>{% if icon_name %}{{ icon(icon_name, 16) }}{% endif %}{{ label }}</a>
{%- else -%}<button class="ui-menu-item{{ ' ui-menu-danger' if danger }}" role="menuitem" type="submit" {{ attrs | safe }}>{% if icon_name %}{{ icon(icon_name, 16) }}{% endif %}{{ label }}</button>{%- endif -%}
{%- endmacro %}

{#- 7.9 dialog: a native <dialog>; CSS turns it into a bottom sheet below 768. -#}
{% macro ui_dialog_begin(id, title) -%}
<dialog id="{{ id }}" class="ui-dialog" aria-labelledby="{{ id }}-title">
  <div class="ui-sheet">
    <span class="ui-sheet-handle" aria-hidden="true"></span>
    <h2 id="{{ id }}-title">{{ title }}</h2>
{%- endmacro %}
{% macro ui_dialog_end() -%}
  </div>
</dialog>
{%- endmacro %}

{#- 7.11 empty state: title, one sentence, one button. -#}
{% macro ui_empty(title, body='', action_label='', action_href='', primary=true) -%}
<div class="ui-empty" data-empty-state>
  <h2>{{ title }}</h2>
  {% if body %}<p>{{ body }}</p>{% endif %}
  {% if action_href %}{{ ui_button(action_label, 'primary' if primary else 'secondary', href=action_href) }}{% endif %}
  {% if caller is defined %}{{ caller() }}{% endif %}
</div>
{%- endmacro %}

{#- 7.12 help tip: reuses the help-tip JS hooks. -#}
{% macro ui_tip(id, text, href='') -%}
<span class="ui-tip help-tip" data-help-tip><button type="button" class="ui-btn ui-btn-quiet ui-btn-icon ui-btn-compact help-tip-btn" aria-label="{{ t('help.tip.label') }}" aria-expanded="false" aria-controls="{{ id }}">{{ icon('circle-help', 16) }}</button><span class="help-tip-body" id="{{ id }}" role="tooltip">{{ text }}{% if href %} <a href="{{ href }}">{{ t('help.tip.more') }}</a>{% endif %}</span></span>
{%- endmacro %}

{#- 7.13 pagination: phone shows one "Show more" link; desktop Previous / Next. -#}
{% macro ui_pagination(page, pages, prev_url='', next_url='', label='', more_label='', prev_label='', next_label='') -%}
<nav class="ui-pagination" aria-label="{{ label }}">
  {% if next_url %}{{ ui_button(more_label, 'secondary', href=next_url, attrs='data-pagination-more') }}{% endif %}
  <span class="ui-num">{{ page }} / {{ pages }}</span>
  {% if prev_url %}{{ ui_button(prev_label, 'secondary', href=prev_url, size='compact') }}{% else %}{{ ui_button(prev_label, 'secondary', size='compact', disabled=true) }}{% endif %}
  {% if next_url %}{{ ui_button(next_label, 'secondary', href=next_url, size='compact') }}{% else %}{{ ui_button(next_label, 'secondary', size='compact', disabled=true) }}{% endif %}
</nav>
{%- endmacro %}

{#- property identity dot: index 1 to 4 cycles the property tokens. -#}
{% macro ui_pdot(index, name) -%}
<span class="ui-pdot" data-property="{{ (index | int % 4) + 1 }}">{{ name }}</span>
{%- endmacro %}
```

   Command: `cd App && .venv/bin/python -c "
import jinja2;env=jinja2.Environment(loader=jinja2.FileSystemLoader('app/templates'));env.globals['t']=lambda k,**kw:k
print(env.from_string('{% from \"_ui.html\" import ui_button, ui_badge %}{{ ui_button(\"Save\",\"primary\") }}{{ ui_badge(\"action\",\"x\",true) }}').render())"`. Expected: a `<button class="ui-btn ui-btn-primary" type="button" >…` and `<span class="ui-badge ui-badge-action ui-badge-overdue">! x</span>`.

2. Create `App/app/static/host2.css` (part 1; 0129 appends part 2):

```
/* UbyHost host app v2 stylesheet. docs/design/MASTER.md is the rule book.
   Tokens only (scripts/design_lint.py S1, S2). Scoped to .host-workspace so
   it wins over the sheets loaded before it until 0142 deletes them. */

/* ---- 7.1 buttons ---- */
.host-workspace .ui-btn { display: inline-flex; align-items: center; justify-content: center; gap: var(--space-2); min-height: var(--control-h); height: var(--control-h); padding: 0 var(--control-px); border-radius: var(--control-radius); font: inherit; font-size: var(--control-font); font-weight: var(--control-weight); line-height: 1; cursor: pointer; text-decoration: none; border: 1px solid transparent; white-space: nowrap; position: relative; transition: background var(--motion-1) var(--ease-standard); box-shadow: none; }
.host-workspace .ui-btn-primary { background: var(--accent); color: var(--on-accent); }
.host-workspace .ui-btn-primary:hover { background: var(--accent-hover); color: var(--on-accent); }
.host-workspace .ui-btn-secondary { background: var(--surface); color: var(--ink); border-color: var(--line-strong); }
.host-workspace .ui-btn-secondary:hover { background: var(--surface-2); color: var(--ink); }
.host-workspace .ui-btn-quiet { background: transparent; color: var(--ink-2); }
.host-workspace .ui-btn-quiet:hover { background: var(--surface-2); color: var(--ink); }
.host-workspace .ui-btn-danger { background: var(--surface); color: var(--danger); border-color: var(--danger); }
.host-workspace .ui-btn-danger:hover { background: var(--danger-bg); color: var(--danger); }
.host-workspace .ui-btn:active { transform: none; filter: none; background: var(--surface-3); }
.host-workspace .ui-btn-primary:active { background: var(--accent-pressed); }
.host-workspace .ui-btn-compact { min-height: var(--control-h-compact); height: var(--control-h-compact); padding: 0 var(--space-3); font-size: var(--size-13); }
.host-workspace .ui-btn-icon { width: var(--control-h); padding: 0; }
.host-workspace .ui-btn-icon.ui-btn-compact { width: var(--control-h-compact); }
.host-workspace .ui-btn:disabled, .host-workspace .ui-btn[aria-disabled="true"] { opacity: 0.5; cursor: not-allowed; pointer-events: none; }
.host-workspace .ui-btn-loading { color: transparent; pointer-events: none; }
.host-workspace .ui-btn-loading::after { content: ""; position: absolute; width: var(--space-4); height: var(--space-4); border: 2px solid var(--on-accent); border-right-color: transparent; border-bottom-color: transparent; border-radius: var(--radius-pill); animation: ui-spin 0.7s linear infinite; }
.host-workspace .ui-btn-secondary.ui-btn-loading::after, .host-workspace .ui-btn-quiet.ui-btn-loading::after { border-color: var(--ink); border-right-color: transparent; border-bottom-color: transparent; }
@keyframes ui-spin { to { transform: rotate(360deg); } }
.host-workspace .ui-btn-group { display: flex; gap: var(--space-2); flex-wrap: wrap; align-items: center; }
.host-workspace .ui-btn .ui-icon { flex: none; }
.host-workspace :is(.ui-btn, .ui-chip, .ui-input, .ui-select, .ui-textarea, .ui-menu-item, .ui-tab):focus-visible { outline: 0; box-shadow: var(--focus-ring-2); }

/* ---- 7.2 fields ---- */
.host-workspace .ui-field { display: flex; flex-direction: column; gap: var(--space-1); margin: 0 0 var(--space-4); min-width: 0; }
.host-workspace .ui-label { font-size: var(--size-14); font-weight: var(--control-weight); color: var(--ink); }
.host-workspace .ui-opt { color: var(--ink-3); font-weight: 400; }
.host-workspace .ui-field .ui-input:not([type="checkbox"]):not([type="radio"]), .host-workspace .ui-field .ui-select, .host-workspace .ui-field .ui-textarea { min-height: var(--input-h); height: var(--input-h); width: 100%; box-sizing: border-box; border: 1px solid var(--input-border); border-radius: var(--input-radius); padding: 0 var(--input-px); font: inherit; font-size: var(--body-size); color: var(--ink); background: var(--surface); box-shadow: none; }
.host-workspace .ui-field .ui-textarea { height: auto; min-height: calc(var(--input-h) * 2); padding: var(--space-3) var(--input-px); resize: vertical; }
.host-workspace .ui-field .ui-select { padding-right: calc(var(--space-8) + var(--space-1)); appearance: none; background-image: linear-gradient(45deg, transparent 50%, var(--ink-2) 50%), linear-gradient(135deg, var(--ink-2) 50%, transparent 50%); background-position: calc(100% - var(--space-5)) 50%, calc(100% - var(--space-4)) 50%; background-size: var(--space-1) var(--space-1); background-repeat: no-repeat; }
.host-workspace .ui-field :is(.ui-input, .ui-select, .ui-textarea):focus { border-color: var(--accent); }
.host-workspace .ui-field-err :is(.ui-input, .ui-select, .ui-textarea) { border-color: var(--danger); }
.host-workspace .ui-help { font-size: var(--size-13); color: var(--ink-3); }
.host-workspace .ui-error { display: flex; gap: var(--space-1); align-items: center; font-size: var(--size-13); color: var(--danger); }
.host-workspace .ui-pair { display: grid; grid-template-columns: 1fr 1fr; gap: 0 var(--space-4); }
.host-workspace .ui-check { display: flex; align-items: center; gap: var(--space-3); min-height: var(--control-h-phone); font-size: var(--body-size); color: var(--ink); }
.host-workspace .ui-check .ui-input { width: var(--space-5); height: var(--space-5); accent-color: var(--accent); margin: 0; }
.host-workspace .ui-toggle { display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); min-height: var(--control-h-phone); font-size: var(--body-size); color: var(--ink); }
.host-workspace .ui-switch { appearance: none; width: var(--control-h-phone); height: var(--space-6); border-radius: var(--radius-pill); background: var(--line-strong); position: relative; margin: 0; cursor: pointer; border: 0; flex: none; }
.host-workspace .ui-switch::after { content: ""; position: absolute; top: 2px; left: 2px; width: var(--space-5); height: var(--space-5); border-radius: var(--radius-pill); background: var(--surface); transition: left var(--motion-1) var(--ease-standard); }
.host-workspace .ui-switch:checked { background: var(--accent); }
.host-workspace .ui-switch:checked::after { left: calc(100% - var(--space-5) - 2px); }
.host-workspace .ui-form-actions { display: flex; justify-content: flex-end; gap: var(--space-2); padding-top: var(--space-2); }
.host-workspace .ui-sticky-actions { display: none; }
.host-workspace .ui-steps { color: var(--ink-3); font-size: var(--size-14); margin: 0 0 var(--space-4); }

/* ---- 7.5 badge, identity dot ---- */
.host-workspace .ui-badge { display: inline-flex; align-items: center; gap: var(--space-1); height: var(--badge-h); padding: 0 var(--badge-px); border-radius: var(--badge-radius); font-size: var(--badge-font); font-weight: var(--control-weight); line-height: 1; white-space: nowrap; vertical-align: middle; }
.host-workspace .ui-badge::before { content: ""; width: var(--space-1); height: var(--space-1); padding: 1px; border-radius: var(--radius-pill); background: var(--ui-dot); }
.host-workspace .ui-badge-action { --ui-dot: var(--st-action-dot); background: var(--st-action-bg); color: var(--st-action-ink); }
.host-workspace .ui-badge-attention { --ui-dot: var(--st-attention-dot); background: var(--st-attention-bg); color: var(--st-attention-ink); }
.host-workspace .ui-badge-done { --ui-dot: var(--st-done-dot); background: var(--st-done-bg); color: var(--st-done-ink); }
.host-workspace .ui-badge-neutral { --ui-dot: var(--st-neutral-dot); background: var(--st-neutral-bg); color: var(--st-neutral-ink); }
.host-workspace .ui-badge-overdue { border: 1px solid var(--st-action-dot); }
.host-workspace .ui-pdot { display: inline-flex; align-items: center; gap: var(--space-2); }
.host-workspace .ui-pdot::before { content: ""; width: var(--space-2); height: var(--space-2); border-radius: var(--radius-pill); background: var(--property-1); flex: none; }
.host-workspace .ui-pdot[data-property="2"]::before { background: var(--property-2); }
.host-workspace .ui-pdot[data-property="3"]::before { background: var(--property-3); }
.host-workspace .ui-pdot[data-property="4"]::before { background: var(--property-4); }
.host-workspace .ui-num { font-variant-numeric: tabular-nums; }
.host-workspace .ui-mono { font-family: var(--font-mono); font-size: var(--size-14); }

/* ---- 7.7 chips ---- */
.host-workspace .ui-chips { display: flex; gap: var(--space-2); flex-wrap: wrap; }
.host-workspace .ui-chip { display: inline-flex; align-items: center; gap: var(--space-1); height: var(--control-h-compact); padding: 0 var(--space-3); border-radius: var(--radius-pill); background: var(--surface-2); color: var(--ink-2); font: inherit; font-size: var(--size-14); font-weight: 500; text-decoration: none; border: 0; cursor: pointer; }
.host-workspace .ui-chip:hover { background: var(--surface-3); color: var(--ink); }
.host-workspace .ui-chip[aria-pressed="true"], .host-workspace .ui-chip[aria-current="true"] { background: var(--ink); color: var(--surface); }

/* ---- 7.8 menu ---- */
.host-workspace .ui-menu { position: relative; display: inline-flex; }
.host-workspace .ui-menu-panel { position: absolute; right: 0; top: calc(100% + var(--space-1)); min-width: calc(var(--space-12) * 4 + var(--space-6)); background: var(--surface); border: 1px solid var(--line); border-radius: var(--card-radius); box-shadow: var(--shadow-2); padding: var(--space-2); z-index: var(--z-popover); display: none; flex-direction: column; }
.host-workspace .ui-menu-panel.is-open, .host-workspace .ui-menu-panel:not([hidden]) { display: flex; }
.host-workspace .ui-menu-item { display: flex; align-items: center; gap: var(--space-3); min-height: var(--control-h); padding: 0 var(--space-3); border-radius: var(--radius-2); color: var(--ink); text-decoration: none; font: inherit; font-size: var(--body-size); background: transparent; border: 0; width: 100%; text-align: left; cursor: pointer; white-space: nowrap; }
.host-workspace .ui-menu-item:hover { background: var(--surface-2); }
.host-workspace .ui-menu-danger { color: var(--danger); }

/* ---- 7.9 dialog and sheet ---- */
.host-workspace .ui-dialog { border: 0; padding: 0; background: transparent; max-width: none; width: min(var(--dialog-w), calc(100vw - var(--space-8))); }
.host-workspace .ui-dialog::backdrop { background: rgba(32, 32, 30, 0.4); }
.host-workspace .ui-dialog .ui-sheet { background: var(--surface); border-radius: var(--sheet-radius); padding: var(--space-6); box-shadow: var(--shadow-3); }
.host-workspace .ui-dialog h2 { margin: 0 0 var(--space-3); font-size: var(--size-18); font-weight: var(--control-weight); }
.host-workspace .ui-sheet-handle { display: none; }

/* ---- 7.10 toast (restyles the existing stack) ---- */
.host-workspace .ui-toast, .host-workspace .toast-stack .toast { background: var(--surface); color: var(--ink); border: 1px solid var(--line); border-radius: var(--card-radius); box-shadow: var(--shadow-2); max-width: var(--toast-w); padding: var(--space-3) var(--space-4); font-size: var(--body-size); }

/* ---- 7.11 empty state, 7.12 tip, 7.13 pagination ---- */
.host-workspace .ui-empty { text-align: center; padding: var(--space-12) var(--space-6); color: var(--ink-2); }
.host-workspace .ui-empty h2 { margin: 0 0 var(--space-1); font-size: var(--size-18); font-weight: var(--control-weight); color: var(--ink); }
.host-workspace .ui-empty p { margin: 0 auto var(--space-4); max-width: 48ch; }
.host-workspace .ui-tip { display: inline-flex; vertical-align: middle; position: relative; }
.host-workspace .ui-pagination { display: flex; justify-content: flex-end; align-items: center; gap: var(--space-3); color: var(--ink-3); font-size: var(--size-14); margin-top: var(--space-4); }
.host-workspace .ui-pagination [data-pagination-more] { display: none; }

/* ---- phone (below 1024): 44 px targets, compact renders regular, sheets ---- */
@media (max-width: 1023px) {
  .host-workspace .ui-btn, .host-workspace .ui-btn-compact { min-height: var(--control-h-phone); height: var(--control-h-phone); font-size: var(--control-font); padding: 0 var(--control-px); }
  .host-workspace .ui-btn-icon, .host-workspace .ui-btn-icon.ui-btn-compact { width: var(--control-h-phone); padding: 0; }
  .host-workspace .ui-field .ui-input:not([type="checkbox"]):not([type="radio"]), .host-workspace .ui-field .ui-select { min-height: var(--control-h-phone); height: var(--control-h-phone); }
  .host-workspace .ui-chip { min-height: var(--control-h-phone); }
  .host-workspace .ui-pair { grid-template-columns: 1fr; }
  .host-workspace .ui-form-actions { display: none; }
  .host-workspace .ui-sticky-actions { display: flex; gap: var(--space-2); position: sticky; bottom: calc(var(--tabbar-h) + env(safe-area-inset-bottom)); margin: 0 calc(-1 * var(--space-4)); padding: var(--space-2) var(--space-4); background: var(--surface); border-top: 1px solid var(--line); z-index: var(--z-sticky); }
  .host-workspace .ui-sticky-actions .ui-btn { flex: 1; }
  .host-workspace .ui-pagination { justify-content: stretch; }
  .host-workspace .ui-pagination [data-pagination-more] { display: inline-flex; flex: 1; }
  .host-workspace .ui-pagination .ui-num, .host-workspace .ui-pagination .ui-btn-compact { display: none; }
}
@media (max-width: 767px) {
  .host-workspace .ui-dialog { width: 100vw; max-width: 100vw; margin: 0; position: fixed; inset: auto 0 0 0; }
  .host-workspace .ui-dialog .ui-sheet { border-radius: var(--sheet-radius) var(--sheet-radius) 0 0; max-height: 85vh; overflow: auto; padding: var(--space-2) var(--space-4) var(--space-6); }
  .host-workspace .ui-sheet-handle { display: block; width: var(--space-8); height: var(--space-1); border-radius: var(--radius-pill); background: var(--line-strong); margin: var(--space-1) auto var(--space-4); }
  .host-workspace .ui-menu-panel { position: fixed; inset: auto 0 0 0; border-radius: var(--sheet-radius) var(--sheet-radius) 0 0; min-width: 0; padding: var(--space-4) var(--space-4) calc(var(--space-6) + env(safe-area-inset-bottom)); }
  .host-workspace .ui-menu-item { min-height: var(--control-h-phone); }
}
@media (prefers-reduced-motion: reduce) {
  .host-workspace .ui-btn-loading::after, .host-workspace .ui-switch::after { animation: none; transition: none; }
}
```

   Command: `python3 scripts/design_lint.py`. Expected: `design lint: OK` (the stylesheet is on the enforced list).

3. In `App/app/templates/base.html`, replace Anchor A with:

```
  <link rel="stylesheet" href="/static/host-design0123.css?v=20261016-0123f">
  <link rel="stylesheet" href="/static/host2.css?v=20261019-v2a">
  {% endif %}
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_skeleton_loaders.py tests/test_signed_in_chrome.py -q --tb=short -x 2>&1 | tail -30`. Expected: passed.

4. Create `App/tests/test_design_ui_macros.py`:

```python
"""_ui.html renders the v2 catalog (docs/design/MASTER.md section 7)."""
import json
from pathlib import Path

import jinja2

APP_DIR = Path(__file__).resolve().parents[1] / "app"
ROOT = APP_DIR.parents[1]
CATALOG = json.loads((ROOT / "docs" / "design" / "catalog.json").read_text(encoding="utf-8"))
ENV = jinja2.Environment(loader=jinja2.FileSystemLoader(str(APP_DIR / "templates")), undefined=jinja2.StrictUndefined)
ENV.globals["t"] = lambda key, **kw: key


def _r(src, **ctx):
    return ENV.from_string('{% from "_ui.html" import ' + ", ".join(
        ["ui_button", "ui_icon_button", "ui_badge", "ui_chip", "ui_field", "ui_select", "ui_textarea", "ui_check",
         "ui_toggle", "ui_menu_begin", "ui_menu_end", "ui_menu_item", "ui_dialog_begin", "ui_dialog_end", "ui_empty",
         "ui_tip", "ui_pagination", "ui_pdot"]) + " with context %}" + src).render(**ctx)


def _classes(html):
    import re
    return {c for m in re.findall(r'class="([^"]*)"', html) for c in m.split()}


def test_button_variants_sizes_and_states():
    html = _r('{{ ui_button("Save", "primary", type="submit") }}{{ ui_button("Open", href="/x", size="compact", icon_name="plus") }}'
              '{{ ui_button("Wait", "secondary", loading=true) }}{{ ui_button("No", "danger", disabled=true) }}{{ ui_icon_button("Close", "x") }}')
    assert 'class="ui-btn ui-btn-primary" type="submit"' in html
    assert 'class="ui-btn ui-btn-secondary ui-btn-compact" href="/x"' in html and 'data-icon="plus"' in html
    assert "ui-btn-loading" in html and 'aria-busy="true"' in html
    assert "ui-btn-danger" in html and " disabled" in html
    assert 'aria-label="Close"' in html and "ui-btn-icon" in html


def test_badge_kinds_carry_a_word_and_overdue_a_mark():
    for kind in ("action", "attention", "done", "neutral"):
        assert f'class="ui-badge ui-badge-{kind}">Word</span>' in _r('{{ ui_badge(kind, "Word") }}', kind=kind)
    assert "ui-badge-overdue\">! Late" in _r('{{ ui_badge("action", "Late", true) }}')


def test_fields_bind_help_and_errors_to_the_control():
    ok = _r('{{ ui_field("name", "Name", help="Only you see it") }}')
    assert 'aria-describedby="name-help"' in ok and 'class="ui-help" id="name-help"' in ok
    bad = _r('{{ ui_field("cp", "Number", error="Required") }}')
    assert "ui-field-err" in bad and 'aria-invalid="true"' in bad and 'id="cp-error"' in bad
    sel = _r('{{ ui_select("s", "State", [("a", "A"), ("b", "B")], selected="b") }}')
    assert '<option value="b" selected>' in sel
    assert 'role="switch"' in _r('{{ ui_toggle("tg", "Fee", checked=true) }}')


def test_menu_dialog_empty_and_pagination_render_their_hooks():
    html = _r('{{ ui_menu_begin() }}{{ ui_menu_item("Open", "/o") }}{{ ui_menu_item("Delete", danger=true) }}{{ ui_menu_end() }}')
    assert 'role="menu"' in html and "row-menu-trigger" in html and "ui-menu-danger" in html
    dlg = _r('{{ ui_dialog_begin("d1", "Title") }}<p>x</p>{{ ui_dialog_end() }}')
    assert '<dialog id="d1" class="ui-dialog" aria-labelledby="d1-title">' in dlg
    empty = _r('{{ ui_empty("None", "Next step.", "Add", "/add") }}')
    assert "ui-btn-primary" in empty and "data-empty-state" in empty
    pag = _r('{{ ui_pagination(2, 5, "/p=1", "/p=3", "Stays", "Show more", "Previous", "Next") }}')
    assert "data-pagination-more" in pag and pag.count("ui-btn-compact") == 2


def test_every_class_the_macros_emit_is_in_the_catalog():
    html = _r('{{ ui_button("a") }}{{ ui_icon_button("b", "x") }}{{ ui_badge("done", "c", true) }}{{ ui_chip("d", selected=true) }}'
              '{{ ui_field("f", "F", error="e") }}{{ ui_select("s", "S", [("1", "1")]) }}{{ ui_textarea("ta", "T") }}{{ ui_check("c1", "C") }}'
              '{{ ui_toggle("t1", "T") }}{{ ui_menu_begin() }}{{ ui_menu_item("i", danger=true) }}{{ ui_menu_end() }}'
              '{{ ui_dialog_begin("d", "D") }}{{ ui_dialog_end() }}{{ ui_empty("E") }}{{ ui_tip("tip", "text") }}'
              '{{ ui_pagination(1, 1) }}{{ ui_pdot(3, "P") }}')
    allowed = set(CATALOG["classes"]) | set(CATALOG["hooks"])
    assert _classes(html) <= allowed, _classes(html) - allowed


def test_host2_css_is_loaded_last_in_the_signed_in_head():
    base = (APP_DIR / "templates" / "base.html").read_text(encoding="utf-8")
    assert base.index("host-design0123.css") < base.index("/static/host2.css")
```

   Command: `cd App && .venv/bin/python -m pytest tests/test_design_ui_macros.py -q --tb=short -x 2>&1 | tail -30`. Expected: `6 passed`. If the catalog test lists a missing class, add that class to `docs/design/catalog.json` `classes` (this brief may edit that one array) and rerun.

5. Commit: `git add App/app/templates/_ui.html App/app/static/host2.css App/app/templates/base.html App/tests/test_design_ui_macros.py docs/design/catalog.json && git commit -m "0128 step 5: v2 controls, macros and host2.css part 1"`.

## 5. Do not touch

Any page template; `_components.html`; the old stylesheets; `app.js` and `host.js`; hard rules 2, 3, 6, 8.

## 6. Commands

- `python3 scripts/design_lint.py` expected: OK.
- `cd App && .venv/bin/python -m pytest tests/test_design_ui_macros.py tests/test_design_lint.py tests/test_design_icons.py -q --tb=short -x 2>&1 | tail -30` expected: all passed.
- `cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_button_contrast_browser.py tests/test_host_geometry.py -q --tb=short -x 2>&1 | tail -30` expected: all passed, 0 skipped (nothing visible changed yet).

## 7. Acceptance

- [ ] The six macro tests pass; the design lint passes with `host2.css` enforced.
- [ ] Existing host pages render unchanged: `test_host_geometry.py` passes with 0 skipped.
- [ ] `git diff df8b842 --stat` lists only section 3 files (plus `catalog.json` if step 4 needed a class).

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a new dependency seems needed; a file outside section 3 needs a change; section 5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0128-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/static/host2.css` (specificity against the old sheets), `App/app/templates/_ui.html`.

## Owner steps

None.
