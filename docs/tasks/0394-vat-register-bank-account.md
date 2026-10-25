# 0394: "Fill from register" also fills the bank account from the MFČR VAT register

Status: review
Depends on: main 6e02f74 | Branch: claude/project-thread-kyxdtg (already checked out; commit here)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Owner (Josef, 2026-10-25): Settings → Invoice details → "Fill from register" only says "We found: VAT registered." and leaves the bank account empty, although the MFČR VAT register (registr plátců DPH) publishes the host's account. ARES has no bank accounts.

After this task, the same click also asks the MFČR VAT register (official SOAP web service "rozhraní CRPDPH", operation `getStatusNespolehlivySubjektRozsirenyV2`, no HTML scraping) and:

1. Finds the DIČ from ARES (`data["dic"]`) or, if ARES has none, from the saved Business details (`entity["dic"]`). A sole trader (fyzická osoba) has DIČ = CZ + rodné číslo, so never build it from the IČO.
2. Fills the account fields (prefix, number, bank code) with the first published account, only if all three are empty, and the BIC if it is empty.
3. Never overwrites a typed account. Any published account that is not in the fields is offered as a button "Use 123/0300" (works without JavaScript; the server accepts only an account the register lists).
4. Sets VAT status from the register (payer or identified person) only when it is still the default "Not a VAT payer".
5. Shows one alert if the register marks the business as an unreliable payer, and one short line if no DIČ is known.

Sends only the DIČ digits, only on the host's click. Nothing is saved until the host presses Save (as today).

## 2. Context

- `App/app/ares.py`: the ARES lookup; the new module copies its style (cache, `requests`, broad `except`).
- `App/app/routes/invoices.py` `lookup_invoice_details` (~479-510): the Invoice details lookup. `_typed_bank_parts(form, entity)` returns `{"prefix","number","bank","iban"}`. `_settings_entity_from_form` copies `bic` and `vat_status` from the form into `row`.
- `App/app/payments.py`: `compose_czech_account(prefix, number, bank)`, `czech_account_parts(raw)`, `bic_for_account(account)`.
- `App/app/routes/admin.py` `_invoice_details_response` (~796): runs the lookup when `fill_from_register` is posted.
- `App/app/templates/_entity_business_fields.html`: `register_messages` and `register_lookup_saved` macros. `App/app/templates/entities.html:63` calls `register_lookup_saved`.
- Copy: `App/app/host_i18n.py` (en, cs) and `App/app/host_vi_i18n.py` (vi).
- XML parsing with stdlib `xml.etree.ElementTree` (same as `App/app/ubyport/soap.py`). No new dependency.

## 3. Files

| Path | Action |
|---|---|
| App/app/vat_register.py | new |
| App/app/routes/invoices.py | lookup fills account, VAT status |
| App/app/routes/admin.py | one condition |
| App/app/templates/_entity_business_fields.html | messages + account buttons |
| App/app/templates/entities.html | one macro call |
| App/app/host_i18n.py, App/app/host_vi_i18n.py | new keys |
| App/app/static/host.css | one rule; bump `host.css?v=` in base.html |
| App/app/templates/base.html | `?v=` key |
| App/tests/test_vat_register.py | new |
| docs/context/decisions.md | one line |

## 4. Steps

### Step 1: new module `App/app/vat_register.py`

Create the file with exactly this content:

