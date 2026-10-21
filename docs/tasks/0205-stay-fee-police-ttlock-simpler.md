# 0205: Simpler stay fee, police abbreviation filled by itself, clearer TTLock steps

Status: todo
Depends on: 0204 (same branch, run after it) | Base commit: after 0204 | Branch: claude/project-thread-cf47ju
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Rows 10 to 12 of the first user test (2026-10-21), app-wide: a pasted bank account splits itself into prefix, number and bank code; the setup wizard's stay-fee step asks only rate, period, variable symbol and account; the "Paid to the account of" and "How to send the report" fields leave every form; the police abbreviation fills itself from the web-service login as the host types; and the TTLock steps name the exact buttons and say where the UbyHost name goes.

## 2. Context

- Owner decision (Josef, 2026-10-21): "build all as proposed ... do some possible easier automations like reading the zkratka for police itself ... this needs to be implemented outside of wizard as well".
- The server already derives an empty abbreviation from the login on save (`validation.mark_from_ws_user`, `routes/admin.py` `_apply_police_defaults`). This brief adds the same rule live in the browser, so the host sees it filled.
- `_stay_fee_fields.html` is shared by property Settings and the wizard. The wizard sets `fee_required`; Settings does not, because Settings is one big form and a host without a stay fee must still be able to save it.
- `routes/stay_fees.py` `fee_form_values` is the one normaliser. After this brief the office fields, payee and instruction are written only when the form carries them: the wizard no longer shows them, and it must not wipe what Settings stored. Stored payee and instruction values stay and still print; the forms no longer offer them.
- AGENTS hard rule 1: filing correctness first. The abbreviation stays an editable field; the browser only fills it while the host has not typed their own.
- Changed JS gets a new `?v=` key; rewrite `tests/static_versions.json` with `--write`. Copy: no em dashes; changed keys in `en`, `cs`, `vi`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/_stay_fee_fields.html | edit | required in the wizard, office section not in the wizard, no payee or instruction |
| App/app/templates/_account_parts.html | edit | required in the wizard, paste marker |
| App/app/templates/setup_wizard/stay_fee.html | edit | `fee_required` |
| App/app/templates/setup_wizard/police.html | edit | required police fields |
| App/app/routes/stay_fees.py | edit | write office fields only when posted |
| App/app/static/host.js | edit | account paste split, abbreviation from login |
| App/app/templates/base.html | edit | new `host.js` key |
| App/app/host_i18n.py | edit | one new strings block |
| App/app/host_vi_i18n.py | edit | the same keys in Vietnamese |
| App/tests/test_reporting_help_0097.py | edit | payee and instruction gone |
| App/tests/test_fee_setup_compatibility.py | edit | instruction gone |
| App/tests/test_host_ux_acceptance.py | edit | payee and instruction gone |
| App/tests/test_property_navigation_browser.py | edit | payee and instruction gone |
| App/tests/test_fee_form_partial.py | create | partial forms keep the office fields |
| App/tests/static_versions.json | regenerate | `--write` |

No other file may change.

## 4. Steps

### Step 1. `App/app/templates/_stay_fee_fields.html`

a) Anchor (exact, 2 lines):

```
      <input type="number" id="stay_fee_rate_czk" name="stay_fee_rate_czk" aria-describedby="stay_fee_rate_czk-help" min="0" max="50" step="1"
             value="{{ apartment.stay_fee_rate_czk or 0 }}">
```

Replace with:

```
      <input type="number" id="stay_fee_rate_czk" name="stay_fee_rate_czk" aria-describedby="stay_fee_rate_czk-help" min="0" max="50" step="1"
             value="{{ apartment.stay_fee_rate_czk or 0 }}"{% if fee_required %} required{% endif %}>
```

