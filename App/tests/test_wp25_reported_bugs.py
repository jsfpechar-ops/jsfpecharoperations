"""WP25: the owner's reported bugs on the house book, guest and report pages.

* The house book keeps every word whole and truncates the property name with
  the full name in a tooltip, inside a sideways-scrolling panel.
* A filed guest (sent by UbyHost or filed by hand) shows one "Download signed
  form" button, a read-only signature with no Clear, and disabled reported
  fields; the save route refuses a change to any of them even when the form
  is posted by hand, and still saves what never went to the police.
* The report page offers "Download Doručenka (PDF)" when UbyPort sent one and
  says so when it did not; the outcome accent follows the outcome level.
"""
from __future__ import annotations

import base64
import re

import pytest
from fastapi.testclient import TestClient

from app import auth, db, demo, host_i18n
from app.main import app

PASSWORD = "Secure-Password-123"
OTHER_SIGNATURE = "data:image/png;base64," + base64.b64encode(base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGMAAQAABQAB"
    "DQottAAAAABJRU5ErkJggg=="
)).decode()
LONG_PROPERTY = "Downtown Comfort Apartment with a very long name"


def _cleanup():
    for row in db.query("SELECT id FROM user_account WHERE username LIKE 'wp25-%'"):
        user_id = row["id"]
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        for apartment in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (user_id,)):
            apartment_id = apartment["id"]
            db.execute(
                "DELETE FROM guest WHERE reservation_id IN "
                "(SELECT id FROM reservation WHERE apartment_id = ?)",
                (apartment_id,),
            )
            db.execute("DELETE FROM submission WHERE apartment_id = ?", (apartment_id,))
            db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment_id,))
            db.execute("DELETE FROM apartment WHERE id = ?", (apartment_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


@pytest.fixture()
def seeded():
    db.init_db()
    _cleanup()
    owner = auth.create_account("wp25-host", PASSWORD, "WP25 Host", must_change_password=False)
    now = db.utcnow()
    entity = db.insert("legal_entity", {"name": "WP25 entity", "owner_user_id": owner, "created_at": now})
    apartment = db.insert(
        "apartment",
        {
            "legal_entity_id": entity,
            "owner_user_id": owner,
            "internal_name": LONG_PROPERTY,
            "permalink_token": "wp25tok",
            "automation_mode": "manual",
            "default_purpose": "10",
            "active": 1,
            "created_at": now,
        },
    )
    reservation = db.insert(
        "reservation",
        {
            "apartment_id": apartment,
            "uid": "wp25-stay",
            "date_from": "2026-01-01",
            "date_to": "2026-01-03",
            "status": "active",
            "declared_guests": 3,
            "created_at": now,
            "updated_at": now,
        },
    )

    def guest(surname, **extra):
        return db.insert(
            "guest",
            {
                "reservation_id": reservation,
                "surname": surname,
                "first_name": "JANE",
                "birth_date": "01011990",
                "nationality": "GBR",
                "doc_number": "PA1234567",
                "res_street": "Baker Street 221B",
                "res_city": "London",
                "res_country": "GBR",
                "purpose": "10",
                "entered_by": "guest",
                "signature_png": demo.DEMO_SIGNATURE,
                "signed_at": "2026-01-01T10:00:00+00:00",
                "created_at": now,
                "updated_at": now,
                **extra,
            },
        )

    filed = guest("FILED", submit_state="sent", submitted_at=now)
    by_hand = guest("BYHAND", submit_state="sent", manual_filed_at=now)
    pending = guest("PENDING", submit_state="pending")
    with_pdf = db.insert(
        "submission",
        {
            "apartment_id": apartment,
            "created_at": now,
            "finished_at": now,
            "state": "ok",
            "guest_ids": f"[{filed}]",
            "receipt_pdf": base64.b64encode(b"%PDF-1.4 receipt").decode(),
            "pseudo_stamp": "A94208F8-DA48-4F07-BBF9-95CB757B41F7",
        },
    )
    without_pdf = db.insert(
        "submission",
        {
            "apartment_id": apartment,
            "created_at": now,
            "finished_at": now,
            "state": "ok",
            "guest_ids": f"[{filed}]",
            "pseudo_stamp": "B94208F8-DA48-4F07-BBF9-95CB757B41F7",
        },
    )
    rejected = db.insert(
        "submission",
        {
            "apartment_id": apartment,
            "created_at": now,
            "finished_at": now,
            "state": "error",
            "guest_ids": f"[{pending}]",
            "record_errors": '[";101;"]',
        },
    )
    db.update("guest", filed, {"submission_id": with_pdf})
    yield {
        "owner": owner,
        "reservation": reservation,
        "filed": filed,
        "by_hand": by_hand,
        "pending": pending,
        "with_pdf": with_pdf,
        "without_pdf": without_pdf,
        "rejected": rejected,
    }
    _cleanup()


@pytest.fixture()
def client(seeded):
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"username": "wp25-host", "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client


def _form_from_page(guest) -> dict:
    """What an old tab of the pre-WP25 form would post back: every field."""
    return {
        "surname": guest["surname"],
        "first_name": guest["first_name"],
        "birth_date": "01.01.1990",
        "nationality": guest["nationality"],
        "doc_type": "pas",
        "doc_number": guest["doc_number"],
        "visa_number": "",
        "res_street": guest["res_street"],
        "res_city": guest["res_city"],
        "res_country": guest["res_country"],
        "stay_from": "2026-01-01",
        "stay_to": "2026-01-03",
        "purpose": guest["purpose"],
        "note": "",
        "signature": "",
    }


def _guest(guest_id):
    return db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))


