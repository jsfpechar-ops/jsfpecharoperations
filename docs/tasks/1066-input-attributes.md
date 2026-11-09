# 1066: Input attributes (keyboard, autofill, capitals, examples) and help-dot tap size

Status: todo
Depends on: none | Base commit: 0d851ca4 | Branch: task/1066-input-attributes
Executor: Sonnet 5.5 at medium effort (owner override; the template says Haiku) | Fits one session: 30 tool calls, 60k tokens

**Order.** 1066 goes first. Queue item 1.2 (guest form scan and errors, plan S2/S7/S8) and 1.3 (operator prefill, plan Q3) edit the same templates (`guest/form.html`, `_entity_business_fields.html`) later and must re-read them after 1066 merges; their anchors will see the attributes added here.

**Which goes first (context-lint overlaps).** 1066 touches `guest/form.html`, `setup_wizard/property.html`, `app2.css`, `base.html` and `static_versions.json`, which older briefs 0885, 0932, 0933 (guest form), 0884 (wizard), 0796, 0848, 0889 (`app2.css`) and others also name. Those briefs are still marked `todo` but their work is already in the base commit `0d851ca4` as far as the repo history shows; they run BEFORE 1066 only if the owner re-opens them, and then they stop at their first missing anchor. 1066 goes before queue items 1.2 and 1.3. `static_versions.json` is regenerated with `--write` on top of whatever is merged, never merged by hand.

## 1. Objective

Guest, property-address and operator (entity) inputs get the right `autocomplete`, `autocapitalize`, `inputmode` and example placeholders (plan Q1/S4); the host help "?" gets a 44 px tap target on desktop without changing its look (plan S12). Behaviour and attributes only: no field name, value, validation or order changes, and the guest form design stays exactly as it is. Everything is still validated server-side.

## 2. Context

Rules that apply (pasted):
- AGENTS rule 7: a guest-template change needs the browser and geometry tests for the changed pages, 0 skipped, plus one 390 px screenshot per changed page. Rule 10: a host page change needs `test_layout_lint_browser.py` green, the 390/768/1280 screenshots opened, a per-page line in the PR, and the design-system checklist ticked. Never silence a finding.
- Design system rule 7: the "?" is a plain 18 px icon, "the tap target is an invisible hit area". No `<style>`, `style=""` or raw colour in new code. CI blocks them.
- Never change a police field's name, value, validation or order (`first_name`, `surname`, `birth_date`, `nationality`, `doc_number`, `visa_number`, `res_*`, `purpose`, `parent_doc_number`).
- The guest form has no per-language placeholder keys beyond `date_placeholder`, and guests use many languages. Do NOT add guest placeholders (no new i18n keys in this brief). The host placeholders below are digits or Czech place names, the same in every language, so they are literals, not keys.

Findings from reading the code (so you do not redo them):
- Guest help dots already have a 44 x 44 px `summary` and an 18 px drawn dot (`App/app/static/guest.css`, `details.g-head-help > summary`). S12 on the guest page is "verify only, change nothing".
- Host `.help-tip-btn`: phone (max 1023 px) is already 44 px (`app2.css` line ~1626). Desktop (min 1024 px) is 24 px with the ring drawn by `::after` (`app2.css` line ~1625), so desktop needs a hit area. `app2.css` line ~2543 already does this for one page with `::before` (a centred transparent box); reuse that pattern. `app2.css` line ~3389 sets `content:none` for `#stay-fee-settings`: leave it and report it as left at its own size.
- `host.css` (old shell) `.help-tip-btn::after{inset:-11px}` is already a 44 px area; `admin2.css` already has `inset:-13px` on an 18 px button. Do not touch them.
- The nationality and residence `<select>` use police country codes (`country.code`), not ISO-2, so the standard `country` token cannot match by value. `res_country` keeps its existing `autocomplete="country"`; `nationality` gets `off` (residence autofill must never fill nationality).
- `birth_date` has `autocomplete="bday"` and is a dd.mm.yyyy text field. A browser may fill it as yyyy-mm-dd. That is existing behaviour and not verified here: leave the attribute as it is (see §8).
- The passport photo `<input type=file>` gets `capture="environment"` from JS only when the guest taps "Take a photo" (`guest/form.html`, `openPicker`); with "Choose a file" it is removed. That is right: a static `capture` would remove the gallery choice. The OCR scan input (`guest/_ocr_scan.html`) sits behind a label button where a gallery photo is allowed, so no `capture` there either. No change to either.
- The property address fields are the accommodation's address, which goes to the police. It is not the host's home address, so browser autofill would file the wrong address: `autocomplete="off"` is justified on all seven. The RÚIAN suggest (`data-ruian-suggest`) is the helper.
- Existing tests that must keep passing: `tests/test_guest_doc_field_attrs.py` (document fields keep `autocapitalize="characters"`, `spellcheck="false"`, `autocorrect="off"`, `name="doc_number" maxlength="30"`, `value="{{ val('visa_number') }}"`; the `first_name` tag must NOT contain `spellcheck`) and `tests/test_guest_residence_prefill.py` (`address-line1` on the street, no `street-address` there, `country` on `res_country`).

