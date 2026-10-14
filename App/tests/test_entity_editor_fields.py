"""Task 0075: one owner for each business and invoice-default field.

The business editor (``/entities``) saves identity fields and, in its Invoice
details section (``POST /entities/{id}/invoice``), invoice defaults. These tests pin
the stored result of both handlers for the same input, the explicit policy
differences between them, and the rendered contract (names, types,
requiredness, upload encoding and action targets). No network: ARES is mocked.
"""
from __future__ import annotations

import base64
import os
import re
import secrets
import socket
import threading
import time
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import uvicorn
from fastapi.testclient import TestClient

from app import ares, auth, db, host_i18n, invoices, payments
from app.main import app
from tests.conftest import login_as

USERNAME = "entity-fields-0075-host"
ICO = "04656679"
TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"

DETAIL_COLUMNS = (
    "bank_account", "iban", "bic", "registry_entry", "vat_status",
    "invoice_prefix", "invoice_next_number", "invoice_next_number_year",
    "invoice_due_days",
)
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 32


def _owner() -> int:
    return db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]


def _cleanup():
    owner = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    if not owner:
        return
    user_id = owner["id"]
    db.execute(
        "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '1') "
        "ON CONFLICT(key) DO UPDATE SET value = '1'"
    )
    db.execute("DELETE FROM invoice_item WHERE invoice_id IN (SELECT id FROM invoice WHERE "
               "legal_entity_id IN (SELECT id FROM legal_entity WHERE owner_user_id = ?))", (user_id,))
    db.execute("DELETE FROM invoice WHERE legal_entity_id IN "
               "(SELECT id FROM legal_entity WHERE owner_user_id = ?)", (user_id,))
    db.execute("DELETE FROM invoice_sequence WHERE legal_entity_id IN "
               "(SELECT id FROM legal_entity WHERE owner_user_id = ?)", (user_id,))
    db.execute(
        "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '') "
        "ON CONFLICT(key) DO UPDATE SET value = ''"
    )
    db.execute("DELETE FROM rate_limit_event WHERE scope = 'ares' AND key = ?", (str(user_id),))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    ares._CACHE.clear()
    auth.create_account(f"{USERNAME}@example.test", "Fields Host", username=USERNAME)
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        ares._CACHE.clear()
        _cleanup()


def _entity(**over) -> int:
    values = {
        "name": "Pole s.r.o.", "seat": "Praha 1", "ico": ICO, "dic": "CZ04656679",
        "contact_email": "pole@example.test", "contact_phone": "+420777000111",
        "bank_account": "123/0600", "iban": "CZ9106000000000000000123", "bic": "AGBACZPP",
        "registry_entry": "Živnostenský rejstřík", "vat_status": "identified",
        "invoice_prefix": "UB", "invoice_next_number": 9, "invoice_next_number_year": 2026,
        "invoice_due_days": 21, "signature_name": "Jana Pole",
        "owner_user_id": _owner(), "created_at": db.utcnow(),
    }
    values.update(over)
    return db.insert("legal_entity", values)


def _row(entity_id):
    return dict(db.query_one("SELECT * FROM legal_entity WHERE id = ?", (entity_id,)))


def _details(entity_id):
    row = _row(entity_id)
    return {key: row[key] for key in DETAIL_COLUMNS}


def _post_entity(host, entity_id, data, **kwargs):
    body = {"name": "Pole s.r.o.", **data}
    return host.post(f"/entities/{entity_id}?lang=en", data=body,
                     follow_redirects=kwargs.pop("follow_redirects", False), **kwargs)


def _post_settings(host, entity_id, data, follow_redirects=False):
    body = {"legal_entity_id": str(entity_id), "next": f"/invoices/new?entity={entity_id}", **data}
    return host.post(f"/entities/{entity_id}/invoice?lang=en", data=body, follow_redirects=follow_redirects)


# --- normalisation equivalence: the same detail input stores the same value ---