b) Anchor: `    <input type="text" id="stay_fee_vs" name="stay_fee_vs" aria-describedby="stay_fee_vs-help" inputmode="numeric" maxlength="10" value="{{ apartment.stay_fee_vs or '' }}">`
Replace with:
`    <input type="text" id="stay_fee_vs" name="stay_fee_vs" aria-describedby="stay_fee_vs-help" inputmode="numeric" maxlength="10" value="{{ apartment.stay_fee_vs or '' }}"{% if fee_required %} required{% endif %}>`

c) Anchor (exact, 2 lines):

```
  {% set prefix = '' %}
  {% include "_account_parts.html" %}
```

Replace with:

```
  {% set prefix = '' %}
  {% set account_required = fee_required %}
  {% include "_account_parts.html" %}
```

d) Anchor: `<div class="fee-setup-section" id="stay-fee-council">`
Replace with (one line becomes two):

```
{#- 0205: the wizard asks only rate, period, symbol and account; the office details are asked in Settings when the first report needs them. -#}
{% if not fee_required %}<div class="fee-setup-section" id="stay-fee-council">
```

e) Anchor (exact, 9 lines; the last two fields and the closing tag of the council section):

```
  <div class="field">
    {{ field_label('stay_fee_payee', t('apartment.form.stay_fee.payee_label'), t('apartment.form.stay_fee.payee_hint'), true) }}
    <input id="stay_fee_payee" name="stay_fee_payee" aria-describedby="stay_fee_payee-help" maxlength="60" value="{{ apartment.stay_fee_payee or '' }}" placeholder="{{ apartment.stay_fee_authority_name or '' }}">
  </div>
  <div class="field">
    {{ field_label('stay_fee_instruction', t('apartment.form.stay_fee.instruction_label'), t('apartment.form.stay_fee.instruction_hint')) }}
    <textarea id="stay_fee_instruction" name="stay_fee_instruction" aria-describedby="stay_fee_instruction-help" rows="2" maxlength="500">{{ apartment.stay_fee_instruction or '' }}</textarea>
  </div>
</div>
```

Replace with:

```
</div>{% endif %}
```

Command: `grep -c "stay_fee_payee\|stay_fee_instruction" App/app/templates/_stay_fee_fields.html` → `0`.

### Step 2. `App/app/templates/_account_parts.html`

a) Anchor: `    <input id="{{ prefix }}account_number" name="account_number" inputmode="numeric" maxlength="10" value="{{ parts.number }}">`
Replace with:
`    <input id="{{ prefix }}account_number" name="account_number" inputmode="numeric" maxlength="10" value="{{ parts.number }}"{% if account_required %} required{% endif %}>`

b) Anchor: `    <input id="{{ prefix }}account_bank" name="account_bank" inputmode="numeric" maxlength="4" value="{{ parts.bank }}">`
Replace with:
`    <input id="{{ prefix }}account_bank" name="account_bank" inputmode="numeric" maxlength="4" value="{{ parts.bank }}"{% if account_required %} required{% endif %}>`

c) Anchor: `<div class="account-parts">`
Replace with: `<div class="account-parts" data-account-parts>`

### Step 3. `App/app/templates/setup_wizard/stay_fee.html`

Anchor: `  {% set account = fee_account %}`
Replace with:

```
  {% set account = fee_account %}
  {% set fee_required = true %}
```

### Step 4. `App/app/templates/setup_wizard/police.html`

a) Anchor (exact, 6 lines):

```
{% macro text_field(name, label, value, help='', optional=false, maxlength=none) %}
  <div class="field">
    {{ field_label(name, label, help, optional) }}
    <input type="text" id="{{ name }}" name="{{ name }}" value="{{ value or '' }}"
           {%- if maxlength %} maxlength="{{ maxlength }}"{% endif %}>
  </div>
```

Replace with:

```
{% macro text_field(name, label, value, help='', optional=false, maxlength=none, required=false) %}
  <div class="field">
    {{ field_label(name, label, help, optional) }}
    <input type="text" id="{{ name }}" name="{{ name }}" value="{{ value or '' }}"
           {%- if maxlength %} maxlength="{{ maxlength }}"{% endif %}
           {%- if required %} required{% endif %}>
  </div>
```

