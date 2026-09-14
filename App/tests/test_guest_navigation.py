"""Guest navigation: picking the wrong stay, then the right one, must never dead-end."""
import base64
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app import db, passport_photos
from app.main import app

SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()
PNG_BYTES = base64.b64decode(SIGNATURE.split(",", 1)[1])
MINIMAL_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 3 3]>>endobj\n"
    b"trailer<</Size 4/Root 1 0 R>>\n"
    b"startxref\n"
    b"149\n"
    b"%%EOF\n"
)

TOKEN = "navflowtoken"


def _form(**overrides):
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
        "party_size": "2",
        "signature": SIGNATURE,
        "legal_ack": "1",
    }
    data.update(overrides)
    return data


def _passport_files(nationality: str = "GBR"):
    if nationality == "CZE":
        return None
    return {"passport_photo": ("passport.png", PNG_BYTES, "image/png")}


def _cleanup():
    apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
    if not apartment:
        return
    db.execute(
        "DELETE FROM guest WHERE reservation_id IN "
        "(SELECT id FROM reservation WHERE apartment_id = ?)",
        (apartment["id"],),
    )
    db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))
    db.execute(
        "DELETE FROM legal_entity WHERE name = ? AND id NOT IN (SELECT legal_entity_id FROM apartment WHERE legal_entity_id IS NOT NULL)",
        ("Nav Test",),
    )