DETAIL_CASES = [
    pytest.param({}, id="all-absent-keeps"),
    pytest.param({"bank_account": ""}, id="blank-account-clears"),
    pytest.param({"bank_account": "19-2000781379/0800"}, id="domestic-account"),
    pytest.param({"bank_account": "CZ6508000000192000145399"}, id="iban-account"),
    pytest.param({"bank_account": "19-2000781379/0800", "bic": " gibaczpx "}, id="explicit-bic"),
    pytest.param({"bic": ""}, id="blank-bic-clears"),
    pytest.param({"vat_status": "non_payer"}, id="vat-non-payer"),
    pytest.param({"vat_status": "identified"}, id="vat-identified"),
    pytest.param({"vat_status": "payer"}, id="vat-payer"),
    pytest.param({"vat_status": "bogus"}, id="vat-unknown-falls-back"),
    pytest.param({"registry_entry": ""}, id="blank-registry-clears"),
    pytest.param({"registry_entry": " Městský soud "}, id="registry-trimmed"),
    pytest.param({"invoice_prefix": "ab-12#xyz9"}, id="prefix-sanitised"),
    pytest.param({"invoice_prefix": ""}, id="blank-prefix-clears"),
    pytest.param({"invoice_next_number": "42"}, id="next-number-stamps-year"),
    pytest.param({"invoice_next_number": "0"}, id="next-number-zero-clears"),
    pytest.param({"invoice_next_number": "abc"}, id="next-number-text-clears"),
    pytest.param({"invoice_next_number": ""}, id="next-number-blank-clears"),
    pytest.param({"invoice_due_days": "400"}, id="due-days-capped"),
    pytest.param({"invoice_due_days": "0"}, id="due-days-zero"),
    pytest.param({"invoice_due_days": ""}, id="due-days-blank-defaults"),
    pytest.param({"invoice_due_days": "-3"}, id="due-days-negative-defaults"),
]


@pytest.mark.parametrize("data", DETAIL_CASES)
def test_both_handlers_store_the_same_invoice_details(host, data):
    """Same input, same stored details (stored BIC present, so no derivation)."""
    via_entity = _entity()
    via_settings = _entity(name="Pole II s.r.o.")
    _post_entity(host, via_entity, data)
    _post_settings(host, via_settings, data)
    assert _details(via_entity) == _details(via_settings)


def test_the_normalised_values_are_the_documented_ones(host):
    entity_id = _entity()
    _post_settings(host, entity_id, {
        "bank_account": "19-2000781379/0800", "bic": " gibaczpx ", "vat_status": "payer",
        "registry_entry": " Městský soud ", "invoice_prefix": "ab-12#xyz9",
        "invoice_next_number": "42", "invoice_due_days": "400",
    })
    assert _details(entity_id) == {
        "bank_account": "19-2000781379/0800",
        "iban": payments.normalise_account("19-2000781379/0800")[1],
        "bic": "GIBACZPX", "registry_entry": "Městský soud", "vat_status": "payer",
        "invoice_prefix": "AB12XY", "invoice_next_number": 42,
        "invoice_next_number_year": date.today().year, "invoice_due_days": 365,
    }


def test_absent_fields_keep_and_blank_fields_clear(host):
    entity_id = _entity()
    before = _details(entity_id)
    _post_settings(host, entity_id, {})
    assert _details(entity_id) == before
    _post_settings(host, entity_id, {
        "bank_account": "", "bic": "", "registry_entry": "", "invoice_prefix": "",
        "invoice_next_number": "", "invoice_due_days": "",
    })
    after = _details(entity_id)
    assert after["bank_account"] is None and after["iban"] is None and after["bic"] is None
    assert after["registry_entry"] is None and after["invoice_prefix"] is None
    assert after["invoice_next_number"] is None and after["invoice_next_number_year"] is None
    assert after["invoice_due_days"] == 14
    assert after["vat_status"] == "identified"  # absent, kept


# --- bank account parts, IBAN-only preservation, BIC policy -----------------

def test_account_parts_compose_and_normalise(host):
    entity_id = _entity(bic=None)
    _post_settings(host, entity_id, {"account_prefix": "19", "account_number": "2000781379",
                                     "account_bank": "0800"})
    row = _row(entity_id)
    assert row["bank_account"] == "19-2000781379/0800"
    assert row["iban"] == payments.normalise_account("19-2000781379/0800")[1]
    assert row["bic"] == "GIBACZPX"  # derived: bic absent and none stored