b) Anchor: `{{ text_field('uby_idub', 'IDUB', values.uby_idub, t('apartment.form.ubyport.idub_hint'), false, 14) }}`
Replace with: `{{ text_field('uby_idub', 'IDUB', values.uby_idub, t('apartment.form.ubyport.idub_hint'), false, 14, true) }}`

c) Anchor: `    {{ text_field('uby_ws_user', t('automation.login'), values.uby_ws_user, t('apartment.form.ubyport.login_hint')) }}`
Replace with: `    {{ text_field('uby_ws_user', t('automation.login'), values.uby_ws_user, t('apartment.form.ubyport.login_hint'), false, none, true) }}`

d) Anchor: `      <input type="password" id="uby_ws_password" name="uby_ws_password" autocomplete="new-password"{% if has_password %} placeholder="••••••••"{% endif %}>`
Replace with:
`      <input type="password" id="uby_ws_password" name="uby_ws_password" autocomplete="new-password"{% if has_password %} placeholder="••••••••"{% else %} required{% endif %}>`

e) Anchor: `    {{ text_field('uby_name', t('automation.facility_name'), values.uby_name, t('apartment.form.ubyport.name_hint'), false, 35) }}`
Replace with: `    {{ text_field('uby_name', t('automation.facility_name'), values.uby_name, t('apartment.form.ubyport.name_hint'), false, 35, true) }}`

(The abbreviation `uby_mark` stays optional: the server fills it from the login.)

### Step 5. `App/app/routes/stay_fees.py` (`fee_form_values`)

Anchor (exact, 11 lines):

```
    for key, limit in (
        ("stay_fee_authority_name", 200),
        ("stay_fee_authority_address", 200),
        ("stay_fee_authority_contact", 200),
        ("stay_fee_payee", 60),
        ("stay_fee_instruction", 500),
    ):
        values[key] = _form_str(form, key)[:limit].strip() or None
    values["stay_fee_authority_databox"] = (
        validation.normalise_databox(_form_str(form, "stay_fee_authority_databox")) or None
    )
```

Replace with:

```
    # 0205: the setup wizard asks only rate, period, symbol and account, and no
    # form offers the payee or the instruction any more. These are written only
    # when the form carries them, so a shorter form never wipes stored values.
    for key, limit in (
        ("stay_fee_authority_name", 200),
        ("stay_fee_authority_address", 200),
        ("stay_fee_authority_contact", 200),
        ("stay_fee_payee", 60),
        ("stay_fee_instruction", 500),
    ):
        if key in form:
            values[key] = _form_str(form, key)[:limit].strip() or None
    if "stay_fee_authority_databox" in form:
        values["stay_fee_authority_databox"] = (
            validation.normalise_databox(_form_str(form, "stay_fee_authority_databox")) or None
        )
```

### Step 6. `App/app/static/host.js`

Anchor: `  document.querySelectorAll('[data-phone-country-code]').forEach(function (input) {`
Insert these lines immediately BEFORE the anchor (keep the anchor line):

