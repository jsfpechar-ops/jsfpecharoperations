# 0209: The fee-report signature moves to the stay-fee setup

Status: todo
Depends on: 0210 | Base commit: f547ef0 | Branch: claude/project-thread-cf47ju
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

A test user did not understand "Signature on the fee report" on Business details. The signature block moves next to the stay fee it is printed on (wizard stay-fee step and settings → Reporting & fees), saved to the property's operator, and leaves the Business page.

## 2. Context

The signature is stored on the operator (`legal_entity.signature_png_enc`, encrypted; `signature_name`) and printed on stay-fee reports. It stays stored there; only where it is edited changes.

`App/app/templates/_entity_business_fields.html` has `{% macro signature_fields(prefix, entity, preview='') %}` (a `<fieldset class="signature-block" data-host-signature>` with a canvas, hidden `signature_drawn`, file input `signature_file`, optional `signature_remove`, and `signature_name`). `host.js` wires every `[data-host-signature]`. `business_form_body` calls it:

```
  {{ business_fields(prefix, entity) }}
  {{ signature_fields(prefix, entity, preview) }}
{% endmacro %}
```

`App/app/routes/admin.py` has `async def _signature_payload(form)` (returns `None` for an invalid image, `{}` when nothing was sent, else the columns to write). The `/entities` POST routes keep using it; do not change them.

`apartment_update` (`admin.py`, verbatim start):

```
    form = await request.form()
    rejected, _address_mismatch = _save_apartment_form(apartment_id, request, form)
    if rejected:
        return rejected
```

The settings form tag (`_property_editor.html`, verbatim):

```
<form method="post" action="{{ base_url }}" class="property-settings-form" id="property-settings-form" data-property-settings-form data-unsaved-guard>
```

The wizard stay-fee form tag (`setup_wizard/stay_fee.html`, verbatim):

```
<form method="post" action="/apartments/{{ apartment.id }}" class="setup-wizard-form" id="stay-fee-form">
```

`_stay_fee_fields.html` ends with the line `</div>{% endif %}`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/_fee_signature_fields.html | create | the block, for both forms |
| App/app/templates/_stay_fee_fields.html | edit | include it at the end |
| App/app/templates/_property_editor.html | edit | form becomes multipart |
| App/app/templates/setup_wizard/stay_fee.html | edit | form becomes multipart |
| App/app/templates/_entity_business_fields.html | edit | no signature on Business details |
| App/app/routes/admin.py | edit | context helper + save on property update |
| App/app/routes/onboarding_wizard.py | edit | context on the stay-fee step |
| App/app/host_i18n.py | edit | `_ONBOARDING_TEST_0209_STRINGS` |
| App/app/host_vi_i18n.py | edit | Vietnamese |
| App/tests/test_host_ux_acceptance.py | edit | business field list |
| App/tests/test_property_navigation_browser.py | edit | settings field names |
| App/tests/test_fee_signature_0209.py | create | tests |
| App/tests/test_stay_fee_property_panel.py | edit | Step 0 pin |
| App/tests/test_entity_editor_fields.py | edit | Step 11 pins |

No other file may change.

## 4. Steps

### Step 0. CI fix first (PR #418 CI red after 0208)

`App/tests/test_stay_fee_property_panel.py`: replace `    assert "Enter a valid Czech bank account or IBAN." in invalid.text` with `    assert "This account number does not add up." in invalid.text  # 0208 copy`. Run `.venv/bin/python -m pytest tests/test_stay_fee_property_panel.py -q --tb=short 2>&1 | tail -10` from `App/`. Commit `0209 step 0`.

### Step 1. `App/app/templates/_fee_signature_fields.html` (new)

```
{#- 0209: the stay-fee report signature, edited where the stay fee is set up.
    Saved to the property's operator by apartment_update; needs a multipart form. -#}
{%- from "_entity_business_fields.html" import signature_fields with context -%}
{% if fee_signature and fee_signature.entity %}
<input type="hidden" name="fee_signature_section" value="1">
{{ signature_fields('fee_', fee_signature.entity, fee_signature.preview) }}
{% endif %}
```

### Step 2. `_stay_fee_fields.html`

After its last line `</div>{% endif %}` add a new last line: `{% include "_fee_signature_fields.html" %}`

### Step 3. Multipart forms