def test_empty_account_parts_clear_a_domestic_account(host):
    entity_id = _entity()
    _post_settings(host, entity_id, {"account_prefix": "", "account_number": "",
                                     "account_bank": ""})
    row = _row(entity_id)
    assert row["bank_account"] is None and row["iban"] is None


def test_empty_account_parts_keep_an_iban_only_account(host):
    iban = "CZ6508000000192000145399"
    entity_id = _entity(bank_account=iban, iban=iban)
    page = host.get(f"/entities?edit={entity_id}&lang=en")
    assert f"IBAN {iban}" in page.text
    _post_settings(host, entity_id, {"account_prefix": "", "account_number": "",
                                     "account_bank": "", "invoice_due_days": "30"})
    row = _row(entity_id)
    assert row["bank_account"] == iban and row["iban"] == iban
    assert row["invoice_due_days"] == 30


def test_an_explicit_blank_bic_is_not_replaced_by_a_derived_one(host):
    entity_id = _entity(bic=None)
    _post_settings(host, entity_id, {"bank_account": "19-2000781379/0800", "bic": ""})
    assert _row(entity_id)["bic"] is None


def test_a_stored_bic_is_never_overwritten_by_derivation(host):
    entity_id = _entity(bic="KOMBCZPP")
    _post_settings(host, entity_id, {"bank_account": "19-2000781379/0800"})
    assert _row(entity_id)["bic"] == "KOMBCZPP"


def test_bic_derivation_is_an_invoice_settings_policy_only(host):
    """Explicit difference: the entity handler never derives a BIC."""
    via_entity = _entity(bic=None)
    via_settings = _entity(name="Pole II s.r.o.", bic=None)
    data = {"bank_account": "19-2000781379/0800"}
    _post_entity(host, via_entity, data)
    _post_settings(host, via_settings, data)
    assert _row(via_entity)["bic"] is None
    assert _row(via_settings)["bic"] == "GIBACZPX"


def test_the_derived_bic_is_labelled_on_the_settings_page(host):
    entity_id = _entity(bank_account="19-2000781379/0800", bic="GIBACZPX")
    page = host.get(f"/entities?edit={entity_id}&lang=en").text
    assert 'name="bic"' in page and 'value="GIBACZPX"' in page
    hint = host_i18n.translate("en", "invoice.fill_guest.bic_filled")
    assert hint in page
    other = _entity(name="Pole II s.r.o.", bank_account="19-2000781379/0800", bic="KOMBCZPP")
    assert hint not in host.get(f"/entities?edit={other}&lang=en").text


def test_an_invalid_account_keeps_the_stored_value_and_every_typed_value(host):
    entity_id = _entity()
    response = _post_settings(host, entity_id, {
        "account_prefix": "", "account_number": "1234567890", "account_bank": "0100",
        "bic": "TYPEDBIC", "registry_entry": "Typed registry", "vat_status": "payer",
        "invoice_prefix": "TY", "invoice_next_number": "77", "invoice_due_days": "5",
        "ico": ICO,
    })
    assert response.status_code == 422
    page = response.text
    assert "That account number is not valid." in page
    for typed in ('value="1234567890"', 'value="0100"', 'value="TYPEDBIC"',
                  'value="Typed registry"', 'value="TY"', 'value="77"', 'value="5"'):
        assert typed in page, typed
    assert re.search(r'<option value="payer"\s+selected', page)
    row = _row(entity_id)
    assert row["bank_account"] == "123/0600" and row["invoice_prefix"] == "UB"


def test_the_entity_handler_rejects_a_bad_account_without_saving(host):
    entity_id = _entity()
    response = _post_entity(host, entity_id, {"bank_account": "not-an-account"},
                            follow_redirects=True)
    assert "That account number is not valid." in response.text
    assert _row(entity_id)["bank_account"] == "123/0600"


# --- business identity and the split between the two pages -----------------

def test_identity_saves_keep_every_invoice_default(host):
    entity_id = _entity()
    before = _details(entity_id)
    _post_entity(host, entity_id, {"seat": "Brno", "ico": ICO, "dic": "",
                                   "contact_email": "new@example.test", "contact_phone": ""})
    row = _row(entity_id)
    assert row["seat"] == "Brno" and row["contact_email"] == "new@example.test"
    assert row["dic"] == "" and row["contact_phone"] == ""
    assert _details(entity_id) == before
    assert row["signature_name"] == "Jana Pole"


