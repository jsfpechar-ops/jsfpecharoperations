# 0424: Copy settings opens a small dialog

Status: review

## 1. Objective

Owner (2026-10-26, screenshot): on property Settings the "Copy settings from… *" block at the top
(big select, red asterisk, Copy button) looks ugly and reads as if it could copy police details.
Follow-up (same evening): copying is a one-time thing, so offer it when the property is new, not
forever. Result:

- One shared dialog (`_copy_settings_dialog.html`) opened by one small bordered button. It says
  what is copied and what is never copied. No asterisk, no `required`.
- Add property page: the button sits where the old select was (the first-time moment).
- Settings: the button shows only while the property's setup wizard is not finished. Finished and
  older properties never show it.

## 2. Context (orchestrator checked these; do not re-audit)

- What is copied: `_COPY_PROPERTY_KEYS` in `App/app/routes/admin.py` (operator, data controller,
  automation mode, send time, default purpose, guest link days, stay fee settings). Police (`uby_*`),
  address, guest link token/PIN, door lock and the variable symbol are NOT copied, and
  `test_allowed_settings_are_copied_on_edit` already asserts this. On edit, `_apply_property_copy`
  fills only fields that are still empty. Do not change which keys are copied.
- `shell.js` already opens any `dialog.ui-dialog` from `[data-sheet-open="<id>"]` and closes on
  backdrop click. Escape closes natively.
- The red asterisk comes from `host2.css:685` (`.field:has(... [required])`). So the select has no
  `required` and the first property is preselected.
- No-JS fallback: the opener is a real link to `?copy=choose`; the dialog then renders with
  `open`. Cancel uses `formmethod="dialog"`, which closes a dialog without JS.
- `icon` is imported with `{%- from "_icons.html" import icon with context -%}` (as
  `_property_create.html` does). `request` is in every template context
  (`cleaning_settings.html` uses `request.query_params`).
- `property_setup.load(id)` returns `None` or a dict with `"finished"`. A new property calls
  `property_setup.start` at creation (admin.py ~1595).

## 3. Files

- new `App/app/templates/_copy_settings_dialog.html`
- `App/app/templates/_property_editor.html`, `App/app/templates/_property_create.html`
- `App/app/routes/admin.py` (only `_property_copy_form_context`)
- `App/app/static/host2.css`, `App/app/templates/base.html` (cache key only)
- `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`
- `App/tests/test_copy_property_settings.py`

## 4. Steps

### Step 1: the shared dialog

Create `App/app/templates/_copy_settings_dialog.html`:

```jinja
{#- 0424: copy settings from another property. One small button + one dialog.
    Callers set copy_action (form action) and optionally copy_section. -#}
{%- from "_icons.html" import icon with context -%}
{%- set copy_open = request.query_params.get('copy') == 'choose' -%}
{%- set copy_query = ('view=settings&section=' ~ copy_section ~ '&') if copy_section else '' -%}
<a class="ui-btn ui-btn-secondary ui-btn-compact copy-settings-open" href="{{ copy_action }}?{{ copy_query }}copy=choose" data-sheet-open="copy-settings">{{ icon('copy', 16) }}{{ t('apartment.form.copy_from.open') }}</a>
<dialog id="copy-settings" class="ui-dialog copy-settings-dialog" aria-labelledby="copy-settings-title"{% if copy_open %} open{% endif %}>
  <div class="ui-sheet">
    <span class="ui-sheet-handle" aria-hidden="true"></span>
    <h2 id="copy-settings-title">{{ t('apartment.form.copy_from.title') }}</h2>
    <form method="get" action="{{ copy_action }}" class="copy-property-form">
      {% if copy_section %}
      <input type="hidden" name="view" value="settings">
      <input type="hidden" name="section" value="{{ copy_section }}">
      {% endif %}
      <div class="field">
        <label for="copy_from">{{ t('apartment.form.copy_from.source') }}</label>
        <select id="copy_from" name="copy_from">
          {% for peer in copy_property_peers %}
          <option value="{{ peer.id }}" {% if copy_from_id == peer.id %}selected{% endif %}>{{ peer.internal_name }}</option>
          {% endfor %}
        </select>
      </div>
      <h3>{{ t('apartment.form.copy_from.copied_head') }}</h3>
      <ul class="copy-settings-list">
        <li>{{ t('apartment.form.copy_from.item_operator') }}</li>
        <li>{{ t('apartment.form.copy_from.item_automation') }}</li>
        <li>{{ t('apartment.form.copy_from.item_link') }}</li>
        <li>{{ t('apartment.form.copy_from.item_fee') }}</li>
      </ul>
      <h3>{{ t('apartment.form.copy_from.never_head') }}</h3>
      <p class="copy-settings-never">{{ t('apartment.form.copy_from.never_body') }}</p>
      {% if copy_section %}<p class="ui-sub">{{ t('apartment.form.copy_from.empty_only') }}</p>{% endif %}
      <div class="copy-settings-actions">
        <button class="ui-btn ui-btn-primary" type="submit">{{ t('apartment.form.copy_from.button') }}</button>
        <button class="ui-btn ui-btn-secondary" type="submit" formmethod="dialog" formnovalidate data-sheet-close>{{ t('confirm.cancel') }}</button>
      </div>
    </form>
  </div>
</dialog>
```