a) `_property_editor.html`: in the settings form tag quoted in §2 insert ` enctype="multipart/form-data"` after `action="{{ base_url }}"`.
b) `setup_wizard/stay_fee.html`: in the form tag quoted in §2 insert ` enctype="multipart/form-data"` after `action="/apartments/{{ apartment.id }}"`.

### Step 4. Business page

In `_entity_business_fields.html`, `business_form_body`: replace `  {{ signature_fields(prefix, entity, preview) }}` with `  <p class="small">{{ t('entity.signature.moved') }}</p>`. Keep the `signature_fields` macro itself.

### Step 5. `admin.py`

a) Directly above `def _render_apartment_detail(` add:

```python
def _fee_signature_context(request: Request, apartment) -> Optional[Dict[str, Any]]:
    """0209: the operator's stay-fee report signature, shown with the stay fee."""
    entity_id = dict(apartment).get("legal_entity_id")
    entity = access.entity(request, int(entity_id)) if entity_id else None
    if not entity:
        return None
    preview = db.decrypt_field(entity["signature_png_enc"]) if entity["signature_png_enc"] else ""
    return {"entity": entity, "preview": preview or ""}
```

b) In `_render_apartment_detail`, in the dict passed to `render(... "apartment_form.html", {`, directly after `            "apartment": apartment,` add `            "fee_signature": _fee_signature_context(request, apartment),`.

c) In `apartment_update`, directly after the `if rejected:` / `return rejected` lines quoted in §2, add:

```python
    # 0209: the stay-fee signature is saved to the property's operator.
    if _form_str(form, "fee_signature_section") == "1":
        saved = access.apartment(request, apartment_id)
        entity = (
            access.entity(request, saved["legal_entity_id"])
            if saved and saved["legal_entity_id"] else None
        )
        if entity:
            signature = await _signature_payload(form)
            if signature is None:
                back = (
                    property_setup.wizard_url(apartment_id, "stay_fee")
                    if _form_str(form, "setup_step") == "stay_fee"
                    else f"/apartments/{apartment_id}?view=settings&section=reporting#stay-fee-settings"
                )
                return _back(back, err=_flash(request, "flash.entities.signature_invalid"))
            if signature:
                db.update("legal_entity", entity["id"], signature)
```

Check `property_setup` is imported in `admin.py` (`grep -n "property_setup" App/app/routes/admin.py | head -2`); it is used there already. If `access.entity` takes a different signature than `(request, entity_id)`, read it and match; say so in the report.

### Step 6. `onboarding_wizard.py`

In `_wizard_context`'s returned dict, directly after `        "lock_available": lock_available,` add:

```python
        # 0209: the report signature sits with the stay fee it is printed on.
        "fee_signature": (
            admin_routes._fee_signature_context(request, apartment) if step == "stay_fee" else None
        ),
```

### Step 7. Text

`host_i18n.py`, above `STRINGS["vi"] = dict(_VI_STRINGS)`, after the last `_ONBOARDING_TEST_..._STRINGS` loop:

```python
_ONBOARDING_TEST_0209_STRINGS = {
    "en": {
        "entity.signature.moved": "The signature for stay-fee reports is now set with the stay fee, in each property's Reporting & fees.",
    },
    "cs": {
        "entity.signature.moved": "Podpis na hlášení poplatku z pobytu nastavíte u poplatku, v části Hlášení a poplatky u ubytování.",
    },
}
for _lang, _strings in _ONBOARDING_TEST_0209_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

Append to `host_vi_i18n.py`:

```python

