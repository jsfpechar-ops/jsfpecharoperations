# 0414: Copy settings opens a small dialog

Status: ready. Executor: Haiku 5.5. Branch: `claude/project-thread-mtzx1z`.

## 1. Objective

Owner (2026-10-26, screenshot): on property Settings the "Copy settings from… *" block at the top
(big select, red asterisk, Copy button) looks ugly and reads as if it could copy police details.
Replace it with one small bordered button that opens a dialog. The dialog says what is copied and
what is never copied. No asterisk, no `required`.

## 2. Context (orchestrator checked these; do not re-audit)

- What is copied: `_COPY_PROPERTY_KEYS` in `App/app/routes/admin.py` (operator, data controller,
  automation mode, send time, default purpose, guest link days, stay fee settings). Police (`uby_*`),
  address, guest link token/PIN, door lock and the variable symbol are NOT copied, and
  `test_allowed_settings_are_copied_on_edit` already asserts this. On edit, `_apply_property_copy`
  fills only fields that are still empty. **Do not change admin.py.**
- `shell.js` already opens any `dialog.ui-dialog` from `[data-sheet-open="<id>"]` and closes on
  backdrop click. Escape closes natively. `host2.css` lines 84-87 and 115 style `.ui-dialog`
  (bottom sheet on phone).
- The red asterisk comes from `host2.css:685` (`.field:has(... [required])`). So the select has no
  `required` and the first property is preselected.
- No-JS fallback: the opener is a real link to `?copy=choose`; the template then renders the
  dialog with `open`. Cancel uses `formmethod="dialog"`, which closes a dialog without JS.
- The create page (`_property_create.html`) is out of scope.

## 3. Files

- `App/app/templates/_property_editor.html`
- `App/app/static/host2.css`
- `App/app/templates/base.html` (cache key only)
- `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`
- `App/tests/test_copy_property_settings.py`

## 4. Steps

### Step 1: template

In `App/app/templates/_property_editor.html` replace the whole block from the anchor
`{% if copy_property_peers %}` through its matching `{% endif %}` (the `<form ... class="panel
copy-property-form">` block, about 22 lines, ends right before `<div class="property-settings">`) with:

```jinja
{% if copy_property_peers %}
{%- set copy_open = request.query_params.get('copy') == 'choose' -%}
<div class="copy-settings-bar">
  {% if copied_from_name %}<p class="ui-sub" role="status">{{ t('apartment.form.copy_from.notice', name=copied_from_name) }}</p>{% endif %}
  <a class="ui-btn ui-btn-secondary ui-btn-compact" href="{{ base_url }}?view=settings&amp;section={{ settings_section }}&amp;copy=choose" data-sheet-open="copy-settings" data-copy-settings-open>{{ icon('copy', 16) }}{{ t('apartment.form.copy_from.open') }}</a>
</div>
<dialog id="copy-settings" class="ui-dialog copy-settings-dialog" aria-labelledby="copy-settings-title"{% if copy_open %} open{% endif %}>
  <div class="ui-sheet">
    <span class="ui-sheet-handle" aria-hidden="true"></span>
    <h2 id="copy-settings-title">{{ t('apartment.form.copy_from.title') }}</h2>
    <form method="get" action="{{ base_url }}" class="copy-property-form">
      <input type="hidden" name="view" value="settings">
      <input type="hidden" name="section" value="{{ settings_section }}">
      <div class="field">
        <label for="copy_from">{{ t('apartment.form.copy_from.source') }}</label>
        <select id="copy_from" name="copy_from">
          {% for peer in copy_property_peers %}
          <option value="{{ peer.id }}" {% if copy_from_id == peer.id %}selected{% endif %}>{{ peer.internal_name }}</option>
          {% endfor %}
        </select>
      </div>
      <h3>{{ t('apartment.form.copy_from.copied_head') }}</h3>
      <ul class="copy-settings-list" data-copy-settings-copied>
        <li>{{ t('apartment.form.copy_from.item_operator') }}</li>
        <li>{{ t('apartment.form.copy_from.item_automation') }}</li>
        <li>{{ t('apartment.form.copy_from.item_link') }}</li>
        <li>{{ t('apartment.form.copy_from.item_fee') }}</li>
      </ul>
      <h3>{{ t('apartment.form.copy_from.never_head') }}</h3>
      <p class="copy-settings-never" data-copy-settings-never>{{ t('apartment.form.copy_from.never_body') }}</p>
      <p class="ui-sub">{{ t('apartment.form.copy_from.empty_only') }}</p>
      <div class="ui-dialog-actions">
        <button class="ui-btn ui-btn-primary" type="submit">{{ t('apartment.form.copy_from.button') }}</button>
        <button class="ui-btn ui-btn-secondary" type="submit" formmethod="dialog" formnovalidate data-sheet-close>{{ t('confirm.cancel') }}</button>
      </div>
    </form>
  </div>
</dialog>
{% endif %}
```

