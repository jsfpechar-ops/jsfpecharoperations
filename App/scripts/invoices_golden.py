"""Write go/internal/web/invoices/testdata/draft_golden.json from the real Python.

Brief 1421. Run from App/:

    .venv/bin/python scripts/invoices_golden.py          write the file
    .venv/bin/python scripts/invoices_golden.py --check  exit 1 when stale

Every case runs App/app/invoices.py build_draft, validate_for_issue and
stay_problem on a made-up operator, stay and form (no database, no network).
go/internal/web/invoices/draft_test.go builds the same drafts in Go and
compares every field, so the Go amounts, descriptions, caps and issue keys are
the Python ones. All names and addresses are made up (rule 3).
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "invoices" / "testdata" / "draft_golden.json"
sys.path.insert(0, str(APP))

from app import invoices  # noqa: E402


class Form:
    """The slice of Starlette's FormData that invoices.py reads."""

    def __init__(self, pairs):
        self._pairs = [(str(k), str(v)) for k, v in pairs]
        self._dict = dict(self._pairs)  # the last value wins, as in Starlette

    def get(self, key, default=None):
        return self._dict.get(key, default)

    def getlist(self, key):
        return [v for k, v in self._pairs if k == key]

    def __contains__(self, key):
        return key in self._dict

    def __iter__(self):
        return iter(self._dict)


def entity(**over):
    row = {
        "id": 7, "name": "Test Provoz s.r.o.", "seat": "Ulice 1, 110 00 Praha", "ico": "12345679",
        "dic": "CZ12345679", "contact_email": "host@example.test", "contact_phone": "+420 700 000 000",
        "bank_account": "123-2000000000/0300", "iban": "CZ0603000000000123456789", "bic": "CEKOCZPP",
        "vat_status": "non_payer", "registry_entry": "C 12345 vedená u Městského soudu v Praze",
        "invoice_prefix": "", "invoice_next_number": None, "invoice_next_number_year": None,
        "invoice_due_days": 14,
    }
    row.update(over)
    return row


def stay(**over):
    reservation = {
        "id": 41, "apartment_id": 5, "date_from": "2026-11-10", "date_to": "2026-11-13",
        "status": "active", "source": "ical", "guest_email": "guest@example.test",
    }
    reservation.update(over.pop("reservation", {}))
    out = {"reservation": reservation, "property_name": "Chata U Lesa", "entity_id": 7}
    out.update(over)
    return out


TODAY = date(2026, 11, 13)
BASE = [("stay_price", "1500"), ("buyer_name", "Jana Testová"), ("lang", "cs"), ("already_paid", "1"),
        ("paid_via", "cash")]


def case(name, pairs=None, ent=None, st=None, today=TODAY):
    return {"name": name, "entity": ent or entity(), "stay": st or stay(), "today": today.isoformat(),
            "form": [list(p) for p in (BASE if pairs is None else pairs)]}