# --- guest page ------------------------------------------------------------

def test_download_signed_form_appears_once(client, seeded):
    for key in ("filed", "pending"):
        page = client.get(f"/guests/{seeded[key]}?lang=en").text
        assert page.count(f'href="/guests/{seeded[key]}/form.pdf"') == 1


@pytest.mark.parametrize("key", ["filed", "by_hand"])
def test_filed_guest_shows_signature_read_only(client, seeded, key):
    page = client.get(f"/guests/{seeded[key]}?lang=en").text
    en = host_i18n.STRINGS["en"]
    assert 'id="sig-clear"' not in page
    assert 'id="sig-canvas"' not in page
    assert 'name="signature"' not in page
    assert 'class="signature-saved"' in page
    assert "Signed on" in page
    assert en["guest.admin.banner.sent_help"] in page
    for field in ("surname", "first_name", "birth_date", "doc_number", "res_city", "stay_from", "note"):
        assert re.search(rf'id="{field}" name="{field}" disabled', page), field
    for field in ("nationality", "res_country", "purpose"):
        assert re.search(rf'id="{field}" name="{field}" disabled', page), field
    # Not sent to the police, so still editable.
    assert re.search(r'<select id="doc_type" name="doc_type">', page)


def test_filed_guest_page_in_czech(client, seeded):
    page = client.get(f"/guests/{seeded['filed']}?lang=cs").text
    assert "Podepsáno" in page
    assert host_i18n.STRINGS["cs"]["guest.admin.banner.sent_help"] in page


def test_pending_guest_keeps_the_signature_pad(client, seeded):
    page = client.get(f"/guests/{seeded['pending']}?lang=en").text
    assert 'id="sig-clear"' in page
    assert 'name="signature"' in page
    assert ' disabled aria-describedby="filed-lock-note"' not in page


@pytest.mark.parametrize("key", ["filed", "by_hand"])
@pytest.mark.parametrize(
    "change",
    [
        {"surname": "CHANGED"},
        {"doc_number": "ZZ9999999"},
        {"birth_date": "02.02.1991"},
        {"res_city": "Paris"},
        {"stay_to": "2026-01-05"},
        {"note": "added later"},
        {"signature": OTHER_SIGNATURE},
    ],
)
def test_server_refuses_changes_to_a_filed_record(client, seeded, key, change):
    guest_id = seeded[key]
    before = dict(_guest(guest_id))
    form = {**_form_from_page(before), **change}
    response = client.post(f"/guests/{guest_id}", data=form, follow_redirects=False)
    assert response.status_code == 303
    assert "err=" in response.headers["location"]
    after = dict(_guest(guest_id))
    for column in ("surname", "doc_number", "birth_date", "res_city", "stay_to", "note",
                   "signature_png", "signed_at", "submit_state", "updated_at"):
        assert after[column] == before[column], column
    assert db.query_one(
        "SELECT 1 AS x FROM audit WHERE action = 'guest_update_refused_filed' AND detail = ?",
        (f"id={guest_id} by=host",),
    )