```python
"""MFČR VAT register (registr plátců DPH) lookup for invoice details.

Uses the official "rozhraní CRPDPH" SOAP service, on the host's click only,
and sends only the DIČ digits. Returns the published bank accounts and the
VAT status; ARES does not publish accounts.
"""
from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

import requests

from . import payments

_API_URL = "https://adisrws.mfcr.cz/dpr/axis2/services/rozhraniCRPDPH.rozhraniCRPDPHSOAP"
_ACTION = "http://adis.mfcr.cz/rozhraniCRPDPH/getStatusNespolehlivySubjektRozsirenyV2"
_NS = "{http://adis.mfcr.cz/rozhraniCRPDPH/}"
_TIMEOUT_SECONDS = 6
_MAX_BYTES = 200_000
_USER_AGENT = "UbyHost"
_CACHE_TTL_SECONDS = 24 * 60 * 60
_DIC_RE = re.compile(r"^(?:CZ)?(\d{8,10})$")
_VAT_STATUS = {
    "PLATCE_DPH": "payer",
    "SKUPINA_DPH": "payer",
    "IDENTIFIKOVANA_OSOBA": "identified",
}
_ENVELOPE = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">'
    "<soapenv:Body>"
    '<StatusNespolehlivySubjektRozsirenyV2Request xmlns="http://adis.mfcr.cz/rozhraniCRPDPH/">'
    "<dic>{dic}</dic>"
    "</StatusNespolehlivySubjektRozsirenyV2Request>"
    "</soapenv:Body></soapenv:Envelope>"
)

_CACHE: Dict[str, Tuple[float, Optional[Dict[str, Any]]]] = {}


def dic_digits(raw: str) -> str:
    """The digits of a Czech DIČ ("CZ12345678" -> "12345678"), or "" if it is not one."""
    text = re.sub(r"\s+", "", raw or "").upper()
    match = _DIC_RE.match(text)
    return match.group(1) if match else ""


def _accounts(subject: ET.Element) -> List[str]:
    accounts: List[str] = []
    for ucet in subject.iter(f"{_NS}ucet"):
        if ucet.get("datumZverejneniUkonceni"):
            continue
        standard = ucet.find(f"{_NS}standardniUcet")
        if standard is None:
            continue
        account = payments.compose_czech_account(
            standard.get("predcisli") or "", standard.get("cislo") or "", standard.get("kodBanky") or ""
        )
        if account and account not in accounts:
            accounts.append(account)
    return accounts


def _parse(body: bytes, digits: str) -> Optional[Dict[str, Any]]:
    """Mapped data, None when the register does not know the DIČ; raises on a bad answer."""
    root = ET.fromstring(body)
    status = root.find(f".//{_NS}status")
    if status is None or status.get("statusCode") != "0":
        raise ValueError("register error")
    for subject in root.iter(f"{_NS}statusSubjektu"):
        if subject.get("dic") != digits:
            continue
        vat_status = _VAT_STATUS.get(subject.get("typSubjektu") or "")
        if not vat_status:
            return None
        return {
            "vat_status": vat_status,
            "unreliable": subject.get("nespolehlivyPlatce") == "ANO",
            "accounts": _accounts(subject),
        }
    return None


def lookup(dic: str) -> Optional[Dict[str, Any]]:
    """Return the register data for ``dic`` or None (unknown DIČ or any failure)."""
    digits = dic_digits(dic)
    if not digits:
        return None
    now = time.time()
    cached = _CACHE.get(digits)
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]
    try:
        response = requests.post(
            _API_URL,
            data=_ENVELOPE.format(dic=digits).encode("utf-8"),
            timeout=_TIMEOUT_SECONDS,
            headers={
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": f'"{_ACTION}"',
                "User-Agent": _USER_AGENT,
            },
        )
        if not response.ok or len(response.content) > _MAX_BYTES:
            return None
        data = _parse(response.content, digits)
    except Exception:
        return None
    if len(_CACHE) > 1000:
        _CACHE.clear()
    _CACHE[digits] = (now, data)
    return data
```

Run: `cd App && .venv/bin/python -c "from app import vat_register; print(vat_register.dic_digits('CZ 12345678'))" 2>&1 | tail -3` → `12345678`.

### Step 2: `App/app/routes/invoices.py`

2a. Anchor `grep -nF "from typing import Any, Dict, Optional" App/app/routes/invoices.py` → replace the line with:

```python
from typing import Any, Dict, List, Optional
```

2b. In the `from .. import (` block (line ~14-36) add `vat_register,` as its own line in alphabetical position (keep the existing style; if the names are not alphabetical, add it as the last name before `)`).

