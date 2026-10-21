# 0208: One forgiving box for the town's bank account

Status: blocked
Depends on: 0211 | Base commit: f547ef0 | Branch: claude/project-thread-cf47ju
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The stay-fee account is three boxes (prefix, number, bank code); a test user did not know how to split it. Replace them, in the wizard and in property settings, with one box that takes the account however it is written (19-2000145399/0800, with spaces, or an IBAN); the server already parses and checks that format.

## 2. Context

The server path for one box already exists. `App/app/routes/stay_fees.py`, `fee_form_values` (verbatim):

```
    if any(key in form for key in ("account_prefix", "account_number", "account_bank")):
        ...
    else:
        values[FEE_ACCOUNT_RAW] = _form_str(form, "stay_fee_council_account")
    return values
```

`apply_fee_account` turns the raw text into stored account plus IBAN with `payments.normalise_account` (strips whitespace, accepts `prefix-number/bank` or an IBAN, checks mod 11 and the IBAN checksum, raises `ValueError` on bad input) and refuses the save.

The three-box path stays on the server, so old posts and the invoice account (entity editor, `_entity_invoice_fields.html`) keep working. The invoice account is NOT changed in this brief.

`App/app/templates/_stay_fee_fields.html` (verbatim, lines 31-34):

```
  <div class="field-label-row fee-account-label"><span class="field-group-label" id="stay-fee-account-label">{{ t('apartment.form.stay_fee.account_label') }}</span>{{ help_tip('stay-fee-account-help', t('apartment.form.stay_fee.account_help')) }}</div>
  {% set prefix = '' %}
  {% set account_required = fee_required %}
  {% include "_account_parts.html" %}
```

On a refused save the page re-renders with a `draft` dict as `apartment` (wizard: `App/app/routes/onboarding_wizard.py` around line 236; settings: `App/app/routes/admin.py` around line 1938).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/_stay_fee_fields.html | edit | one box |
| App/app/routes/stay_fees.py | edit | `else` → `elif` |
| App/app/routes/onboarding_wizard.py | edit | keep the typed text on refusal |
| App/app/routes/admin.py | edit | keep the typed text on refusal |
| App/app/static/app.js | edit | "copy from another property" fills the one box |
| App/app/templates/base.html | edit | new `app.js` key |
| App/tests/static_versions.json | regenerate | `--write` |
| App/app/host_i18n.py | edit | new `_ONBOARDING_TEST_0208_STRINGS` block |
| App/app/host_vi_i18n.py | edit | Vietnamese |
| App/tests/test_reporting_help_0097.py | edit | pins |
| App/tests/test_copy_property_settings.py | edit | pin |
| App/tests/test_fee_setup_compatibility.py | edit | browser fill |
| App/tests/test_host_ux_acceptance.py | edit | field names |
| App/tests/test_property_navigation_browser.py | edit | field names |
| App/tests/test_fee_one_box_0208.py | create | new tests |
| App/tests/test_fee_setup_compatibility.py | edit | step 9 pins |

No other file may change.

## 4. Steps

### Step 1. `_stay_fee_fields.html`

Replace the four lines quoted in §2 with:

```
  {#- 0208: one box; the server splits and checks it (payments.normalise_account). -#}
  <div class="field">
    {{ field_label('stay_fee_council_account', t('apartment.form.stay_fee.account_label'), t('apartment.form.stay_fee.account_help')) }}
    <input type="text" id="stay_fee_council_account" name="stay_fee_council_account" autocomplete="off" spellcheck="false" maxlength="42"
           aria-describedby="stay_fee_council_account-help{% if fee_account_error %} stay-fee-account-error{% endif %}"
           value="{{ apartment.stay_fee_council_account or apartment.stay_fee_council_iban or '' }}"{% if fee_required %} required{% endif %}{% if fee_account_error %} aria-invalid="true"{% endif %}>
  </div>
```

Check that `field_label` is imported at the top of the file (`grep -n "import" App/app/templates/_stay_fee_fields.html`); if not, STOP.
Leave the hidden `_stay_fee_account_existing` input in place.

### Step 2. `stay_fees.py`

Replace `    else:\n        values[FEE_ACCOUNT_RAW] = _form_str(form, "stay_fee_council_account")` with:

```python
    elif "stay_fee_council_account" in form:
        values[FEE_ACCOUNT_RAW] = _form_str(form, "stay_fee_council_account")
```

(a form without any account field never wipes the stored account.)

### Step 3. Refused save keeps what was typed

a) `onboarding_wizard.py`: directly after the loop
```
        for key in ("account_prefix", "account_number", "account_bank"):
            if key in form:
                draft[key] = _form_str(form, key)
```
add (same indentation as the `for`):
```
        if "stay_fee_council_account" in form:
            draft["stay_fee_council_account"] = _form_str(form, "stay_fee_council_account")
            draft["stay_fee_council_iban"] = None
```