The old `vs_hint` line is dropped here on purpose (the variable symbol is now in the "never" line).
Do not delete the `vs_hint` keys: the create page still uses them. If `icon` is not defined in this
template, add `icon` to the existing `{%- from "_components.html" import ... %}` line only if
`_components.html` exports it; otherwise STOP and ask.

Command: `cd App && .venv/bin/python -m pytest tests/test_copy_property_settings.py -q --tb=short -x 2>&1 | tail -30`
(the i18n keys come in step 3; a missing-key failure here is expected, go on).

### Step 2: CSS

In `App/app/static/host2.css` replace the line
`.host-workspace .copy-property-form .copyrow { display: flex; align-items: flex-end; gap: var(--space-3); }`
with:

```css
/* 0414: copy settings is one small button that opens a dialog. */
.host-workspace .copy-settings-bar { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: var(--space-3); margin: 0 0 var(--space-4); }
.host-workspace .copy-settings-bar p { margin: 0; margin-right: auto; }
.host-workspace .copy-settings-dialog h3 { margin: var(--space-4) 0 var(--space-2); font-size: var(--size-14); font-weight: var(--control-weight); }
.host-workspace .copy-settings-list { margin: 0; padding-left: 1.25rem; }
.host-workspace .copy-settings-list li + li { margin-top: var(--space-1); }
.host-workspace .copy-settings-never { margin: 0; }
.host-workspace .copy-settings-dialog .ui-dialog-actions { display: flex; flex-wrap: wrap; gap: var(--space-3); margin-top: var(--space-5); }
.host-workspace .copy-settings-dialog select { width: 100%; }
```

If `--size-14`, `--space-1` or `--space-5` does not exist in host2.css `:root`, use the nearest
existing token and note it under Deviations.

Then in `App/app/templates/base.html` change `host2.css?v=20261025-0410` to `host2.css?v=20261026-0414`.

### Step 3: copy (EN, CS, VI)

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

### Step 4: tests

Append to `App/tests/test_copy_property_settings.py`:

```python
def test_copy_settings_is_a_small_dialog_that_lists_what_is_copied(host_pair):
    client, _source_id, target_id, _foreign_id, _entity_id, _controller_id = host_pair
    text = client.get(f"/apartments/{target_id}?view=settings&lang=en").text
    assert 'data-sheet-open="copy-settings"' in text
    assert '<dialog id="copy-settings"' in text
    assert 'id="copy-settings" class="ui-dialog copy-settings-dialog" aria-labelledby="copy-settings-title">' in text
    select = text.split('<select id="copy_from"', 1)[1].split(">", 1)[0]
    assert "required" not in select
    assert "Police (Ubyport) details" in text
    assert "Never copied" in text
    no_js = client.get(f"/apartments/{target_id}?view=settings&copy=choose&lang=en").text
    assert 'aria-labelledby="copy-settings-title" open>' in no_js


def test_copy_keys_never_include_police_address_link_or_lock():
    from app.routes.admin import _COPY_PROPERTY_KEYS

    for key in _COPY_PROPERTY_KEYS:
        assert not key.startswith(("uby_", "addr_", "permalink_token", "permalink_pin", "door_", "ttlock")), key
        assert key != "stay_fee_vs", key
```

If the import path `app.routes.admin` fails, use whatever import the top of this test file already
uses for app modules.

Command: `cd App && .venv/bin/python -m pytest tests/test_copy_property_settings.py -q --tb=short -x 2>&1 | tail -30`

## 5. Do not touch

`admin.py`, `_property_create.html`, `shell.js`, any other page.

## 6. Commands

```
cd App && .venv/bin/python -m pytest tests/test_copy_property_settings.py tests/test_property_operator_defaults.py -q --tb=short -x 2>&1 | tail -30
cd App && .venv/bin/python -m pytest tests/test_design_guardrails_browser.py -q --tb=short -rs 2>&1 | tail -30
cd .. && python3 scripts/context_lint.py 2>&1 | tail -30
```

## 7. Acceptance

- [ ] No select, asterisk or Copy button above the Settings grid; one compact bordered button instead.
- [ ] The dialog lists what is copied and what is never copied (police, address, link/PIN, lock, VS).
- [ ] `?copy=choose` renders the dialog open (no-JS path).
- [ ] New keys in EN, CS, VI. host2.css cache key bumped.
- [ ] Section 6 commands pass, browser test 0 skipped.

## 8. Stop and ask

An anchor is not found, `request` or `icon` is undefined in the template, or a test outside
`test_copy_property_settings.py` fails because of this change.

## 9. Report

`docs/tasks/0414-report.md` per executor.md. Screenshots are done by the orchestrator. Commit each
step; do not push.