# 0209: signature moved to the stay fee.
STRINGS.update({
    "entity.signature.moved": "Chữ ký trên báo cáo phí lưu trú giờ được đặt cùng phần phí lưu trú, trong mục Báo cáo và phí của từng chỗ ở.",
})
```

### Step 8. Test pins

a) `test_host_ux_acceptance.py`: in `BUSINESS_FIELDS` remove `"signature_file", "signature_name"` (keep the set valid Python: the second line becomes `}` or join it onto the first line).
b) `test_property_navigation_browser.py`: run `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_property_navigation_browser.py -q --tb=short -k "not fit_every_width" 2>&1 | tail -30`. If the `SETTINGS_NAMES` assertion fails only with the new names (`fee_signature_section`, `signature_drawn`, `signature_file`, `signature_name`, `signature_remove`), add exactly those it lists to `SETTINGS_NAMES`. Any other difference: STOP.

### Step 9. New test `App/tests/test_fee_signature_0209.py`

Reuse fixtures from `tests/test_fee_form_partial.py` (it posts a fee form for a property with an operator) and the PNG data-URL helper from `tests/test_entity_editor_fields.py` (`_drawn`). Tests:

1. GET the property settings page `?view=settings&section=reporting&lang=en`: contains `name="fee_signature_section"` and `id="fee_sig-canvas"`, and the form tag has `enctype="multipart/form-data"`.
2. GET `/entities?edit=<entity id>&lang=en`: contains no `sig-canvas` and contains the English `entity.signature.moved` text.
3. POST the fee form plus `fee_signature_section=1`, `signature_drawn=<valid PNG data URL>`, `signature_name="Jana Pole"`: the operator row then has `signature_name == "Jana Pole"` and a non-empty `signature_png_enc`.
4. POST the same with `signature_drawn="data:image/png;base64,AAAA"`: response is a redirect whose location contains `stay-fee-settings` and `err=`; the operator signature is unchanged.

### Step 10. Commit

`0209 signature with stay fee`, only §3 files, trailers from your prompt, never PNGs.

### Step 11 (follow-up). Business-page signature pins in `App/tests/test_entity_editor_fields.py`

The signature left Business details on purpose (Step 4), so these pins move. Add the file to §3.

a) `test_the_remove_checkbox_only_shows_with_a_stored_signature`: replace its last line `    assert page.count('name="signature_remove"') == 1` with `    assert 'name="signature_remove"' not in page  # 0209: the signature is edited with the stay fee`. Then in `App/tests/test_fee_signature_0209.py` add one test: on the property settings page (`?view=settings&section=reporting&lang=en`) `name="signature_remove"` is absent while the operator has no signature, and present exactly once after `db.update("legal_entity", <id>, {"signature_png_enc": db.encrypt_field(<valid PNG data URL>)})`. That test also asserts `'accept="image/png,image/jpeg"' in page` and `'maxlength="80"' in page`.

b) `test_the_entity_forms_keep_their_contract`: delete the two `expected` entries lines
```
        "signature_name": ('type="text"', False), "signature_file": ('type="file"', False),
        "signature_drawn": ('type="hidden"', False),
```
then delete the two lines `    assert 'accept="image/png,image/jpeg"' in _tag(page, "signature_file")` and `    assert 'maxlength="80"' in _tag(page, "signature_name")`. Add, after the `for form, prefix in forms:` loop, `    assert "sig-canvas" not in page  # 0209`.
   The `field_id = "signature" if ...` line may stay.

c) `test_entity_lookup_keeps_typed_identity`: remove `            "signature_name": "Typed signer",` from the posted dict and `'value="Typed signer"', ` from the `typed` tuple.

d) Run `.venv/bin/python -m pytest tests/test_entity_editor_fields.py tests/test_fee_signature_0209.py -q --tb=short 2>&1 | tail -30` from `App/`. If a fourth failure remains, and it pins the signature on Business details, change it the same way (absent instead of present) and list it; anything else: STOP.

Commit `0209 step 11`.

## 5. Do not touch

`/entities` POST handlers, `_signature_payload`, `stay_fee_remittance_pdf.py`, filing code, guest templates, CSS, JS. AGENTS hard rules 1, 2, 3, 5, 6, 8.

## 6. Commands

1. From `App/`: `.venv/bin/python -m pytest tests/test_fee_signature_0209.py tests/test_stay_fee_signature.py tests/test_entity_editor_fields.py tests/test_entity_editor_navigation.py tests/test_fee_form_partial.py tests/test_fee_one_box_0208.py tests/test_stay_fee.py -q --tb=short 2>&1 | tail -30`
2. From `App/`: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_ux_acceptance.py tests/test_onboarding_wizard_browser.py tests/test_fee_setup_compatibility.py tests/test_host_unsaved_changes_browser.py -q --tb=line -rs 2>&1 | tail -30` (0 skipped)
3. From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -5` → `OK`
4. 390 px screenshots of the wizard stay-fee step and settings → Reporting & fees (signature block visible) to `/mnt/project-files/onboarding-0209/`. Do not commit them.

## 7. Acceptance

- [ ] The signature block is on the stay-fee step and in settings, saves to the operator, and is gone from Business details with a one-line pointer.
- [ ] §6 passes.

## 8. Stop and ask

As in TEMPLATE.md §8. If the multipart change breaks the unsaved-changes browser test, STOP and report the assertion.

## 9. Report

`docs/tasks/0209-report.md`, as in TEMPLATE.md §9.
