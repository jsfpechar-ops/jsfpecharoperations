# 0204: Required-field asterisks and simpler property and business forms

Status: done
Depends on: 0203 (same branch, run after it) | Base commit: ebe3109 | Branch: claude/project-thread-cf47ju
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Make every host form show which fields are required with an asterisk, and cut the property and business forms down, app-wide (not only in the setup wizard). This covers rows 3 to 8 of the first user test (2026-10-21): asterisks, IČO first, the signature explained, no English city box, the street explained, and the guest message template explained.

## 2. Context

- Owner decision (Josef, 2026-10-21): "build all as proposed, ... this should also apply to the app, it's too complicated at times, so we need to cut it down".
- The asterisk comes from CSS only: a `.field` that holds a `required` input, select or textarea gets ` *` after its label. `content: " *" / ""` hides the star from screen readers, which already announce "required". So the star is right wherever `required` is right. The "(optional)" text in `field_label` goes away so a form uses one system.
- City for guests: the property stores `city_en`, shown to guests next to the property name. It is no longer typed: the server sets it from the address town (`addr_obec`), with "Prague" for Praha and "Pilsen" for Plzeň. The form keeps a hidden `city_en` input with the same id so form-shape tests still see it.
- Changed CSS gets a new `?v=` key; `tests/static_versions.json` is rewritten with `--write`. Copy: no em dashes; every new key in `en`, `cs`, `vi`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/static/host2.css | edit | asterisk, legend, message steps |
| App/app/templates/base.html | edit | new `host2.css` key |
| App/app/templates/_components.html | edit | `field_label` drops "(optional)" |
| App/app/templates/_entity_business_fields.html | edit | IČO first, legend, no "(optional)" spans |
| App/app/templates/_property_identity_fields.html | edit | city box becomes hidden |
| App/app/templates/_property_address_fields.html | edit | natural order, street hint |
| App/app/templates/_property_editor.html | edit | legend |
| App/app/templates/_property_create.html | edit | legend |
| App/app/templates/setup_wizard/_layout.html | edit | legend on form steps |
| App/app/templates/setup_wizard/guest_link.html | edit | visible template steps |
| App/app/property_setup.py | edit | `guest_city()` |
| App/app/routes/admin.py | edit | set `city_en` from the town on save |
| App/app/host_i18n.py | edit | one new strings block |
| App/app/host_vi_i18n.py | edit | the same keys in Vietnamese |
| App/tests/test_property_address_required.py | edit | optional labels carry no "(optional)" now |
| App/tests/test_property_create_browser.py | edit | city follows the town |
| App/tests/test_property_guest_city.py | create | unit test for `guest_city` and the save |
| App/tests/test_onboarding_wizard_browser.py | edit | 0203 left-over: the finish button now goes to the dashboard |
| App/tests/static_versions.json | regenerate | `--write` |

No other file may change.

## 4. Steps

### Step 0. `App/tests/test_onboarding_wizard_browser.py` (left over from 0203)

0203 sent the wizard's finish button to the dashboard; this test still waited for the property overview.

Anchor (exact, 2 lines):

```
        page.locator(".setup-wizard-foot .ui-btn-primary").click()
        page.wait_for_url("**/apartments/*?view=overview**")
```

Replace with:

```
        with page.expect_navigation():
            page.locator(".setup-wizard-foot .ui-btn-primary").click()
        # 0203: the finish button goes to the dashboard, not the property.
        assert "/setup" not in page.url and "/apartments/" not in page.url, page.url
        page.goto(f"{base_url}/apartments/{flat['id']}?view=overview&lang={lang}")
```

Command: `cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_onboarding_wizard_browser.py -k wizard_polish_and_overview_cards -q --tb=short -x -rs 2>&1 | tail -15` → all pass, 0 skipped.

### Step 1. `App/app/static/host2.css`

Append at the very end of the file:

