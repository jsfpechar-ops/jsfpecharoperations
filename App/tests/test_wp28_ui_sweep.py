"""WP28: rendered-markup checks for the UI bug sweep.

Each test pins one defect found by clicking through the demo workspace, so a
later template change cannot quietly bring it back. Geometry that markup cannot
prove lives in tests/test_wp28_geometry.py.
"""
from __future__ import annotations

import re
import secrets
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import FormData

from app import auth, db, demo, host_i18n, invoices
from tests.conftest import login_as

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"


@pytest.fixture(scope="module")
def world():
    db.init_db()
    username = f"sweep{secrets.token_hex(4)}"
    owner = auth.create_account(f"{username}@example.test", "Sweep Host", role="host", username=username)
    studio = demo.seed(owner)
    assert studio, "the demo seed needs UBYHOST_UBYPORT_ENV=mock"
    loft = db.query_one(
        "SELECT id FROM apartment WHERE owner_user_id = ? AND internal_name = ?", (owner, demo.DEMO_LOFT)
    )["id"]
    entity = db.query_one(
        "SELECT * FROM legal_entity WHERE owner_user_id = ? AND name = ?", (owner, demo.DEMO_ENTITY)
    )
    db.execute(
        "UPDATE legal_entity SET registry_entry = ? WHERE id = ?",
        ("Zapsán v živnostenském rejstříku", entity["id"]),
    )
    entity = db.query_one("SELECT * FROM legal_entity WHERE id = ?", (entity["id"],))
    draft = invoices.build_draft(
        entity,
        FormData([("buyer_name", "Demo Buyer s.r.o."), ("item_description", "Accommodation"),
                  ("item_quantity", "2"), ("item_unit_price", "1500")]),
        "en",
        today=date.today(),
    )
    draft["legal_entity_id"] = entity["id"]
    draft["owner_user_id"] = owner
    invoice = invoices.issue(draft, owner)
    return {"username": username, "owner": owner, "studio": studio, "loft": loft, "invoice": invoice}


@pytest.fixture(scope="module")
def client(world):
    from app.main import app

    with TestClient(app) as test_client:
        response = login_as(test_client, world["username"], follow_redirects=False)
        assert response.status_code == 303
        yield test_client


def _stay(world, apartment, status="active", guests=None):
    rows = db.query(
        "SELECT r.id, (SELECT COUNT(*) FROM guest g WHERE g.reservation_id = r.id) AS n "
        "FROM reservation r WHERE r.apartment_id = ? AND r.status = ? ORDER BY r.date_from",
        (apartment, status),
    )
    for row in rows:
        if guests is None or (row["n"] > 0) == guests:
            return row["id"]
    raise AssertionError("the demo seed has no such stay")


def test_wide_tables_scroll_instead_of_clipping_their_last_column():
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    # .panel.tight (overflow: hidden) outranked .scroll-x and hid row actions.
    assert re.search(r"\.panel\.tight\.scroll-x\s*\{\s*overflow-x:\s*auto;", css)
    host = (STATIC / "host.css").read_text(encoding="utf-8")
    assert ".host-workspace .table-cards td { overflow-wrap: break-word; }" in host
    assert ".table-cards td, .host-workspace .guest-facts dd { overflow-wrap: anywhere" not in host


def test_every_text_like_input_gets_the_field_style():
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    selector = css[css.index("input:not([type]), input[type=text]"):].split("{", 1)[0]
    for kind in ("tel", "datetime-local"):
        assert f"input[type={kind}]" in selector
    assert "input[type=search]:not([data-command-input])" in selector


def test_the_guest_privacy_cookie_table_scrolls_inside_its_card():
    css = (STATIC / "guest.css").read_text(encoding="utf-8")
    assert re.search(r"\.scroll-x\s*\{[^}]*overflow-x:\s*auto", css)


def test_cancelling_an_invoice_asks_first(client, world):
    page = client.get(f"/invoices/{world['invoice']}?lang=en")
    assert page.status_code == 200
    form = re.search(r'<form[^>]*action="/invoices/%d/cancel"[^>]*>' % world["invoice"], page.text, re.S)
    assert form, "the cancel form is missing"
    assert "data-confirm" in form.group(0)
    assert host_i18n.translate("en", "confirm.cancel_invoice") in page.text
    assert "\u2014" not in host_i18n.translate("en", "invoice.cancel_help")


def test_the_property_page_counts_calendars_in_the_right_form(client, world):
    en = client.get(f"/apartments/{world['studio']}?lang=en").text
    assert "<small>1 calendar</small>" in en
    assert "1 calendars" not in en
    assert "Back to apartments" not in en
    cs = client.get(f"/apartments/{world['studio']}?lang=cs").text
    assert "<small>1 kalendář</small>" in cs


def test_the_feed_table_keeps_room_for_remove(client, world):
    page = client.get(f"/apartments/{world['studio']}?lang=en").text
    assert 'class="table-cards feed-table"' in page


def test_automation_button_label_is_capitalised(client):
    page = client.get("/automation?lang=en").text
    buttons = re.findall(r'<a class="btn small" href="/apartments/\d+">([^<]+)</a>', page)
    assert buttons and set(buttons) == {"Full property setup"}


def test_finished_onboarding_shows_skip_once(client):
    page = client.get("/onboarding?lang=en").text
    assert page.count(">Skip setup guidance<") == 1
    assert "share the link below" not in page
    assert "Share the guest link above with your guests." in page


def test_settings_does_not_nest_a_second_data_protection_heading(client):
    page = client.get("/settings?lang=en").text
    assert page.count(">Data protection</h2>") == 1
    assert ">Retention status</h3>" in page
    assert "record(s)" not in page


def test_stay_page_hand_filing_panel_and_verify_button_have_room(client, world):
    stay = _stay(world, world["studio"], guests=True)
    page = client.get(f"/reservations/{stay}?lang=en").text
    if 'id="file-by-hand"' in page:
        assert '<details class="panel" id="file-by-hand">' in page
    assert 'class="inline verify-form' not in page
    # A guest without a document type no longer prints a lone dash before the number.
    assert '<span class="fact-extra">\u2014 </span>' not in page


def test_cancelled_stay_does_not_say_waiting_for_guest(client, world):
    stay = _stay(world, world["loft"], status="cancelled")
    page = client.get(f"/reservations/{stay}?lang=en").text
    reporting = page[page.index('id="reports"'):]
    reporting = reporting[: reporting.index("</section>")]
    assert '<span class="pill grey">Cancelled</span>' in reporting
    assert "Waiting for guest" not in reporting


def test_new_strings_exist_in_both_languages():
    for key in (
        "confirm.cancel_invoice",
        "automation.full_setup_button",
        "apartment.form.calendars_count",
        "apartment.form.calendars_count.one",
        "apartment.form.calendars_count.few",
    ):
        assert key in host_i18n.STRINGS["en"], key
        assert key in host_i18n.STRINGS["cs"], key
        assert host_i18n.STRINGS["cs"][key] != host_i18n.STRINGS["en"][key], key