```js
  // 0205: a whole account pasted into any of the three boxes splits itself:
  // 19-2000145399/0800, 2000145399/0800 or a Czech IBAN.
  document.querySelectorAll('[data-account-parts]').forEach(function (group) {
    var prefix = group.querySelector('[name="account_prefix"]');
    var number = group.querySelector('[name="account_number"]');
    var bank = group.querySelector('[name="account_bank"]');
    if (!prefix || !number || !bank) return;
    function strip(digits) { return digits.replace(/^0+/, ''); }
    function split(text) {
      var plain = text.replace(/\s+/g, '').toUpperCase();
      var local = plain.match(/^(?:(\d{1,6})-)?(\d{2,10})\/(\d{4})$/);
      if (local) return [local[1] || '', local[2], local[3]];
      var iban = plain.match(/^CZ\d{2}(\d{4})(\d{6})(\d{10})$/);
      if (iban) return [strip(iban[2]), strip(iban[3]), iban[1]];
      return null;
    }
    [prefix, number, bank].forEach(function (input) {
      input.addEventListener('paste', function (event) {
        var text = event.clipboardData ? event.clipboardData.getData('text') : '';
        var parts = split(text || '');
        if (!parts) return;
        event.preventDefault();
        prefix.value = parts[0];
        number.value = parts[1];
        bank.value = parts[2];
        [prefix, number, bank].forEach(function (field) {
          field.dispatchEvent(new Event('input', { bubbles: true }));
        });
      });
    });
  });

  // 0205: the police abbreviation follows the web-service login as it is
  // typed (UBY-WS_ABCDE gives ABCDE), the rule of validation.mark_from_ws_user.
  // A value the host typed themselves is never replaced.
  var wsUser = document.getElementById('uby_ws_user');
  var ubyMark = document.getElementById('uby_mark');
  if (wsUser && ubyMark) {
    var markFrom = function (login) {
      var value = (login || '').trim();
      var lower = value.toLowerCase();
      if (lower.indexOf('uby-tws') === 0) return '';
      if (lower.indexOf('uby-ws_') === 0) return value.slice(7).toUpperCase().slice(0, 6);
      if (lower.indexOf('uby-ws') === 0) return value.slice(6).toUpperCase().slice(0, 6);
      return '';
    };
    var autoMark = !ubyMark.value || ubyMark.value === markFrom(wsUser.value);
    ubyMark.addEventListener('input', function (event) {
      if (event.isTrusted) autoMark = !ubyMark.value;
    });
    wsUser.addEventListener('input', function () {
      if (!autoMark) return;
      ubyMark.value = markFrom(wsUser.value);
      ubyMark.dispatchEvent(new Event('input', { bubbles: true }));
    });
  }

```

Note: the synthetic `input` event has `isTrusted === false`, so it does not switch `autoMark` off.

### Step 7. `App/app/templates/base.html`

Anchor: `/static/host.js?v=20261021-0203` → replace with `/static/host.js?v=20261021-0205`

### Step 8. `App/app/host_i18n.py`

Anchor: `STRINGS["vi"] = dict(_VI_STRINGS)`
Insert immediately BEFORE the anchor:

```python
# 0205: onboarding user test (2026-10-21): the abbreviation fills itself, a
# pasted account splits itself, and the TTLock steps name the exact buttons.
_ONBOARDING_TEST_0205_STRINGS = {
    "en": {
        "apartment.form.ubyport.mark_hint": "Fills in by itself from your login: the part after UBY-WS_. Change it only if the police letter gives a different “Zkratka ubytovacího zařízení”.",
        "apartment.form.stay_fee.account_help": "The town's bank account for the stay fee, from its website or letter. Paste the whole account (19-2000145399/0800) or an IBAN into any box and it splits itself. Used for the payment QR code.",
        "smart_locks.essential1": "In the TTLock app, open your lock and tap Authorized Admin (eAdmin in some app versions).",
        "smart_locks.essential2": "Tap Create Admin. In the Recipient field, where TTLock expects an e-mail or phone number, paste your UbyHost name from above. Leave Permanent on and tap Send.",
        "smart_locks.essential3": "Come back here and tap Check connection.",
        "smart_locks.s4": "Tap Authorized Admin (eAdmin in some app versions). It is the icon with a person and a tick, in the grid under the padlock.",
        "smart_locks.s6": "Leave Permanent switched on. In Recipient, where TTLock expects an e-mail or phone number, paste your UbyHost name. In Name type UbyHost.",
    },
    "cs": {
        "apartment.form.ubyport.mark_hint": "Vyplní se samo z přihlašovacího jména: je to část za UBY-WS_. Změňte ji, jen když dopis od policie uvádí jinou „Zkratku ubytovacího zařízení“.",
        "apartment.form.stay_fee.account_help": "Bankovní účet obce pro poplatek z pobytu, z jejího webu nebo dopisu. Vložte celé číslo účtu (19-2000145399/0800) nebo IBAN do kteréhokoli pole a rozdělí se samo. Použije se pro platební QR kód.",
        "smart_locks.essential1": "V aplikaci TTLock otevřete zámek a klepněte na Autorizovaný správce (anglicky Authorized Admin, v některých verzích eAdmin).",
        "smart_locks.essential2": "Klepněte na Vytvořit správce (Create Admin). Do pole Příjemce (Recipient), kde TTLock čeká e-mail nebo telefon, vložte svůj název UbyHost z řádku výše. Nechte zapnuto Trvalý (Permanent) a klepněte na Odeslat (Send).",
        "smart_locks.essential3": "Vraťte se sem a klepněte na Zkontrolovat připojení.",
        "smart_locks.s4": "Klepněte na Autorizovaný správce (Authorized Admin, v některých verzích eAdmin). Je to ikona s osobou a fajfkou v mřížce pod zámkem.",
        "smart_locks.s6": "Nechte zapnuto Trvalý (Permanent). Do pole Příjemce (Recipient), kde TTLock čeká e-mail nebo telefon, vložte svůj název UbyHost. Do pole Jméno (Name) napište UbyHost.",
    },
}
for _lang, _strings in _ONBOARDING_TEST_0205_STRINGS.items():
    STRINGS[_lang].update(_strings)

```

