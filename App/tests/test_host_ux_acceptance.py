"""0084: whole-host acceptance for the combined host UX candidate.

Synthetic fixtures only; no live provider (UbyPort mock, no feed sync, no
TTLock call, console mail). The matrix in docs/plans/host-ux-acceptance.md
links every behaviour row either to a focused test elsewhere or to a test here.

What this file adds on top of the per-task tests:

* ownership counted on the rendered pages of every host page family: each
  property setting, entity field and fee field has one editable control in
  the whole host, no page carries a cloned (desktop/mobile) editor form;
* one/many/no/archived property behaviour of the legacy hubs and Search;
* every legacy GET/POST adapter in one place, landing on the canonical home;
* browser: page families reached through the rail, cards, Search and Back in
  EN and CS; keyboard focus; JavaScript-off tabs and saves; and a geometry
  sweep of every family at 360-2048 px with the rail expanded and collapsed.

Screenshots: ``UBYHOST_CAPTURE_0084=1`` writes docs/tasks/0084-evidence/.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import socket
import threading
import time
from datetime import timedelta
from html.parser import HTMLParser
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, claim, config, db
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "0084-evidence"
CAPTURE = os.environ.get("UBYHOST_CAPTURE_0084") == "1"
WIDTHS = (360, 390, 760, 1024, 1280, 1440, 1680, 1920, 2048)
RAIL_WIDTHS = tuple(w for w in WIDTHS if w > 960)  # the rail exists from 961 px
CAPTURE_WIDTHS = (360, 390, 1280)
LONG_NAME = "Dům U Šesti růží — synthetic acceptance property with a deliberately long name"
LONG_ENTITY = "Ukázka Dlouhého Názvu Provozovatele pro Akceptační Test s.r.o."
LOCK = {"lock_id": "70840001", "alias": "Synthetic Acceptance Door", "battery": 88, "tz_offset_ms": 3600000}

# Property settings: their one editable home is Settings on the property page.
PROPERTY_SETTINGS = {
    "internal_name", "city_en", "legal_entity_id", "data_controller_entity_id",
    "addr_okres", "addr_obec", "addr_obec_cast", "addr_street", "addr_house_no", "addr_orient_no", "addr_zip",
    "notes", "permalink_pin", "guest_message", "permalink_window_days",
    "permalink_reachback_days", "passport_photo_policy", "door_codes", "lock_id", "checkin_hour",
    "checkout_hour", "uby_idub", "uby_ws_user", "uby_ws_password", "uby_mark", "uby_name", "uby_contact",
    "stay_fee_rate_czk", "stay_fee_cadence", "stay_fee_vs", "account_prefix", "account_number",
    "account_bank", "stay_fee_authority_name", "stay_fee_authority_address", "stay_fee_authority_contact",
    "stay_fee_authority_databox", "stay_fee_payee", "stay_fee_instruction", "automation_mode",
    "submit_after_hours", "default_purpose",
}
# The create page legitimately asks for these (creation, not a second editor).
CREATE_FIELDS = {"internal_name", "city_en", "legal_entity_id", "addr_okres", "addr_obec", "addr_obec_cast",
                 "addr_street", "addr_house_no", "addr_orient_no", "addr_zip"}
GUEST_LINK_AND_AUTOMATION = {"permalink_pin", "guest_message", "permalink_window_days",
                             "permalink_reachback_days", "passport_photo_policy", "automation_mode",
                             "submit_after_hours", "default_purpose"}
# 0098 (owner): the Properties summary has the inline timing control, a second
# entry point to the Automation save (one normaliser). Nothing else is allowed.
INLINE_TIMING_0098 = {"automation_mode", "submit_after_hours"}
FEE_FIELDS = {n for n in PROPERTY_SETTINGS if n.startswith("stay_fee_")}
BUSINESS_FIELDS = {"name", "seat", "ico", "dic", "contact_email", "contact_phone",
                   "signature_file", "signature_name"}
INVOICE_DETAIL_FIELDS = {"vat_status", "registry_entry", "invoice_prefix", "invoice_next_number",
                         "invoice_due_days", "bic"}

# Every host page family: key -> (path template, lane selector).
FAMILIES = {
    "dashboard": "/",
    "stays": "/reservations",
    "stay-detail": "/reservations/{stay}",
    "properties": "/apartments",
    "property-overview": "/apartments/{p1}",
    "property-bookings": "/apartments/{p1}?view=bookings",
    "property-settings": "/apartments/{p1}?view=settings&section=property",
    "property-guests": "/apartments/{p1}?view=settings&section=guests",
    "property-reporting": "/apartments/{p1}?view=settings&section=reporting",
    "property-automation": "/apartments/{p1}?view=settings&section=automation",
    "property-archived": "/apartments/{p3}?view=settings&section=property",
    "property-new": "/apartments/new",
    "businesses": "/entities",
    "business-editor": "/entities?edit={e1}&next=/apartments/{p1}",
    "invoices": "/invoices",
    "invoice-new": "/invoices/new?entity={e1}",
    "invoice-detail": "/invoices/{invoice}",
    "fees": "/stay-fees",
    "fee-report": "/stay-fees/{p1}?month={month}",
    "reports": "/submissions",
    "report-detail": "/submissions/{submission}",
    "housebook": "/housebook?apartment={p1}",
    "settings": "/settings",
    "archive": "/settings/archived",
    "smart-locks": "/smart-locks",
    "guide": "/guide",
}
CAPTURE_FAMILIES = ("dashboard", "stays", "stay-detail", "properties", "property-overview", "property-bookings",
                    "property-guests", "property-reporting", "property-new", "business-editor", "invoices",
                    "invoice-detail", "fees", "fee-report", "settings", "smart-locks")


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _account(prefix, role="host"):
    username = f"{prefix}-{secrets.token_hex(4)}"
    user_id = auth.create_account(f"{username}@example.test", f"{prefix.title()} Fixture", role=role, username=username)
    return username, user_id


def _client(username):
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    return client


def _property(owner, entity, name, **over):
    values = {
        "internal_name": name, "owner_user_id": owner, "legal_entity_id": entity, "city_en": "Praha",
        "automation_mode": "manual", "submit_after_hours": 24, "default_purpose": "10",
        "permalink_token": f"acc{secrets.token_hex(6)}", "permalink_pin": "135790",
        "addr_obec": "Praha", "addr_street": "Synthetická", "addr_house_no": "12", "addr_zip": "11000",
        "active": 1, "created_at": db.utcnow(),
    }
    values.update(over)
    return db.insert("apartment", values)


@pytest.fixture(scope="module")
def acc():
    db.init_db()
    patcher = pytest.MonkeyPatch()
    patcher.setattr(config, "DOOR_CODES_ENABLED", True)
    patcher.setattr(config, "TTLOCK_CLIENT_ID", "cid-synthetic")
    patcher.setattr(config, "TTLOCK_CLIENT_SECRET", "csecret-synthetic")
    now = db.utcnow()
    username, owner = _account("acc-many")
    e1 = db.insert("legal_entity", {
        "name": LONG_ENTITY, "seat": "Praha 1", "ico": "04656679", "contact_email": "acc@example.test",
        "vat_status": "non_payer", "invoice_due_days": 14, "invoice_prefix": "AC", "owner_user_id": owner,
        "created_at": now,
    })
    e2 = db.insert("legal_entity", {
        "name": "Druhá Synthetic s.r.o.", "seat": "Brno", "ico": "87654321", "contact_email": "acc2@example.test",
        "owner_user_id": owner, "created_at": now,
    })
    p1 = _property(owner, e1, LONG_NAME, data_controller_entity_id=e2,
                   uby_idub="123456789012", uby_mark="SYNTH", uby_name="Synthetic Acceptance",
                   uby_ws_user="UBY-WSacc", uby_contact="host@example.test",
                   uby_ws_password_enc=db.encrypt_secret("synthetic-secret"),
                   automation_mode="scheduled", submit_after_hours=6, guest_message="Synthetic welcome.",
                   stay_fee_rate_czk=30, stay_fee_cadence="quarterly", stay_fee_vs="1234",
                   stay_fee_authority_name="Synthetic Council",
                   stay_fee_council_iban="CZ6508000000192000145399",
                   lock_provider="ttlock", lock_id=LOCK["lock_id"], checkin_hour=15, checkout_hour=10)
    p2 = _property(owner, e1, "Studio Beta", stay_fee_rate_czk=0)
    p3 = _property(owner, e1, "Archived Gamma", active=0, archived_at=now)
    db.insert("ical_feed", {"apartment_id": p1, "url": "https://calendar.example.test/acc.ics",
                            "label": "Airbnb", "own_name": "Synthetic Airbnb", "last_status": "ok",
                            "last_sync_at": now, "created_at": now})
    db.insert("lock_account", {"owner_user_id": owner, "provider": "ttlock", "username": "synthetic_acc",
                               "status": "ok", "locks_json": json.dumps([LOCK]), "created_at": now,
                               "updated_at": now})
    today = claim.prague_today()
    stay = db.insert("reservation", {
        "apartment_id": p1, "source": "manual", "uid": f"acc-{secrets.token_hex(4)}",
        "date_from": today.isoformat(), "date_to": (today + timedelta(days=3)).isoformat(),
        "status": "active", "expected_guests_override": 2, "created_at": now, "updated_at": now,
    })
    db.insert("guest", {
        "reservation_id": stay, "surname": "SYNTHETIC", "first_name": "GUEST", "birth_date": "01011990",
        "nationality": "GBR", "doc_number": "P0840001", "res_street": "Street 1", "res_city": "London",
        "res_country": "GBR", "purpose": "10", "is_lead": 1, "entered_by": "host", "signature_png": "imported",
        "signed_at": now, "identity_verified_at": now, "submit_state": "pending", "created_at": now,
        "updated_at": now,
    })
    invoice = db.insert("invoice", {
        "legal_entity_id": e1, "apartment_id": p1, "reservation_id": stay, "kind": "invoice",
        "seq_year": today.year, "seq_no": 84, "number": f"{today.year}-0084-{secrets.token_hex(2)}",
        "vs": f"{today.year}0084", "lang": "en", "vat_status": "non_payer", "issue_date": today.isoformat(),
        "seller_name": LONG_ENTITY, "seller_seat": "Praha 1", "buyer_name": "Synthetic Buyer",
        "total_haler": 300000, "owner_user_id": owner, "created_at": now,
    })
    db.insert("invoice_item", {
        "invoice_id": invoice, "position": 1, "kind": "accommodation", "description": "Synthetic stay",
        "quantity": 3, "unit": "nights", "vat_rate": 0, "base_haler": 300000, "vat_haler": 0,
        "gross_haler": 300000,
    })
    submission = db.insert("submission", {
        "apartment_id": p1, "created_at": now, "finished_at": now, "mode": "manual", "state": "error",
        "guest_ids": "[]", "header_errors": "", "record_errors": "[]", "error_text": "Synthetic acceptance fixture",
    })
    one_name, one_owner = _account("acc-one")
    one_entity = db.insert("legal_entity", {"name": "Jedna s.r.o.", "seat": "Praha", "ico": "11111111",
                                            "contact_email": "one@example.test", "owner_user_id": one_owner,
                                            "created_at": now})
    one_property = _property(one_owner, one_entity, "Only Property")
    one_archived = _property(one_owner, one_entity, "Old Archived", active=0, archived_at=now)
    none_name, none_owner = _account("acc-none")
    client = _client(username)
    data = {
        "username": username, "owner": owner, "client": client, "e1": e1, "e2": e2,
        "p1": p1, "p2": p2, "p3": p3, "stay": stay, "invoice": invoice, "submission": submission,
        "month": today.strftime("%Y-%m"),
        "one": {"username": one_name, "owner": one_owner, "property": one_property,
                "archived": one_archived, "entity": one_entity},
        "none": {"username": none_name, "owner": none_owner},
        "cookie": client.cookies.get(auth.SESSION_COOKIE),
    }
    try:
        yield data
    finally:
        patcher.undo()
        for user in (owner, one_owner, none_owner):
            apartments = "SELECT id FROM apartment WHERE owner_user_id = ?"
            db.execute(f"DELETE FROM guest WHERE reservation_id IN (SELECT id FROM reservation WHERE apartment_id IN ({apartments}))", (user,))
            db.execute(f"DELETE FROM invoice_item WHERE invoice_id IN (SELECT id FROM invoice WHERE owner_user_id = ?)", (user,))
            db.execute("DELETE FROM invoice WHERE owner_user_id = ?", (user,))
            db.execute(f"DELETE FROM submission WHERE apartment_id IN ({apartments})", (user,))
            db.execute(f"DELETE FROM reservation WHERE apartment_id IN ({apartments})", (user,))
            db.execute(f"DELETE FROM ical_feed WHERE apartment_id IN ({apartments})", (user,))
            db.execute(f"DELETE FROM apartment_slug WHERE apartment_id IN ({apartments})", (user,))
            db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user,))
            db.execute("DELETE FROM lock_account WHERE owner_user_id = ?", (user,))
            db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user,))
            db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user,))
            db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user,))


def _url(acc, key):
    return FAMILIES[key].format(**{k: v for k, v in acc.items() if not isinstance(v, dict)})


def _with_lang(path, lang):
    return f"{path}{'&' if '?' in path else '?'}lang={lang}"


# --- rendered-control inventory ------------------------------------------------


class _Controls(HTMLParser):
    """Every form and every named control as the browser would build them."""

    def __init__(self):
        super().__init__()
        self.forms, self.stack, self.controls, self.ids, self.nested = [], [], [], [], False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.append(a["id"])
        if tag == "form":
            self.nested = self.nested or bool(self.stack)
            form = {"action": a.get("action") or "", "method": (a.get("method") or "get").lower(), "names": []}
            self.forms.append(form)
            self.stack.append(form)
            return
        if tag not in ("input", "select", "textarea") or not a.get("name"):
            return
        kind = (a.get("type") or "text").lower() if tag == "input" else tag
        form = self.stack[-1] if self.stack else None
        attr_form = a.get("form")
        control = {"name": a["name"], "kind": kind, "form": form, "form_attr": attr_form,
                   "editable": kind not in ("hidden", "submit", "button", "image", "reset") and "disabled" not in a}
        self.controls.append(control)
        if form is not None:
            form["names"].append(a["name"])

    def handle_endtag(self, tag):
        if tag == "form" and self.stack:
            self.stack.pop()


def _inventory(html):
    parser = _Controls()
    parser.feed(html)
    return parser


def _pages(acc, lang="en"):
    client = acc["client"]
    pages = {}
    for key in FAMILIES:
        response = client.get(_with_lang(_url(acc, key), lang))
        assert response.status_code == 200, (key, response.status_code, response.url)
        pages[key] = response.text
    return pages


def _editable(inventory):
    return [c["name"] for c in inventory.controls if c["editable"]]


@pytest.mark.parametrize("lang", ["en", "cs"])
def test_every_host_page_has_unique_ids_no_nested_and_no_cloned_editor_forms(acc, lang):
    for key, html in _pages(acc, lang).items():
        inv = _inventory(html)
        assert not inv.nested, f"{key}: a form is nested inside another"
        dupes = sorted({i for i in inv.ids if inv.ids.count(i) > 1})
        assert not dupes, f"{key}: duplicate ids {dupes}"
        # A cloned desktop/mobile editor shows up as two POST forms with the same
        # action and the same editable field set.
        editors = [(f["action"], tuple(sorted(set(f["names"]))))
                   for f in inv.forms if f["method"] == "post" and len(set(f["names"])) >= 3]
        clones = sorted({e for e in editors if editors.count(e) > 1})
        assert not clones, f"{key}: cloned editor forms {clones}"


def test_each_property_setting_has_exactly_one_editable_control_in_the_whole_host(acc):
    pages = _pages(acc)
    for view in ("property-overview", "property-bookings", "property-settings", "property-guests",
                 "property-reporting", "property-automation"):
        # All three views and four groups are in every property document.
        names = _editable(_inventory(pages[view]))
        counts = {n: names.count(n) for n in PROPERTY_SETTINGS}
        missing = sorted(n for n, c in counts.items() if c == 0)
        doubled = sorted(n for n, c in counts.items() if c > 1 and n not in ("account_prefix", "account_number", "account_bank"))
        assert not doubled, f"{view}: setting rendered twice {doubled}"
        assert not missing, f"{view}: setting has no editor {missing}"
        # The fee account parts are one set of three on the property page.
        for part in ("account_prefix", "account_number", "account_bank"):
            assert counts[part] == 1, (view, part, counts[part])
    for key, html in pages.items():
        if key.startswith("property-") and key not in ("property-new",):
            continue
        names = set(_editable(_inventory(html)))
        allowed = CREATE_FIELDS if key == "property-new" else set()
        if key in ("invoice-new", "business-editor", "businesses"):
            # legal_entity_id is the supplier choice / entity id there, not a property setting.
            allowed = allowed | {"legal_entity_id"}
        if key in ("business-editor", "businesses"):
            # The entity editor's own invoice account fields share the generic part names (0075).
            allowed = allowed | {"account_prefix", "account_number", "account_bank"}
        if key == "properties":
            allowed = allowed | INLINE_TIMING_0098
        stray = sorted((names & PROPERTY_SETTINGS) - allowed)
        assert not stray, f"{key}: property setting editable outside the property page: {stray}"


def test_guest_link_automation_and_fee_have_no_copied_editor(acc):
    pages = _pages(acc)
    for key, html in pages.items():
        if key.startswith("property-") and key != "property-new":
            continue
        names = set(_editable(_inventory(html)))
        if key == "properties":
            names -= INLINE_TIMING_0098
        assert not names & GUEST_LINK_AND_AUTOMATION, (key, names & GUEST_LINK_AND_AUTOMATION)
        assert not names & FEE_FIELDS, (key, names & FEE_FIELDS)
    # The fee list only links to the one editor (Set up for the rate-0 property);
    # the report's forms are decisions and manual records, never fee configuration.
    assert f"/apartments/{acc['p2']}?view=settings&amp;section=reporting" in pages["fees"]
    # 0098: the Properties summary posts only to the scoped timing route and
    # the existing regenerate-pin route; no other editor lives there.
    listing = pages["properties"]
    start = listing.index('id="property-summaries"')
    summary = listing[start:listing.index("</section>", start)]
    actions = set(re.findall(r'<form[^>]*action="/apartments/\d+/([a-z-]+)"', summary))
    assert actions == {"automation-timing", "regenerate-pin"}, actions
    assert "<textarea" not in summary and len(re.findall(r"<form", summary)) == 2 * summary.count("data-summary-row")


def test_one_shared_entity_editor_owns_business_and_invoice_fields(acc):
    pages = _pages(acc)
    editor = _inventory(pages["business-editor"])
    business = [f for f in editor.forms if f["action"] == f"/entities/{acc['e1']}"]
    invoice = [f for f in editor.forms if f["action"] == f"/entities/{acc['e1']}/invoice"]
    assert len(business) == 1 and len(invoice) == 1, [f["action"] for f in editor.forms]
    for name in BUSINESS_FIELDS:
        assert business[0]["names"].count(name) == 1, ("business", name)
    for name in INVOICE_DETAIL_FIELDS:
        assert invoice[0]["names"].count(name) == 1, ("invoice", name)
        assert name not in business[0]["names"], ("invoice field in business form", name)
    # 0076 decision 1: the invoice IČO is a lookup-only input; the saved IČO is the business one.
    assert invoice[0]["names"].count("ico") <= 1
    shared = BUSINESS_FIELDS | INVOICE_DETAIL_FIELDS
    for key, html in pages.items():
        if key in ("business-editor", "businesses"):
            continue
        names = set(_editable(_inventory(html)))
        # The invoice builder has buyer_* fields only; the supplier is a select.
        stray = sorted((names & shared) - {"name"} if key == "settings" else names & shared)
        assert not stray, f"{key}: entity field copied outside the entity editor: {stray}"
    # The issued invoice shows its own frozen snapshot, never an editor.
    detail = _inventory(pages["invoice-detail"])
    assert not set(_editable(detail)) & shared


def test_one_many_no_and_archived_properties_on_hubs_and_search(acc):
    many = acc["client"]
    # 0101: /guest-links stays (lifecycle e-mails link it); /automation is gone.
    assert many.get("/guest-links", follow_redirects=False).headers["location"] == "/apartments#property-summaries"
    one = _client(acc["one"]["username"])
    # The archived second property does not count: one active property opens its group.
    pid = acc["one"]["property"]
    assert one.get("/guest-links", follow_redirects=False).headers["location"] == \
        f"/apartments/{pid}?view=settings&section=guests#communication"
    none = _client(acc["none"]["username"])
    assert none.get("/guest-links", follow_redirects=False).headers["location"] == "/apartments#property-summaries"
    # Search follows the same rule and never lists an archived property.
    def palette(client):
        return client.get("/api/command-palette").json()["items"]
    one_urls = {i.get("url") for i in palette(one)}
    assert f"/apartments/{pid}?view=settings&section=guests#communication" in one_urls
    assert f"/apartments/{acc['one']['archived']}" not in one_urls
    many_items = palette(many)
    many_urls = {i.get("url") for i in many_items}
    assert "/apartments#property-summaries" in many_urls
    assert f"/apartments/{acc['p3']}" not in many_urls
    assert "/smart-locks" in many_urls  # connected lock account
    assert "/smart-locks" not in {i.get("url") for i in palette(none)}
    # Properties list: active rows, archived listed separately with Restore.
    listing = many.get("/apartments?lang=en").text
    assert f'/apartments/{acc["p3"]}/unarchive' in listing
    summary = listing[listing.index('id="property-summaries"'):]
    summary = summary[:summary.index("</section>")]
    assert "Archived Gamma" not in summary and "Studio Beta" in summary
    empty = none.get("/apartments?lang=en").text
    # No business yet: the empty state points at the business first (0078), no summary.
    assert "/entities" in empty and 'id="property-summaries"' not in empty
    # The archived property still opens (read-only lifecycle) with Restore at the bottom of Property information.
    archived = many.get(f"/apartments/{acc['p3']}?view=settings&section=property&lang=en")
    assert archived.status_code == 200 and f"/apartments/{acc['p3']}/unarchive" in archived.text


def test_removed_old_links_are_gone_and_write_nothing(acc):
    """0101 (owner, 2026-10-13): the old adapters are removed, not redirected."""
    client, p1, e1 = acc["client"], acc["p1"], acc["e1"]
    for path in (
        f"/invoices/settings?entity={e1}", "/invoices/settings", f"/stay-fees/{p1}/setup?month={acc['month']}",
        "/setup", f"/setup/address?apartment={p1}", "/automation", f"/apartments/{p1}/ws-request.txt",
    ):
        assert client.get(path, follow_redirects=False).status_code == 404, path
    before = dict(db.query_one("SELECT * FROM legal_entity WHERE id = ?", (e1,)))
    refused = client.post("/invoices/settings", data={
        "legal_entity_id": str(e1), "account_prefix": "", "account_number": "not-an-account",
        "account_bank": "0100", "invoice_prefix": "ZZ", "_invoice_account_existing": "",
    }, follow_redirects=False)
    assert refused.status_code in (404, 405)
    assert dict(db.query_one("SELECT * FROM legal_entity WHERE id = ?", (e1,))) == before
    fee_refused = client.post(f"/stay-fees/{p1}/setup", data={
        "stay_fee_rate_czk": "40", "stay_fee_cadence": "monthly",
    }, follow_redirects=False)
    assert fee_refused.status_code in (404, 405)
    row = db.query_one("SELECT stay_fee_rate_czk, stay_fee_council_iban FROM apartment WHERE id = ?", (p1,))
    assert row["stay_fee_rate_czk"] == 30 and row["stay_fee_council_iban"] == "CZ6508000000192000145399"


def test_issued_invoice_snapshot_survives_a_shared_business_edit(acc):
    client, e1, invoice = acc["client"], acc["e1"], acc["invoice"]
    before = dict(db.query_one("SELECT * FROM invoice WHERE id = ?", (invoice,)))
    entity = dict(db.query_one("SELECT * FROM legal_entity WHERE id = ?", (e1,)))
    response = client.post(f"/entities/{e1}", data={
        "name": entity["name"], "seat": "Praha 2 (moved)", "ico": entity["ico"], "dic": "",
        "contact_email": entity["contact_email"], "contact_phone": "+420 600 000 084",
        "next": f"/apartments/{acc['p1']}",
    }, files={"signature_file": ("", b"", "application/octet-stream")}, follow_redirects=False)
    assert response.status_code == 303, response.text
    assert response.headers["location"].startswith(f"/apartments/{acc['p1']}")
    try:
        assert db.query_one("SELECT seat FROM legal_entity WHERE id = ?", (e1,))["seat"] == "Praha 2 (moved)"
        assert dict(db.query_one("SELECT * FROM invoice WHERE id = ?", (invoice,))) == before
        # Both properties point at the one shared business editor.
        for pid in (acc["p1"], acc["p2"]):
            page = client.get(f"/apartments/{pid}?lang=en").text
            assert LONG_ENTITY in page and f"/entities?edit={e1}&amp;next=/apartments/{pid}" in page, pid
    finally:
        db.execute("UPDATE legal_entity SET seat = ?, contact_phone = ? WHERE id = ?",
                   (entity["seat"], entity["contact_phone"], e1))


# --- browser ------------------------------------------------------------------


@pytest.fixture(scope="module")
def base(acc):
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("the acceptance test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def _context(browser, base, cookie, *, width=1280, height=900, collapsed=False, **kwargs):
    context = browser.new_context(viewport={"width": width, "height": height}, **kwargs)
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": base + "/"}])
    context.add_init_script(
        "try { localStorage.setItem('ubyhost-sidebar-collapsed', '%s'); } catch (e) {}" % ("1" if collapsed else "0")
    )
    return context


def _settle(page):
    page.wait_for_load_state("load")
    page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")


def _dismiss_prompt(page):
    later = page.locator("button[data-security-prompt-later]")
    if later.count() and later.first.is_visible():
        later.first.click()


_GEOMETRY_JS = """() => {
  const vw = document.documentElement.clientWidth;
  const compact = window.innerWidth <= 960;
  const navOpen = document.body.classList.contains('nav-open');
  const bad = [];
  let scrollers = 0, checked = 0;
  const sel = 'a[href], button, input:not([type=hidden]), select, textarea, summary, [role=switch]';
  for (const el of document.querySelectorAll(sel)) {
    if (el.closest('[inert], .sr-only, [hidden], dialog:not([open]), .skip-link, .nav-backdrop')) continue;
    if (compact && !navOpen && el.closest('#app-sidebar')) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || Number(cs.opacity) === 0) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) continue;
    let p = el.parentElement, scroller = null, clipper = null;
    while (p && p !== document.body) {
      const ps = getComputedStyle(p);
      if ((ps.overflowX === 'auto' || ps.overflowX === 'scroll') && p.scrollWidth > p.clientWidth + 1) { scroller = p; break; }
      if (!clipper && (ps.overflowX === 'hidden' || ps.overflowX === 'clip')) clipper = p;
      p = p.parentElement;
    }
    if (scroller) { scrollers += 1; continue; }
    checked += 1;
    let reason = '';
    if (r.right > vw + 1) reason = 'past right edge';
    else if (r.left < -1) reason = 'past left edge';
    else if (clipper) {
      const c = clipper.getBoundingClientRect();
      if (r.right > c.right + 1 || r.left < c.left - 1) reason = 'clipped by ' + (clipper.className || clipper.tagName);
    }
    if (reason) bad.push({reason, tag: el.tagName, id: el.id, cls: String(el.className).slice(0, 60),
                         text: (el.innerText || el.value || el.name || '').trim().slice(0, 40),
                         left: Math.round(r.left), right: Math.round(r.right), vw});
  }
  // Diagnostics only: the innermost elements that stick out past the viewport.
  const wide = [];
  if (document.documentElement.scrollWidth > vw + 1) {
    for (const el of document.body.querySelectorAll('*')) {
      const r = el.getBoundingClientRect();
      if (r.right <= vw + 1 || !r.width) continue;
      if ([...el.children].some(child => child.getBoundingClientRect().right > vw + 1)) continue;
      wide.push({tag: el.tagName, cls: String(el.className).slice(0, 60), text: (el.innerText || '').trim().slice(0, 40),
                 right: Math.round(r.right), parent: String(el.parentElement && el.parentElement.className).slice(0, 40)});
      if (wide.length >= 4) break;
    }
  }
  const lane = document.querySelector('main.wrap.with-sidebar, main');
  return {vw, scrollWidth: document.documentElement.scrollWidth, bad, wide, scrollers, checked,
          collapsed: document.body.classList.contains('sidebar-collapsed'),
          lane: lane ? Math.round(lane.getBoundingClientRect().width) : null};
}"""


def _shot(page, name):
    if CAPTURE:
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(EVIDENCE / f"{name}.jpg"), full_page=True, type="jpeg", quality=55)


def test_every_page_family_fits_every_width_language_and_rail_state(acc, base):
    """No horizontal overflow and no clipped control, 360-2048 px, EN/CS, rail expanded/collapsed."""
    measurements = []
    failures = []
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        runs = [(lang, width, False) for lang in ("en", "cs") for width in WIDTHS]
        runs += [(lang, width, True) for lang in ("en", "cs") for width in RAIL_WIDTHS]
        for lang, width, collapsed in runs:
            context = _context(browser, base, acc["cookie"], width=width, height=900, collapsed=collapsed)
            page = context.new_page()
            for key in FAMILIES:
                response = page.goto(base + _with_lang(_url(acc, key), lang))
                assert response and response.status == 200, (key, lang, width)
                _settle(page)
                _dismiss_prompt(page)
                result = page.evaluate(_GEOMETRY_JS)
                if width in RAIL_WIDTHS:
                    assert result["collapsed"] == collapsed, (key, width, collapsed)
                measurements.append({"family": key, "lang": lang, "width": width,
                                     "rail": "collapsed" if collapsed else ("expanded" if width > 960 else "drawer"),
                                     "scrollWidth": result["scrollWidth"], "lane": result["lane"],
                                     "controls": result["checked"], "inScroller": result["scrollers"],
                                     "bad": len(result["bad"])})
                if result["scrollWidth"] > result["vw"] + 1 or result["bad"]:
                    failures.append((key, lang, width, collapsed, result["scrollWidth"], result["bad"][:4], result["wide"]))
                if not collapsed and width in CAPTURE_WIDTHS and key in CAPTURE_FAMILIES:
                    _shot(page, f"{key}-{width}-{lang}")
            context.close()
        browser.close()
    if CAPTURE:
        (EVIDENCE / "measurements.json").write_text(json.dumps(measurements, indent=1, ensure_ascii=False) + "\n")
    assert not failures, json.dumps(failures, ensure_ascii=False, indent=1)


def test_page_families_through_rail_cards_search_and_back(acc, base):
    p1, e1 = acc["p1"], acc["e1"]
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for lang, search_term in (("en", "Stay fees"), ("cs", "Poplatky")):
            page = _context(browser, base, acc["cookie"]).new_page()
            page.goto(f"{base}/?lang={lang}")
            _settle(page)
            _dismiss_prompt(page)
            # Rail -> Properties -> Open the long-named property.
            page.locator('.sidebar-nav a[href="/apartments"]').click()
            page.wait_for_url(re.compile(r"/apartments(\?.*)?$"))
            page.locator(f'a.btn[href^="/apartments/{p1}"]').first.click()
            page.wait_for_url(re.compile(rf"/apartments/{p1}"))
            _settle(page)
            assert page.locator(".property-tabs").is_visible()
            # Tabs in place, then the business card opens the one entity editor.
            page.locator('.property-tabs a[data-property-tab="settings"]').click()
            page.locator('[data-property-view="settings"].is-active').wait_for()
            page.locator('.property-tabs a[data-property-tab="overview"]').click()
            page.locator(f'[data-property-view="overview"] a[href^="/entities?edit={e1}"]').first.click()
            page.wait_for_url(re.compile(rf"/entities\?edit={e1}"))
            assert page.locator("#entity-business").is_visible()
            # Back returns to the property overview.
            page.go_back()
            page.wait_for_url(re.compile(rf"/apartments/{p1}"))
            _settle(page)
            assert page.locator('[data-property-view="overview"]').is_visible()
            # Search -> Stay fees -> report period -> Back.
            page.locator(".command-trigger").click()
            page.locator("[data-command-input]").fill(search_term)
            page.wait_for_timeout(150)
            page.keyboard.press("Enter")
            page.wait_for_url(re.compile(r"/stay-fees(\?.*)?$"))
            _settle(page)
            page.locator(f'a[href^="/stay-fees/{p1}?month="]').first.click()
            page.wait_for_url(re.compile(rf"/stay-fees/{p1}\?month="))
            page.go_back()
            page.wait_for_url(re.compile(r"/stay-fees(\?.*)?$"))
            # Rail -> Invoices -> issued invoice -> its stay -> Back.
            page.locator('.sidebar-nav a[href="/invoices"]').click()
            page.wait_for_url(re.compile(r"/invoices(\?.*)?$"))
            page.goto(f"{base}/invoices/{acc['invoice']}?lang={lang}")
            page.locator(f'a[href^="/reservations/{acc["stay"]}"]').first.click()
            page.wait_for_url(re.compile(rf"/reservations/{acc['stay']}"))
            page.go_back()
            page.wait_for_url(re.compile(rf"/invoices/{acc['invoice']}"))
            # Account menu reaches Settings; the archive and guide stay reachable.
            for path in ("/settings", "/settings/archived", "/guide", "/housebook", "/submissions"):
                response = page.goto(f"{base}{path}?lang={lang}")
                assert response.status == 200, path
            page.context.close()
        browser.close()


def test_keyboard_reaches_rail_tabs_and_editor_with_visible_focus(acc, base):
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        page = _context(browser, base, acc["cookie"]).new_page()
        page.goto(f"{base}/apartments/{acc['p1']}?view=settings&section=guests&lang=cs")
        _settle(page)
        _dismiss_prompt(page)
        # Read the settled focus style, not a frame of its transition.
        page.add_style_tag(content="*, *::before, *::after { transition: none !important; }")
        page.evaluate("() => { document.activeElement && document.activeElement.blur(); window.scrollTo(0, 0); }")
        page.keyboard.press("Tab")
        assert page.evaluate("() => document.activeElement.classList.contains('skip-link')")
        seen, unseen_focus = set(), []
        for _ in range(60):
            page.keyboard.press("Tab")
            info = page.evaluate("""() => {
              const el = document.activeElement;
              const r = el.getBoundingClientRect();
              const cs = getComputedStyle(el);
              const ring = (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0) || cs.boxShadow !== 'none';
              return {tag: el.tagName, href: el.getAttribute('href') || '', tab: el.getAttribute('data-property-tab') || '',
                      id: el.id, ring, inView: r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth};
            }""")
            if info["tag"] == "BODY":
                break  # past the last control: the browser's own UI takes focus
            seen.add(info["href"].split("?")[0] or info["tab"] or info["id"])
            seen.add(info["href"])
            if not (info["ring"] and info["inView"]):
                unseen_focus.append(info)
        assert {"/", "/reservations", "/apartments", "/invoices", "/stay-fees"} <= seen, seen
        for view in ("overview", "bookings", "settings"):
            assert f"/apartments/{acc['p1']}?view={view}" in seen, (view, seen)
        assert {"permalink_pin", "guest_message"} <= seen, seen
        assert not unseen_focus, unseen_focus[:5]
        # 0096: the door-code switch is in its own Door lock group, one sub-nav link away.
        assert f"/apartments/{acc['p1']}?view=settings&section=lock" in seen, seen
        page.goto(f"{base}/apartments/{acc['p1']}?view=settings&section=lock&lang=cs")
        _settle(page)
        _dismiss_prompt(page)
        page.add_style_tag(content="*, *::before, *::after { transition: none !important; }")
        page.evaluate("() => { document.activeElement && document.activeElement.blur(); window.scrollTo(0, 0); }")
        reached = None
        for _ in range(60):
            page.keyboard.press("Tab")
            info = page.evaluate("""() => { const el = document.activeElement; const r = el.getBoundingClientRect();
              const cs = getComputedStyle(el);
              return {id: el.id, tag: el.tagName, ring: (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0) || cs.boxShadow !== 'none',
                      inView: r.bottom > 0 && r.top < innerHeight}; }""")
            if info["id"] == "door_codes" or info["tag"] == "BODY":
                reached = info
                break
        assert reached and reached["id"] == "door_codes" and reached["inView"] and reached["ring"], reached
        # Search opens from the keyboard and Escape returns focus to the trigger.
        page.locator(".command-trigger").focus()
        page.keyboard.press("Enter")
        page.locator("#command-dialog[open]").wait_for()
        page.keyboard.press("Escape")
        page.wait_for_function("() => !document.getElementById('command-dialog').open")
        assert page.evaluate("() => document.activeElement.classList.contains('command-trigger')")
        browser.close()


def test_without_javascript_tabs_reload_and_the_shared_editors_save(acc, base):
    p1, e1 = acc["p1"], acc["e1"]
    original = dict(db.query_one("SELECT contact_phone FROM legal_entity WHERE id = ?", (e1,)))
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = _context(browser, base, acc["cookie"], java_script_enabled=False)
        page = context.new_page()
        page.goto(f"{base}/apartments/{p1}?lang=en")
        page.locator('.property-tabs a[data-property-tab="settings"]').click()
        page.wait_for_url(re.compile(r"view=settings"))
        assert page.locator("#internal_name").is_visible()
        # 0101: links carry ?view=&section=; the hash only scrolls.
        page.goto(f"{base}/apartments/{p1}?view=settings&section=reporting&lang=en#ubyport")
        assert page.locator("#ubyport").is_visible()
        # The business editor saves without JavaScript and returns to the property.
        page.goto(f"{base}/entities?edit={e1}&next=/apartments/{p1}&lang=en")
        page.locator('#entity-business input[name="contact_phone"]').fill("+420 600 084 084")
        page.locator('#entity-business button[type="submit"]').last.click()
        page.wait_for_load_state()
        assert f"/apartments/{p1}" in page.url, page.url
        assert db.query_one("SELECT contact_phone FROM legal_entity WHERE id = ?", (e1,))["contact_phone"] == "+420 600 084 084"
        # Invoice details too.
        page.goto(f"{base}/entities?edit={e1}&next=/apartments/{p1}&lang=en")
        page.locator('#entity-invoice input[name="invoice_due_days"]').fill("21")
        page.locator('#entity-invoice button[type="submit"]').last.click()
        page.wait_for_load_state()
        assert db.query_one("SELECT invoice_due_days FROM legal_entity WHERE id = ?", (e1,))["invoice_due_days"] == 21
        # The login form is a plain POST with its own CSRF field.
        anonymous = browser.new_context(java_script_enabled=False).new_page()
        anonymous.goto(f"{base}/login?lang=cs")
        login = anonymous.locator('form[method="post"]').first
        assert login.locator('input[name="_csrf"]').count() == 1
        context.close()
        browser.close()
    db.execute("UPDATE legal_entity SET contact_phone = ?, invoice_due_days = 14 WHERE id = ?",
               (original["contact_phone"], e1))