def test_invoice_default_saves_keep_identity_contact_and_signature(host):
    entity_id = _entity(signature_png_enc=db.encrypt_field(
        "data:image/png;base64," + base64.b64encode(PNG).decode()))
    before = _row(entity_id)
    _post_settings(host, entity_id, {"ico": "99999999", "vat_status": "payer",
                                     "invoice_due_days": "7"})
    row = _row(entity_id)
    for key in ("name", "seat", "ico", "dic", "contact_email", "contact_phone",
                "signature_name", "signature_png_enc"):
        assert row[key] == before[key], key
    assert row["vat_status"] == "payer" and row["invoice_due_days"] == 7


def test_create_and_edit_share_the_identity_rules(host):
    response = host.post("/entities?lang=en", data={
        "name": "Nová s.r.o.", "seat": "Praha", "ico": ICO, "dic": "",
        "contact_email": "nova@example.test", "contact_phone": "",
    }, follow_redirects=False)
    assert response.status_code in (302, 303)
    created = db.query_one("SELECT * FROM legal_entity WHERE name = ? AND owner_user_id = ?",
                           ("Nová s.r.o.", _owner()))
    assert created["contact_email"] == "nova@example.test"
    bad = host.post("/entities?lang=en", data={"name": "Špatná", "ico": "12345678"},
                    follow_redirects=True)
    assert host_i18n.translate("en", "entities.ico.invalid") in bad.text
    assert db.query_one("SELECT id FROM legal_entity WHERE name = ?", ("Špatná",)) is None
    entity_id = _entity()
    _post_entity(host, entity_id, {"ico": "12345678"})
    assert _row(entity_id)["ico"] == ICO


# --- signature lifecycle ----------------------------------------------------

def _drawn(content=PNG, kind="png"):
    return f"data:image/{kind};base64," + base64.b64encode(content).decode()


def test_signature_lifecycle(host):
    entity_id = _entity()
    # drawn signature is stored encrypted
    _post_entity(host, entity_id, {"signature_drawn": _drawn(), "signature_name": " Jana "})
    row = _row(entity_id)
    assert db.decrypt_field(row["signature_png_enc"]) == _drawn()
    assert row["signature_name"] == "Jana"
    # an edit without signature fields keeps it
    _post_entity(host, entity_id, {"seat": "Praha 2"})
    assert db.decrypt_field(_row(entity_id)["signature_png_enc"]) == _drawn()
    # an upload replaces it
    host.post(f"/entities/{entity_id}?lang=en", data={"name": "Pole s.r.o."},
              files={"signature_file": ("s.jpg", JPEG, "image/jpeg")})
    assert db.decrypt_field(_row(entity_id)["signature_png_enc"]) == _drawn(JPEG, "jpeg")
    # an invalid drawing is refused and the stored one stays
    response = _post_entity(host, entity_id, {"signature_drawn": "data:image/png;base64,AAAA"},
                            follow_redirects=True)
    assert db.decrypt_field(_row(entity_id)["signature_png_enc"]) == _drawn(JPEG, "jpeg")
    assert response.status_code == 200
    # an unsupported upload is refused
    host.post(f"/entities/{entity_id}?lang=en", data={"name": "Pole s.r.o."},
              files={"signature_file": ("s.gif", b"GIF89a....", "image/gif")})
    assert db.decrypt_field(_row(entity_id)["signature_png_enc"]) == _drawn(JPEG, "jpeg")
    # remove plus a new upload keeps the upload
    host.post(f"/entities/{entity_id}?lang=en",
              data={"name": "Pole s.r.o.", "signature_remove": "1"},
              files={"signature_file": ("s.png", PNG, "image/png")})
    assert db.decrypt_field(_row(entity_id)["signature_png_enc"]) == _drawn()
    # remove alone clears; a blank name clears the name; long names are cut to 80
    _post_entity(host, entity_id, {"signature_remove": "1", "signature_name": "x" * 90})
    row = _row(entity_id)
    assert row["signature_png_enc"] is None and row["signature_name"] == "x" * 80
    _post_entity(host, entity_id, {"signature_name": "  "})
    assert _row(entity_id)["signature_name"] is None