CASES = [
    case("non_payer_simple"),
    case("english_document", [("stay_price", "99,5"), ("buyer_name", "John Doe"), ("lang", "en")]),
    case("czech_thousands", [("stay_price", "1.234,50"), ("buyer_name", "A B"), ("lang", "cs")]),
    case("spaces_and_nbsp", [("stay_price", "1 234 567"), ("buyer_name", "A"), ("lang", "cs")]),
    case("garbage_price", [("stay_price", "abc"), ("buyer_name", "A"), ("lang", "cs")]),
    case("empty_price", [("stay_price", ""), ("buyer_name", "A"), ("lang", "cs")]),
    case("negative_price", [("stay_price", "-5"), ("buyer_name", "A"), ("lang", "cs")]),
    case("too_big_price", [("stay_price", "10000001"), ("buyer_name", "A"), ("lang", "cs")]),
    case("exponent_price", [("stay_price", "1e3"), ("buyer_name", "A"), ("lang", "cs")]),
    case("rounding_half_up", [("stay_price", "0.005"), ("buyer_name", "A"), ("lang", "cs")]),
    case("payer_default_rate", [("stay_price", "1000"), ("buyer_name", "A"), ("lang", "cs")],
         ent=entity(vat_status="payer")),
    case("payer_21", [("stay_price", "1234.57"), ("stay_vat_rate", "21"), ("buyer_name", "A"), ("lang", "cs")],
         ent=entity(vat_status="payer")),
    case("payer_bad_rate", [("stay_price", "100"), ("stay_vat_rate", "15"), ("buyer_name", "A"), ("lang", "cs")],
         ent=entity(vat_status="payer")),
    case("payer_no_dic", [("stay_price", "100"), ("buyer_name", "A"), ("lang", "cs")],
         ent=entity(vat_status="payer", dic="")),
    case("extras_all_kinds", BASE + [
        ("item_kind", "cleaning"), ("item_description", "ignored"), ("item_quantity", "1"), ("item_unit", "ks"),
        ("item_unit_price", "100"), ("item_vat_rate", "21"),
        ("item_kind", "stay_fee"), ("item_description", ""), ("item_quantity", "3"), ("item_unit", ""),
        ("item_unit_price", "50"), ("item_vat_rate", "21"),
        ("item_kind", "other"), ("item_description", "Pozdní příjezd"), ("item_quantity", "1"), ("item_unit", "x"),
        ("item_unit_price", "100"), ("item_vat_rate", "12")]),
    case("payer_extras", BASE + [
        ("item_kind", "breakfast"), ("item_description", ""), ("item_quantity", "2"), ("item_unit", ""),
        ("item_unit_price", "120"), ("item_vat_rate", "12"),
        ("item_kind", "stay_fee"), ("item_description", ""), ("item_quantity", "3"), ("item_unit", ""),
        ("item_unit_price", "50"), ("item_vat_rate", "21")], ent=entity(vat_status="payer")),
    case("forged_stay_kind", BASE + [
        ("item_kind", "stay"), ("item_description", "x"), ("item_quantity", "1"), ("item_unit", ""),
        ("item_unit_price", "10"), ("item_vat_rate", "21")]),
    case("unknown_kind", BASE + [
        ("item_kind", "spa"), ("item_description", "x"), ("item_quantity", "1"), ("item_unit", ""),
        ("item_unit_price", "10"), ("item_vat_rate", "21")]),
    case("two_other_lines", BASE + [
        ("item_kind", "other"), ("item_description", "A"), ("item_quantity", "1"), ("item_unit", ""),
        ("item_unit_price", "10"), ("item_vat_rate", "21"),
        ("item_kind", "other"), ("item_description", "B"), ("item_quantity", "1"), ("item_unit", ""),
        ("item_unit_price", "10"), ("item_vat_rate", "21")]),
    case("other_over_30_percent", BASE + [
        ("item_kind", "other"), ("item_description", "Big"), ("item_quantity", "1"), ("item_unit", ""),
        ("item_unit_price", "451"), ("item_vat_rate", "21")]),
    case("other_exactly_30_percent", BASE + [
        ("item_kind", "other"), ("item_description", "Edge"), ("item_quantity", "1"), ("item_unit", ""),
        ("item_unit_price", "450"), ("item_vat_rate", "21")]),
    case("extras_over_stay", BASE + [
        ("item_kind", "parking"), ("item_description", ""), ("item_quantity", "2"), ("item_unit", ""),
        ("item_unit_price", "800"), ("item_vat_rate", "21")]),
    case("extras_exactly_stay", BASE + [
        ("item_kind", "parking"), ("item_description", ""), ("item_quantity", "3"), ("item_unit", ""),
        ("item_unit_price", "500"), ("item_vat_rate", "21")]),
    case("extra_quantity_zero_and_100", BASE + [
        ("item_kind", "pet"), ("item_description", ""), ("item_quantity", "0"), ("item_unit", ""),
        ("item_unit_price", "10"), ("item_vat_rate", "21"),
        ("item_kind", "pet"), ("item_description", ""), ("item_quantity", "100"), ("item_unit", ""),
        ("item_unit_price", "1"), ("item_vat_rate", "21")]),
    case("extra_blank_quantity_and_garbage_price", BASE + [
        ("item_kind", "pet"), ("item_description", ""), ("item_quantity", ""), ("item_unit", ""),
        ("item_unit_price", "zz"), ("item_vat_rate", "")]),
    case("typed_text_without_kind", BASE + [
        ("item_kind", ""), ("item_description", "Late fee"), ("item_quantity", "1"), ("item_unit", ""),
        ("item_unit_price", "5"), ("item_vat_rate", "21")]),
    case("blank_row_skipped", BASE + [
        ("item_kind", ""), ("item_description", ""), ("item_quantity", "1"), ("item_unit", ""),
        ("item_unit_price", ""), ("item_vat_rate", "21")]),
    case("too_many_items", BASE + sum(([
        ("item_kind", "cleaning"), ("item_description", ""), ("item_quantity", "1"), ("item_unit", ""),
        ("item_unit_price", "1"), ("item_vat_rate", "21")] for _ in range(4)), [])),
    case("other_text_cut_to_60", BASE + [
        ("item_kind", "other"), ("item_description", "x" * 80), ("item_quantity", "1"), ("item_unit", "u" * 30),
        ("item_unit_price", "1"), ("item_vat_rate", "21")]),
    case("missing_buyer", [("stay_price", "100"), ("lang", "cs")]),
    case("payment_requested_default_due", [("stay_price", "100"), ("buyer_name", "A"), ("already_paid", "0"),
                                            ("lang", "cs")]),
    case("payment_requested_own_due_and_duzp", [("stay_price", "100"), ("buyer_name", "A"), ("already_paid", "0"),
                                                ("due_date", "2026-12-01"), ("duzp", "2026-11-11"), ("lang", "cs")]),
    case("due_days_zero", [("stay_price", "100"), ("buyer_name", "A"), ("already_paid", "0")],
         ent=entity(invoice_due_days=0)),
    case("checkbox_on_paid", [("stay_price", "100"), ("buyer_name", "A"), ("already_paid", "on"),
                              ("paid_via", "airbnb")]),
    case("paid_via_custom", [("stay_price", "100"), ("buyer_name", "A"), ("already_paid", "1"),
                             ("paid_via", "custom"), ("paid_via_custom", "  Karta v recepci  ")]),
    case("paid_via_ignored_when_unpaid", [("stay_price", "100"), ("buyer_name", "A"), ("already_paid", "0"),
                                          ("paid_via", "cash")]),
    case("buyer_company", [("stay_price", "100"), ("buyer_name", "Firma s.r.o."), ("buyer_street", "Ulice 2"),
                           ("buyer_city", "Brno"), ("buyer_zip", "602 00"), ("buyer_country", "DEU"),
                           ("buyer_ico", "27082440"), ("buyer_dic", "CZ27082440"), ("buyer_email", "a@example.test"),
                           ("note", "n" * 400)]),
    case("future_checkout_duzp_today", [("stay_price", "100"), ("buyer_name", "A")],
         st=stay(reservation={"date_from": "2026-11-12", "date_to": "2026-11-20"})),
    case("seller_fields_from_form", BASE + [("seller_name", "Forged Name"), ("seller_seat", ""), ("seller_ico", "999"),
                                            ("seller_registry", "R 1"), ("seller_email", "")]),
    case("seller_valid_bank_account", BASE + [("seller_bank_account", "19-2000145399/0800")]),
    case("seller_iban_account", BASE + [("seller_bank_account", "CZ65 0800 0000 1920 0014 5399")]),
    case("seller_bad_bank_account", BASE + [("seller_bank_account", "19-2000145398/0800")]),
    case("seller_blank_bank_account", BASE + [("seller_bank_account", "")]),
    case("entity_without_registry", BASE, ent=entity(registry_entry=None)),
    case("duplicate_form_keys_last_wins", [("stay_price", "1"), ("stay_price", "2000"), ("buyer_name", "A"),
                                           ("buyer_name", "B")]),
    case("nights_one_cs", BASE, st=stay(reservation={"date_from": "2026-11-12", "date_to": "2026-11-13"})),
    case("nights_five_en", [("stay_price", "1"), ("buyer_name", "A"), ("lang", "en")],
         st=stay(reservation={"date_from": "2026-11-01", "date_to": "2026-11-06"})),
]