```css

/* 0204: a required field carries a red asterisk, read from its own required attribute.
   Screen readers already say "required", so the star is hidden from them. */
.host-workspace .field:has(:is(input, select, textarea)[required]) > label::after,
.host-workspace .field:has(:is(input, select, textarea)[required]) > .field-label-row > label::after { content: " *" / ""; color: var(--danger); font-weight: 700; }
.host-workspace .required-legend { margin: 0 0 var(--space-3); color: var(--ink-muted); font-size: 14px; }
.host-workspace .setup-wizard-message-steps { margin: var(--space-2) 0 var(--space-3); padding-left: var(--space-5); }
```

### Step 2. `App/app/templates/base.html`

Anchor: `/static/host2.css?v=20261021-0203` → replace with `/static/host2.css?v=20261021-0204`

### Step 3. `App/app/templates/_components.html`

Anchor: `    <label for="{{ for }}">{{ text }}{% if optional %} <span class="muted">{{ t('common.optional') }}</span>{% endif %}</label>`
Replace with: `    <label for="{{ for }}">{{ text }}</label>`

(Keep the `optional` parameter in the macro signature; callers still pass it.)

### Step 4. `App/app/templates/_entity_business_fields.html`

a) Anchor (exact, 3 lines):

```
{% macro business_fields(prefix, entity) %}
  <div class="field">
    <label for="{{ prefix }}name">{{ t('entities.name') }}</label>
```

Replace with:

```
{% macro business_fields(prefix, entity) %}
  {#- 0204: IČO and the register lookup come first; the lookup fills the rest. -#}
  <div class="grid">
    {{ ico_field(prefix ~ 'ico', entity.ico if entity else '', 'business') }}
    <div class="field">
      <label for="{{ prefix }}dic">{{ t('entities.dic') }}</label>
      <input type="text" id="{{ prefix }}dic" name="dic" value="{{ (entity.dic or '') if entity else '' }}">
    </div>
  </div>
  <div class="field">
    <label for="{{ prefix }}name">{{ t('entities.name') }}</label>
```

b) Anchor (exact, 7 lines; this is the old IČO block, now further down):

```
  <div class="grid">
    {{ ico_field(prefix ~ 'ico', entity.ico if entity else '', 'business') }}
    <div class="field">
      <label for="{{ prefix }}dic">{{ t('entities.dic') }} <span class="opt">{{ t('common.optional') }}</span></label>
      <input type="text" id="{{ prefix }}dic" name="dic" value="{{ (entity.dic or '') if entity else '' }}">
    </div>
  </div>
```

Delete these 7 lines.

c) Anchor: `      <label for="{{ prefix }}contact_phone">{{ t('entities.phone') }} <span class="opt">{{ t('common.optional') }}</span></label>`
Replace with: `      <label for="{{ prefix }}contact_phone">{{ t('entities.phone') }}</label>`

d) Anchor (exact, 2 lines):

```
  {{ register_messages(ares_error, ares_note) }}
  {{ business_fields(prefix, entity) }}
```

Replace with:

```
  <p class="required-legend">{{ t('common.required_legend') }}</p>
  {{ register_messages(ares_error, ares_note) }}
  {{ business_fields(prefix, entity) }}
```

Command: `grep -c "ico_field(prefix" App/app/templates/_entity_business_fields.html` → `1`.

### Step 5. `App/app/templates/_property_identity_fields.html`

Anchor (exact, 4 lines):

```
  <div class="field">
    {{ field_label('city_en', t('apartment.form.city_en.label'), t('apartment.form.city_en.hint'), true) }}
    <input type="text" id="city_en" name="city_en" value="{{ pv.city_en or '' }}" aria-describedby="city_en-help">
  </div>
```

Replace with:

```
  {#- 0204: guests see the town from the address; the server sets city_en on save. -#}
  <input type="hidden" id="city_en" name="city_en" value="{{ pv.city_en or '' }}">
```

### Step 6. `App/app/templates/_property_address_fields.html`

Anchor (exact, 10 lines):