Base commit `0d851ca4`. Every excerpt below must be found verbatim; if one is not, STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/guest/form.html` | edit | attributes on 9 fields |
| `App/app/templates/guest/claim.html` | edit | attributes on the e-mail field |
| `App/app/templates/_property_address_fields.html` | edit | macro gets `autocomplete="off"`, `autocapitalize`, `placeholder`; 7 calls updated |
| `App/app/templates/_entity_business_fields.html` | edit | attributes on 6 operator fields |
| `App/app/templates/_entity_invoice_fields.html` | edit | attributes on `bic` and `invoice_prefix` |
| `App/app/templates/setup_wizard/property.html` | edit | placeholder on the wizard IČO |
| `App/app/static/app2.css` | edit | one desktop hit-area rule for `.help-tip-btn` |
| `App/app/templates/base.html` | edit | bump the `app2.css` `?v=` key |
| `App/tests/static_versions.json` | regenerate | with `--write`, never by hand |
| `App/tests/test_input_attributes_1066.py` | create | small test of the new attributes |
| `docs/tasks/screenshots-1066/` | create | the 390 px guest screenshots |

No other file may change. Never `App/app/static/guest.css`, never any police validation code.

### Field table (every field; "none" = unchanged and checked)

Line numbers are at base commit `0d851ca4`.

| # | Template:line | Field name | Current attributes | New attributes |
|---|---|---|---|---|
| 1 | guest/form.html:103 | `party_size` | number, `inputmode="numeric"`, `autocomplete="off"` | none (already right) |
| 2 | guest/form.html:118 | `first_name` | `autocomplete="given-name"` | add `autocapitalize="words"` (no `spellcheck`: an existing test forbids it) |
| 3 | guest/form.html:124 | `surname` | `autocomplete="family-name"` | add `autocapitalize="words"` |
| 4 | guest/form.html:133 | `birth_date` | `inputmode="numeric"`, `placeholder=date_placeholder`, `autocomplete="bday"` | none (see §8) |
| 5 | guest/form.html:144 | `nationality` (select) | none | add `autocomplete="off"` |
| 6 | guest/form.html:163 | `doc_number` | `autocapitalize="characters" spellcheck="false" autocorrect="off"` | add `autocomplete="off"` (autofill would insert another guest's document number on a shared phone) |
| 7 | guest/form.html:183 | `parent_doc_number` | `autocapitalize="characters"` | add `autocomplete="off" spellcheck="false" autocorrect="off"` (same as doc_number) |
| 8 | guest/form.html:190 | `visa_number` | `autocapitalize="characters" spellcheck="false" autocorrect="off"` | add `autocomplete="off"` |
| 9 | guest/form.html:198 | `purpose` (select) | none | add `autocomplete="off"` |
| 10 | guest/form.html:222 | `res_country` (select) | `autocomplete="country"` | none |
| 11 | guest/form.html:239 | `res_city` | `autocomplete="address-level2"` | add `autocapitalize="words"` |
| 12 | guest/form.html:245 | `res_street` | `autocomplete="address-line1"` | add `autocapitalize="words"` |
| 13 | guest/form.html:282 | `passport_photo` (file) | hidden; JS sets and removes `capture` | none (capture stays JS-only, see §2) |
| 14 | guest/_ocr_scan.html:3 | `ocr-scan-file` (file) | `accept=image/...` | none (no `capture`, see §2) |
| 15 | guest/claim.html:45 | `guest_email` | `type="email" required autocomplete="email" maxlength="254"` | add `autocapitalize="none" autocorrect="off" spellcheck="false" inputmode="email"` |
| 16 | guest/claim.html:34 | `party_size` | numeric, `autocomplete="off"` | none |
| 17 | _property_address_fields.html:12 (macro) | all seven `addr_*` | none | macro adds `autocomplete="off"`, optional `autocapitalize`, optional `placeholder` |
| 18 | _property_address_fields.html:23 | `addr_street` | `maxlength=48`, `data-ruian-suggest` | `autocapitalize="words"`, `placeholder="Vinohradská"` |
| 19 | _property_address_fields.html:24 | `addr_house_no` | `maxlength=5` | `placeholder="12"` |
| 20 | _property_address_fields.html:25 | `addr_orient_no` | `maxlength=4`, optional | `placeholder="5"` |
| 21 | _property_address_fields.html:26 | `addr_zip` | `maxlength=6`, `inputmode="numeric"` | `placeholder="12000"` |
| 22 | _property_address_fields.html:29 | `addr_obec` | `maxlength=48` | `autocapitalize="words"`, `placeholder="Praha"` |
| 23 | _property_address_fields.html:30 | `addr_obec_cast` | `maxlength=48`, optional | `autocapitalize="words"`, `placeholder="Vinohrady"` |
| 24 | _property_address_fields.html:31 | `addr_okres` | `maxlength=32`, optional | `autocapitalize="words"`, `placeholder="Praha"` |
| 25 | _entity_business_fields.html:20 | `ico` | `inputmode="numeric"` | add `autocomplete="off" placeholder="12345678"` |
| 26 | _entity_business_fields.html:35 | `dic` | none | add `autocomplete="off" autocapitalize="characters" spellcheck="false" placeholder="CZ12345678"` |
| 27 | _entity_business_fields.html:40 | `name` | `placeholder=entities.name_placeholder` | add `autocomplete="organization" autocapitalize="words"` |
| 28 | _entity_business_fields.html:48 | `seat` | `placeholder=entities.seat_placeholder` | add `autocomplete="street-address" autocapitalize="words"` |
| 29 | _entity_business_fields.html:55 | `contact_email` | `type="email" required` | add `autocomplete="email" autocapitalize="none" spellcheck="false"` |
| 30 | _entity_business_fields.html:64 and :69 | `contact_phone_country_code`, `contact_phone` | `tel-country-code`, `tel-national`, `inputmode` | none (already right) |
| 31 | _entity_business_fields.html:106 | `signature_name` | `autocomplete="name"` | add `autocapitalize="words"` |
| 32 | _entity_invoice_fields.html:19 | `bic` | none | add `autocomplete="off" autocapitalize="characters" spellcheck="false" placeholder="ABCDCZPP"` |
| 33 | _entity_invoice_fields.html:44 | `invoice_prefix` | `maxlength="6"` | add `autocomplete="off" autocapitalize="characters"` |
| 34 | setup_wizard/property.html:19 | `ico` (wizard) | `inputmode="numeric" maxlength="8" autocomplete="off"` | add `placeholder="12345678"` |
| 35 | _account_parts.html:5, :9, :13 | account prefix, number, bank | `inputmode="numeric"` | none (out of scope: banks have no autofill token) |

Changed fields: 26 (guest form 9, claim e-mail 1, property address 7, operator 6, invoice 2, wizard IČO 1). Unchanged and checked: rows 1, 4, 10, 13, 14, 16, 30, 35.

## 4. Steps

Work from your worktree root. Use Edit with the exact old and new text. Each step is one file. Old strings may be a substring of a line (leading spaces are not part of them).

### Step 1: guest form, names

File `App/app/templates/guest/form.html`.
Edit A. Old: `autocomplete="given-name" required value="{{ val('first_name') }}">`
New: `autocomplete="given-name" autocapitalize="words" required value="{{ val('first_name') }}">`
Edit B. Old: `autocomplete="family-name" value="{{ val('surname') }}">`
New: `autocomplete="family-name" autocapitalize="words" value="{{ val('surname') }}">`
Command: `grep -c 'autocapitalize="words"' App/app/templates/guest/form.html`
Expected: `2`.

### Step 2: guest form, nationality and purpose

Same file.
Edit A. Old: `data-guest-required="{{ t('tw_country_required') }}" required>`
New: `data-guest-required="{{ t('tw_country_required') }}" autocomplete="off" required>`
(Unique: the residence select has `autocomplete="country" required>` instead.)
Edit B. Old: `<select id="purpose" name="purpose">`
New: `<select id="purpose" name="purpose" autocomplete="off">`
Command: `grep -n 'autocomplete="off"' App/app/templates/guest/form.html`
Expected: 3 lines (`party_size`, `nationality`, `purpose`).

### Step 3: guest form, document fields

Same file.
Edit A (doc_number). Old:
```
name="doc_number" maxlength="30"
             autocapitalize="characters" spellcheck="false" autocorrect="off"