2c. Replace the whole function `lookup_invoice_details` (from `def lookup_invoice_details` to its `return {...}` closing `}`) with:

```python
def lookup_invoice_details(request: Request, form, entity: Dict[str, Any]) -> Dict[str, Any]:
    """The click-only register lookup of the invoice details; saves nothing.

    The IČO here is lookup-only (0075 policy, kept by 0076): it fills a blank
    registry entry and proposes VAT payer, but is never stored from this form.
    0394: the MFČR VAT register adds the published bank account and VAT status.
    """
    owner_id = access.owner_id(request)
    lang = _lang(request)
    row = _settings_entity_from_form(entity, form)
    bank_parts = _typed_bank_parts(form, entity)
    state: Dict[str, Any] = {
        "entity": row,
        "bank_parts": bank_parts,
        "bic_from_bank": False,
        "ares_error": None,
        "ares_note": None,
        "ares_vat_found": False,
        "ares_source": "ares.source_note",
        "register_accounts": [],
        "vat_needs_dic": False,
        "vat_unreliable": False,
    }
    ico = (_form_str(form, "ico") or row.get("ico") or "").strip()
    row["ico"] = ico
    data, state["ares_error"] = register_lookup(owner_id, lang, ico)
    if not data:
        return state
    filled = ares.merge_blank(row, data, _SETTINGS_ARES_FIELDS)
    current = _form_str(form, "vat_status") or entity.get("vat_status") or "non_payer"
    dic = data.get("dic") or entity.get("dic") or ""
    vat = vat_register.lookup(dic) if vat_register.dic_digits(dic) else None
    vat_status = vat["vat_status"] if vat else ("payer" if data.get("vat_payer") else "")
    state["ares_vat_found"] = vat_status == "payer"
    if vat_status and current == "non_payer":
        row["vat_status"] = vat_status
        filled.append("vat_status")
    if vat:
        state["ares_source"] = "vat_register.source_note"
        state["vat_unreliable"] = vat["unreliable"]
        filled += _fill_register_account(form, row, state, vat["accounts"])
    elif not vat_register.dic_digits(dic):
        state["vat_needs_dic"] = not payments.compose_czech_account(
            bank_parts["prefix"], bank_parts["number"], bank_parts["bank"]
        )
    state["ares_note"] = register_filled_note(lang, filled)
    return state


def _fill_register_account(form, row: Dict[str, Any], state: Dict[str, Any], accounts: List[str]) -> List[str]:
    """0394: put a published account into empty account fields, or the one the host picked.

    A typed account is never replaced; the other published accounts become
    "Use …" buttons. Only accounts the register lists are accepted.
    """
    filled: List[str] = []
    parts = state["bank_parts"]
    typed = payments.compose_czech_account(parts["prefix"], parts["number"], parts["bank"])
    picked = _form_str(form, "use_register_account")
    choice = picked if picked in accounts else ("" if typed else (accounts[0] if accounts else ""))
    if choice and choice != typed:
        new_parts = payments.czech_account_parts(choice)
        new_parts["iban"] = ""
        state["bank_parts"] = new_parts
        typed = choice
        filled.append("bank_account")
        if not str(row.get("bic") or "").strip():
            bic = payments.bic_for_account(choice)
            if bic:
                row["bic"] = bic
                state["bic_from_bank"] = True
                filled.append("bic")
    state["register_accounts"] = [account for account in accounts if account != typed]
    return filled
```

Check `payments` is already imported in that file: `grep -nE "^\s+payments,|import payments" App/app/routes/invoices.py`. If not, add `payments,` to the same `from .. import (` block.

Run: `cd App && .venv/bin/python -c "import app.routes.invoices" 2>&1 | tail -3` → no output.

### Step 3: `App/app/routes/admin.py`

Anchor `grep -nF 'if form.get("fill_from_register"):' App/app/routes/admin.py`. Change only the occurrence inside `_invoice_details_response` (the one followed by `invoice_routes.lookup_invoice_details`) to:

```python
    if form.get("fill_from_register") or form.get("use_register_account"):
```