```
<div class="grid property-address-grid">
  {{ address_input('addr_okres', t('apartment.form.addr.okres'), t('apartment.form.addr.okres_hint'), true, 32) }}
  {{ address_input('addr_obec', t('apartment.form.addr.obec'), '', false, 48, '', true) }}
  {{ address_input('addr_obec_cast', t('apartment.form.addr.obec_cast'), '', true, 48) }}
</div>
<div class="grid property-address-grid">
  {{ address_input('addr_street', t('apartment.form.addr.street'), '', true, 48) }}
  {{ address_input('addr_house_no', t('apartment.form.addr.house_no'), t('apartment.form.addr.house_no_hint'), false, 5, '', true) }}
  {{ address_input('addr_orient_no', t('apartment.form.addr.orient_no'), t('apartment.form.addr.orient_no_hint'), true, 4) }}
  {{ address_input('addr_zip', t('apartment.form.addr.zip'), t('apartment.form.addr.zip_hint'), false, 6, 'numeric', true) }}
</div>
```

Replace with (same fields, the order people write an address, a hint on the street):

```
<div class="grid property-address-grid">
  {{ address_input('addr_street', t('apartment.form.addr.street'), t('apartment.form.addr.street_hint'), true, 48) }}
  {{ address_input('addr_house_no', t('apartment.form.addr.house_no'), t('apartment.form.addr.house_no_hint'), false, 5, '', true) }}
  {{ address_input('addr_orient_no', t('apartment.form.addr.orient_no'), t('apartment.form.addr.orient_no_hint'), true, 4) }}
  {{ address_input('addr_zip', t('apartment.form.addr.zip'), t('apartment.form.addr.zip_hint'), false, 6, 'numeric', true) }}
</div>
<div class="grid property-address-grid">
  {{ address_input('addr_obec', t('apartment.form.addr.obec'), '', false, 48, '', true) }}
  {{ address_input('addr_obec_cast', t('apartment.form.addr.obec_cast'), '', true, 48) }}
  {{ address_input('addr_okres', t('apartment.form.addr.okres'), t('apartment.form.addr.okres_hint'), true, 32) }}
</div>
```

### Step 7. `App/app/templates/_property_editor.html`

Anchor: `<form method="post" action="{{ base_url }}" class="property-settings-form" id="property-settings-form" data-property-settings-form data-unsaved-guard>`
Insert this line immediately AFTER the anchor line:
`  <p class="required-legend">{{ t('common.required_legend') }}</p>`

### Step 8. `App/app/templates/_property_create.html`

Anchor: `    <form method="post" action="/apartments" class="property-create-form" id="property-create-form">`
Insert this line immediately AFTER the anchor line:
`      <p class="required-legend">{{ t('common.required_legend') }}</p>`

### Step 9. `App/app/templates/setup_wizard/_layout.html`

Anchor: `    {% if setup_notice %}<p class="err-text" role="alert">{{ setup_notice }}</p>{% endif %}`
Insert this line immediately BEFORE the anchor line:
`    {% if wizard_step in ('property', 'police', 'stay_fee') %}<p class="required-legend">{{ t('common.required_legend') }}</p>{% endif %}`

### Step 10. `App/app/templates/setup_wizard/guest_link.html`

Anchor (exact, 2 lines):

```
    {{ help_tip('wizard-message-help', t('wizard.guest_link.message_help')) }}
  </header>
```

Replace with:

```
  </header>
  {#- 0204: said on the page, not in a tip: this is a template to paste into Airbnb or Booking. -#}
  <ol class="setup-wizard-message-steps">
    <li>{{ t('wizard.guest_link.message_step1') }}</li>
    <li>{{ t('wizard.guest_link.message_step2') }}</li>
  </ol>
```

### Step 11. `App/app/property_setup.py`

Append at the very end of the file:

```python


# 0204: the town guests see next to the property name. It follows the police
# address; the biggest towns get their English name, the rest stay as typed.
_GUEST_CITY_NAMES = {"plzeň": "Pilsen"}


def guest_city(obec: str) -> str:
    town = " ".join((obec or "").split())
    if town.lower().startswith("praha"):
        return "Prague"
    return _GUEST_CITY_NAMES.get(town.lower(), town)
```

### Step 12. `App/app/routes/admin.py` (three small edits)