def test_the_remove_checkbox_only_shows_with_a_stored_signature(host):
    entity_id = _entity()
    page = host.get(f"/entities?edit={entity_id}&lang=en").text
    assert 'name="signature_remove"' not in page
    db.update("legal_entity", entity_id, {"signature_png_enc": db.encrypt_field(_drawn())})
    page = host.get(f"/entities?edit={entity_id}&lang=en").text
    assert page.count('name="signature_remove"') == 1


# --- issued invoices are never touched --------------------------------------

def test_saving_details_never_changes_an_issued_invoice(host):
    entity_id = _entity(bank_account=None, iban=None, bic=None, invoice_next_number=None,
                        invoice_next_number_year=None)
    draft = {
        "legal_entity_id": entity_id, "apartment_id": None, "reservation_id": None,
        "kind": "invoice", "lang": "cs", "vat_status": "non_payer",
        "issue_date": "2026-09-26", "duzp": None, "due_date": None,
        "paid_on": None, "paid_via": None,
        "seller": {"name": "Pole s.r.o.", "seat": "Praha 1", "ico": ICO, "dic": "",
                   "registry": "ŽR", "bank_account": "", "iban": "", "bic": "",
                   "email": "", "phone": ""},
        "buyer": {"name": "Buyer", "street": "", "city": "", "zip": "", "country": "CZE",
                  "ico": "", "dic": "", "email": ""},
        "stay_from": "2026-09-10", "stay_to": "2026-09-14", "stay_label": "Flat",
        "items": [{"kind": "accommodation", "description": "Ubytování", "quantity": 1,
                   "unit": "pobyt", "vat_rate": None, "base_haler": None,
                   "vat_haler": None, "gross_haler": 10000}],
        "total_base_haler": None, "total_vat_haler": None, "total_haler": 10000,
    }
    invoice_id = invoices.issue(draft, actor_user_id=_owner())
    before = dict(db.query_one("SELECT * FROM invoice WHERE id = ?", (invoice_id,)))
    sequence = [dict(r) for r in db.query(
        "SELECT * FROM invoice_sequence WHERE legal_entity_id = ?", (entity_id,))]
    _post_settings(host, entity_id, {"bank_account": "19-2000781379/0800",
                                     "invoice_prefix": "ZZ", "invoice_next_number": "500",
                                     "vat_status": "payer"})
    _post_entity(host, entity_id, {"seat": "Ostrava", "ico": ICO})
    assert dict(db.query_one("SELECT * FROM invoice WHERE id = ?", (invoice_id,))) == before
    assert [dict(r) for r in db.query(
        "SELECT * FROM invoice_sequence WHERE legal_entity_id = ?", (entity_id,))] == sequence


# --- rendered contract ------------------------------------------------------

def _form_body(page, marker):
    """The markup of the one form whose opening tag contains ``marker``."""
    return page.split(marker, 1)[1].split("</form>", 1)[0]


def _tag(page, name, index=0):
    tags = re.findall(r'<(?:input|select)\b[^>]*\bname="%s"[^>]*>' % re.escape(name), page)
    return tags[index]


def test_the_entity_forms_keep_their_contract(host):
    entity_id = _entity()
    page = host.get(f"/entities?edit={entity_id}&lang=en").text
    assert f'action="/entities/{entity_id}" enctype="multipart/form-data"' in page
    assert 'action="/entities" enctype="multipart/form-data"' in page
    expected = {
        "name": ('type="text"', True), "seat": ('type="text"', True),
        "ico": ('type="text"', True), "dic": ('type="text"', False),
        "contact_email": ('type="email"', True), "contact_phone": ('type="tel"', False),
        "contact_phone_country_code": ('type="text"', False),
        "signature_name": ('type="text"', False), "signature_file": ('type="file"', False),
        "signature_drawn": ('type="hidden"', False),
    }
    # 0076: the edit panel also holds Invoice details; check each business form alone.
    forms = (
        (_form_body(page, f'action="/entities/{entity_id}" enctype'), "edit_"),
        (_form_body(page, 'action="/entities" enctype'), "new_"),
    )
    for form, prefix in forms:
        assert form.count('name="fill_from_register" value="1" formnovalidate') == 1
        for absent in ("vat_status", "invoice_prefix", "account_number", "registry_entry"):
            assert f'name="{absent}"' not in form
        for name, (kind, required) in expected.items():
            tag = _tag(form, name)
            assert kind in tag, (name, tag)
            assert (" required" in tag) is required, (name, tag)
            field_id = "signature" if name == "signature_drawn" else name
            assert f'id="{prefix}{field_id}"' in tag, (name, tag)
    assert 'accept="image/png,image/jpeg"' in _tag(page, "signature_file")
    assert 'maxlength="80"' in _tag(page, "signature_name")
    # Business details + the Invoice details lookup + Add business.
    assert page.count('name="fill_from_register" value="1" formnovalidate') == 3