PROBLEMS = [
    ["ok", {"date_from": "2026-11-10", "date_to": "2026-11-13", "status": "active", "source": "ical"}],
    ["demo", {"date_from": "2026-11-10", "date_to": "2026-11-13", "status": "active", "source": "demo"}],
    ["cancelled", {"date_from": "2026-11-10", "date_to": "2026-11-13", "status": "cancelled", "source": "ical"}],
    ["zero_nights", {"date_from": "2026-11-10", "date_to": "2026-11-10", "status": "active", "source": "ical"}],
    ["bad_dates", {"date_from": "x", "date_to": "2026-11-10", "status": "active", "source": "ical"}],
    ["too_old", {"date_from": "2025-09-01", "date_to": "2025-09-03", "status": "active", "source": "ical"}],
    ["old_edge_ok", {"date_from": "2025-10-04", "date_to": "2025-10-10", "status": "active", "source": "ical"}],
    ["too_far", {"date_from": "2027-12-01", "date_to": "2027-12-03", "status": "active", "source": "ical"}],
    ["far_edge_ok", {"date_from": "2027-11-13", "date_to": "2027-11-15", "status": "active", "source": "ical"}],
    ["no_source", {"date_from": "2026-11-10", "date_to": "2026-11-13", "status": "active", "source": None}],
]


def summary(d):
    out = {k: d[k] for k in (
        "kind", "lang", "vat_status", "issue_date", "duzp", "due_date", "paid_on", "paid_via", "note",
        "total_haler", "total_base_haler", "total_vat_haler", "stay_label", "stay_from", "stay_to",
        "reservation_id", "apartment_id")}
    out["seller"] = d["seller"]
    out["buyer"] = d["buyer"]
    out["items"] = [
        {k: item.get(k) for k in ("kind", "extra_kind", "description", "quantity", "unit", "vat_rate",
                                  "base_haler", "vat_haler", "gross_haler", "price_invalid")}
        for item in d["items"]
    ]
    return out


def build() -> dict:
    cases = []
    for c in CASES:
        form = Form(c["form"])
        today = date.fromisoformat(c["today"])
        draft = invoices.build_draft(c["entity"], form, "cs", today=today, stay=c["stay"])
        draft.update({"legal_entity_id": c["entity"]["id"], "owner_user_id": 1})
        issues = invoices.validate_for_issue(draft)
        cases.append({**c, "draft": summary(draft), "issues": [[i.field, i.message] for i in issues],
                      "stay_problem": invoices.stay_problem(c["stay"]["reservation"], today)})
    problems = [
        {"name": n, "reservation": r, "today": TODAY.isoformat(),
         "key": invoices.stay_problem(r, TODAY)} for n, r in PROBLEMS
    ]
    return {"cases": cases, "stay_problems": problems}


def main(argv: list) -> int:
    text = json.dumps(build(), indent=1, ensure_ascii=False, sort_keys=True) + "\n"
    if "--check" in argv:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print("stale:", OUT)
            return 1
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