### Step 9. `App/app/host_vi_i18n.py`

Append at the very end of the file:

```python

# 0205: onboarding user test (2026-10-21).
STRINGS.update({
    "apartment.form.ubyport.mark_hint": "Tự điền từ tên đăng nhập: phần sau UBY-WS_. Chỉ sửa nếu thư của cảnh sát ghi “Zkratka ubytovacího zařízení” khác.",
    "apartment.form.stay_fee.account_help": "Tài khoản ngân hàng của thành phố cho phí lưu trú, lấy từ trang web hoặc thư của họ. Dán cả số tài khoản (19-2000145399/0800) hoặc IBAN vào ô bất kỳ, hệ thống sẽ tự tách. Dùng cho mã QR thanh toán.",
    "smart_locks.essential1": "Trong ứng dụng TTLock, mở khóa của bạn và bấm Authorized Admin (một số phiên bản ghi eAdmin).",
    "smart_locks.essential2": "Bấm Create Admin. Ở ô Recipient, nơi TTLock chờ email hoặc số điện thoại, dán tên UbyHost của bạn ở trên. Để nguyên Permanent bật và bấm Send.",
    "smart_locks.essential3": "Quay lại đây và bấm Kiểm tra kết nối.",
    "smart_locks.s4": "Bấm Authorized Admin (một số phiên bản ghi eAdmin). Đó là biểu tượng hình người có dấu tích, trong lưới bên dưới ổ khóa.",
    "smart_locks.s6": "Để nguyên Permanent ở trạng thái bật. Ở ô Recipient, nơi TTLock chờ email hoặc số điện thoại, dán tên UbyHost của bạn. Ở ô Name, nhập UbyHost.",
})
```

Before writing `essential3` in Vietnamese, run `grep -n '"smart_locks.check"' App/app/host_vi_i18n.py` and use that exact button text instead of "Kiểm tra kết nối" if it differs.

### Step 10. `App/tests/test_reporting_help_0097.py`

a) Anchor (exact, 2 lines):

```
    "stay_fee_payee": "apartment.form.stay_fee.payee_hint",
    "stay_fee_instruction": "apartment.form.stay_fee.instruction_hint",
```

Delete these 2 lines.

b) Anchor (exact, 2 lines):

```
                     "stay_fee_authority_contact", "stay_fee_authority_databox", "stay_fee_payee",
                     "stay_fee_instruction"):
```

Replace with:

```
                     "stay_fee_authority_contact", "stay_fee_authority_databox"):
```