def test_the_invoice_settings_form_keeps_its_contract(host):
    entity_id = _entity()
    # 0076: Invoice details is the business editor's own
    # urlencoded form (no enctype) with the same fields and guards.
    page = host.get(f"/entities?edit={entity_id}&lang=en").text
    form = _form_body(page, f'<form method="post" action="/entities/{entity_id}/invoice" data-unsaved-guard>')
    assert 'name="_csrf"' in form and f'name="legal_entity_id" value="{entity_id}"' in form
    # One IČO per business: the lookup sends the saved Business details value
    # (hidden), never a second editable IČO box.
    assert 'id="lookup_ico"' not in form
    ico = _tag(form, "ico")
    assert 'type="hidden"' in ico
    assert 'name="fill_from_register" value="1" formnovalidate' in form
    for name, needle in (("account_prefix", 'maxlength="6"'), ("account_number", 'maxlength="10"'),
                         ("account_bank", 'maxlength="4"'), ("bic", 'type="text"'),
                         ("registry_entry", 'type="text"'), ("invoice_prefix", 'maxlength="6"'),
                         ("invoice_next_number", 'min="1"'), ("invoice_due_days", 'max="365"')):
        assert needle in _tag(form, name), name
    assert 'id="invoice_account_number"' in form
    assert re.search(r'<option value="identified"\s+selected', form)
    assert 'name="_invoice_account_existing" value="123/0600"' in form
    for absent in ("name", "seat", "contact_email", "signature_name", "signature_file"):
        assert f'name="{absent}"' not in form


def test_each_shared_field_has_one_template_definition():
    owners = {
        'name="seat"': "_entity_business_fields.html",
        'name="contact_email"': "_entity_business_fields.html",
        'name="contact_phone"': "_entity_business_fields.html",
        'name="signature_name"': "_entity_business_fields.html",
        'name="fill_from_register"': "_entity_business_fields.html",
        'name="vat_status"': "_entity_invoice_fields.html",
        'name="invoice_prefix"': "_entity_invoice_fields.html",
        'name="invoice_next_number"': "_entity_invoice_fields.html",
        'name="invoice_due_days"': "_entity_invoice_fields.html",
        'name="registry_entry"': "_entity_invoice_fields.html",
    }
    for needle, owner in owners.items():
        found = sorted(p.name for p in TEMPLATES.rglob("*.html") if needle in p.read_text())
        assert found == [owner], (needle, found)
    # 0076: invoice_settings.html is gone; the business editor is the one page.
    assert not (TEMPLATES / "invoice_settings.html").exists()
    text = (TEMPLATES / "entities.html").read_text()
    assert "<details" not in text and "{% macro" not in text


# --- ARES: click-only, rate-limited, retains typed values -------------------

ARES_PAYLOAD = {
    "obchodniJmeno": "ARES Pole s.r.o.",
    "sidlo": {"textovaAdresa": "Praha 1, Václavské náměstí 1"},
    "dic": "CZ04656679",
    "seznamRegistraci": {"stavZdrojeDph": "AKTIVNI"},
    "dalsiUdaje": [{"datovyZdroj": "vr", "spisovaZnacka": "B 8525/MSPH"}],
}


def _ares_response():
    response = MagicMock()
    response.status_code = 200
    response.ok = True
    response.json.return_value = ARES_PAYLOAD
    return response