```
New:
```
name="doc_number" maxlength="30"
             autocapitalize="characters" autocomplete="off" spellcheck="false" autocorrect="off"
```
Edit B (parent). Old:
```
name="parent_doc_number" maxlength="30"
             autocapitalize="characters" value="{{ values.get('parent_doc_number', '') }}">
```
New:
```
name="parent_doc_number" maxlength="30"
             autocapitalize="characters" autocomplete="off" spellcheck="false" autocorrect="off" value="{{ values.get('parent_doc_number', '') }}">
```
Edit C (visa). Old: `autocapitalize="characters" spellcheck="false" autocorrect="off" value="{{ val('visa_number') }}">`
New: `autocapitalize="characters" autocomplete="off" spellcheck="false" autocorrect="off" value="{{ val('visa_number') }}">`
Command: `cd App && .venv/bin/python -m pytest tests/test_guest_doc_field_attrs.py -q --tb=short -x 2>&1 | tail -30`
Expected: all pass.

### Step 4: guest form, residence

Same file.
Edit A. Old: `autocomplete="address-level2" required value="{{ val('res_city') }}">`
New: `autocomplete="address-level2" autocapitalize="words" required value="{{ val('res_city') }}">`
Edit B. Old: `autocomplete="address-line1" required value="{{ val('res_street') }}">`
New: `autocomplete="address-line1" autocapitalize="words" required value="{{ val('res_street') }}">`
Command: `cd App && .venv/bin/python -m pytest tests/test_guest_residence_prefill.py -q --tb=short -x 2>&1 | tail -30`
Expected: pass (0 failed).

### Step 5: guest claim e-mail

File `App/app/templates/guest/claim.html`.
Old:
```
      <input type="email" id="guest_email" name="guest_email" required autocomplete="email"
             maxlength="254">
