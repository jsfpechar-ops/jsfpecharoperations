# 0019: Stay invoice rules (backend only)

Status: todo
Depends on: none | Base commit: branch `claude/bold-ride-leloxm` (has the plan) | Branch: task/0019-stay-invoice-rules
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

Add the rules that tie an invoice to one stay: a fixed accommodation line, extras from a fixed list with caps, and at most one active invoice (3 in total) per stay. This brief only adds Python functions and tests in `App/app/invoices.py`. No page changes yet; brief 0020 wires them into the pages.

## 2. Context

Plan: `docs/plans/stay-only-invoices.md` (don't open it; everything you need is here).

How it fits together:
- Today the route calls `invoices.build_draft(entity, form, lang, today=...)`, then `invoices.issue(draft, actor)`. `issue()` calls `validate_for_issue(draft)` and then `_write_issued(draft, actor)`, which holds the write lock (`db.immediate()`). If an exception is raised inside `with db.immediate() as cur:`, everything rolls back (`db._transaction` calls `_rollback` on `BaseException`).
- `build_draft` gets a new optional argument `stay=`. When `stay` is `None`, **everything behaves exactly as today** (old tests and corrections keep working). When `stay` is given, the new rules apply.
- The DB column `invoice_item.kind` only allows `'accommodation'`, `'stay_fee'` and `'other'` (CHECK constraint in `App/app/db.py`). So the stay line is stored as `'accommodation'`, the stay fee as `'stay_fee'`, and every other extra as `'other'`. The exact extra kind (cleaning, parking …) lives only in the draft under the new key `"extra_kind"`, which is never written to the DB.
- `invoice.reservation_id`, `stay_from`, `stay_to`, `stay_label` and the index `idx_invoice_reservation` already exist. **No migration.**
- Stay fee (poplatek z pobytu) is a municipal fee, outside VAT: for VAT payers its rate is always 0 (owner, 2026-10-08).

Verbatim excerpts you must find first (open the file, search for each line). If one is missing: STOP (§8).

E1, `App/app/invoices.py` near the top:
```python
from . import db, invoice_pdf, payments, validation
```
E2, `App/app/invoices.py`:
```python
PAID_VIA_LABELS = {
```
E3, `App/app/invoices.py` inside `build_draft`:
```python
    vat_status = (entity["vat_status"] or "non_payer") if entity else "non_payer"
    items = _items_from_form(form, vat_status)
```
E4, `App/app/invoices.py` at the end of `build_draft`:
```python
        "total_haler": total_haler,
    }
```
E5, `App/app/invoices.py` at the end of `validate_for_issue`:
```python
    if draft["total_haler"] <= 0 or any(i.get("price_invalid") for i in draft["items"]):
        issues.append(validation.Issue("price_czk", "invoice.err.amount"))
    return issues
```
E6, `App/app/invoices.py` inside `_write_issued`:
```python
        entity = cur.execute(
            "SELECT * FROM legal_entity WHERE id = ?", (draft["legal_entity_id"],)
        ).fetchone()
        seq_year, seq_no, number, vs = allocate_number(cur, entity, year)
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/invoices.py` | edit | steps 1–7 |
| `App/tests/test_invoice_stay_rules.py` | new | step 8 |

No other file may change.

## 4. Steps

Do them in order. After each step, save the file. Run the tests only where a step says so.

**Step 1: docstring.** Replace the first 5 lines of `App/app/invoices.py` (the module docstring) with:
```python
"""Invoice building, numbering and issuing (host tool).

A new invoice belongs to one stay: line 1 is the accommodation, built from the
stay; up to three extras come from a fixed list (``EXTRA_KINDS``). Amounts are
integers in haléře. An issued invoice is immutable; a correction is a new paper.
Drafts built without a stay (corrections, older tests) keep the free-form path.
"""
```

**Step 2: imports.** Find E1 and the line above it. Make sure `timedelta` is imported from datetime (it already is: `from datetime import date, timedelta`). Change nothing else in the imports.

**Step 3: constants.** Directly **above** E2 (`PAID_VIA_LABELS = {`), insert:
```python
# Invoices belong to one stay (docs/plans/stay-only-invoices.md).
STAY_PAST_DAYS = 400
STAY_FUTURE_DAYS = 365
STAY_MAX_INVOICES = 3
EXTRA_MAX_QUANTITY = 99
OTHER_MAX_CHARS = 60
# All extras together may equal the accommodation line; "Other" alone 30 % of it.
EXTRAS_MAX_SHARE = Decimal("1.00")
OTHER_MAX_SHARE = Decimal("0.30")
EXTRA_KINDS = (
    "cleaning", "stay_fee", "breakfast", "parking", "pet", "extra_bed", "late_checkout", "other",
)
EXTRA_LABELS = {
    "cs": {
        "cleaning": "Úklid", "stay_fee": "Poplatek z pobytu", "breakfast": "Snídaně",
        "parking": "Parkování", "pet": "Domácí zvíře", "extra_bed": "Přistýlka",
        "late_checkout": "Pozdní odjezd",
    },
    "en": {
        "cleaning": "Cleaning", "stay_fee": "Local stay fee", "breakfast": "Breakfast",
        "parking": "Parking", "pet": "Pet", "extra_bed": "Extra bed",
        "late_checkout": "Late check-out",
    },
}
STAY_LINE_PREFIX = {"cs": "Ubytování", "en": "Accommodation"}
```

**Step 4: stay helpers.** Directly **above** the line `def build_draft(`, insert:
```python
def stay_nights(reservation) -> int:
    """Nights between check-in and check-out; 0 when a date is unreadable."""
    try:
        start = date.fromisoformat(str(reservation["date_from"])[:10])
        end = date.fromisoformat(str(reservation["date_to"])[:10])
    except ValueError:
        return 0
    return (end - start).days


def stay_problem(reservation, today: date) -> Optional[str]:
    """None when an invoice may be issued for this stay, else an i18n key."""
    if reservation is None:
        return "invoice.err.no_stay"
    if (reservation["status"] or "") == "cancelled":
        return "invoice.err.stay_cancelled"
    if stay_nights(reservation) < 1:
        return "invoice.err.stay_dates"
    if str(reservation["date_to"])[:10] < (today - timedelta(days=STAY_PAST_DAYS)).isoformat():
        return "invoice.err.stay_too_old"
    if str(reservation["date_from"])[:10] > (today + timedelta(days=STAY_FUTURE_DAYS)).isoformat():
        return "invoice.err.stay_too_far"
    return None


def _nights_text(nights: int, lang: str) -> str:
    if lang == "cs":
        word = "noc" if nights == 1 else ("noci" if 2 <= nights <= 4 else "nocí")
    else:
        word = "night" if nights == 1 else "nights"
    return f"{nights} {word}"


def stay_label(property_name: str, reservation, lang: str) -> str:
    """'Chata, 12.10.2026 – 15.10.2026 (3 noci)': the PDF prints it under the header."""
    dates = validation.fmt_date_range(reservation["date_from"], reservation["date_to"])
    return f"{property_name}, {dates} ({_nights_text(stay_nights(reservation), lang)})"


def _price_invalid(raw_price: str, price: Decimal) -> bool:
    return (not raw_price) or _parse_decimal(raw_price) is None or price <= 0


def _stay_item(form, vat_status: str, label: str, lang: str) -> Dict[str, Any]:
    """Line 1. Only the price (and, for payers, the rate) comes from the form."""
    raw_price = _form_str(form, "stay_price")
    price = _to_decimal(raw_price)
    if vat_status == "payer":
        rate = _to_rate(_form_str(form, "stay_vat_rate") or "12")
        base, vat, gross = vat_parts(1, price, rate)
    else:
        rate = None
        base = vat = None
        gross = int((price * 100).to_integral_value(rounding=ROUND_HALF_UP))
    return {
        "kind": "accommodation",
        "extra_kind": "stay",
        "description": f"{STAY_LINE_PREFIX[lang]} – {label}"[:150],
        "quantity": 1,
        "unit": "pobyt" if lang == "cs" else "stay",
        "vat_rate": rate,
        "base_haler": base,
        "vat_haler": vat,
        "gross_haler": gross,
        "price_invalid": _price_invalid(raw_price, price),
    }


def _extras_from_form(form, vat_status: str, lang: str) -> List[Dict[str, Any]]:
    """Lines 2-4. The wording comes from EXTRA_LABELS; only "other" takes typed text."""
    kinds = _getlist(form, "item_kind")
    descs = _getlist(form, "item_description")
    qtys = _getlist(form, "item_quantity")
    units = _getlist(form, "item_unit")
    prices = _getlist(form, "item_unit_price")
    rates = _getlist(form, "item_vat_rate")
    count = max(len(kinds), len(descs), len(qtys), len(units), len(prices), len(rates))
    items: List[Dict[str, Any]] = []
    for i in range(count):
        kind = _at(kinds, i).strip()
        text = _at(descs, i).strip()
        raw_price = _at(prices, i).strip()
        if not (kind or text or raw_price):
            continue  # an untouched blank row
        if not kind:
            kind = "other"  # no kind picked: typed text is an "Other" line
        quantity = _to_int(_at(qtys, i, "1"), default=1)
        price = _to_decimal(raw_price)
        if kind == "other":
            description = text[:OTHER_MAX_CHARS]
        else:
            description = EXTRA_LABELS[lang].get(kind, "")
        if vat_status == "payer":
            # The local stay fee is a municipal fee outside VAT (owner, 2026-10-08).
            rate = 0 if kind == "stay_fee" else _to_rate(_at(rates, i))
            base, vat, gross = vat_parts(quantity, price, rate)
        else:
            rate = None
            base = vat = None
            gross = int((price * quantity * 100).to_integral_value(rounding=ROUND_HALF_UP))
        items.append(
            {
                "kind": "stay_fee" if kind == "stay_fee" else "other",
                "extra_kind": kind,
                "description": description,
                "quantity": quantity,
                "unit": _at(units, i).strip()[:20],
                "vat_rate": rate,
                "base_haler": base,
                "vat_haler": vat,
                "gross_haler": gross,
                "price_invalid": _price_invalid(raw_price, price),
            }
        )
    return items


```

**Step 5: build_draft uses the stay.**

5a. Change the signature line
```python
def build_draft(entity, form, lang: str, *, today: date) -> Dict[str, Any]:
```
to
```python
def build_draft(entity, form, lang: str, *, today: date, stay: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
```
5b. Replace E3 (the 2 lines) with:
```python
    vat_status = (entity["vat_status"] or "non_payer") if entity else "non_payer"
    doc_lang = "cs" if _form_str(form, "lang") == "cs" else "en"
    label = ""
    if stay is not None:
        # stay = {"reservation": row, "property_name": str}; the route checked ownership.
        label = stay_label(stay["property_name"], stay["reservation"], doc_lang)
        items = [_stay_item(form, vat_status, label, doc_lang)]
        items += _extras_from_form(form, vat_status, doc_lang)
    else:
        items = _items_from_form(form, vat_status)
```
5c. Find E4 at the end of `build_draft`:
```python
        "total_haler": total_haler,
    }
```
It belongs to `return {`. Change `return {` (the one in `build_draft`, directly after the `paid_via` lines) to `draft = {`, and right after the closing `}` of E4 add:
```python
    if stay is not None:
        reservation = stay["reservation"]
        stay_to = str(reservation["date_to"])[:10]
        draft.update(
            {
                "reservation_id": reservation["id"],
                "apartment_id": reservation["apartment_id"],
                "stay_from": str(reservation["date_from"])[:10],
                "stay_to": stay_to,
                "stay_label": label,
                # Tax point: the check-out day, never in the future.
                "duzp": draft["duzp"] or min(stay_to, today.isoformat()),
            }
        )
    return draft
```
Do not change the line `"lang": "cs" if _form_str(form, "lang") == "cs" else "en",` inside the dict.

**Step 6: validation.** Directly **above** `def validate_for_issue(`, insert:
```python
def _stay_issues(draft: Dict[str, Any]) -> List[validation.Issue]:
    items = draft["items"]
    stay_gross = items[0]["gross_haler"] if items and items[0].get("extra_kind") == "stay" else 0
    extras = [i for i in items if i.get("extra_kind") not in (None, "stay")]
    issues: List[validation.Issue] = []
    if any(i["extra_kind"] not in EXTRA_KINDS or not i["description"] for i in extras):
        issues.append(validation.Issue("items", "invoice.err.extra_kind"))
    if sum(1 for i in extras if i["extra_kind"] == "other") > 1:
        issues.append(validation.Issue("items", "invoice.err.one_other"))
    if any(not 1 <= i["quantity"] <= EXTRA_MAX_QUANTITY for i in extras):
        issues.append(validation.Issue("items", "invoice.err.extra_quantity"))
    extras_gross = sum(i["gross_haler"] for i in extras)
    other_gross = sum(i["gross_haler"] for i in extras if i["extra_kind"] == "other")
    if extras_gross > stay_gross * EXTRAS_MAX_SHARE:
        issues.append(validation.Issue("items", "invoice.err.extras_cap"))
    if other_gross > stay_gross * OTHER_MAX_SHARE:
        issues.append(validation.Issue("items", "invoice.err.other_cap"))
    return issues


```
Then replace E5 with:
```python
    if draft["total_haler"] <= 0 or any(i.get("price_invalid") for i in draft["items"]):
        issues.append(validation.Issue("price_czk", "invoice.err.amount"))
    if draft["kind"] == "invoice" and draft.get("reservation_id"):
        issues.extend(_stay_issues(draft))
    return issues
```
(Corrections have kind `storno`/`corrective`, so they skip these checks. That is on purpose: their lines are negative copies.)

**Step 7: one active invoice per stay.** Directly **above** `def _write_issued(`, insert:
```python
class StayLimit(ValueError):
    """The stay already has its invoice, or its last allowed one."""

    def __init__(self, key: str, invoice_id: Optional[int] = None):
        super().__init__(key)
        self.key = key
        self.invoice_id = invoice_id


_ACTIVE_FOR_STAY_SQL = (
    "SELECT i.id, i.number FROM invoice i WHERE i.reservation_id = ? AND i.kind = 'invoice' "
    "AND NOT EXISTS (SELECT 1 FROM invoice c WHERE c.corrects_invoice_id = i.id) "
    "ORDER BY i.id DESC LIMIT 1"
)


def active_invoice_for_stay(reservation_id: int):
    """The stay's invoice that has no storno/ODD yet, or None."""
    return db.query_one(_ACTIVE_FOR_STAY_SQL, (reservation_id,))


def _check_stay_limit(cur, reservation_id: int) -> None:
    """Runs inside the write lock, so a double click cannot slip a second one in."""
    active = cur.execute(_ACTIVE_FOR_STAY_SQL, (reservation_id,)).fetchone()
    if active:
        raise StayLimit("invoice.err.stay_has_invoice", int(active["id"]))
    total = cur.execute(
        "SELECT COUNT(*) FROM invoice WHERE reservation_id = ? AND kind = 'invoice'",
        (reservation_id,),
    ).fetchone()[0]
    if total >= STAY_MAX_INVOICES:
        raise StayLimit("invoice.err.stay_limit")


```
Then in `_write_issued`, replace E6 with:
```python
        entity = cur.execute(
            "SELECT * FROM legal_entity WHERE id = ?", (draft["legal_entity_id"],)
        ).fetchone()
        if draft["kind"] == "invoice" and draft.get("reservation_id"):
            _check_stay_limit(cur, draft["reservation_id"])
        seq_year, seq_no, number, vs = allocate_number(cur, entity, year)
```
Run: `cd App && .venv/bin/python -m pytest tests -q -k invoice` → all pass. If something fails, you changed old behaviour: re-check step 5 (the `stay is None` path must be untouched).

**Step 8: tests.** Create `App/tests/test_invoice_stay_rules.py` with exactly:
```python
"""Invoices belong to one stay: fixed stay line, capped extras, one active per stay."""
from __future__ import annotations

from datetime import date

import pytest

from app import db, invoices

PREFIX = "t0019-"
TODAY = date(2026, 10, 8)
_counter = 0


@pytest.fixture(autouse=True)
def _clean():
    db.init_db()
    yield
    db.execute(
        "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '1') "
        "ON CONFLICT(key) DO UPDATE SET value = '1'"
    )
    ids = [r["id"] for r in db.query("SELECT id FROM legal_entity WHERE name LIKE ?", (PREFIX + "%",))]
    for entity_id in ids:
        db.execute(
            "DELETE FROM invoice_item WHERE invoice_id IN (SELECT id FROM invoice WHERE legal_entity_id = ?)",
            (entity_id,),
        )
        db.execute("DELETE FROM invoice WHERE legal_entity_id = ?", (entity_id,))
        db.execute("DELETE FROM invoice_sequence WHERE legal_entity_id = ?", (entity_id,))
    db.execute("DELETE FROM reservation WHERE uid LIKE ?", (PREFIX + "%",))
    db.execute("DELETE FROM apartment WHERE permalink_token LIKE ?", (PREFIX + "%",))
    for entity_id in ids:
        db.execute("DELETE FROM legal_entity WHERE id = ?", (entity_id,))
    db.execute(
        "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '') "
        "ON CONFLICT(key) DO UPDATE SET value = ''"
    )


def _setup(vat="non_payer", date_from="2026-10-01", date_to="2026-10-04", status="active"):
    global _counter
    _counter += 1
    now = db.utcnow()
    entity_id = db.insert(
        "legal_entity",
        {"name": f"{PREFIX}{_counter}", "seat": "Praha", "ico": "04656679", "registry_entry": "ŽR",
         "dic": "CZ04656679" if vat == "payer" else None,
         "vat_status": vat, "invoice_due_days": 14, "created_at": now},
    )
    apartment_id = db.insert(
        "apartment",
        {"legal_entity_id": entity_id, "internal_name": "Chata", "permalink_token": f"{PREFIX}tok-{_counter}",
         "automation_mode": "manual", "default_purpose": "10", "active": 1, "created_at": now},
    )
    reservation_id = db.insert(
        "reservation",
        {"apartment_id": apartment_id, "source": "manual", "uid": f"{PREFIX}stay-{_counter}",
         "date_from": date_from, "date_to": date_to, "status": status,
         "created_at": now, "updated_at": now},
    )
    entity = db.query_one("SELECT * FROM legal_entity WHERE id = ?", (entity_id,))
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))
    return entity, reservation


def _form(**over):
    data = {
        "lang": "cs", "buyer_name": "Buyer", "already_paid": "1",
        "seller_name": "S", "seller_seat": "Praha", "seller_registry": "ŽR",
        "stay_price": "3000",
        "item_kind": [], "item_description": [], "item_quantity": [],
        "item_unit": [], "item_unit_price": [], "item_vat_rate": [],
    }
    data.update(over)
    return data


def _draft(entity, reservation, **over):
    draft = invoices.build_draft(
        entity, _form(**over), "cs", today=TODAY,
        stay={"reservation": reservation, "property_name": "Chata"},
    )
    draft["legal_entity_id"] = entity["id"]
    return draft


def _keys(draft):
    return [issue.message for issue in invoices.validate_for_issue(draft)]


def test_stay_line_is_built_from_the_stay_and_ignores_typed_text():
    entity, stay = _setup()
    draft = _draft(entity, stay, item_description=["Hacked"], item_quantity=["50"])
    line = draft["items"][0]
    assert line["kind"] == "accommodation"
    assert line["description"] == "Ubytování – Chata, 01.10.2026 – 04.10.2026 (3 noci)"
    assert line["quantity"] == 1
    assert line["gross_haler"] == 300000
    assert draft["reservation_id"] == stay["id"]
    assert draft["stay_label"] == "Chata, 01.10.2026 – 04.10.2026 (3 noci)"
    assert draft["duzp"] == "2026-10-04"


def test_english_label_and_future_stay_tax_point_is_today():
    entity, stay = _setup(date_from="2026-11-01", date_to="2026-11-02")
    draft = _draft(entity, stay, lang="en")
    assert draft["items"][0]["description"].startswith("Accommodation – Chata")
    assert draft["items"][0]["description"].endswith("(1 night)")
    assert draft["duzp"] == TODAY.isoformat()


def test_missing_stay_price_is_an_error():
    entity, stay = _setup()
    assert "invoice.err.amount" in _keys(_draft(entity, stay, stay_price=""))


def test_extras_use_fixed_wording():
    entity, stay = _setup()
    draft = _draft(entity, stay, item_kind=["cleaning"], item_description=["anything"],
                   item_quantity=["1"], item_unit_price=["500"])
    assert draft["items"][1]["description"] == "Úklid"
    assert draft["items"][1]["kind"] == "other"
    assert _keys(draft) == []


def test_unknown_kind_and_two_other_lines_are_refused():
    entity, stay = _setup()
    assert "invoice.err.extra_kind" in _keys(
        _draft(entity, stay, item_kind=["consulting"], item_unit_price=["100"]))
    assert "invoice.err.one_other" in _keys(
        _draft(entity, stay, item_kind=["other", "other"], item_description=["A", "B"],
               item_quantity=["1", "1"], item_unit_price=["100", "100"]))


def test_extras_caps():
    entity, stay = _setup()
    assert "invoice.err.other_cap" in _keys(
        _draft(entity, stay, item_kind=["other"], item_description=["Taxi"], item_unit_price=["901"]))
    assert "invoice.err.other_cap" not in _keys(
        _draft(entity, stay, item_kind=["other"], item_description=["Taxi"], item_unit_price=["900"]))
    assert "invoice.err.extras_cap" in _keys(
        _draft(entity, stay, item_kind=["cleaning", "parking"], item_quantity=["1", "1"],
               item_unit_price=["2000", "1001"]))


def test_extra_quantity_range():
    entity, stay = _setup()
    assert "invoice.err.extra_quantity" in _keys(
        _draft(entity, stay, item_kind=["parking"], item_quantity=["100"], item_unit_price=["1"]))


def test_payer_stay_fee_is_always_zero_vat():
    entity, stay = _setup(vat="payer")
    draft = _draft(entity, stay, item_kind=["stay_fee"], item_quantity=["2"],
                   item_unit_price=["50"], item_vat_rate=["21"])
    fee = draft["items"][1]
    assert fee["kind"] == "stay_fee"
    assert fee["vat_rate"] == 0
    assert draft["items"][0]["vat_rate"] == 12


def test_stay_problem_window_and_status():
    _, stay = _setup()
    assert invoices.stay_problem(stay, TODAY) is None
    assert invoices.stay_problem(None, TODAY) == "invoice.err.no_stay"
    _, cancelled = _setup(status="cancelled")
    assert invoices.stay_problem(cancelled, TODAY) == "invoice.err.stay_cancelled"
    _, old = _setup(date_from="2025-08-01", date_to="2025-08-31")
    assert invoices.stay_problem(old, TODAY) == "invoice.err.stay_too_old"
    _, far = _setup(date_from="2027-12-01", date_to="2027-12-03")
    assert invoices.stay_problem(far, TODAY) == "invoice.err.stay_too_far"
    _, zero = _setup(date_from="2026-10-01", date_to="2026-10-01")
    assert invoices.stay_problem(zero, TODAY) == "invoice.err.stay_dates"


def test_one_active_invoice_then_storno_then_cap_of_three():
    entity, stay = _setup()
    first = invoices.issue(_draft(entity, stay), actor_user_id=None)
    assert invoices.active_invoice_for_stay(stay["id"])["id"] == first
    with pytest.raises(invoices.StayLimit) as caught:
        invoices.issue(_draft(entity, stay), actor_user_id=None)
    assert caught.value.key == "invoice.err.stay_has_invoice"
    assert caught.value.invoice_id == first
    invoices.cancel(first, "Chyba", None, None, today=TODAY)
    second = invoices.issue(_draft(entity, stay), actor_user_id=None)
    invoices.cancel(second, "Chyba", None, None, today=TODAY)
    third = invoices.issue(_draft(entity, stay), actor_user_id=None)
    invoices.cancel(third, "Chyba", None, None, today=TODAY)
    with pytest.raises(invoices.StayLimit) as caught:
        invoices.issue(_draft(entity, stay), actor_user_id=None)
    assert caught.value.key == "invoice.err.stay_limit"
    count = db.query_one(
        "SELECT COUNT(*) AS n FROM invoice WHERE reservation_id = ? AND kind = 'invoice'", (stay["id"],))
    assert count["n"] == 3


def test_a_refused_issue_uses_no_number():
    entity, stay = _setup()
    invoices.issue(_draft(entity, stay), actor_user_id=None)
    with pytest.raises(invoices.StayLimit):
        invoices.issue(_draft(entity, stay), actor_user_id=None)
    seq = db.query_one(
        "SELECT last_no FROM invoice_sequence WHERE legal_entity_id = ?", (entity["id"],))
    assert seq["last_no"] == 1


def test_drafts_without_a_stay_keep_the_old_path():
    entity, _ = _setup()
    form = _form(item_description=["Consulting"], item_quantity=["2"], item_unit=["h"],
                 item_unit_price=["1000"], item_vat_rate=["21"])
    draft = invoices.build_draft(entity, form, "cs", today=TODAY)
    assert draft["items"][0]["description"] == "Consulting"
    assert draft.get("reservation_id") is None
```
If `test_stay_line_is_built_from_the_stay_and_ignores_typed_text` fails only on the date format (for example `1.10.2026` instead of `01.10.2026`), change the **test** to what `validation.fmt_date_range` actually returns, and say so in the report. Don't change `validation.py`.

Run: `cd App && .venv/bin/python -m pytest tests/test_invoice_stay_rules.py -q` → all pass.

## 5. Do not touch

Everything except the two files in §3. In particular: `App/app/db.py` (no schema change, no migration), `App/app/routes/`, templates, `host_i18n.py` (the new i18n keys are added in 0020), `invoice_pdf.py`, `stay_fee*`, `retention.py`. Hard rules: SQL only through `db.py` helpers or the `cur` that `db.immediate()` gives you; no new dependency.

## 6. Commands

From `App/`:
1. `.venv/bin/python -m pytest tests/test_invoice_stay_rules.py -q` → `12 passed`.
2. `.venv/bin/python -m pytest tests -q` → everything passes; the summary line shows no `failed`.

From the repo root: `python3 scripts/context_lint.py` → `context lint: OK`.

## 7. Acceptance

- [ ] `git diff --stat` shows only the two files in §3.
- [ ] The 12 new tests pass.
- [ ] The full suite passes (all old invoice tests unchanged and green).
- [ ] `grep -n "stay is None\|stay is not None" App/app/invoices.py` shows the two branches in `build_draft`.

## 8. Stop and ask

Stop, and write the report, if:
- an excerpt E1–E6 is not found exactly;
- a test fails twice after you re-read the step;
- an **old** test fails (the `stay=None` path must not change);
- a new dependency seems needed;
- a file outside §3 needs a change;
- a step is unclear;
- you need push to main, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/0019-report.md` (1,500 tokens at most) and set `Status: review` in this file. The report has:
1. `git diff --stat`.
2. Each command from §6 with the last 5 lines of its output.
3. §7 ticked.
4. Deviations (for example a test date format you adjusted).
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

`App/app/invoices.py`: `_write_issued` (limit inside the lock), `build_draft` (old path unchanged), `_stay_issues` (caps).

## Owner steps

1. Merge the PR with `scripts/merge-pr-on-green.sh` when CI is green. Nothing to deploy yet: no page changes until 0020.