def test_pages_and_saves_never_call_the_register(host):
    entity_id = _entity()
    with patch("app.ares.requests.get") as mock_get:
        host.get(f"/entities?edit={entity_id}&lang=en")
        host.get(f"/entities?edit={entity_id}&lang=en")
        _post_entity(host, entity_id, {"ico": ICO})
        _post_settings(host, entity_id, {"ico": ICO, "registry_entry": ""})
    assert not mock_get.called


def test_settings_lookup_keeps_typed_account_parts_and_details(host):
    entity_id = _entity(registry_entry=None, vat_status="non_payer")
    with patch("app.ares.requests.get") as mock_get:
        mock_get.return_value = _ares_response()
        response = _post_settings(host, entity_id, {
            "fill_from_register": "1", "ico": ICO, "account_prefix": "19",
            "account_number": "2000781379", "account_bank": "0800", "bic": "TYPED",
            "vat_status": "non_payer", "registry_entry": "", "invoice_prefix": "QQ",
            "invoice_next_number": "3", "invoice_due_days": "9",
        })
        assert mock_get.call_count == 1
        # the second click is served from the existing cache
        _post_settings(host, entity_id, {"fill_from_register": "1", "ico": ICO})
        assert mock_get.call_count == 1
    assert response.status_code == 200
    page = response.text
    for typed in ('value="19"', 'value="2000781379"', 'value="0800"', 'value="TYPED"',
                  'value="QQ"', 'value="3"', 'value="9"'):
        assert typed in page, typed
    assert "Městského soudu v Praze" in page
    assert re.search(r'<option value="payer"\s+selected', page)
    assert _row(entity_id)["registry_entry"] is None


def test_entity_lookup_keeps_typed_identity(host):
    entity_id = _entity(dic="")
    with patch("app.ares.requests.get") as mock_get:
        mock_get.return_value = _ares_response()
        response = _post_entity(host, entity_id, {
            "fill_from_register": "1", "ico": ICO, "name": "Typed name", "seat": "",
            "dic": "", "contact_email": "typed@example.test", "contact_phone": "+420 1",
            "signature_name": "Typed signer",
        })
    page = response.text
    assert response.status_code == 200
    for typed in ('value="Typed name"', 'value="typed@example.test"',
                  'value="Typed signer"', 'value="CZ04656679"', "Václavské náměstí"):
        assert typed in page, typed
    assert 'value="420"' in _tag(page, "contact_phone_country_code")
    assert 'value="1"' in _tag(page, "contact_phone")
    assert _row(entity_id)["name"] == "Pole s.r.o."


def test_lookup_errors_rerender_with_the_actual_message(host):
    entity_id = _entity()
    with patch("app.ares.requests.get") as mock_get:
        bad = _post_settings(host, entity_id, {"fill_from_register": "1", "ico": "123",
                                               "invoice_prefix": "KEEP"})
        bad_entity = _post_entity(host, entity_id, {"fill_from_register": "1", "ico": "123",
                                                    "name": "Kept"})
    assert not mock_get.called
    for response in (bad, bad_entity):
        assert response.status_code == 200
        assert '<p class="alert">' in response.text
    assert 'value="KEEP"' in bad.text and 'value="Kept"' in bad_entity.text
    for _ in range(20):
        ares.record_lookup(_owner())
    limited = _post_settings(host, entity_id, {"fill_from_register": "1", "ico": ICO})
    assert host_i18n.translate("en", "ares.rate_limited") in limited.text


# --- browser: both editors fit 360-1280 in EN and CS -------------------------

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "0075-evidence"
BROWSER_USER = "fields0075"


@pytest.fixture(scope="module")
def browser_host():
    db.init_db()
    username = f"{BROWSER_USER}-{secrets.token_hex(3)}"
    owner_id = auth.create_account(f"{username}@example.test", "Pole Host", username=username)
    entity_id = db.insert("legal_entity", {
        "name": "Ukázka Pole s.r.o.", "seat": "Václavské náměstí 1, 110 00 Praha 1",
        "ico": ICO, "dic": "CZ04656679", "contact_email": "pole@example.test",
        "contact_phone": "+420 777 000 111", "bank_account": "19-2000781379/0800",
        "iban": payments.normalise_account("19-2000781379/0800")[1], "bic": "GIBACZPX",
        "registry_entry": "Zapsáno v živnostenském rejstříku", "vat_status": "non_payer",
        "invoice_prefix": "UB", "invoice_due_days": 14, "signature_name": "Jana Pole",
        "owner_user_id": owner_id, "created_at": db.utcnow(),
    })
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    yield {"client": client, "owner": owner_id, "entity": entity_id}
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