def _make_apartment_with_stays():
    db.init_db()
    _cleanup()
    now = db.utcnow()
    today = date.today()
    entity_id = db.insert("legal_entity", {"name": "Nav Test", "created_at": now})
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Nav apartment",
            "permalink_token": TOKEN,
            "permalink_window_days": 14,
            "default_purpose": "10",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    wrong = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "airbnb",
            "uid": "nav-wrong",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=4)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    right = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "booking",
            "uid": "nav-right",
            "date_from": (today + timedelta(days=1)).isoformat(),
            "date_to": (today + timedelta(days=5)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    return TOKEN, wrong, right


def test_stay_cards_are_links_not_radios():
    token, wrong, right = _make_apartment_with_stays()
    try:
        browser = TestClient(app)
        page = browser.get(f"/l/{token}", follow_redirects=True)
        assert page.status_code == 200
        assert 'type="radio"' not in page.text
        assert f'href="/l/{token}/{wrong}?lang=en"' in page.text
        assert f'href="/l/{token}/{right}?lang=en"' in page.text
        assert "Tap your arrival" in page.text
    finally:
        _cleanup()


def test_tapping_an_empty_stay_opens_the_form():
    token, wrong, _right = _make_apartment_with_stays()
    try:
        browser = TestClient(app)
        page = browser.get(f"/l/{token}/{wrong}", follow_redirects=True)
        assert page.status_code == 200
        assert 'name="surname"' in page.text
        assert "Start with your own details" not in page.text
        assert "Not your dates?" in page.text
    finally:
        _cleanup()


def test_wrong_stay_then_correct_stay_opens_a_fresh_form():
    token, wrong, right = _make_apartment_with_stays()
    try:
        browser = TestClient(app)

        saved = browser.post(
            f"/l/{token}/{wrong}/save",
            data=_form(),
            files=_passport_files(),
            follow_redirects=False,
        )
        assert saved.status_code == 303
        assert f"/{wrong}" in saved.headers["location"]

        picker = browser.get(f"/l/{token}", follow_redirects=True)
        assert "A form was submitted from this device" in picker.text
        assert "You already filled this in" not in picker.text

        correct = browser.get(f"/l/{token}/{right}", follow_redirects=True)
        assert correct.status_code == 200
        assert 'name="surname"' in correct.text
        assert "SMITH" not in correct.text
        assert "Not your dates?" in correct.text
    finally:
        _cleanup()


def test_party_size_is_blank_and_invalid_value_is_not_silently_coerced():
    token, wrong, _right = _make_apartment_with_stays()
    try:
        browser = TestClient(app)
        form = browser.get(f"/l/{token}/{wrong}", follow_redirects=True)
        assert 'name="party_size"' in form.text
        assert 'name="party_size" min="1" max="60" required' in form.text
        assert 'value="2"' not in form.text

        invalid = browser.post(
            f"/l/{token}/{wrong}/save",
            data=_form(party_size=""),
        )
        assert invalid.status_code == 422
        assert "Please enter how many people are staying" in invalid.text
        assert not db.query_one("SELECT 1 AS x FROM guest WHERE reservation_id = ?", (wrong,))
    finally:
        _cleanup()


def test_czech_guest_validation_is_localized():
    token, wrong, _right = _make_apartment_with_stays()
    try:
        page = TestClient(app).post(
            f"/l/{token}/{wrong}/save?lang=cs",
            data=_form(surname="", party_size="1"),
        )
        assert page.status_code == 422
        assert "Příjmení je povinné." in page.text
        assert "Surname is required." not in page.text
    finally:
        _cleanup()


def test_an_unexpected_extra_guest_can_still_register():
    """The lead under-declares the party; the extra arrival must not dead-end."""
    token, stay, _right = _make_apartment_with_stays()
    try:
        lead = TestClient(app)
        saved = lead.post(
            f"/l/{token}/{stay}/save",
            data=_form(party_size="1"),
            files=_passport_files(),
            follow_redirects=False,
        )
        assert saved.status_code == 303

        # A second person arrives. The stay page must offer a way in, not just
        # "everything is complete".
        second = TestClient(app)
        hub = second.get(f"/l/{token}/{stay}", follow_redirects=True)
        assert hub.status_code == 200
        assert f'action="/l/{token}/{stay}/another' in hub.text, hub.text

        raised = second.post(f"/l/{token}/{stay}/another", follow_redirects=False)
        assert raised.status_code == 303
        assert "/new" in raised.headers["location"]
        assert db.query_one(
            "SELECT declared_guests FROM reservation WHERE id = ?", (stay,)
        )["declared_guests"] == 2

        filled = second.post(
            f"/l/{token}/{stay}/save",
            data=_form(surname="Jones", first_name="Mary", party_size="2"),
            files=_passport_files(),
            follow_redirects=False,
        )
        assert filled.status_code == 303
        assert db.query_one(
            "SELECT COUNT(*) AS n FROM guest WHERE reservation_id = ?", (stay,)
        )["n"] == 2
    finally:
        _cleanup()


def test_save_does_not_overshoot_the_declared_party_size():
    """/new guards capacity on GET; a slow filler must not slip past it."""
    token, stay, _right = _make_apartment_with_stays()
    try:
        first = TestClient(app)
        assert first.post(
            f"/l/{token}/{stay}/save",
            data=_form(party_size="1"),
            files=_passport_files(),
            follow_redirects=False,
        ).status_code == 303

        # A second phone had the form open from before the party filled up.
        latecomer = TestClient(app)
        response = latecomer.post(
            f"/l/{token}/{stay}/save",
            data=_form(surname="Jones", first_name="Mary"),
            files=_passport_files(),
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert db.query_one(
            "SELECT COUNT(*) AS n FROM guest WHERE reservation_id = ?", (stay,)
        )["n"] == 1
    finally:
        _cleanup()


def test_guest_form_accepts_pdf_passport_attachment():
    token, wrong, _right = _make_apartment_with_stays()
    try:
        browser = TestClient(app)
        saved = browser.post(
            f"/l/{token}/{wrong}/save",
            data=_form(),
            files={"passport_photo": ("registration.pdf", MINIMAL_PDF, "application/pdf")},
            follow_redirects=False,
        )
        assert saved.status_code == 303, saved.text
        guest = db.query_one("SELECT * FROM guest WHERE reservation_id = ?", (wrong,))
        assert guest["passport_photo_at"]
        assert passport_photos.is_pdf_attachment(guest["id"])
        payload = passport_photos.read_photo(guest["id"])
        assert payload is not None
        assert payload[1] == "application/pdf"
    finally:
        _cleanup()
