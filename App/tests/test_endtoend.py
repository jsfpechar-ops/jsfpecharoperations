"""The whole path, once: calendar -> guest form -> police -> Doručenka.

Nothing here is mocked out inside the application. The only stand-in is the
police service itself, which runs as a real HTTP server in another process.
"""
import base64
import html
import json
import os
import re
from datetime import date, timedelta

# The manual stay created in test 25 and reused by the two tests after it.
MANUAL_STAY = {}

import pytest
import requests
from fastapi.testclient import TestClient

from app import auth, codelists, db, reporting
from app.main import app
from tests.conftest import complete_guest_claim

PASSWORD = "Correct-Horse-Battery-123"

# A one-pixel PNG is enough to stand for a drawn signature.
SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()
PNG_BYTES = base64.b64decode(SIGNATURE.split(",", 1)[1])


def ics_for(start: date, nights: int = 4) -> str:
    end = start + timedelta(days=nights)
    return (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Airbnb Inc//Hosting Calendar 0.8.8//EN\r\n"
        "BEGIN:VEVENT\r\n"
        f"DTSTART;VALUE=DATE:{start:%Y%m%d}\r\n"
        f"DTEND;VALUE=DATE:{end:%Y%m%d}\r\n"
        "UID:e2e-stay-0001@airbnb.com\r\n"
        "SUMMARY:Reserved\r\n"
        "DESCRIPTION:Reservation URL: https://www.airbnb.com/hosting/reservations/details/HME2E1\\n"
        "Phone Number (Last 4 Digits): 0431\r\n"
        "END:VEVENT\r\n"
        "BEGIN:VEVENT\r\n"
        f"DTSTART;VALUE=DATE:{end + timedelta(days=2):%Y%m%d}\r\n"
        f"DTEND;VALUE=DATE:{end + timedelta(days=4):%Y%m%d}\r\n"
        "UID:e2e-block-0002@airbnb.com\r\nSUMMARY:Airbnb (Not available)\r\n"
        "END:VEVENT\r\nEND:VCALENDAR\r\n"
    )