### Step 11. `App/tests/test_fee_setup_compatibility.py`

Anchor: `                              "stay_fee_authority_name", "stay_fee_authority_databox", "stay_fee_instruction"):`
Replace with: `                              "stay_fee_authority_name", "stay_fee_authority_databox"):`

### Step 12. `App/tests/test_host_ux_acceptance.py`

Anchor: `    "stay_fee_authority_databox", "stay_fee_payee", "stay_fee_instruction", "automation_mode",`
Replace with: `    "stay_fee_authority_databox", "automation_mode",`

### Step 13. `App/tests/test_property_navigation_browser.py`

Anchor: `    "stay_fee_payee", "stay_fee_instruction", "automation_mode", "submit_after_hours", "default_purpose",`
Replace with: `    "automation_mode", "submit_after_hours", "default_purpose",`

### Step 14. Create `App/tests/test_fee_form_partial.py`

```python
"""0205: a shorter stay-fee form (the setup wizard) never wipes stored office details."""
from __future__ import annotations

from starlette.datastructures import FormData

from app.routes import stay_fees

KEPT = (
    "stay_fee_authority_name", "stay_fee_authority_address", "stay_fee_authority_contact",
    "stay_fee_authority_databox", "stay_fee_payee", "stay_fee_instruction",
)


def test_a_form_without_the_office_fields_leaves_them_out():
    values = stay_fees.fee_form_values(FormData([
        ("stay_fee_rate_czk", "30"), ("stay_fee_vs", "123"),
        ("account_number", "2000145399"), ("account_bank", "0800"),
    ]))
    assert values["stay_fee_rate_czk"] == 30 and values["stay_fee_vs"] == "123"
    for key in KEPT:
        assert key not in values, key


def test_a_full_form_still_writes_the_office_fields():
    values = stay_fees.fee_form_values(FormData([(key, "") for key in KEPT]))
    for key in KEPT:
        assert key in values and values[key] is None, key
```

If `values["stay_fee_rate_czk"]` is a string or Decimal, not `30`, adjust only that comparison to the type `fee_form_values` returns and say so in the report.

### Step 15. Cache keys

Command: `cd App && .venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`

## 5. Do not touch

Filing code (`soap`, `worker`, `claim`, `validation.py`), `routes/admin.py`, the stay-fee report and PDF code, guest templates, `_smart_locks_panel.html`. AGENTS hard rules 1, 3, 5, 8.

## 6. Commands

From `App/`, each ending `-q --tb=short -x 2>&1 | tail -30`:

1. `.venv/bin/python -m pytest tests/test_fee_form_partial.py tests/test_fee_setup_compatibility.py tests/test_stay_fee_property_panel.py tests/test_reporting_help_0097.py tests/test_onboarding_wizard_survival.py tests/test_smart_locks_page.py tests/test_static_versions.py tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py`
2. `.venv/bin/python -m pytest tests/test_stay_fee*.py tests/test_invoice_*.py`
3. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_ux_acceptance.py tests/test_property_navigation_browser.py tests/test_onboarding_wizard_browser.py tests/test_design_setup_wizard_browser.py tests/test_design_guardrails_browser.py -rs` (0 skipped)

A browser test that fails because a wizard step now refuses a save with an empty required field: STOP and report the test and the field; do not change it.

## 7. Acceptance

- [ ] All §6 commands pass, 0 skipped.
- [ ] `grep -rn "stay_fee_payee\|stay_fee_instruction" App/app/templates` prints nothing.
- [ ] `git diff --stat` lists only §3 files.

## 8. Stop and ask

As in TEMPLATE.md §8.

## 9. Report

`docs/tasks/0205-report.md`, as in TEMPLATE.md §9.

## Risk list (for the reviewer)

`routes/stay_fees.py` `fee_form_values`, `host.js` paste split, `police.html` required fields.

## Owner steps

1. After merge, deploy as usual. New cache keys ship with it.