a) Anchor: `    payload["addr_zip"] = validation.normalise_zip(payload["addr_zip"])`
(4-space indent, inside `_apartment_payload`). Insert this line immediately AFTER it:
`    payload["city_en"] = property_setup.guest_city(payload["addr_obec"])`

b) Anchor: `            payload["addr_zip"] = validation.normalise_zip(payload.get("addr_zip", ""))`
(12-space indent, inside `_wizard_step_payload`). Insert this line immediately AFTER it (8-space indent):
`        payload["city_en"] = property_setup.guest_city(payload.get("addr_obec", ""))`

c) Anchor (exact, 2 lines):

```
                # A section form without address inputs must not blank the address.
                payload.pop(field, None)
```

Insert immediately AFTER these two lines (8-space indent):

```
        if "addr_obec" not in form:
            # 0204: no town posted, so the guest-facing city stays as it is.
            payload.pop("city_en", None)
```

Command: `cd App && .venv/bin/python -c "from app import property_setup as p; print(p.guest_city('Praha'), p.guest_city(' Plzeň '), p.guest_city('Brno'))" 2>&1 | tail -3` → `Prague Pilsen Brno`.

### Step 13. `App/app/host_i18n.py`

Anchor: `STRINGS["vi"] = dict(_VI_STRINGS)`
Insert immediately BEFORE the anchor:

```python
# 0204: onboarding user test (2026-10-21): required marks, the signature and
# the guest message template explained, the street explained.
_ONBOARDING_TEST_0204_STRINGS = {
    "en": {
        "common.required_legend": "Fields marked * are required.",
        "entity.signature.heading": "Your signature on stay-fee reports",
        "entity.signature.scope": "Optional. The town wants the stay-fee report signed. Draw your signature once and UbyHost adds it to every report, so you do not print and sign it by hand. Without it, your typed name is printed.",
        "apartment.form.addr.street_hint": "Fill it in if the street has a name. In villages without streets, the house number is enough.",
        "wizard.guest_link.message_title": "Message template for guests",
        "wizard.guest_link.message_step1": "Replace the parts in [square brackets] with your own details: key handover, directions, quiet hours.",
        "wizard.guest_link.message_step2": "Paste it into the automatic message Airbnb or Booking.com sends after each booking. UbyHost does not send it.",
        "wizard.guest_link.done": "Continue",
    },
    "cs": {
        "common.required_legend": "Pole označená * jsou povinná.",
        "entity.signature.heading": "Váš podpis na hlášení poplatku z pobytu",
        "entity.signature.scope": "Nepovinné. Obec chce hlášení poplatku z pobytu podepsané. Nakreslete podpis jednou a UbyHost ho vloží do každého hlášení, takže ho nemusíte tisknout a podepisovat ručně. Bez podpisu se vytiskne vaše jméno.",
        "apartment.form.addr.street_hint": "Vyplňte, pokud ulice existuje. V obcích bez ulic stačí číslo popisné.",
        "wizard.guest_link.message_title": "Šablona zprávy pro hosty",
        "wizard.guest_link.message_step1": "Části v [hranatých závorkách] nahraďte svými údaji: předání klíčů, cesta, noční klid.",
        "wizard.guest_link.message_step2": "Vložte ji do automatické zprávy, kterou Airbnb nebo Booking.com posílá po každé rezervaci. UbyHost ji neposílá.",
        "wizard.guest_link.done": "Pokračovat",
    },
}
for _lang, _strings in _ONBOARDING_TEST_0204_STRINGS.items():
    STRINGS[_lang].update(_strings)

```

### Step 14. `App/app/host_vi_i18n.py`

Append at the very end of the file:

```python

# 0204: onboarding user test (2026-10-21).
STRINGS.update({
    "common.required_legend": "Các trường có dấu * là bắt buộc.",
    "entity.signature.heading": "Chữ ký của bạn trên báo cáo phí lưu trú",
    "entity.signature.scope": "Không bắt buộc. Thành phố yêu cầu báo cáo phí lưu trú có chữ ký. Vẽ chữ ký một lần, UbyHost sẽ thêm vào mọi báo cáo, bạn không cần in và ký tay. Nếu không có, tên bạn nhập sẽ được in.",
    "apartment.form.addr.street_hint": "Điền nếu đường có tên. Ở làng không có tên đường, chỉ cần số nhà.",
    "wizard.guest_link.message_title": "Mẫu tin nhắn cho khách",
    "wizard.guest_link.message_step1": "Thay các phần trong [ngoặc vuông] bằng thông tin của bạn: giao chìa khóa, chỉ đường, giờ yên tĩnh.",
    "wizard.guest_link.message_step2": "Dán vào tin nhắn tự động mà Airbnb hoặc Booking.com gửi sau mỗi lượt đặt. UbyHost không gửi tin nhắn này.",
    "wizard.guest_link.done": "Tiếp tục",
})
```

### Step 15. `App/tests/test_property_address_required.py`

Anchor (the LAST line of `test_create_page_marks_the_three_parts_required_and_the_rest_optional`):
`            assert optional in label, (lang, field)`
Replace with:
`            assert optional not in label, (lang, field)  # 0204: the asterisk marks required fields instead`

### Step 16. `App/tests/test_property_create_browser.py`

a) Anchor: `    assert row["internal_name"] == "Synthetic Loft" and row["city_en"] == "Brno"`
Replace with: `    assert row["internal_name"] == "Synthetic Loft" and row["city_en"] == "Prague"  # 0204: from the town`

Before replacing, check with `grep -n '"addr_obec"' App/tests/test_property_create_browser.py` that the create data in that test uses `"addr_obec": "Praha"`. If it uses another town, write `property_setup.guest_city(<that town>)`'s result instead and say so in the report.

b) Anchor: `        page.locator("#city_en").fill("Brno")`
Replace with: `        page.locator("#addr_obec").fill("Brno")`

### Step 17. Create `App/tests/test_property_guest_city.py`

```python
"""0204: the guest-facing city is never typed; it follows the address town."""
from __future__ import annotations

from app import property_setup


def test_big_towns_get_their_english_name_and_the_rest_stay_as_typed():
    assert property_setup.guest_city("Praha") == "Prague"
    assert property_setup.guest_city("Praha 3") == "Prague"
    assert property_setup.guest_city(" Plzeň ") == "Pilsen"
    assert property_setup.guest_city("Český  Krumlov") == "Český Krumlov"
    assert property_setup.guest_city("") == ""
```

### Step 18. Cache keys

Command: `cd App && .venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`

## 5. Do not touch

Guest templates (`templates/guest/`), `guest.css`, filing code, `_smart_locks_panel.html`, the stay-fee files (brief 0205). AGENTS hard rules 1, 3, 5, 8.

## 6. Commands

From `App/`, each ending `-q --tb=short -x 2>&1 | tail -30`:

1. `.venv/bin/python -m pytest tests/test_property_guest_city.py tests/test_property_address_required.py tests/test_onboarding.py tests/test_onboarding_wizard_survival.py tests/test_property_operator_defaults.py tests/test_property_readiness.py tests/test_static_versions.py tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py`
2. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_property_create_browser.py tests/test_onboarding_wizard_browser.py tests/test_design_setup_wizard_browser.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py -rs` (0 skipped)
3. `.venv/bin/python -m pytest tests -k "entit or business" -rs` (entity form tests)

## 7. Acceptance

- [ ] All §6 commands pass, 0 skipped.
- [ ] `grep -n "common.optional" App/app/templates/_components.html App/app/templates/_entity_business_fields.html` prints nothing.
- [ ] `git diff --stat` lists only §3 files.

## 8. Stop and ask

As in TEMPLATE.md §8. A geometry or guardrail test that fails because of the asterisk or the new order: STOP and report the failing assertion; do not change the test.

## 9. Report

`docs/tasks/0204-report.md`, as in TEMPLATE.md §9.

## Risk list (for the reviewer)

`routes/admin.py` city lines, `host2.css` `:has()` rule, `_entity_business_fields.html`.

## Owner steps

1. After merge, deploy as usual. New cache keys ship with it.