@pytest.fixture(scope="module")
def feed_url(tmp_path_factory):
    """Serve the calendar from a file:// - style local HTTP stub."""
    import http.server
    import socketserver
    import threading

    check_in = date.today() - timedelta(days=1)
    body = ics_for(check_in).encode()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/calendar; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/calendar.ics", check_in
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="module")
def client(mock_ubyport):
    db.init_db()
    account = db.query_one("SELECT * FROM user_account WHERE username = 'e2e-admin'")
    if not account:
        account_id = auth.create_account(
            "e2e-admin", PASSWORD, "End-to-end admin", role="admin",
            must_change_password=False,
        )
    else:
        account_id = account["id"]
    with TestClient(app) as test_client:
        response = test_client.post(
            "/login",
            data={"username": "e2e-admin", "password": PASSWORD},
            follow_redirects=False,
        )
        assert response.status_code == 303
        yield test_client
    db.execute("UPDATE apartment SET owner_user_id = NULL WHERE owner_user_id = ?", (account_id,))
    db.execute("UPDATE legal_entity SET owner_user_id = NULL WHERE owner_user_id = ?", (account_id,))
    db.execute("UPDATE alert SET owner_user_id = NULL WHERE owner_user_id = ?", (account_id,))
    db.execute("UPDATE audit SET owner_user_id = NULL WHERE owner_user_id = ?", (account_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (account_id,))


@pytest.fixture(scope="module")
def host(client):
    """An authenticated administrator browser."""
    return client


def test_01_the_app_opens_onto_the_authenticated_dashboard(host):
    page = host.get("/", follow_redirects=False)
    assert page.status_code == 200
    assert "UbyHost" in page.text
    assert 'action="/logout"' in page.text
    assert host.get("/login", follow_redirects=False).status_code == 303


def test_02_an_empty_install_offers_the_demo(host):
    page = host.get("/")
    assert "Set it once. Welcome every guest calmly." in page.text
    assert 'action="/demo"' in page.text


def test_03_apartment_is_created_with_encrypted_credentials(host):
    host.post("/entities", data={"name": "Josef Novák", "ico": "12345678", "seat": "Praha"})
    entity = db.query_one("SELECT * FROM legal_entity")
    assert entity is not None

    response = host.post(
        "/apartments",
        data={
            "internal_name": "Vinohrady 1",
            "legal_entity_id": str(entity["id"]),
            "uby_idub": "100227887600",
            "uby_mark": "CZGFW",
            "uby_name": "Apartment Vinohrady",
            "uby_contact": "host@example.com",
            "addr_okres": "Praha 2",
            "addr_obec": "Praha",
            "addr_obec_cast": "Vinohrady",
            "addr_street": "Korunní",
            "addr_house_no": "1234",
            "addr_orient_no": "12a",
            "addr_zip": "120 00",
            "uby_ws_user": "UBY-WS12cdef",
            "uby_ws_password": "police-secret",
            "automation_mode": "immediate",
            "default_purpose": "10",
            "permalink_window_days": "3",
            "guest_message": "Welcome — please complete the registration before arrival.",
            "active": "on",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    apartment = db.query_one("SELECT * FROM apartment")
    assert apartment["addr_zip"] == "12000"
    # The password must not be readable in the database file.
    assert apartment["uby_ws_password_enc"]
    assert "police-secret" not in apartment["uby_ws_password_enc"]
    assert db.decrypt_secret(apartment["uby_ws_password_enc"]) == "police-secret"
    assert apartment["permalink_token"]
    assert apartment["guest_message"] == "Welcome — please complete the registration before arrival."


def test_04_connection_test_reaches_the_service(host):
    apartment = db.query_one("SELECT * FROM apartment")
    response = host.post(
        f"/apartments/{apartment['id']}/test-connection", follow_redirects=False
    )
    assert response.status_code == 303
    assert "msg=" in response.headers["location"]
    assert "error" not in response.headers["location"].lower()


def test_05_codelists_are_fetched_and_cached(host):
    apartment = db.query_one("SELECT * FROM apartment")
    host.post(f"/apartments/{apartment['id']}/refresh-codelists", follow_redirects=False)
    cached = db.query("SELECT * FROM codelist")
    assert cached, "no code list was cached"
    kinds = {row["kind"] for row in cached}
    assert codelists.KIND_COUNTRIES in kinds
    assert codelists.KIND_ERRORS in kinds
    assert codelists.last_fetched(codelists.KIND_COUNTRIES)


def test_06_calendar_import_creates_the_stay_and_skips_the_block(host, feed_url):
    url, check_in = feed_url
    apartment = db.query_one("SELECT * FROM apartment")
    response = host.post(
        f"/apartments/{apartment['id']}/feeds",
        data={"url": url, "label": "Airbnb", "own_name": "Airbnb"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    reservations = db.query("SELECT * FROM reservation")
    assert len(reservations) == 1, "the blocked dates should not become a stay"
    stay = reservations[0]
    assert stay["date_from"] == check_in.isoformat()
    assert stay["source"] == "airbnb"
    assert stay["phone_last4"] == "0431"
    assert "HME2E1" in (stay["reservation_url"] or "")


def test_07_resync_is_idempotent(host):
    before = db.query_one("SELECT COUNT(*) AS n FROM reservation")["n"]
    host.post("/sync", follow_redirects=False)
    after = db.query_one("SELECT COUNT(*) AS n FROM reservation")["n"]
    assert before == after


def test_08_dashboard_shows_the_stay_as_awaiting_the_guest(host):
    page = host.get("/")
    assert "Vinohrady 1" in page.text
    stay = db.query_one("SELECT * FROM reservation")
    progress = reporting.reservation_progress(stay)
    assert progress["status"] == "awaiting_guest"
    assert progress["filled"] == 0


def permalink(reservation=None):
    apartment = db.query_one("SELECT * FROM apartment")
    stay = reservation or db.query_one("SELECT * FROM reservation")
    return f"/l/{apartment['permalink_token']}/{stay['id']}"


def test_09_guest_opens_the_link_and_declares_the_party(client):
    apartment = db.query_one("SELECT * FROM apartment")
    stay = db.query_one("SELECT * FROM reservation")

    guest_browser = TestClient(app)
    landing = guest_browser.get(f"/l/{apartment['permalink_token']}", follow_redirects=True)
    assert landing.status_code == 200

    complete_guest_claim(
        guest_browser,
        apartment["permalink_token"],
        stay["id"],
        party_size=2,
    )
    assert db.query_one("SELECT * FROM reservation")["declared_guests"] == 2


def test_10_unknown_token_gives_nothing_away(client):
    response = client.get("/l/ZZZZZZZZZZ", follow_redirects=True)
    assert response.status_code == 404
    assert "Vinohrady" not in response.text


def guest_form_data(**overrides):
    data = {
        "surname": "Smith",
        "first_name": "John Paul",
        "birth_date": "1.1.1990",
        "nationality": "GBR",
        "doc_number": "P1234567",
        "res_street": "Baker Street 221B",
        "res_city": "London",
        "res_country": "GBR",
        "purpose": "10",
        "signature": SIGNATURE,
        "legal_ack": "1",
    }
    data.update(overrides)
    return data


def passport_files(nationality: str = "GBR"):
    if nationality == "CZE":
        return None
    return {"passport_photo": ("passport.png", PNG_BYTES, "image/png")}


def save_guest_form(browser, stay, host=None, verify: bool = True, **overrides):
    apartment = db.query_one("SELECT * FROM apartment")
    party = stay["declared_guests"] or 2
    if overrides.get("party_size"):
        party = int(overrides["party_size"])
    complete_guest_claim(
        browser,
        apartment["permalink_token"],
        stay["id"],
        party_size=int(party),
    )
    nationality = overrides.get("nationality", guest_form_data()["nationality"])
    data = guest_form_data(**overrides)
    kwargs = {"data": data, "follow_redirects": False}
    files = passport_files(nationality)
    if files:
        kwargs["files"] = files
    response = browser.post(permalink(stay) + "/save", **kwargs)
    if verify and host and nationality != "CZE" and response.status_code == 303:
        guest = db.query_one("SELECT * FROM guest ORDER BY id DESC")
        host.post(
            f"/guests/{guest['id']}/verify-identity",
            data={"return_to": f"/guests/{guest['id']}"},
            follow_redirects=False,
        )
    return response


def host_verifies_guest(host, guest_id: int) -> None:
    host.post(
        f"/guests/{guest_id}/verify-identity",
        data={"return_to": f"/guests/{guest_id}"},
        follow_redirects=False,
    )


def test_12_incomplete_form_is_refused_before_it_reaches_the_police(client):
    stay = db.query_one("SELECT * FROM reservation")
    apartment = db.query_one("SELECT * FROM apartment")
    complete_guest_claim(client, apartment["permalink_token"], stay["id"], party_size=2)
    response = client.post(
        permalink(stay) + "/save", data=guest_form_data(doc_number="", signature="")
    )
    assert response.status_code == 422
    assert not db.query("SELECT * FROM guest")


def test_13_completed_party_is_reported_without_passport_verification(client, host):
    stay = db.query_one("SELECT * FROM reservation")
    db.update(
        "reservation",
        stay["id"],
        {"declared_guests": 1, "registration_completed_at": None},
    )
    stay = db.query_one("SELECT * FROM reservation WHERE id = ?", (stay["id"],))
    guest_browser = TestClient(app)
    response = save_guest_form(guest_browser, stay, host=host, verify=False)
    assert response.status_code == 303, response.text

    guest = db.query_one("SELECT * FROM guest ORDER BY id DESC")
    assert guest["surname"] == "SMITH", "the name must be normalised for the police"
    assert guest["birth_date"] == "01011990"
    assert guest["signature_png"].startswith("data:image/")
    assert guest["signed_at"]
    assert guest["is_lead"] == 1
    assert not guest["identity_verified_at"]

    # Immediate mode sends when the declared party is complete; verification
    # remains an independent, explicit host action.
    assert guest["submit_state"] == reporting.SENT, guest["last_errors"]
    assert guest["submitted_at"], "rule 10.5(3) requires the time of the successful notification"

    submission = db.query_one("SELECT * FROM submission ORDER BY id DESC")
    assert submission["state"] == "ok", submission["error_text"]
    assert submission["pseudo_stamp"], "the pseudo-stamp identifies the transmission"
    assert json.loads(submission["guest_ids"]) == [guest["id"]]


def test_14_the_receipt_is_a_real_pdf_the_host_can_save(host):
    submission = db.query_one("SELECT * FROM submission ORDER BY id DESC")
    response = host.get(f"/submissions/{submission['id']}/receipt.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_15_the_sent_envelope_is_kept_for_evidence(host):
    submission = db.query_one("SELECT * FROM submission ORDER BY id DESC")
    request_xml = host.get(f"/submissions/{submission['id']}/request.xml")
    assert request_xml.status_code == 200
    assert "ZapisUbytovane" in request_xml.text
    assert "SMITH" in request_xml.text
    # The password must never be written into the stored envelope.
    assert "police-secret" not in request_xml.text
    assert host.get(f"/submissions/{submission['id']}/response.xml").status_code == 200


def test_16_an_accepted_record_is_never_resent_automatically(host):
    """Duplicates are refused by the police and count against the host."""
    apartment = db.query_one("SELECT * FROM apartment")
    assert reporting.collect_sendable(apartment["id"]) == []
    before = db.query_one("SELECT COUNT(*) AS n FROM submission")["n"]
    reporting.sweep()
    assert db.query_one("SELECT COUNT(*) AS n FROM submission")["n"] == before


def test_17_a_deliberate_resend_is_rejected_as_a_duplicate(host):
    guest = db.query_one("SELECT * FROM guest ORDER BY id DESC")

    # Without the explicit acknowledgement nothing is sent at all.
    unconfirmed = host.post(f"/guests/{guest['id']}/resend", follow_redirects=False)
    assert unconfirmed.status_code == 303
    assert "err=" in unconfirmed.headers["location"]
    assert db.query_one("SELECT submit_state FROM guest WHERE id = ?", (guest["id"],))[
        "submit_state"
    ] == reporting.SENT

    response = host.post(
        f"/guests/{guest['id']}/resend",
        data={"confirm_duplicate": "on"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    after = db.query_one("SELECT * FROM guest WHERE id = ?", (guest["id"],))
    assert "duplic" in (after["last_errors"] or "").lower()
    # A duplicate means the register already holds the record, so the guest is
    # still reported; the stay must not start looking like a failure.
    assert after["submit_state"] == reporting.SENT
    assert after["submitted_at"]

    submission = db.query_one("SELECT * FROM submission ORDER BY id DESC")
    assert submission["state"] == "error"
    assert db.query_one(
        "SELECT * FROM alert WHERE kind = 'submission_rejected' AND resolved_at IS NULL"
    ), "the host has to learn that the record bounced"


def test_18_a_second_guest_completes_the_party(client, host):
    stay = db.query_one("SELECT * FROM reservation")
    db.update(
        "reservation",
        stay["id"],
        {"declared_guests": 2, "registration_completed_at": None},
    )
    stay = db.query_one("SELECT * FROM reservation WHERE id = ?", (stay["id"],))
    guest_browser = TestClient(app)
    response = save_guest_form(
        guest_browser,
        stay,
        host=host,
        verify=False,
        surname="Smithová",
        first_name="Anna",
        birth_date="15.03.1992",
        doc_number="P7654321",
    )
    assert response.status_code == 303, response.text

    guest = db.query_one("SELECT * FROM guest ORDER BY id DESC")
    assert guest["surname"] == "SMITHOVÁ"
    assert guest["is_lead"] == 0
    assert guest["submit_state"] == reporting.SENT
    assert not guest["identity_verified_at"]

    progress = reporting.reservation_progress(db.query_one("SELECT * FROM reservation"))
    assert progress["filled"] == 2
    assert progress["expected"] == 2
    assert progress["status"] == "reported"


def test_19_a_czech_national_is_house_book_only(client):
    stay = db.query_one("SELECT * FROM reservation")
    guest_browser = TestClient(app)
    complete_guest_claim(
        guest_browser,
        db.query_one("SELECT permalink_token FROM apartment")["permalink_token"],
        stay["id"],
        email="guest@example.test",
        party_size=3,
    )
    response = guest_browser.post(
        permalink(stay) + "/save",
        data=guest_form_data(
            surname="Dvořák",
            first_name="Petr",
            birth_date="20.07.1985",
            nationality="CZE",
            doc_number="123456789",
            res_city="Brno",
            res_country="CZE",
            res_street="Hlavní 5",
        ),
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    guest = db.query_one("SELECT * FROM guest ORDER BY id DESC")
    assert guest["nationality"] == "CZE"
    assert guest["submit_state"] == reporting.NOT_REQUIRED
    assert not guest["submitted_at"]


def test_20_a_guest_only_sees_their_own_entry(client):
    stay = db.query_one("SELECT * FROM reservation")
    stranger = TestClient(app)
    page = stranger.get(permalink(stay))
    # Check-in was yesterday, so the public picker hides the stay; a stranger
    # with no claim cookie must not see another guest's names either way.
    assert page.status_code in {200, 404}
    assert "SMITH" not in page.text.upper().replace("UBYHOST", "")
    assert "DVOŘÁK" not in page.text.upper()


def test_21_registration_pdf_is_produced_per_guest(host):
    guest = db.query_one("SELECT * FROM guest ORDER BY id")
    response = host.get(f"/guests/{guest['id']}/form.pdf")
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")


def test_22_house_book_export_covers_everyone_including_czechs(host, monkeypatch):
    from app import housebook

    page = host.get("/housebook")
    assert page.status_code == 200
    assert "Your legal duty" in page.text

    csv = host.get("/housebook.csv")
    assert csv.status_code == 200
    text = csv.content.decode("utf-8-sig")
    assert text.count("\n") >= 4  # header plus three guests
    assert "SMITH" in text
    assert "DVOŘÁK" in text, "Czech nationals belong in the house book even so"

    zip_response = host.get("/housebook/pdfs.zip")
    assert zip_response.status_code == 200
    assert zip_response.content[:2] == b"PK"

    import tempfile

    rows = housebook.housebook_rows()
    assert rows, "house book should list every guest from earlier tests"
    assert "Export" in html.unescape(page.text)
    assert 'data-csv-export="/housebook.csv"' in page.text
    assert "Download PDF bundle (inspection)" in page.text
    assert "Import existing records" not in page.text
    assert "Download import template" not in page.text
    assert "import-housebook-panel" not in page.text

    stays_page = host.get("/reservations")
    assert stays_page.status_code == 200
    assert 'data-csv-export="/reservations.csv"' in stays_page.text
    assert "Export stays (CSV)" in stays_page.text
    assert "Import stays (CSV)" not in stays_page.text
    assert "import-stays-panel" not in stays_page.text
    assert host.post("/reservations/import").status_code >= 400
    assert host.get("/reservations-sample.csv").status_code == 404
    assert host.post("/housebook/import").status_code == 404
    assert host.get("/housebook-sample.csv").status_code == 404

    fd, path = tempfile.mkstemp(suffix=".zip")
    os.close(fd)
    try:
        count = housebook.build_housebook_pdfs_zip(rows, path)
        assert count == len(rows)
        assert os.path.getsize(path) > 100
    finally:
        os.unlink(path)

    assert len(rows) > 1
    monkeypatch.setattr(housebook, "MAX_INSPECTION_PDFS", 1)
    blocked = host.get("/housebook/pdfs.zip", follow_redirects=False)
    assert blocked.status_code == 303
    from urllib.parse import unquote

    assert "Too many entries" in unquote(blocked.headers["location"])


def test_23_deadline_watch_raises_nothing_once_everyone_is_reported(host):
    reporting.check_deadlines()
    open_alerts = db.query(
        "SELECT * FROM alert WHERE resolved_at IS NULL AND level IN ('critical','warning')"
    )
    kinds = {a["kind"] for a in open_alerts}
    assert "deadline" not in kinds, [dict(a) for a in open_alerts]


def create_manual_stay(host, start: date, nights: int, expected_guests: int) -> int:
    """A direct booking entered by hand, the way a phone reservation arrives."""
    apartment = db.query_one("SELECT * FROM apartment")
    response = host.post(
        "/reservations",
        data={
            "apartment_id": str(apartment["id"]),
            "date_from": start.isoformat(),
            "date_to": (start + timedelta(days=nights)).isoformat(),
            "expected_guests": str(expected_guests),
            "summary": "Direct booking",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return int(re.search(r"/reservations/(\d+)", response.headers["location"]).group(1))


def test_24_an_incomplete_stay_past_the_deadline_raises_an_alert(host):
    reservation_id = create_manual_stay(host, date.today() - timedelta(days=10), 2, 2)
    assert reporting.check_deadlines() >= 1
    alert = db.query_one(
        "SELECT * FROM alert WHERE reservation_id = ? AND resolved_at IS NULL", (reservation_id,)
    )
    assert alert is not None
    assert alert["level"] == "critical"

    page = host.get("/")
    assert "overdue" in page.text.lower()


def test_25_manual_mode_waits_for_the_host(host, mock_ubyport):
    """Automation degree 3: nothing leaves without a click."""
    apartment = db.query_one("SELECT * FROM apartment")
    db.update("apartment", apartment["id"], {"automation_mode": "manual"})
    requests.post(mock_ubyport + "/reset", timeout=5)

    reservation_id = create_manual_stay(host, date.today() - timedelta(days=1), 3, 1)
    MANUAL_STAY["id"] = reservation_id
    guest_browser = TestClient(app)
    complete_guest_claim(
        guest_browser,
        apartment["permalink_token"],
        reservation_id,
        email="marco@example.test",
        party_size=1,
    )
    guest_browser.post(
        f"/l/{apartment['permalink_token']}/{reservation_id}/save",
        data=guest_form_data(
            surname="Rossi",
            first_name="Marco",
            doc_number="YA1122334",
            nationality="ITA",
            res_city="Roma",
            res_country="ITA",
            res_street="Via Roma 1",
        ),
        files=passport_files("ITA"),
        follow_redirects=False,
    )
    guest = db.query_one("SELECT * FROM guest ORDER BY id DESC")
    assert guest["submit_state"] == reporting.PENDING, "manual mode must not send by itself"
    host_verifies_guest(host, guest["id"])
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest["id"],))
    assert guest["submit_state"] == reporting.PENDING, "manual mode still waits for host send"

    reporting.sweep()
    assert db.query_one("SELECT submit_state FROM guest WHERE id = ?", (guest["id"],))[
        "submit_state"
    ] == reporting.PENDING

    response = host.post(f"/reservations/{reservation_id}/submit", follow_redirects=False)
    assert response.status_code == 303
    after = db.query_one("SELECT * FROM guest WHERE id = ?", (guest["id"],))
    assert after["submit_state"] == reporting.SENT, after["last_errors"]


def host_adds_guest(host, reservation_id: int, **overrides) -> int:
    """The host typing a record in themselves, for a guest who never filled the form."""
    data = {
        "surname": "Tester",
        "first_name": "Erik",
        "birth_date": "01.01.1980",
        "nationality": "USA",
        "doc_number": "P9988776",
        "res_street": "Main Street 1",
        "res_city": "Boston",
        "res_country": "USA",
        "purpose": "10",
        "signature": SIGNATURE,
    }
    data.update(overrides)
    response = host.post(
        f"/reservations/{reservation_id}/guests", data=data, follow_redirects=False
    )
    assert response.status_code == 303, response.text
    assert response.headers["location"].startswith(f"/reservations/{reservation_id}")
    guest = db.query_one(
        "SELECT id FROM guest WHERE reservation_id = ? AND entered_by = 'host' ORDER BY id DESC",
        (reservation_id,),
    )
    return int(guest["id"])


def test_26_a_field_error_is_reported_back_as_correctable(host, mock_ubyport):
    """Rule 10.4: an obstacle must reach the host, and the record must be fixable."""
    apartment = db.query_one("SELECT * FROM apartment")
    guest_id = host_adds_guest(host, MANUAL_STAY["id"], surname="Bounced")
    # Plant a document number the police refuse. The app's own checks would
    # normally stop this, so the batch is handed straight to the transport to
    # exercise what happens when the service rejects something anyway.
    db.execute("UPDATE guest SET doc_number = 'BAD' WHERE id = ?", (guest_id,))
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    stay = db.query_one("SELECT * FROM reservation WHERE id = ?", (MANUAL_STAY["id"],))

    result = reporting.submit_batch(apartment, [(guest, stay)], mode="manual")
    assert result["failed"] == 1 and result["submitted"] == 0

    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    assert guest["submit_state"] == reporting.ERROR
    assert guest["last_errors"], "the host must be able to read what went wrong"

    submission = db.query_one("SELECT * FROM submission ORDER BY id DESC")
    detail = host.get(f"/submissions/{submission['id']}")
    assert detail.status_code == 200
    assert "BOUNCED" in detail.text.upper()

    # Correcting the record puts it back in the queue rather than leaving it stuck.
    fixed = host.post(
        f"/guests/{guest_id}",
        data={
            "surname": "Bounced",
            "first_name": "Erik",
            "birth_date": "01.01.1980",
            "nationality": "USA",
            "doc_number": "P5544332",
            "res_street": "Main Street 1",
            "res_city": "Boston",
            "res_country": "USA",
            "purpose": "10",
            "signature": SIGNATURE,
        },
        follow_redirects=False,
    )
    assert fixed.status_code == 303
    assert db.query_one("SELECT submit_state FROM guest WHERE id = ?", (guest_id,))[
        "submit_state"
    ] == reporting.PENDING

    host.post(f"/reservations/{MANUAL_STAY['id']}/submit", follow_redirects=False)
    assert db.query_one("SELECT submit_state FROM guest WHERE id = ?", (guest_id,))[
        "submit_state"
    ] == reporting.SENT


def test_27_transport_failure_keeps_the_record_queued(host, monkeypatch):
    """Rule 10.2(e): a network problem must not lose the queue."""
    from app.ubyport.client import UbyportTransportError

    apartment = db.query_one("SELECT * FROM apartment")
    guest_id = host_adds_guest(
        host, MANUAL_STAY["id"], surname="Offline", doc_number="P1100220"
    )

    def explode(*args, **kwargs):
        raise UbyportTransportError("simulated outage")

    monkeypatch.setattr("app.ubyport.client.UbyportClient.submit", explode)
    reporting.submit_for_apartment(
        apartment["id"], only_guest_ids=[guest_id], mode="manual", ignore_automation=True
    )

    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    assert guest["submit_state"] == reporting.PENDING, "the record must stay in the queue"
    submission = db.query_one("SELECT * FROM submission ORDER BY id DESC")
    assert submission["state"] == "transport_error"
    assert "simulated outage" in submission["error_text"]

    alert = db.query_one(
        "SELECT * FROM alert WHERE kind = 'submission_transport' AND resolved_at IS NULL"
    )
    assert alert is not None, "the host has to be told the police could not be reached"
    assert alert["level"] == "critical"

    # Once the service answers again the queued record goes out and the alert clears.
    monkeypatch.undo()
    reporting.submit_for_apartment(
        apartment["id"], only_guest_ids=[guest_id], mode="manual", ignore_automation=True
    )
    assert db.query_one("SELECT submit_state FROM guest WHERE id = ?", (guest_id,))[
        "submit_state"
    ] == reporting.SENT
    assert not db.query_one(
        "SELECT * FROM alert WHERE kind = 'submission_transport' AND resolved_at IS NULL"
    )


def test_28_the_audit_trail_records_what_happened(host):
    kinds = {row["action"] for row in db.query("SELECT action FROM audit")}
    assert {"apartment_created", "guest_form_saved", "ubyport_submit"} <= kinds
    page = host.get("/settings")
    assert page.status_code == 200
    assert "guest_form_saved" in page.text


def test_29_host_accounts_require_username_and_password(host):
    user_id = auth.create_account(
        "test-admin", PASSWORD, "Test admin", role="admin", must_change_password=False
    )
    try:
        stranger = TestClient(app)
        assert stranger.get("/", follow_redirects=False).status_code == 303
        assert stranger.post(
            "/login", data={"username": "test-admin", "password": "wrong"}
        ).status_code == 401
        assert stranger.post(
            "/login",
            data={"username": "test-admin", "password": PASSWORD},
            follow_redirects=False,
        ).status_code == 303
        assert 'action="/logout"' in stranger.get("/").text

        stored = db.query_one("SELECT password_hash FROM user_account WHERE id = ?", (user_id,))
        assert PASSWORD not in stored["password_hash"]
        assert auth.verify_password(PASSWORD, stored["password_hash"])

        # Guest links do not require a host account.
        apartment = db.query_one("SELECT * FROM apartment")
        assert TestClient(app).get(
            f"/l/{apartment['permalink_token']}", follow_redirects=True
        ).status_code == 200
    finally:
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))