@pytest.fixture(scope="module")
def live_base(browser_host):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("the test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


_FIT_SCRIPT = """(selector) => {
  const root = document.documentElement;
  const form = document.querySelector(selector);
  const fields = [...form.querySelectorAll('input:not([type=hidden]):not(.sr-only), select, button')];
  const width = root.clientWidth;
  const bad = fields.filter((el) => {
    const box = el.getBoundingClientRect();
    return box.width > 0 && (box.left < -0.5 || box.right > width + 0.5
      || (el.tagName !== 'BUTTON' && el.type !== 'checkbox' && box.width < 40)
      || box.height < 16);
  }).map((el) => el.name || el.id || el.textContent.trim());
  return {overflow: root.scrollWidth - width, bad, count: fields.length};
}"""


def test_entity_and_invoice_editors_fit_every_width(browser_host, live_base):
    sync_api = pytest.importorskip("playwright.sync_api")
    from tests.browser_support import chromium_launch_kwargs

    entity_id = browser_host["entity"]
    pages = (
        ("entity-edit", f"/entities?edit={entity_id}", "#entity-business form"),
        ("entity-add", "/entities", "#entity-add form"),
        # 0101: Invoice details of the business editor.
        ("invoice-settings", f"/entities?edit={entity_id}#entity-invoice",
         "#entity-invoice form"),
    )
    capture = os.environ.get("UBYHOST_CAPTURE_0075") == "1"
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        try:
            for width in (360, 390, 1280):
                context = browser.new_context(viewport={"width": width, "height": 900})
                cookie = browser_host["client"].cookies.get(auth.SESSION_COOKIE)
                context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie,
                                      "url": live_base + "/"}])
                page = context.new_page()
                for lang in ("en", "cs"):
                    for name, path, selector in pages:
                        joiner = "&" if "?" in path else "?"
                        page.goto(f"{live_base}{path}{joiner}lang={lang}")
                        result = page.evaluate(_FIT_SCRIPT, selector)
                        assert result["count"] >= 4, (name, width, lang, result)
                        assert result["overflow"] <= 0, (name, width, lang, result)
                        assert not result["bad"], (name, width, lang, result)
                        if capture:
                            EVIDENCE.mkdir(parents=True, exist_ok=True)
                            page.locator(selector).scroll_into_view_if_needed()
                            page.locator(selector).screenshot(
                                path=str(EVIDENCE / f"{name}-{width}-{lang}.png"))
                context.close()
        finally:
            browser.close()


@pytest.mark.parametrize(
    "prefix,number,expected",
    [("+420", "777 000 111", "+420777000111"),
     ("+49", "15123456789", "+4915123456789"),
     ("+420", "+44 7700 900123", "+447700900123"),
     ("+420", "0044 7700 900123", "+447700900123"),
     ("+420", "", "")],
)
def test_country_code_is_saved_in_the_existing_operator_phone(host, prefix, number, expected):
    entity_id = _entity()
    response = _post_entity(host, entity_id, {
        "contact_phone": number, "contact_phone_country_code": prefix,
    })
    assert response.status_code == 303
    assert _row(entity_id)["contact_phone"] == expected
    if expected:
        page = host.get(f"/entities?edit={entity_id}&lang=en").text
        assert 'name="contact_phone_country_code"' in page


def test_country_code_create_and_partial_post_preserve_other_fields(host):
    response = host.post("/entities", data={
        "name": "Prefix Operator", "seat": "Sample City", "ico": ICO,
        "contact_email": "prefix@example.test",
        "contact_phone_country_code": "+421", "contact_phone": "901 234 567",
    }, follow_redirects=False)
    assert response.status_code == 303
    row = db.query_one("SELECT * FROM legal_entity WHERE owner_user_id = ? AND name = ?",
                       (_owner(), "Prefix Operator"))
    assert row["contact_phone"] == "+421901234567"
    response = _post_entity(host, row["id"], {"seat": "Updated city"})
    assert response.status_code == 303
    assert _row(row["id"])["contact_phone"] == "+421901234567"