```
New:
```
      <input type="email" id="guest_email" name="guest_email" required autocomplete="email"
             autocapitalize="none" autocorrect="off" spellcheck="false" inputmode="email"
             maxlength="254">
```
Command: `grep -n 'inputmode="email"' App/app/templates/guest/claim.html`
Expected: one line.

### Step 6: property address macro and calls

File `App/app/templates/_property_address_fields.html`.
Edit A (macro head). Old: `{% macro address_input(name, label, help='', optional=false, maxlength=none, inputmode='', required=false, extra='') %}`
New: `{% macro address_input(name, label, help='', optional=false, maxlength=none, inputmode='', required=false, extra='', autocapitalize='', placeholder='') %}`
Edit B (input start). Old: `<input type="text" id="{{ name }}" name="{{ name }}" value="{{ pv[name] or '' }}"`
New: `<input type="text" id="{{ name }}" name="{{ name }}" autocomplete="off" value="{{ pv[name] or '' }}"`
Edit C. Old: `           {%- if inputmode %} inputmode="{{ inputmode }}"{% endif %}`
New:
```
           {%- if inputmode %} inputmode="{{ inputmode }}"{% endif %}
           {%- if autocapitalize %} autocapitalize="{{ autocapitalize }}"{% endif %}
           {%- if placeholder %} placeholder="{{ placeholder }}"{% endif %}