b) `admin.py`: directly after `    draft.update(fee_draft)` (in the function that has `account_draft = stay_fee_routes.fee_account_draft(form)`) add:
```
    if "stay_fee_council_account" in form:
        draft["stay_fee_council_account"] = _form_str(form, "stay_fee_council_account")
        draft["stay_fee_council_iban"] = None
```

If `draft` there is not a plain dict (check two lines above), STOP.

### Step 4. `app.js` (copy from another property)

Replace:
```
      var prefixField = document.getElementById("account_prefix");
      var numberField = document.getElementById("account_number");
      var bankField = document.getElementById("account_bank");
      if (prefixField && numberField && bankField) {
```
with:
```
      var oneBox = document.getElementById("stay_fee_council_account");
      if (oneBox) oneBox.value = account;
      var prefixField = document.getElementById("account_prefix");
      var numberField = document.getElementById("account_number");
      var bankField = document.getElementById("account_bank");
      if (!oneBox && prefixField && numberField && bankField) {
```

Then in `App/app/templates/base.html` replace `app.js?v=20261020-0188` with `app.js?v=20261021-0208` (if the current key differs, grep it and replace that one). Then from `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`.

### Step 5. Text (`host_i18n.py`, `host_vi_i18n.py`)

Insert above `STRINGS["vi"] = dict(_VI_STRINGS)` in `host_i18n.py` (after the last `_ONBOARDING_TEST_..._STRINGS` loop):

```python
_ONBOARDING_TEST_0208_STRINGS = {
    "en": {
        "apartment.form.stay_fee.account_help": "The town's bank account for the stay fee, from its website or letter. Copy it as you have it, for example 19-2000145399/0800, or as an IBAN. Spaces and dashes are fine; we check the number. It goes into the payment QR code.",
        "flash.stay_fees.account_invalid": "This account number does not add up. Check it against the town's website, for example 19-2000145399/0800, or paste the IBAN.",
    },
    "cs": {
        "apartment.form.stay_fee.account_help": "Bankovní účet obce pro poplatek z pobytu najdete na webu obce nebo v dopise. Opište ho tak, jak ho máte, například 19-2000145399/0800, nebo jako IBAN. Mezery ani pomlčky nevadí, číslo zkontrolujeme. Použije se pro platební QR kód.",
        "flash.stay_fees.account_invalid": "Číslo účtu nesedí. Zkontrolujte ho podle webu obce, například 19-2000145399/0800, nebo vložte IBAN.",
    },
}
for _lang, _strings in _ONBOARDING_TEST_0208_STRINGS.items():
    STRINGS[_lang].update(_strings)
```

Append to the end of `host_vi_i18n.py`:

```python

# 0208: one account box.
STRINGS.update({
    "apartment.form.stay_fee.account_help": "Tài khoản ngân hàng của địa phương để nộp phí lưu trú, có trên trang web hoặc trong thư của địa phương. Chép lại đúng như bạn có, ví dụ 19-2000145399/0800, hoặc dạng IBAN. Dấu cách hay gạch ngang đều được; chúng tôi sẽ kiểm tra số. Số này dùng cho mã QR thanh toán.",
    "flash.stay_fees.account_invalid": "Số tài khoản này không hợp lệ. Hãy kiểm tra lại theo trang web của địa phương, ví dụ 19-2000145399/0800, hoặc dán IBAN.",
})
```

### Step 6. Test pins (only the fee account; leave every invoice/entity account pin alone)

a) `test_reporting_help_0097.py`: in `FEE_HELP` replace `"stay-fee-account": ` with `"stay_fee_council_account": `. In the "Input names are unchanged" tuple replace `"account_prefix", "account_number",\n                     "account_bank", ` with `"stay_fee_council_account",\n                     ` (keep the rest).

b) `test_copy_property_settings.py`: `assert 'name="account_number"' in text` → `assert 'name="stay_fee_council_account"' in text`.

c) `test_fee_setup_compatibility.py` (browser test near line 397-430):
- in the visible-fields tuple replace `"account_number"` with `"stay_fee_council_account"`;
- `page.fill("#account_number", "1234567890")` + `page.fill("#account_bank", "0800")` → one line `page.fill("#stay_fee_council_account", "1234567890/0800")`;
- `assert page.input_value("#account_number") == "1234567890"` → `assert page.input_value("#stay_fee_council_account") == "1234567890/0800"`;
- `page.fill("#account_number", "")` + `page.fill("#account_bank", "")` → `page.fill("#stay_fee_council_account", "")`.

d) `test_host_ux_acceptance.py`:
- in `PROPERTY_SETTINGS` replace `"account_prefix", "account_number",\n    "account_bank", ` with `"stay_fee_council_account",\n    `;
- replace the line `        doubled = sorted(n for n, c in counts.items() if c > 1 and n not in ("account_prefix", "account_number", "account_bank"))` with `        doubled = sorted(n for n, c in counts.items() if c > 1)`;
- delete the three lines starting `        # The fee account parts are one set of three on the property page.` through `            assert counts[part] == 1, (view, part, counts[part])`.
- Leave the `business-editor` allowance line alone.