def test_filed_record_unchanged_post_saves_only_the_unreported_field(client, seeded):
    guest_id = seeded["filed"]
    before = dict(_guest(guest_id))
    form = {**_form_from_page(before), "doc_type": "op"}
    response = client.post(f"/guests/{guest_id}", data=form, follow_redirects=False)
    assert response.status_code == 303
    assert "msg=" in response.headers["location"]
    after = dict(_guest(guest_id))
    assert after["doc_type"] == "op"
    for column in ("surname", "doc_number", "signature_png", "signed_at", "submit_state",
                   "submission_id", "identity_verified_at"):
        assert after[column] == before[column], column


def test_disabled_form_post_saves_the_document_type(client, seeded):
    """The locked form posts no reported field at all; that is not a change."""
    guest_id = seeded["by_hand"]
    before = dict(_guest(guest_id))
    response = client.post(
        f"/guests/{guest_id}", data={"doc_type": "op"}, follow_redirects=False
    )
    assert "msg=" in response.headers["location"]
    after = dict(_guest(guest_id))
    assert after["doc_type"] == "op"
    assert after["surname"] == before["surname"]
    assert after["manual_filed_at"] == before["manual_filed_at"]


def test_pending_guest_can_still_be_corrected(client, seeded):
    guest_id = seeded["pending"]
    form = {**_form_from_page(dict(_guest(guest_id))), "surname": "CORRECTED"}
    response = client.post(f"/guests/{guest_id}", data=form, follow_redirects=False)
    assert "msg=" in response.headers["location"]
    assert _guest(guest_id)["surname"] == "CORRECTED"


# --- report and stay pages --------------------------------------------------

def test_report_offers_the_doručenka_download(client, seeded):
    page = client.get(f"/submissions/{seeded['with_pdf']}?lang=en").text
    assert f'href="/submissions/{seeded["with_pdf"]}/receipt.pdf">Download Doručenka (PDF)</a>' in page
    assert "data-receipt-missing" not in page
    assert "stay-command-panel outcome-done" in page
    cs = client.get(f"/submissions/{seeded['with_pdf']}?lang=cs").text
    assert "Stáhnout doručenku (PDF)" in cs


def test_report_without_a_pdf_says_so(client, seeded):
    page = client.get(f"/submissions/{seeded['without_pdf']}?lang=en").text
    assert "/receipt.pdf" not in page
    assert host_i18n.STRINGS["en"]["reports.detail.receipt_missing"] in page
    assert "B94208F8-DA48-4F07-BBF9-95CB757B41F7" in page
    cs = client.get(f"/submissions/{seeded['without_pdf']}?lang=cs").text
    assert host_i18n.STRINGS["cs"]["reports.detail.receipt_missing"] in cs


def test_outcome_accent_follows_the_outcome(client, seeded):
    page = client.get(f"/submissions/{seeded['rejected']}?lang=en").text
    assert "stay-command-panel outcome-critical" in page
    assert "data-receipt-missing" not in page


def test_stamp_sits_beside_an_icon_copy_button(client, seeded):
    page = client.get(f"/submissions/{seeded['with_pdf']}?lang=en").text
    assert 'class="metric-value small-value report-stamp-value"' in page
    assert 'data-copy="report-stamp"' in page


def test_report_texts_have_no_em_dash():
    for lang in ("en", "cs"):
        strings = host_i18n.STRINGS[lang]
        for key in ("reports.detail.note_ok", "reports.detail.note_failed",
                    "reports.detail.receipt_elsewhere", "reports.detail.receipt_none",
                    "reports.detail.receipt_missing", "guest.admin.banner.sent_help"):
            assert "—" not in strings[key], (lang, key)


def test_stay_page_offers_the_doručenka(client, seeded):
    # Everyone on the stay filed: the next step is the proof.
    db.execute("DELETE FROM guest WHERE id = ?", (seeded["pending"],))
    db.update("reservation", seeded["reservation"], {"declared_guests": 2})
    page = client.get(f"/reservations/{seeded['reservation']}?lang=en").text
    assert f'href="/submissions/{seeded["with_pdf"]}/receipt.pdf">Download Doručenka (PDF)</a>' in page


# --- house book -------------------------------------------------------------

def test_housebook_truncates_the_property_with_a_tooltip(client, seeded):
    page = client.get("/housebook?lang=en").text
    assert 'class="table-cards housebook-table"' in page
    assert 'class="panel tight scroll-x housebook-scroll"' in page
    assert f'class="property-identity truncate" title="{LONG_PROPERTY}"' in page
    assert 'class="small col-reported"' in page