### Step 4: templates

4a. `App/app/templates/_entity_business_fields.html`: replace the `register_messages` macro (lines 10-14) with:

```jinja
{% macro register_messages(ares_error=none, ares_note=none, ares_vat_found=false, source_key='ares.source_note') %}
  {% if ares_error %}<p class="alert">{{ ares_error }}</p>{% endif %}
  {% if ares_note %}<p class="entity-register-note">{{ t(source_key) }} {{ ares_note }}</p>{% endif %}
  {% if ares_vat_found %}<p class="hint">{{ t('ares.vat_found') }}</p>{% endif %}
{% endmacro %}
```

4b. Same file, replace the whole `register_lookup_saved` macro with:

```jinja
{% macro register_lookup_saved(ico, invoice) %}
  <div class="field entity-register-lookup">
    {% if ico %}
    <input type="hidden" name="ico" value="{{ ico }}">
    <p class="small">{{ t('entities.register_lookup.uses', ico=ico) }}</p>
    <button class="btn" type="submit" name="fill_from_register" value="1" formnovalidate>{{ t('ares.fill') }}</button>
    {% else %}
    <p class="small muted">{{ t('entities.register_lookup.needs_ico') }} <a href="#entity-business">{{ t('entities.section.business') }} </a></p>
    {% endif %}
    {{ register_messages(invoice.ares_error, invoice.ares_note, invoice.ares_vat_found, invoice.ares_source or 'ares.source_note') }}
    {% if invoice.vat_unreliable %}<p class="alert">{{ t('vat_register.unreliable') }}</p>{% endif %}
    {% if invoice.vat_needs_dic %}<p class="small">{{ t('vat_register.needs_dic') }} <a href="#entity-business">{{ t('entities.section.business') }}</a></p>{% endif %}
    {% if invoice.register_accounts %}
    <div class="register-accounts">
      <p class="small">{{ t('vat_register.accounts') }}</p>
      {% for account in invoice.register_accounts %}
      <button class="btn" type="submit" name="use_register_account" value="{{ account }}" formnovalidate>{{ t('vat_register.use', account=account) }}</button>
      {% endfor %}
    </div>
    {% endif %}
  </div>
{% endmacro %}
```

4c. `App/app/templates/entities.html`: anchor `grep -nF "register_lookup_saved(edit_entity.ico" App/app/templates/entities.html`; replace that line with:

```jinja
      {{ register_lookup_saved(edit_entity.ico, invoice) }}
```

Then `grep -rn "register_lookup_saved" App/app/templates` must show only these two places. If another caller exists: STOP.

### Step 5: CSS and cache key

5a. `App/app/static/host.css`: after the line `.host-workspace .entity-register-lookup > p { margin: 0; }` add:

```css
.host-workspace .entity-register-lookup .register-accounts { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; flex-basis: 100%; }
```

5b. `App/app/templates/base.html`: change `host.css?v=20261022-0276b` to `host.css?v=20261025-0394`. Then `grep -rn "host.css?v=" App/app/templates App/tests | tail -10`: update every other place that pins the old key the same way (tests that pin the key included).

### Step 6: copy

`App/app/host_i18n.py`: add the field labels next to `"ares.field.vat_status"` in **both** the en (~3778) and cs (~4595) dicts:

en:
```python
        "ares.field.bank_account": "bank account",
        "ares.field.bic": "BIC",
```
cs:
```python
        "ares.field.bank_account": "bankovní účet",
        "ares.field.bic": "BIC",
```

Next to `"entities.register_lookup.needs_ico"` (en ~6635, cs ~6639) add:

en:
```python
        "vat_register.source_note": "Filled from the business register (ARES) and the VAT register. Check and save.",
        "vat_register.accounts": "Accounts in the VAT register:",
        "vat_register.use": "Use %(account)s",
        "vat_register.needs_dic": "To fill the bank account too, add your DIČ in",
        "vat_register.unreliable": "The VAT register lists this business as an unreliable VAT payer.",
```
cs:
```python
        "vat_register.source_note": "Vyplněno z obchodního rejstříku (ARES) a registru plátců DPH. Zkontrolujte a uložte.",
        "vat_register.accounts": "Účty v registru plátců DPH:",
        "vat_register.use": "Použít %(account)s",
        "vat_register.needs_dic": "Pro doplnění bankovního účtu vyplňte DIČ v sekci",
        "vat_register.unreliable": "Registr plátců DPH vede tento subjekt jako nespolehlivého plátce.",
```

`App/app/host_vi_i18n.py`: after `"ares.field.vat_status"` add `"ares.field.bank_account": "tài khoản ngân hàng",` and `"ares.field.bic": "BIC",`; after `"entities.register_lookup.needs_ico"` add:

```python
    "vat_register.source_note": "Đã điền từ sổ đăng ký kinh doanh (ARES) và sổ đăng ký VAT. Kiểm tra và lưu.",
    "vat_register.accounts": "Tài khoản trong sổ đăng ký VAT:",
    "vat_register.use": "Dùng %(account)s",
    "vat_register.needs_dic": "Để điền cả tài khoản ngân hàng, hãy thêm DIČ trong",
    "vat_register.unreliable": "Sổ đăng ký VAT ghi doanh nghiệp này là người nộp thuế không đáng tin cậy.",
```

### Step 7: tests `App/tests/test_vat_register.py`

Copy the `host` fixture, `_owner`, `_cleanup` and `_add_entity` from `App/tests/test_invoice_settings.py` lines 1-70 (use `USERNAME = "vat-register-host"`). Use fake data only (never a real DIČ or account). Mock both networks: `patch("app.ares.requests.get")` (copy `_mock_response` and `SAMPLE_PAYLOAD` from `App/tests/test_ares.py` lines 17-40) and `patch("app.vat_register.requests.post")`. Clear `ares._CACHE` and `vat_register._CACHE` in an autouse fixture, and the `rate_limit` rows the way `test_ares.py` does (`clear_ares_cache` fixture ~75).

Fixture answer (fake DIČ 1111111111, one ended account that must be skipped):

```python
VAT_XML = (
    '<?xml version="1.0" encoding="utf-8"?><soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">'
    '<soapenv:Header/><soapenv:Body><StatusNespolehlivySubjektRozsirenyResponse xmlns="http://adis.mfcr.cz/rozhraniCRPDPH/">'
    '<status odpovedGenerovana="2026-10-25" statusCode="0" statusText="OK"/>'
    '<statusSubjektu typSubjektu="PLATCE_DPH" dic="1111111111" nespolehlivyPlatce="NE" cisloFu="451">'
    '<zverejneneUcty>'
    '<ucet datumZverejneni="2024-04-19"><standardniUcet cislo="123456789" kodBanky="0300"/></ucet>'
    '<ucet datumZverejneni="2024-05-01"><standardniUcet predcisli="19" cislo="2000145399" kodBanky="0800"/></ucet>'
    '<ucet datumZverejneni="2020-01-01" datumZverejneniUkonceni="2021-01-01"><standardniUcet cislo="999" kodBanky="0100"/></ucet>'
    '</zverejneneUcty><nazevSubjektu>Test Host</nazevSubjektu></statusSubjektu>'
    '</StatusNespolehlivySubjektRozsirenyResponse></soapenv:Body></soapenv:Envelope>'
).encode("utf-8")
```

A mocked post response: `MagicMock(ok=True, status_code=200, content=VAT_XML)`.

Tests (POST to `/entities/{id}/invoice?lang=en` with `_csrf` handled the same way test_invoice_settings does for that route; find one existing POST to `/entities/` + `/invoice` in that file with `grep -n "/invoice\"" App/tests/test_invoice_settings.py` and copy its form fields):