e) `test_property_navigation_browser.py` `SETTINGS_NAMES`: replace `"account_prefix",\n    "account_number", "account_bank", ` with `"stay_fee_council_account",\n    `.

If an anchor is not verbatim, read 5 lines around it, apply the same intent, and list it in the report.

### Step 7. New test `App/tests/test_fee_one_box_0208.py`

Copy the fixtures/helpers you need from `tests/test_fee_form_partial.py` (read it first; it already posts a fee form). Write three tests:

1. Posting `stay_fee_council_account="19 - 2000145399 / 0800"` (with the other fields that file posts) saves `stay_fee_council_account == "19-2000145399/0800"` and an IBAN starting `CZ`.
2. Posting `stay_fee_council_account="CZ6508000000192000145399"` saves that IBAN.
3. Posting a form with no account field at all (e.g. only `stay_fee_vs`) keeps the stored account.

### Step 8. Commit

`0208 one-box fee account`, only §3 files, trailers from your prompt, never PNGs.

### Step 9 (follow-up). Two more pins, and are the navigation failures ours?

a) `App/tests/test_fee_setup_compatibility.py` (add it to §3):
- `    assert "Enter a valid Czech bank account or IBAN." in text` → `    assert "This account number does not add up." in text  # 0208 copy`
- `    assert 'value="777"' in text and 'value="1234567890"' in text` → `    assert 'value="777"' in text  # 0208: the old three-box post is not echoed into the one box`
- replace the two lines
```
    for name in ("account_prefix", "account_number", "account_bank", "_stay_fee_account_existing"):
        assert page.count(f'name="{name}"') == 1
```
with
```
    for name in ("stay_fee_council_account", "_stay_fee_account_existing"):
        assert page.count(f'name="{name}"') == 1
```
Rerun `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_fee_setup_compatibility.py -q --tb=short 2>&1 | tail -15`.

b) `test_property_navigation_browser.py` failed at line 196 (`<details` in content) and at line 527 (timeout on `.setup-wizard-skip .link-button`). Check them on main, do not fix:
```
git worktree add /tmp/ubyhost-main origin/main 2>&1 | tail -2
cd /tmp/ubyhost-main/App && UBYHOST_REQUIRE_BROWSER=1 /home/user/jsfpecharoperations/App/.venv/bin/python -m pytest tests/test_property_navigation_browser.py -q --tb=line -rs 2>&1 | tail -10
cd /home/user/jsfpecharoperations && git worktree remove --force /tmp/ubyhost-main
```
(`git fetch origin main` first if `origin/main` is missing.) Then on the branch run `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_property_navigation_browser.py -q --tb=short -k "not fit_every_width" 2>&1 | tail -40` and paste, for each failure, the assertion text plus what the page has instead (for 196: which `<details ...>` tag is in `content`, e.g. `grep -o '<details[^>]*>'` on the rendered HTML; for 527: what classes the skip button on that wizard step has now). Report both runs.

Commit `0208 step 9`.

## 5. Do not touch

`_account_parts.html`, `_entity_invoice_fields.html`, invoice routes, filing code, guest templates, CSS. AGENTS hard rules 1, 3, 5, 7, 8.

## 6. Commands

1. From `App/`: `.venv/bin/python -m pytest tests/test_fee_one_box_0208.py tests/test_fee_form_partial.py tests/test_reporting_help_0097.py tests/test_copy_property_settings.py tests/test_static_versions.py tests/test_invoice_settings.py tests/test_entity_editor_fields.py -q --tb=short 2>&1 | tail -30`
2. From `App/`: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_fee_setup_compatibility.py tests/test_host_ux_acceptance.py tests/test_onboarding_wizard_browser.py -q --tb=line -rs 2>&1 | tail -30` (0 skipped)
3. From `App/`: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_property_navigation_browser.py -q --tb=line -rs 2>&1 | tail -15`. Known, not ours: `test_property_views_fit_every_width_and_sidebar` (360 px tabs, fails on main too). Report any other failure.
4. From the repo root: `python3 scripts/design_lint.py 2>&1 | tail -5` → `OK`; `python3 scripts/context_lint.py 2>&1 | tail -5`.
5. Screenshot (UI rule 7): with the dev server or a Playwright script, one 390 px PNG of the wizard stay-fee step and of property settings → Reporting & fees, saved to `/mnt/project-files/onboarding-0208/` (create the folder). Do not commit them.

## 7. Acceptance

- [ ] One account box in the wizard and in settings; spaces, dashes and IBAN all save; a form without the box keeps the account.
- [ ] §6 passes apart from the known failure.

## 8. Stop and ask

As in TEMPLATE.md §8.

## 9. Report

`docs/tasks/0208-report.md`, as in TEMPLATE.md §9.
