# 0020: Stay invoice pages (picker, form, stay button)

Status: review
Depends on: 0019 merged | Base commit: main after 0019 | Branch: task/0020-stay-invoice-pages
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

Connect the 0019 rules to the pages. "Issue invoice" first asks which stay; the form shows the accommodation line built from that stay, and extras come from a list. A new invoice can no longer be made without a stay. Old invoices stay as they are.

## 2. Context

Rules: AGENTS.md hard rules 5 (SQL via db.py), 6 (light mode; forms work without JavaScript), 7 (template change: browser and geometry tests pass with 0 skipped, plus screenshots), 9 (copy: one explanation in one place).

From 0019 (already in `App/app/invoices.py`): `stay_problem(reservation, today)`, `stay_label(name, reservation, lang)`, `active_invoice_for_stay(reservation_id)`, `StayLimit` (has `.key` and `.invoice_id`), `EXTRA_KINDS`, `STAY_PAST_DAYS`, `STAY_FUTURE_DAYS`, and `build_draft(..., stay={"reservation": row, "property_name": str})`. Form field names the backend reads: `stay_price`, `stay_vat_rate`, `item_kind`, `item_description`, `item_quantity`, `item_unit`, `item_unit_price`, `item_vat_rate`.

Verbatim excerpts. Search for each one; if any is missing, STOP (§8).