1. `dic_digits`: `"CZ 12345678"` → `"12345678"`, `"CZ1111111111"` → `"1111111111"`, `"SK123"` → `""`.
2. `lookup("CZ1111111111")` → `vat_status == "payer"`, `accounts == ["123456789/0300", "19-2000145399/0800"]`, `unreliable is False`; the posted body contains `<dic>1111111111</dic>` and not `CZ`.
3. Status code not 0 (`statusCode="1"`) → `None`, and a second call posts again (not cached).
4. Sole trader: ARES payload without `"dic"`, entity saved with `dic="CZ1111111111"`, `bank_account=None, iban=None`, empty account fields posted with `fill_from_register=1` → response 200 contains `value="123456789"` and `value="0300"`, a button `value="19-2000145399/0800"`, text "and the VAT register", the BIC input is filled (the value `bic_for_account("123456789/0300")` returns), and `legal_entity.bank_account` in the DB is still NULL.
5. Typed account kept: post `account_number=555`, `account_bank=0100` → response keeps `value="555"`, does not contain `value="123456789"` in an input, and shows a `use_register_account` button with `value="123456789/0300"`.
6. Picking: post `use_register_account=19-2000145399/0800` (no `fill_from_register`) → inputs show `value="19"`, `value="2000145399"`, `value="0800"`. Posting `use_register_account=1/0100` (not listed) leaves the account fields as posted.
7. VAT status: entity `vat_status="non_payer"` → select shows `payer` selected after the lookup; with `typSubjektu="IDENTIFIKOVANA_OSOBA"` → `identified`; entity already `payer` with register `IDENTIFIKOVANA_OSOBA` → stays `payer`.
8. No DIČ anywhere (ARES without dic, entity dic empty): `requests.post` not called; response contains "add your DIČ in".
9. `nespolehlivyPlatce="ANO"` → response contains "unreliable VAT payer".
10. MFČR down (`post.side_effect = requests.Timeout()`): response 200, ARES note still shown, no account filled, no error page.

Run: `cd App && .venv/bin/python -m pytest tests/test_vat_register.py tests/test_ares.py tests/test_invoice_settings.py -q --tb=short -x 2>&1 | tail -30`.

### Step 8: decisions line

Append to `docs/context/decisions.md` (end of the table, same format as the ARES line ~41):

```
- 2026-10-25 | Invoice details "Fill from register" also asks the MFČR VAT register (official CRPDPH SOAP, getStatusNespolehlivySubjektRozsirenyV2) on the host's click; sends only the DIČ digits; fills empty account fields, offers other published accounts; 24 h cache; no new dependency | owner | [0394](../tasks/0394-vat-register-bank-account.md)
```

## 5. Do not touch

The buyer lookup on the new-invoice form, the entity editor's own IČO lookup, IBAN filling from non-standard accounts, any stored field or migration.

## 6. Commands

From `App/`:

1. `.venv/bin/python -m pytest tests/test_vat_register.py tests/test_ares.py tests/test_invoice_settings.py tests/test_invoice_entity.py tests/test_entity_editor_fields.py -q --tb=short -x 2>&1 | tail -30`
2. `.venv/bin/python -m pytest tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_static_versions.py tests/test_privacy_first.py -q --tb=short 2>&1 | tail -30` (skip a file name that does not exist; say so in the report)
3. `.venv/bin/python -m pytest tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q --tb=short -rs 2>&1 | tail -30` (0 skipped)
4. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -10`

## 7. Acceptance

- [ ] Click fills empty account fields and BIC from the VAT register; nothing saved
- [ ] Typed account never replaced; other accounts offered as "Use …" buttons; only listed accounts accepted
- [ ] DIČ from ARES, else Business details; never CZ+IČO
- [ ] VAT status set only from the default; identified person supported
- [ ] MFČR failure is silent; ARES result still shown
- [ ] host.css key bumped; tests in §6 pass, browser 0 skipped
- [ ] Report `docs/tasks/0394-report.md`; do not push, the orchestrator pushes and opens the PR

## 8. Stop and ask

An anchor is missing, a test fails twice, or a step can be read two ways: STOP, commit what works, write the report with `Status: blocked` and the question.

## 9. Report

`docs/tasks/0394-report.md`, as executor.md says.