### Step 2: Settings uses it

In `App/app/templates/_property_editor.html` replace the whole block from the anchor
`{% if copy_property_peers %}` through its matching `{% endif %}` (the `<form ... class="panel
copy-property-form">` block, ends right before `<div class="property-settings">`) with:

```jinja
{% if copy_property_peers or copied_from_name %}
<div class="copy-settings-bar">
  {% if copied_from_name %}<p class="ui-sub" role="status">{{ t('apartment.form.copy_from.notice', name=copied_from_name) }}</p>{% endif %}
  {% if copy_property_peers %}{% with copy_action=base_url, copy_section=settings_section %}{% include "_copy_settings_dialog.html" %}{% endwith %}{% endif %}
</div>
{% endif %}
```

(The old `vs_hint` line goes; the variable symbol is in the dialog's "never" line. Keep the key.)

In `App/app/routes/admin.py`, inside `_property_copy_form_context`, directly after the `peers = [ ... ]`
list (anchor `if apartment_id is None or row["id"] != apartment_id`, then the closing `]`), add:

```python
    # 0424: copying is a first-time step. Settings offers it only until setup is finished.
    if apartment_id is not None:
        setup = property_setup.load(apartment_id)
        if not setup or setup["finished"]:
            peers = []
```

### Step 3: Add property page uses it

In `App/app/templates/_property_create.html` replace the block from `{% if copy_property_peers %}`
(the one containing `<form method="get" action="/apartments/new" class="property-create-copy">`)
through its matching `{% endif %}` with:

```jinja
    {% if copy_property_peers %}
    <div class="property-create-copy">{% with copy_action='/apartments/new', copy_section='' %}{% include "_copy_settings_dialog.html" %}{% endwith %}</div>
    {% endif %}
```

Command: `cd App && .venv/bin/python -m pytest tests/test_copy_property_settings.py tests/test_property_create_browser.py -q --tb=short -x 2>&1 | tail -30`
(missing i18n keys come in step 5; existing tests asserting `name="copy_from"` must still pass.
`test_allowed_settings_are_copied_on_edit` asserts "Copied from Source flat": the notice now
renders even without the button, so it must still pass.)

### Step 4: CSS

In `App/app/static/host2.css` replace the line
`.host-workspace .copy-property-form .copyrow { display: flex; align-items: flex-end; gap: var(--space-3); }`
with:

```css
/* 0424: copy settings is one small button that opens a dialog. */
.host-workspace .copy-settings-bar { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: var(--space-3); margin: 0 0 var(--space-4); }
.host-workspace .copy-settings-bar p { margin: 0; margin-right: auto; }
.host-workspace .copy-settings-open { gap: var(--space-2); }
.host-workspace .copy-settings-dialog h3 { margin: var(--space-4) 0 var(--space-2); font-size: var(--size-14); font-weight: var(--control-weight); }
.host-workspace .copy-settings-list { margin: 0; padding-left: 1.25rem; }
.host-workspace .copy-settings-list li + li { margin-top: var(--space-1); }
.host-workspace .copy-settings-never { margin: 0; }
.host-workspace .copy-settings-dialog .copy-settings-actions { display: flex; flex-wrap: wrap; gap: var(--space-3); margin-top: var(--space-5); }
.host-workspace .copy-settings-dialog select { width: 100%; }
```

If `--size-14`, `--space-1` or `--space-5` does not exist in host2.css `:root`, use the nearest
existing token and note it under Deviations.

Then in `App/app/templates/base.html` change `host2.css?v=20261025-0410` to `host2.css?v=20261026-0424`.

### Step 5: copy (EN, CS, VI)

Add next to the existing `apartment.form.copy_from.*` keys, same quoting style as the neighbours.

| key | EN | CS | VI |
|---|---|---|---|
| open | Copy from another property | Zkopírovat z jiného ubytování | Sao chép từ chỗ ở khác |
| title | Copy settings from another property | Zkopírovat nastavení z jiného ubytování | Sao chép cài đặt từ chỗ ở khác |
| source | Copy from | Zkopírovat z | Sao chép từ |
| copied_head | What is copied | Co se zkopíruje | Những gì được sao chép |
| item_operator | Operator and data controller | Provozovatel a správce údajů | Đơn vị vận hành và bên kiểm soát dữ liệu |
| item_automation | Automatic sending, send time and purpose of stay | Automatické odesílání, čas odeslání a účel pobytu | Gửi tự động, giờ gửi và mục đích lưu trú |
| item_link | Guest link days | Dny pro odkaz pro hosty | Số ngày của liên kết cho khách |
| item_fee | Stay fee settings | Nastavení poplatku z pobytu | Cài đặt phí lưu trú |
| never_head | Never copied | Nikdy se nekopíruje | Không bao giờ sao chép |
| never_body | Police (Ubyport) details, address, guest link and PIN, door lock, variable symbol. | Údaje pro policii (Ubyport), adresa, odkaz a PIN pro hosty, zámek dveří, variabilní symbol. | Thông tin khai báo công an (Ubyport), địa chỉ, liên kết và mã PIN cho khách, khóa cửa, mã VS. |
| empty_only | Only empty fields here are filled. Nothing is saved until you press Save. | Vyplní se jen prázdná pole. Nic se neuloží, dokud nestisknete Uložit. | Chỉ điền vào các ô còn trống. Không có gì được lưu cho đến khi bạn bấm Lưu. |

Full key = `apartment.form.copy_from.<key>`. EN/CS go in `host_i18n.py` (EN block ~line 3459,
CS block ~line 4279); VI in `host_vi_i18n.py` (~line 1681). No em dashes.

Command: `cd App && .venv/bin/python -m pytest tests/test_copy_property_settings.py tests/test_host_i18n.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -30`
(skip a file in that list only if it does not exist; say so in the report).

### Step 6: tests

Append to `App/tests/test_copy_property_settings.py`:

```python
def test_settings_offers_copy_only_until_setup_is_finished(host_pair):
    from app import property_setup

    client, _source_id, target_id, _foreign_id, _entity_id, _controller_id = host_pair
    url = f"/apartments/{target_id}?view=settings&lang=en"
    assert 'data-sheet-open="copy-settings"' not in client.get(url).text
    property_setup.start(target_id)
    text = client.get(url).text
    assert 'data-sheet-open="copy-settings"' in text
    assert 'id="copy-settings" class="ui-dialog copy-settings-dialog" aria-labelledby="copy-settings-title">' in text
    select = text.split('<select id="copy_from"', 1)[1].split(">", 1)[0]
    assert "required" not in select
    assert "Police (Ubyport) details" in text
    assert "Never copied" in text
    no_js = client.get(url + "&copy=choose").text
    assert 'aria-labelledby="copy-settings-title" open>' in no_js
    property_setup.finish(target_id)
    assert 'data-sheet-open="copy-settings"' not in client.get(url).text


def test_new_property_page_opens_copy_in_a_dialog(host_pair):
    client = host_pair[0]
    text = client.get("/apartments/new?lang=en").text
    assert 'data-sheet-open="copy-settings"' in text
    assert "Never copied" in text


def test_copy_keys_never_include_police_address_link_or_lock():
    from app.routes.admin import _COPY_PROPERTY_KEYS

    for key in _COPY_PROPERTY_KEYS:
        assert not key.startswith(("uby_", "addr_", "permalink_token", "permalink_pin", "door_", "lock_", "ttlock")), key
        assert key != "stay_fee_vs", key
```

If `_cleanup()` in this file does not delete the `property_setup` setting rows, that is fine
(they key on apartment id). If `test_single_property_host_sees_no_copy_select` or another existing
test fails because the markup moved, fix only the assertion string and list it under Deviations.

Command: `cd App && .venv/bin/python -m pytest tests/test_copy_property_settings.py -q --tb=short -x 2>&1 | tail -30`

## 5. Do not touch

Which keys `_COPY_PROPERTY_KEYS` holds, `shell.js`, the setup wizard templates, any other page.

## 6. Commands

```
cd App && .venv/bin/python -m pytest tests/test_copy_property_settings.py tests/test_property_operator_defaults.py tests/test_property_create_browser.py -q --tb=short -x 2>&1 | tail -30
cd App && .venv/bin/python -m pytest tests/test_design_guardrails_browser.py -q --tb=short -rs 2>&1 | tail -30
cd .. && python3 scripts/context_lint.py 2>&1 | tail -30
```

## 7. Acceptance

- [ ] No select, asterisk or Copy button above the Settings grid; one compact bordered button, shown only while setup is unfinished.
- [ ] Add property page uses the same button and dialog.
- [ ] The dialog lists what is copied and what is never copied (police, address, link/PIN, lock, VS).
- [ ] `?copy=choose` renders the dialog open (no-JS path).
- [ ] New keys in EN, CS, VI. host2.css cache key bumped.
- [ ] Section 6 commands pass, browser test 0 skipped.

## 8. Stop and ask

An anchor is not found, a template error mentions `request` or `icon`, or a test outside
`test_copy_property_settings.py` fails because of this change.

## 9. Report

`docs/tasks/0424-report.md` per executor.md. Screenshots are done by the orchestrator. Commit each
step; do not push.