R1 `App/app/routes/invoices.py`, first lines:
```python
"""Host-only invoice tool: a standalone, free-form invoice builder.

An invoice is NOT tied to a stay. Included in main.py after admin.router.
"""
```
R2 `App/app/routes/invoices.py`:
```python
from datetime import date
```
R3 `App/app/routes/invoices.py`, in the `from .. import (` list:
```python
    stay_fee,
)
```
R4 `App/app/routes/invoices.py`:
```python
def _form_state(request, form, entity) -> Dict[str, Any]:
```
R5 `App/app/routes/invoices.py`:
```python
def _form_context(request, entities, entity, *, errors=None, values=None):
```
R6 `App/app/routes/invoices.py`:
```python
def _draft(request, entity, form):
    draft = invoices.build_draft(entity, form, _lang(request), today=claim.prague_today())
```
R7 `App/app/routes/invoices.py`, in `_preview_view`:
```python
        "stay_label": None,
```
R8 `App/app/routes/invoices.py`: the whole function `invoice_new` (starts `@router.get("/invoices/new")`, ends `return render(request, "invoice_form.html", context)`).
R9 `App/app/routes/invoices.py`: the functions `invoice_preview` and `invoice_issue` (see §4 step 6 and 7).
T1 `App/app/templates/invoice_form.html`:
```html
<form method="post" action="/invoices" class="invoice-form">
  <input type="hidden" name="_csrf" value="{{ csrf_token }}">
```
T2 `App/app/templates/invoice_form.html`:
```html
      <tbody data-item-body>
```
T3 `App/app/templates/invoice_form.html` (appears twice, in the `{% for row in rows %}` branch and in the `{% else %}` branch):
```html
<input type="text" name="item_description" maxlength="150" required
```
T4 `App/app/templates/invoice_form.html` (appears twice):
```js
"/invoices/new?entity=" + encodeURIComponent(wanted)
```
T5 `App/app/templates/invoice_form.html`:
```html
next={{ (('/invoices/new?entity=' ~ entity.id) | urlencode) }}
```
S1 `App/app/templates/reservation_detail.html`:
```html
      <a class="btn" href="/invoices/new">{{ t('invoice.new') }}</a>
```
A1 `App/app/routes/admin.py`, in the `reservation_detail` render context:
```python
            "hand_filing": reporting.hand_filing_view(progress),
```
I1 `App/app/invoices.py`, in `form_item_rows`:
```python
            "description": _at(descs, i),
```
H1 `App/app/host_i18n.py`, two places (en near line 1281, cs near line 2737):
```python
        "invoice.new": "Issue invoice",
```
```python
        "invoice.new": "Vystavit fakturu",
```
H2 `App/app/host_i18n.py`: `"invoices.lede": "One-off invoices you issue yourself.",` and `"invoices.lede": "Jednorázové faktury, které vystavíte sami.",`
H3 `App/app/host_i18n.py`: the two `"invoice.items_help": ...` lines (en and cs).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/invoices.py` | edit | steps 1–7 |
| `App/app/invoices.py` | edit | step 8 (one small change in `form_item_rows`) |
| `App/app/templates/invoice_stay_picker.html` | new | step 9 |
| `App/app/templates/invoice_form.html` | edit | step 10 |
| `App/app/templates/reservation_detail.html` | edit | step 11 |
| `App/app/routes/admin.py` | edit | step 11 (one import, one context line) |
| `App/app/host_i18n.py` | edit | step 12 |
| `App/tests/invoice_stay_helper.py` | new | step 13 |
| `App/tests/test_invoice_ux.py`, `test_invoice_workspace.py`, `test_invoice_settings.py`, `test_invoice_entity.py`, `test_property_names_in_mail.py` | edit | step 14 (fixtures only) |
| `App/tests/test_invoice_stay_pages.py` | new | step 15 |
| `App/tests/test_invoice_stay_browser.py` | new | step 16 |
| `docs/context/known-issues.md` | edit | step 17 |
| `docs/tasks/0020-screenshots/*.png` | new | step 18 |

No other file may change.

## 4. Steps

**Step 1: route docstring.** Replace R1 with:
```python
"""Host-only invoice tool: every new invoice belongs to one stay.

Included in main.py after admin.router.
"""
```

**Step 2: imports.** Replace R2 with `from datetime import date, timedelta`. In the `from .. import (` list, replace R3 with:
```python
    stay_fee,
    validation,
)
```
Also change `from typing import Any, Dict` to `from typing import Any, Dict, Optional`.

**Step 3: stay helpers.** Directly **above** R4 (`def _form_state(`), insert:
```python
def _stay_for(request: Request, raw_id) -> Optional[Dict[str, Any]]:
    """The host's own stay, shaped for invoices.build_draft, or None."""
    text = str(raw_id or "").strip()
    if not text.isdigit():
        return None
    row = access.reservation(
        request,
        int(text),
        columns="r.*, a.legal_entity_id AS apartment_entity_id, a.internal_name, a.uby_name",
    )
    if not row:
        return None
    name = (row["internal_name"] or "").strip() or (row["uby_name"] or "").strip()
    return {"reservation": row, "property_name": name, "entity_id": row["apartment_entity_id"]}


def _entity_for_stay(request, entities, stay, form=None):
    """The property's operator when it has one; otherwise the host's pick."""
    if stay and stay["entity_id"]:
        for entity in entities:
            if entity["id"] == stay["entity_id"]:
                return entity
    return _chosen_entity(request, entities, form)


def _stay_options(request: Request):
    """Stays the host can invoice, newest check-in first, for the picker."""
    today = claim.prague_today()
    rows = db.query(
        "SELECT r.id, r.date_from, r.date_to, a.internal_name, a.uby_name "
        "FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
        f"WHERE {db.null_safe_eq('a.owner_user_id')} AND r.status != 'cancelled' "
        "AND r.date_to > r.date_from AND r.date_to >= ? AND r.date_from <= ? "
        "ORDER BY r.date_from DESC, r.id DESC LIMIT 200",
        (
            access.owner_id(request),
            (today - timedelta(days=invoices.STAY_PAST_DAYS)).isoformat(),
            (today + timedelta(days=invoices.STAY_FUTURE_DAYS)).isoformat(),
        ),
    )
    options = []
    for row in rows:
        name = (row["internal_name"] or "").strip() or (row["uby_name"] or "").strip()
        dates = validation.fmt_date_range(row["date_from"], row["date_to"])
        options.append({"id": row["id"], "label": f"{name}, {dates}"})
    return options


```

**Step 4: form state and context.**

4a. Inside `_form_state`, the tuple of keys starts with `"buyer_name", "buyer_street",`. Add `"stay_price", "stay_vat_rate", "reservation_id",` as the first line inside that tuple.

4b. Inside `_form_state`, the item rows comprehension lists the keys `"description", "quantity", "unit", "unit_price", "vat_rate"`. Change it to `"kind", "description", "quantity", "unit", "unit_price", "vat_rate"`.

4c. Replace the whole `_form_context` function (starts at R5) with:
```python
def _form_context(request, entities, entity, *, errors=None, values=None, stay=None):
    values = dict(values or {})
    if stay and not values and stay["reservation"]["guest_email"]:
        values["buyer_email"] = stay["reservation"]["guest_email"]
    lang = "cs" if _lang(request) == "cs" else "en"
    return {
        "nav": "invoices",
        "entities": entities,
        "entity": entity,
        "next_number": invoices.preview_number(entity) if entity else "",
        "errors": errors or [],
        "values": values,
        "countries": codelists.nationality_options(_lang(request)),
        "stay": stay,
        "stay_label": invoices.stay_label(stay["property_name"], stay["reservation"], lang) if stay else "",
        "extra_kinds": invoices.EXTRA_KINDS,
    }
```

**Step 5: drafts carry the stay.** Replace the first two lines of `_draft` (R6) with:
```python
def _draft(request, entity, form, stay=None):
    draft = invoices.build_draft(
        entity, form, _lang(request), today=claim.prague_today(), stay=stay
    )
```
Keep the rest of `_draft` as it is. In `_preview_view`, replace R7 with `"stay_label": draft.get("stay_label"),`.

**Step 6: the builder page.** Replace the whole `invoice_new` function (R8) with:
```python
@router.get("/invoices/new")
def invoice_new(request: Request):
    guard = auth.require_login(request)
    if guard:
        return guard
    raw_stay = request.query_params.get("reservation_id")
    if not raw_stay:
        return render(
            request, "invoice_stay_picker.html", {"nav": "invoices", "stays": _stay_options(request)}
        )
    stay = _stay_for(request, raw_stay)
    if not stay:
        return _back("/invoices/new", err=_flash(request, "invoice.err.no_stay"))
    problem = invoices.stay_problem(stay["reservation"], claim.prague_today())
    if problem:
        return _back("/invoices/new", err=_flash(request, problem))
    reservation_id = stay["reservation"]["id"]
    active = invoices.active_invoice_for_stay(reservation_id)
    if active:
        return _back(f"/invoices/{active['id']}", err=_flash(request, "invoice.err.stay_has_invoice"))
    entities = _entities(request)
    entity = _entity_for_stay(request, entities, stay)
    if entity and request.query_params.get("entity") != str(entity["id"]):
        # Pin the operator in the URL once, so the details page returns here.
        return RedirectResponse(
            f"/invoices/new?reservation_id={reservation_id}&entity={entity['id']}", status_code=303
        )
    if entity and stay["entity_id"] == entity["id"]:
        entities = [entity]  # the property names its operator: no other choice
    context = _form_context(request, entities, entity, stay=stay)
    if not entity:
        context["errors"] = [host_i18n.translate(_lang(request), "invoice.err.no_entity")]
    return render(request, "invoice_form.html", context)
```

**Step 7: preview and issue need the stay.**

7a. In `invoice_preview`, find these lines:
```python
    form = await request.form()
    entity = _chosen_entity(request, entities, form)
    if not entity:
        return _back("/invoices/new", err=_flash(request, "invoice.err.no_entity"))
    draft = _draft(request, entity, form)
```
Replace them with:
```python
    form = await request.form()
    stay = _stay_for(request, _form_str(form, "reservation_id"))
    if not stay or invoices.stay_problem(stay["reservation"], claim.prague_today()):
        return _back("/invoices/new", err=_flash(request, "invoice.err.no_stay"))
    entity = _entity_for_stay(request, entities, stay, form)
    if not entity:
        return _back("/invoices/new", err=_flash(request, "invoice.err.no_entity"))
    draft = _draft(request, entity, form, stay)
```

7b. In `invoice_issue`, the same 5 lines appear. Replace them the same way, but the problem check must keep the real reason:
```python
    form = await request.form()
    stay = _stay_for(request, _form_str(form, "reservation_id"))
    if not stay:
        return _back("/invoices/new", err=_flash(request, "invoice.err.no_stay"))
    problem = invoices.stay_problem(stay["reservation"], claim.prague_today())
    if problem:
        return _back("/invoices/new", err=_flash(request, problem))
    entity = _entity_for_stay(request, entities, stay, form)
    if not entity:
        return _back("/invoices/new", err=_flash(request, "invoice.err.no_entity"))
    draft = _draft(request, entity, form, stay)
```
7c. In `invoice_issue`, the 422 render is:
```python
        context = _form_context(
            request,
            entities,
            entity,
            errors=[host_i18n.translate(lang, issue.message) for issue in issues],
            values=_form_state(request, form, entity),
        )
```
Add `stay=stay,` as a new line after the `values=` line.

7d. In `invoice_issue`, replace
```python
    invoice_id = invoices.issue(draft, access.owner_id(request))
```
with
```python
    try:
        invoice_id = invoices.issue(draft, access.owner_id(request))
    except invoices.StayLimit as limit:
        if limit.invoice_id:
            return _back(f"/invoices/{limit.invoice_id}", err=_flash(request, limit.key))
        return _back(f"/reservations/{stay['reservation']['id']}", err=_flash(request, limit.key))
```

**Step 8: the 422 form keeps the extra kind.** In `App/app/invoices.py`, `form_item_rows`:
- below `descs = _getlist(form, "item_description")` add `kinds = _getlist(form, "item_kind")`;
- in `range(max(len(descs), ...))` add `len(kinds), ` as the first argument of `max(`;
- above I1 (`"description": _at(descs, i),`) add `"kind": _at(kinds, i),`;
- change `if not (row["description"].strip() or row["unit_price"].strip()):` to `if not (row["kind"].strip() or row["description"].strip() or row["unit_price"].strip()):`.

**Step 9: the picker page.** Create `App/app/templates/invoice_stay_picker.html`:
```html
{% extends "base.html" %}
{% set nav = 'invoices' %}
{% block title %}{{ t('invoice.new') }}{% endblock %}
{% block content %}
{% from "_components.html" import page_header with context %}
{{ page_header(t('invoice.new'), t('invoice.picker.lede'), '/invoices', t('nav.invoices')) }}

<div class="panel">
  {% if stays %}
  <form method="get" action="/invoices/new">
    <div class="field">
      <label for="reservation_id">{{ t('invoice.picker.label') }}</label>
      <select id="reservation_id" name="reservation_id" required>
        {% for option in stays %}
          <option value="{{ option.id }}">{{ option.label }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="actions">
      <button class="btn accent primary" type="submit">{{ t('invoice.picker.continue') }}</button>
    </div>
  </form>
  {% else %}
  <p>{{ t('invoice.picker.empty') }}</p>
  {% endif %}
  <p class="small muted"><a href="/reservations">{{ t('invoice.picker.add_stay') }}</a></p>
</div>
{% endblock %}
```

**Step 10: the invoice form.** All in `App/app/templates/invoice_form.html`.

10a. Replace T1 with:
```html
<form method="post" action="/invoices" class="invoice-form" data-reservation-id="{{ stay.reservation.id if stay else '' }}">
  <input type="hidden" name="_csrf" value="{{ csrf_token }}">
  {% if stay %}<input type="hidden" name="reservation_id" value="{{ stay.reservation.id }}">{% endif %}
```

10b. Directly **above** T2 (`      <tbody data-item-body>`), insert the stay row in its own `tbody`:
```html
      {% if stay %}
      <tbody data-stay-body>
        <tr data-item-row data-stay-row>
          <td data-label="{{ t('invoice.col.description') }}">
            <strong>{{ t('invoice.stay.line') }}</strong><br><span class="small">{{ stay_label }}</span>
          </td>
          <td data-label="{{ t('invoice.col.qty') }}">1<input type="hidden" class="input-qty" value="1"></td>
          <td data-label="{{ t('invoice.col.unit') }}">{{ t('invoice.stay.unit') }}</td>
          <td data-label="{{ t('invoice.col.unit_price') }}">
            <input type="text" name="stay_price" inputmode="decimal" required class="input-price"
                   aria-label="{{ t('invoice.stay.price') }}" value="{{ values.get('stay_price', '') }}">
          </td>
          <td data-label="{{ t('invoice.col.vat') }}" data-vat-col {% if not payer %}hidden{% endif %}>
            <select name="stay_vat_rate" class="input-vat" {% if not payer %}disabled{% endif %}>
              {% for rate in (12, 21, 0) %}
                <option value="{{ rate }}" {% if values.get('stay_vat_rate', '12') == rate|string %}selected{% endif %}>{{ rate }} %</option>
              {% endfor %}
            </select>
          </td>
          <td></td>
        </tr>
      </tbody>
      {% endif %}
```

10c. T3 appears twice. **In the `{% for row in rows %}` branch**, replace the whole `<td ...>` that holds `name="item_description"` with:
```html
            <td data-label="{{ t('invoice.col.description') }}">
              <select name="item_kind" class="input-kind" aria-label="{{ t('invoice.extra.kind') }}">
                <option value="">{{ t('invoice.extra.choose') }}</option>
                {% for kind in extra_kinds %}
                  <option value="{{ kind }}" {% if row.kind == kind %}selected{% endif %}>{{ t('invoice.extra.' ~ kind) }}</option>
                {% endfor %}
              </select>
              <input type="text" name="item_description" maxlength="60" value="{{ row.description }}"
                     placeholder="{{ t('invoice.extra.other_text') }}" aria-label="{{ t('invoice.extra.other_text') }}">
            </td>
```
**In the `{% else %}` branch**, replace that `<td ...>` with the same block, but without `{% if row.kind == kind %}selected{% endif %}` and with `value=""` instead of `value="{{ row.description }}"`.
Do not touch the quantity, unit, price, VAT or remove-button cells.

10d. T4 appears twice in the `<script>`. Replace each with:
```js
"/invoices/new?reservation_id=" + encodeURIComponent(form.getAttribute("data-reservation-id")) + "&entity=" + encodeURIComponent(wanted)
```

10e. Replace T5 with:
```html
next={{ (('/invoices/new?reservation_id=' ~ (stay.reservation.id if stay else '') ~ '&entity=' ~ entity.id) | urlencode) }}
```

10f. Cap the extra rows at 3 in the browser (the server enforces it anyway). In the `<script>`, find the add-item listener: `document.querySelector("[data-add-item]").addEventListener("click", function () {`. Directly **after** its line `body.appendChild(row);` add:
```js
      syncAddButton();
```
Directly **above** `if (body) {` (the block that starts with the comment `/* Items: cloning keeps the rate`) add:
```js
  var MAX_EXTRAS = 3;
  function syncAddButton() {
    var add = document.querySelector("[data-add-item]");
    if (add && body) add.hidden = body.querySelectorAll("[data-item-row]").length >= MAX_EXTRAS;
  }
```
In the remove listener, after `button.closest("[data-item-row]").remove();` add `syncAddButton();`. At the very end of the script, next to the final `syncVat();` and `syncTotal();`, add `syncAddButton();`.

The live total already sums every `[data-item-row]`; the stay row has `.input-qty` and `.input-price`, so it is counted without more changes.

**Step 11: the stay page button.**
11a. `App/app/routes/admin.py`: in the `from .. import (` list near the top, add `invoices,` in alphabetical order. Directly after A1 add:
```python
            "stay_invoice": invoices.active_invoice_for_stay(reservation_id),
```
11b. `App/app/templates/reservation_detail.html`: replace S1 with:
```html
      {% if stay_invoice %}
        <a class="btn" href="/invoices/{{ stay_invoice.id }}">{{ t('invoice.stay.open', number=stay_invoice.number) }}</a>
      {% else %}
        <a class="btn" href="/invoices/new?reservation_id={{ reservation.id }}">{{ t('invoice.new') }}</a>
      {% endif %}
```
If the `t()` helper in templates doesn't accept `number=`, look at how `invoice.next_number` is called in `invoice_form.html` (`t('invoice.next_number', number=next_number)`) and do the same.

**Step 12: texts.** In `App/app/host_i18n.py`, add these keys directly **below** H1: the English block below the English `"invoice.new"` line, the Czech block below the Czech one. Same keys in both, or the i18n tests fail.

English:
```python
        "invoice.picker.lede": "An invoice is always issued for a stay.",
        "invoice.picker.label": "Stay",
        "invoice.picker.continue": "Continue",
        "invoice.picker.empty": "No stays from the last 400 days or the next year.",
        "invoice.picker.add_stay": "Stay not in the list? Add it under Stays.",
        "invoice.stay.line": "Accommodation",
        "invoice.stay.unit": "stay",
        "invoice.stay.price": "Price for the stay",
        "invoice.stay.open": "Invoice %(number)s",
        "invoice.extra.kind": "Type of extra",
        "invoice.extra.choose": "Extra…",
        "invoice.extra.cleaning": "Cleaning",
        "invoice.extra.stay_fee": "Local stay fee",
        "invoice.extra.breakfast": "Breakfast",
        "invoice.extra.parking": "Parking",
        "invoice.extra.pet": "Pet",
        "invoice.extra.extra_bed": "Extra bed",
        "invoice.extra.late_checkout": "Late check-out",
        "invoice.extra.other": "Other",
        "invoice.extra.other_text": "Text for Other",
        "invoice.err.no_stay": "Pick the stay this invoice is for.",
        "invoice.err.stay_cancelled": "This stay is cancelled, so it can't be invoiced.",
        "invoice.err.stay_dates": "The stay needs a check-out after the check-in.",
        "invoice.err.stay_too_old": "This stay ended more than 400 days ago.",
        "invoice.err.stay_too_far": "This stay starts more than a year from now.",
        "invoice.err.stay_has_invoice": "This stay already has an invoice. Cancel it first to issue a new one.",
        "invoice.err.stay_limit": "This stay already has 3 invoices, the most allowed.",
        "invoice.err.extra_kind": "Pick a type for each extra line, and add text for Other.",
        "invoice.err.one_other": "Only one Other line per invoice.",
        "invoice.err.extra_quantity": "The quantity of an extra is 1 to 99.",
        "invoice.err.extras_cap": "Extras together can't cost more than the accommodation.",
        "invoice.err.other_cap": "Other can be at most 30 % of the accommodation.",
```
Czech:
```python
        "invoice.picker.lede": "Faktura se vystavuje vždy k pobytu.",
        "invoice.picker.label": "Pobyt",
        "invoice.picker.continue": "Pokračovat",
        "invoice.picker.empty": "Žádný pobyt za posledních 400 dní ani na příští rok.",
        "invoice.picker.add_stay": "Pobyt v seznamu chybí? Přidejte ho v Pobytech.",
        "invoice.stay.line": "Ubytování",
        "invoice.stay.unit": "pobyt",
        "invoice.stay.price": "Cena za pobyt",
        "invoice.stay.open": "Faktura %(number)s",
        "invoice.extra.kind": "Typ položky",
        "invoice.extra.choose": "Další položka…",
        "invoice.extra.cleaning": "Úklid",
        "invoice.extra.stay_fee": "Poplatek z pobytu",
        "invoice.extra.breakfast": "Snídaně",
        "invoice.extra.parking": "Parkování",
        "invoice.extra.pet": "Domácí zvíře",
        "invoice.extra.extra_bed": "Přistýlka",
        "invoice.extra.late_checkout": "Pozdní odjezd",
        "invoice.extra.other": "Jiné",
        "invoice.extra.other_text": "Popis u Jiné",
        "invoice.err.no_stay": "Vyberte pobyt, ke kterému fakturu vystavujete.",
        "invoice.err.stay_cancelled": "Pobyt je zrušený, fakturu k němu vystavit nelze.",
        "invoice.err.stay_dates": "Pobyt musí mít odjezd po příjezdu.",
        "invoice.err.stay_too_old": "Pobyt skončil před více než 400 dny.",
        "invoice.err.stay_too_far": "Pobyt začíná za více než rok.",
        "invoice.err.stay_has_invoice": "K pobytu už faktura je. Novou vystavíte až po jejím stornu.",
        "invoice.err.stay_limit": "K pobytu už jsou 3 faktury, víc nejde.",
        "invoice.err.extra_kind": "U každé další položky vyberte typ; u Jiné doplňte popis.",
        "invoice.err.one_other": "Položka Jiné může být na faktuře jen jednou.",
        "invoice.err.extra_quantity": "Množství u další položky je 1 až 99.",
        "invoice.err.extras_cap": "Další položky dohromady nesmí stát víc než ubytování.",
        "invoice.err.other_cap": "Položka Jiné smí být nejvýš 30 % ceny ubytování.",
```
Then replace the two H2 lines with
`"invoices.lede": "Invoices for your guests' stays.",` and `"invoices.lede": "Faktury k pobytům vašich hostů.",`
and the two H3 lines with
`"invoice.items_help": "Line 1 is the stay. Add up to 3 extras; only Other takes your own text. For a VAT payer prices are without VAT.",` and
`"invoice.items_help": "První řádek je pobyt. Přidejte až 3 další položky; vlastní text má jen Jiné. U plátce DPH jsou ceny bez DPH.",`

**Step 13: test helper.** Create `App/tests/invoice_stay_helper.py`:
```python
"""A stay to issue test invoices for: every new invoice needs one (task 0020)."""
from __future__ import annotations

import secrets
from datetime import timedelta

from app import claim, db

UID_PREFIX = "invstay-"


def make_stay(owner_user_id, *, entity_id=None, nights=3) -> int:
    """A manual stay that ended yesterday, in its own property. Returns the reservation id."""
    now = db.utcnow()
    today = claim.prague_today()
    tag = secrets.token_hex(4)
    apartment_id = db.insert(
        "apartment",
        {"internal_name": "Chata", "owner_user_id": owner_user_id, "legal_entity_id": entity_id,
         "permalink_token": f"{UID_PREFIX}{tag}", "automation_mode": "manual",
         "default_purpose": "10", "active": 1, "created_at": now},
    )
    return db.insert(
        "reservation",
        {"apartment_id": apartment_id, "source": "manual", "uid": f"{UID_PREFIX}{tag}",
         "date_from": (today - timedelta(days=nights + 1)).isoformat(),
         "date_to": (today - timedelta(days=1)).isoformat(),
         "status": "active", "created_at": now, "updated_at": now},
    )


def stay_form(reservation_id: int, price: str = "10000") -> dict:
    """The fields a stay invoice POST needs on top of the old ones."""
    return {"reservation_id": str(reservation_id), "stay_price": price}


def drop_stays(owner_user_id) -> None:
    """Call after the test's invoices are deleted (invoices point at the apartment)."""
    db.execute(
        "DELETE FROM reservation WHERE uid LIKE ? AND apartment_id IN "
        "(SELECT id FROM apartment WHERE owner_user_id = ?)",
        (UID_PREFIX + "%", owner_user_id),
    )
    db.execute(
        "DELETE FROM apartment WHERE permalink_token LIKE ? AND owner_user_id = ?",
        (UID_PREFIX + "%", owner_user_id),
    )
```

**Step 14: update the existing tests (fixtures only).** Run `cd App && .venv/bin/python -m pytest tests -q -x` and fix the failures **one file at a time**, using only these moves:
1. Add `from tests.invoice_stay_helper import drop_stays, make_stay, stay_form` to the file.
2. In the file's cleanup function, call `drop_stays(user_id)` **after** the line that deletes from `invoice` (and before the user is deleted).
3. Where the test does `host.post("/invoices", data={...})` or posts to `/invoices/preview`, create a stay first with `stay_id = make_stay(_owner())` (use the entity id as `entity_id=` only if the test needs a fixed operator) and add `**stay_form(stay_id)` into the `data={...}` dict.
4. Where the test does `host.get("/invoices/new?entity=X")` or `host.get("/invoices/new")` to look at the **form**, change the URL to `f"/invoices/new?reservation_id={stay_id}&entity=X"` (with the real entity id).
5. Where the test asserts a total, an amount or a number of lines, the stay line (10,000 Kč, 1 line) is now added: update the expected number and write the old and new value in the report.
6. Where a test checks a `"next"` value of `/invoices/new?entity=...` on the settings page, leave it alone unless it fails; if it fails, change only the expected URL.

You may **not** delete a test, remove an assertion, or change what an assertion checks beyond moves 3–6. If a test needs anything else, STOP (§8) and name it in the report.

**Step 15: route tests.** Create `App/tests/test_invoice_stay_pages.py`. Copy the `USERNAME` constant (use `"invoice-stay-host"`), `_cleanup` (add `drop_stays(user_id)` after the invoice delete), the `host` fixture, `_owner` and `_add_entity` from `App/tests/test_invoice_ux.py`. Then write these tests (each one gets `host`):
1. `test_new_without_a_stay_shows_the_picker`: `_add_entity()`; `make_stay(_owner())`; `GET /invoices/new` → 200, has `name="reservation_id"` and `Chata`.
2. `test_issue_without_a_stay_is_refused`: `_add_entity()`; POST `/invoices` with `buyer_name`, `already_paid=1` and an `item_description` row, **no** `reservation_id`, `follow_redirects=False` → 303, location starts with `/invoices/new`; `SELECT COUNT(*) FROM invoice WHERE owner_user_id = ?` is 0.
3. `test_preview_without_a_stay_is_refused`: same, but POST `/invoices/preview` → 303, not a PDF.
4. `test_someone_elses_stay_is_refused`: make a second account with `auth.create_account("other-stay@example.test", "Other", username="other-stay-host")`, `make_stay(<its id>)`; GET `/invoices/new?reservation_id=<that id>` with `follow_redirects=False` → 303 to `/invoices/new`. Clean that account up at the end (invoices none; `drop_stays(other_id)`; delete the user_account row).
5. `test_issue_for_a_stay_prints_the_stay`: `_add_entity()`; `sid = make_stay(_owner())`; POST `/invoices` with `buyer_name`, `already_paid=1`, `lang=cs`, `**stay_form(sid)` → 303 to `/invoices/<id>`; the row has `reservation_id == sid` and `stay_label` containing `Chata`; its first `invoice_item` has `kind == 'accommodation'`; GET `/invoices/<id>.pdf` starts with `b"%PDF"`.
6. `test_second_invoice_for_the_stay_goes_to_the_first`: issue once like test 5, then GET `/invoices/new?reservation_id=<sid>` with `follow_redirects=False` → 303 to `/invoices/<first id>`; POST `/invoices` again → 303 to `/invoices/<first id>`; still one row.
7. `test_property_operator_is_forced`: `a = _add_entity()`, `b = _add_entity(name="Other s.r.o.")`; `sid = make_stay(_owner(), entity_id=b)`; GET `/invoices/new?reservation_id=<sid>` (follow redirects) → the page has `value="<b>"` in the operator select and **not** `value="<a>"` inside the `legal_entity_id` select.
8. `test_stay_page_links_to_the_builder_then_to_the_invoice`: `_add_entity()`; `sid = make_stay(_owner())`; GET `/reservations/<sid>` → contains `/invoices/new?reservation_id=<sid>`; issue as in test 5; GET `/reservations/<sid>` → contains `/invoices/<id>` and the invoice number.
9. `test_the_form_works_without_javascript_fields`: GET the form for a stay → contains `name="stay_price"`, `name="item_kind"`, `name="reservation_id"` and no `required` on `item_description` (`'name="item_description" maxlength="60" required' not in text`).

Run: `.venv/bin/python -m pytest tests/test_invoice_stay_pages.py -q` → `9 passed`.

**Step 16: browser test.** Create `App/tests/test_invoice_stay_browser.py`. Copy the top of `App/tests/test_host_geometry.py` exactly: the docstring style, the `REQUIRE_BROWSER` / `sync_api` import block, `_free_port`, the `base` fixture and `_browser_session_cookie`. Then add:
```python
WIDTHS = (360, 390, 1280)
SHOTS = os.environ.get("UBYHOST_SHOTS_DIR")


def _host():
    username = f"invstay{secrets.token_hex(4)}"
    owner = auth.create_account(f"{username}@example.test", "Stay Invoices", role="host", username=username)
    entity = db.insert("legal_entity", {
        "name": "Stay s.r.o.", "seat": "Praha 1", "ico": "04656679",
        "registry_entry": "Fyzická osoba zapsaná v živnostenském rejstříku",
        "vat_status": "non_payer", "invoice_due_days": 14,
        "owner_user_id": owner, "created_at": db.utcnow(),
    })
    stay = make_stay(owner)
    return username, entity, stay


def _launch(playwright):
    try:
        return playwright.chromium.launch()
    except Exception as exc:
        if REQUIRE_BROWSER:
            raise
        pytest.skip(f"Chromium is not available: {exc}")


def test_stay_invoice_pages_fit_every_width(base):
    username, entity, stay = _host()
    session = _browser_session_cookie(username)
    pages = {
        "picker": "/invoices/new?lang=cs",
        "form": f"/invoices/new?reservation_id={stay}&entity={entity}&lang=cs",
        "stay": f"/reservations/{stay}?lang=cs",
    }
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        for width in WIDTHS:
            context = browser.new_context(viewport={"width": width, "height": 900})
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": session, "url": base + "/"}])
            page = context.new_page()
            for name, path in pages.items():
                page.goto(base + path)
                page.wait_for_load_state("networkidle")
                overflow = page.evaluate(
                    "() => document.documentElement.scrollWidth - window.innerWidth"
                )
                assert overflow <= 1, f"{name} overflows by {overflow}px at {width}px"
                if SHOTS:
                    page.screenshot(path=os.path.join(SHOTS, f"{name}-{width}.png"), full_page=True)
            context.close()
        browser.close()


def test_issue_with_javascript_off(base):
    username, entity, stay = _host()
    session = _browser_session_cookie(username)
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        context = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": session, "url": base + "/"}])
        page = context.new_page()
        page.goto(base + f"/invoices/new?reservation_id={stay}&entity={entity}&lang=cs")
        page.fill("#buyer_name", "Jan Novák")
        page.fill('input[name="stay_price"]', "4500")
        page.click(".invoice-actions button.accent.primary")
        page.wait_for_load_state("load")
        assert "/invoices/" in page.url and "/invoices/new" not in page.url, page.url
        browser.close()
```
Add `from app import auth, db` (already in the copied block) and `from tests.invoice_stay_helper import make_stay`. If `#buyer_name` is not the id of the buyer name input, open `invoice_form.html`, find the input with `name="buyer_name"` and use its id.

Run: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_invoice_stay_browser.py tests/test_host_geometry.py tests/test_wp28_geometry.py -q` → all pass, **0 skipped**. If Chromium is missing locally, run `.venv/bin/python -m playwright install chromium` once (it is already a dev dependency; this is not a new dependency).

**Step 17: known issues.** In `docs/context/known-issues.md`, the row starting `| K-I01 | Med open |`: change `Med open` to `Med fixed` and add ` (0019 lock per stay; 0020 wiring)` at the end of its description cell. Change nothing else.

**Step 18: screenshots.** From `App/`:
```bash
mkdir -p ../docs/tasks/0020-screenshots
UBYHOST_SHOTS_DIR=../docs/tasks/0020-screenshots UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_invoice_stay_browser.py -q -k fit_every_width
ls ../docs/tasks/0020-screenshots
```
Expect 9 files: `picker-360.png` … `stay-1280.png`. Look at each one. If something looks broken (text over text, a button off-screen, the table unreadable at 360 px), fix it with existing CSS classes only, then shoot again. Don't add new CSS files and don't edit `static/`; if you can't fix it without CSS changes, STOP and show the screenshot in the report.

## 5. Do not touch

`App/app/db.py`, `App/app/migrations/`, `App/app/static/`, `invoice_pdf.py`, `stay_fee*`, `retention.py`, `invoice_detail.html`, `invoices.html` (its "Issue invoice" button already goes to `/invoices/new`, which is now the picker), the cancel/send/download routes. Hard rules: light mode only; forms work without JavaScript; no new dependency; SQL only through `db.py` helpers.

## 6. Commands

From `App/`:
1. `.venv/bin/python -m pytest tests/test_invoice_stay_pages.py -q` → `9 passed`.
2. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_invoice_stay_browser.py tests/test_host_geometry.py tests/test_wp28_geometry.py -q` → passed, `0 skipped`.
3. `.venv/bin/python -m pytest tests -q` → no `failed`.

From the repo root: `python3 scripts/context_lint.py` → `context lint: OK`.

## 7. Acceptance

- [ ] `GET /invoices/new` shows the stay picker; with JavaScript off it still works (`<form method="get">`).
- [ ] POST `/invoices` or `/invoices/preview` without a stay creates nothing (test 2, 3).
- [ ] Another host's stay → refused (test 4).
- [ ] The issued invoice has `reservation_id`, `stay_label`, an `accommodation` first line, and a PDF (test 5).
- [ ] A second invoice for the same stay sends you to the first (test 6); the stay page shows "Invoice <number>" (test 8).
- [ ] The property's operator is forced (test 7).
- [ ] Browser and geometry tests: 0 skipped. 9 screenshots in `docs/tasks/0020-screenshots/`.
- [ ] Every change to an old test is listed in the report (file, test name, old → new).
- [ ] `git diff --stat` shows only §3 files.

## 8. Stop and ask

Stop, and write the report, if:
- an excerpt in §2 is not found;
- a test fails twice after you re-read the step;
- an old test needs more than the moves in step 14;
- a new dependency seems needed (installing Chromium for Playwright is fine);
- a file outside §3 needs a change, or you need CSS changes;
- a step is unclear;
- you need push to main, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0020-report.md` (1,500 tokens at most) and set `Status: review` in this file. The report has:
1. `git diff --stat`.
2. Each command in §6 with the last 5 lines of its output.
3. §7 ticked.
4. Deviations, including every old-test change (file, test, old → new).
5. The 9 screenshots as a table (`![picker 360](0020-screenshots/picker-360.png)` …).
6. Questions.
7. Owner steps left.

## Risk list (for the reviewer)

`App/app/routes/invoices.py` (`_stay_for` owner check, `invoice_new`, preview and issue guards, `StayLimit` handling), `App/app/routes/admin.py` (one line), `invoice_form.html` (no-JS form, stay row), every changed old test.

## Owner steps

1. Merge the PR with `scripts/merge-pr-on-green.sh` when CI is green.
2. Deploy when you like (manual, as always).
3. Check it on production: open a stay, tap **Vystavit fakturu**, type a price, tap **Vystavit**. Open the PDF and check that it shows "Ubytování – <property>, <dates> (<n> noci)".
4. Open the same stay again: the button now says **Faktura <number>**.
