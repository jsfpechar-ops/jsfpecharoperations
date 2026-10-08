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


def test_forged_stay_kind_on_an_extra_row_is_refused():
    """A posted item_kind=stay must not skip the extras caps (council 0019)."""
    entity, stay = _setup()
    keys = _keys(
        _draft(entity, stay, item_kind=["stay"], item_description=["Hack"],
               item_quantity=["1"], item_unit_price=["5000"]))
    assert "invoice.err.extra_kind" in keys


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
    assert "invoice.err.extra_quantity" in _keys(
        _draft(entity, stay, item_kind=["parking"], item_quantity=["0"], item_unit_price=["1"]))


def test_stay_plus_four_extras_hits_the_item_cap():
    entity, stay = _setup()
    keys = _keys(
        _draft(
            entity, stay,
            item_kind=["cleaning", "parking", "pet", "breakfast"],
            item_quantity=["1", "1", "1", "1"],
            item_unit_price=["1", "1", "1", "1"],
        )
    )
    assert "invoice.err.too_many_items" in keys


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