```
Edit D (the seven calls; replace only the tail shown):
- Old: `true, extra='data-ruian-suggest') }}` New: `true, extra='data-ruian-suggest', autocapitalize='words', placeholder='Vinohradská') }}`
- Old: `t('apartment.form.addr.house_no_hint'), false, 5, '', true) }}` New: `t('apartment.form.addr.house_no_hint'), false, 5, '', true, placeholder='12') }}`
- Old: `t('apartment.form.addr.orient_no_hint'), true, 4) }}` New: `t('apartment.form.addr.orient_no_hint'), true, 4, placeholder='5') }}`
- Old: `false, 6, 'numeric', true) }}` New: `false, 6, 'numeric', true, placeholder='12000') }}`
- Old: `t('apartment.form.addr.obec'), '', false, 48, '', true) }}` New: `t('apartment.form.addr.obec'), '', false, 48, '', true, autocapitalize='words', placeholder='Praha') }}`
- Old: `t('apartment.form.addr.obec_cast'), '', true, 48) }}` New: `t('apartment.form.addr.obec_cast'), '', true, 48, autocapitalize='words', placeholder='Vinohrady') }}`
- Old: `t('apartment.form.addr.okres_hint'), true, 32) }}` New: `t('apartment.form.addr.okres_hint'), true, 32, autocapitalize='words', placeholder='Praha') }}`
Command: `grep -c "placeholder" App/app/templates/_property_address_fields.html`
Expected: `9` (macro head, the `if placeholder` line, seven calls).

### Step 7: operator business fields

File `App/app/templates/_entity_business_fields.html`.
- Old: `<input type="text" id="{{ input_id }}" name="ico" inputmode="numeric"` New: `<input type="text" id="{{ input_id }}" name="ico" inputmode="numeric" autocomplete="off" placeholder="12345678"`
- Old: `<input type="text" id="{{ prefix }}dic" name="dic" value=` New: `<input type="text" id="{{ prefix }}dic" name="dic" autocomplete="off" autocapitalize="characters" spellcheck="false" placeholder="CZ12345678" value=`
- Old: `<input type="text" id="{{ prefix }}name" name="name" required` New: `<input type="text" id="{{ prefix }}name" name="name" autocomplete="organization" autocapitalize="words" required`
- Old: `<input type="text" id="{{ prefix }}seat" name="seat" required` New: `<input type="text" id="{{ prefix }}seat" name="seat" autocomplete="street-address" autocapitalize="words" required`
- Old: `<input type="email" id="{{ prefix }}contact_email" name="contact_email" required` New: `<input type="email" id="{{ prefix }}contact_email" name="contact_email" autocomplete="email" autocapitalize="none" spellcheck="false" required`
- Old: `autocomplete="name" value="{{ typed }}"` New: `autocomplete="name" autocapitalize="words" value="{{ typed }}"`
Do NOT touch the existing `style="align-items:flex-end"` on the IČO row (not ours).
Command: `grep -c 'autocomplete=' App/app/templates/_entity_business_fields.html`
Expected: `8` (ico, dic, name, seat, e-mail, signature name, plus the two phone fields).

### Step 8: invoice fields and wizard IČO

File `App/app/templates/_entity_invoice_fields.html`.
- Old: `<input type="text" id="bic" name="bic" value="{{ entity.bic or '' }}">` New: `<input type="text" id="bic" name="bic" autocomplete="off" autocapitalize="characters" spellcheck="false" placeholder="ABCDCZPP" value="{{ entity.bic or '' }}">`
- Old: `<input type="text" id="invoice_prefix" name="invoice_prefix" maxlength="6"` New: `<input type="text" id="invoice_prefix" name="invoice_prefix" maxlength="6" autocomplete="off" autocapitalize="characters"`
File `App/app/templates/setup_wizard/property.html`.
- Old: `<input type="text" id="wizard-ares-ico" name="ico" inputmode="numeric" maxlength="8" autocomplete="off" required>` New: `<input type="text" id="wizard-ares-ico" name="ico" inputmode="numeric" maxlength="8" autocomplete="off" placeholder="12345678" required>`
Command: `git diff --stat | tail -12`
Expected: six template files listed.

### Step 9: desktop help hit area (CSS)

File `App/app/static/app2.css`. Find the line that starts `@media (max-width:1023px){body.v2 .help-tip-btn{width:44px;height:44px;` (about line 1626). Insert ONE new line directly after it:
```
@media (min-width:1024px){body.v2 .help-tip-btn::before{content:"";position:absolute;top:50%;left:50%;width:44px;height:44px;transform:translate(-50%,-50%)}} /* 1066: invisible 44 px hit area, the drawn 18 px ring is unchanged */
```
No colour, no border, no change to the size or margin of the button, so the look is identical. Then bump the cache key: in `App/app/templates/base.html` change `app2.css?v=20261109-1130k` to `app2.css?v=20261109-1130l`. Then from `App/`:
`.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30`
Expected: it rewrites `tests/static_versions.json`; check `git diff --stat tests/static_versions.json | tail -5`: one file, a few lines (the `app2.css` entry only).

### Step 10: the new test

Create `App/tests/test_input_attributes_1066.py` with exactly:
```python
"""1066 (plan Q1, S4, S12): input attributes on guest, address and operator fields."""
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
TEMPLATES = APP / "templates"


def _read(rel: str) -> str:
    return (TEMPLATES / rel).read_text(encoding="utf-8")


def _tag(source: str, field_id: str, kind: str = "input") -> str:
    match = re.search(r"<" + kind + r"[^>]*id=\"" + re.escape(field_id) + r"\"[^>]*>", source)
    assert match, f"{field_id} disappeared"
    return " ".join(match.group(0).split())


def test_guest_names_and_address_get_capitals():
    form = _read("guest/form.html")
    for field in ("first_name", "surname", "res_city", "res_street"):
        assert 'autocapitalize="words"' in _tag(form, field), field


def test_guest_document_and_nationality_are_not_autofilled():
    form = _read("guest/form.html")
    for field in ("doc_number", "parent_doc_number", "visa_number"):
        assert 'autocomplete="off"' in _tag(form, field), field
    assert 'autocomplete="off"' in _tag(form, "nationality", "select")
    assert 'autocomplete="off"' in _tag(form, "purpose", "select")


def test_guest_tokens_that_were_right_are_kept():
    form = _read("guest/form.html")
    assert 'autocomplete="given-name"' in _tag(form, "first_name")
    assert 'autocomplete="family-name"' in _tag(form, "surname")
    assert 'autocomplete="address-level2"' in _tag(form, "res_city")
    assert 'autocomplete="address-line1"' in _tag(form, "res_street")
    assert 'autocomplete="country"' in _tag(form, "res_country", "select")
    assert 'autocomplete="bday"' in _tag(form, "birth_date")


def test_guest_email_keyboard():
    tag = _tag(_read("guest/claim.html"), "guest_email")
    assert 'autocomplete="email"' in tag
    assert 'inputmode="email"' in tag
    assert 'autocapitalize="none"' in tag


def test_property_address_is_never_autofilled_and_has_examples():
    source = _read("_property_address_fields.html")
    assert 'name="{{ name }}" autocomplete="off"' in source
    for example in ("Vinohradská", "12000", "Praha", "Vinohrady"):
        assert f"placeholder='{example}'" in source, example


def test_operator_fields_use_standard_tokens():
    source = _read("_entity_business_fields.html")
    assert 'name="name" autocomplete="organization"' in source
    assert 'name="seat" autocomplete="street-address"' in source
    assert 'name="contact_email" autocomplete="email"' in source
    assert 'autocomplete="tel-national"' in source
    assert 'name="ico" inputmode="numeric" autocomplete="off"' in source
    invoice = _read("_entity_invoice_fields.html")
    assert 'autocapitalize="characters"' in _tag(invoice, "bic")


def test_help_dot_tap_targets_stay_44px():
    css = (APP / "static" / "app2.css").read_text(encoding="utf-8")
    assert re.search(
        r"@media \(min-width:1024px\)\{body\.v2 \.help-tip-btn::before\{[^}]*width:44px;height:44px", css
    )
    guest = (APP / "static" / "guest.css").read_text(encoding="utf-8")
    block = guest.split("details.g-head-help > summary {", 1)[1].split("}", 1)[0]
    assert "width: 44px" in block and "height: 44px" in block
```
Command: `cd App && .venv/bin/python -m pytest tests/test_input_attributes_1066.py -q --tb=short -x 2>&1 | tail -30`
Expected: 7 passed. If a test fails only because of whitespace in a template line, fix the TEST regex, not the template, and say so in the report.

## 5. Do not touch

- Any police field's name, `value=`, `required`, `maxlength`, validation, order or label. Any server-side code; `guest.css`, `host.css`, `admin2.css`; `app2.css` beyond the one inserted line.
- No `style=""`, `<style>`, raw colour or new class in templates; no new i18n keys; no new dependency. AGENTS rules 2, 3, 6, 7, 8, 10 apply. Do not merge, push to main or deploy.

## 6. Commands

From `App/`. Each must end with 0 failed; browser runs use `UBYHOST_REQUIRE_BROWSER=1` and `-rs`, and must show 0 skipped.

1. Guest row: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_guest_*.py tests/test_guest_browser_e2e.py tests/test_host_geometry.py tests/test_input_attributes_1066.py -q -rs --tb=short -x 2>&1 | tail -30`. Expected: all pass, 0 skipped.
2. Host rows (host templates, onboarding and properties, invoices): `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_*.py tests/test_onboarding*.py tests/test_property_*.py tests/test_first_*.py tests/test_invoice_*.py -q --tb=short -x 2>&1 | tail -30`. Expected: pass.
3. Design and static: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_static_versions.py tests/test_host_i18n.py -q -rs --tb=short -x 2>&1 | tail -30`. Expected: pass, 0 skipped.
4. UX gate: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -rs -x 2>&1 | tail -30`. Expected: pass, 0 skipped, zero host findings. If the new 44 px desktop hit area causes a finding, do not silence it: STOP and report which page.
5. Screenshots: guest form steps 1 and 2 and the claim page at 390 px (the Playwright fixtures of `test_guest_browser_e2e.py` work; save to `docs/tasks/screenshots-1066/` as `guest-form-390.png`, `guest-claim-390.png`). They must look identical to before. Host: open `/tmp/shots/layout-lint/<page>-{390,768,1280}.png` for the operator (entities), property create and edit, setup wizard property pages, and any page with a help "?" at 1280.
6. Context lint, from the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`. Expected: the only error is `status.md` over its cap (fixed in PR #854).

## 7. Acceptance

- [ ] The §3 field table is implemented exactly; `git diff --stat` lists only the §3 files.
- [ ] No police field name, value, validation or order changed (`git diff` of `guest/form.html` shows only added attributes).
- [ ] `test_input_attributes_1066.py` 7 passed; commands 1 to 4 green, 0 skipped.
- [ ] One 390 px screenshot per changed guest page (form, claim) in the report; the guest form looks unchanged.
- [ ] Host: per touched page "390: ...; 768: ...; 1280: ..." in the PR body, and the design-system checklist (docs/design/design-system.md section 5) ticked in the PR.
- [ ] Help dots: the `.help-tip-btn` look is unchanged at 1280 px (compare a screenshot); the report says `#stay-fee-settings` was left at its own size.
- [ ] `app2.css` key bumped and `static_versions.json` regenerated with `--write`.

## 8. Stop and ask

Stop, and write the report, if:
- an excerpt is not found, or `first_name` would gain `spellcheck`;
- a test fails twice, or the layout lint reports a new finding on a host page;
- you reach 25 tool calls or about 50k tokens;
- a file outside §3 needs a change, or §5 would be touched;
- you think `birth_date` `autocomplete="bday"` is wrong (it may autofill yyyy-mm-dd into a dd.mm.yyyy field; unverified, existing behaviour): do NOT change it; list it as a question in the report;
- you need push, merge, secrets, SSH or deploy (hand it to the owner).

## 9. Report

Write `docs/tasks/1066-report.md` (600 tokens at most) and set `Status: review`. It has: 1 files changed; 2 each command with its last 5 lines; 3 §7 ticked; 4 deviations; 5 questions (bday, stay-fee help dot); 6 owner steps left.

## Risk list (for the reviewer)

- `guest/form.html` diff: only added attributes, no change in names, values or order.
- `_property_address_fields.html`: `autocomplete="off"` is intentional (the filed address is not the host's home).
- `app2.css` new desktop `::before` on `.help-tip-btn`: the 44 px invisible box can overlap a neighbouring label or link; check the layout-lint output and the 1280 screenshots. Not measured by a committed browser test (the test only checks the CSS text); the lint and screenshots are the proof.
- Placeholders are literal Czech examples (digits and place names) in host templates, no i18n key.

## Owner steps

1. Open the PR when the executor reports `Status: review`.
2. After CI is green and the UX gate lines are in the PR body, run `scripts/merge-pr-on-green.sh <PR number>`.
3. Deploy as usual; nothing else to configure.
