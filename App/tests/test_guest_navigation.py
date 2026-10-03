"""Guest navigation: picking the wrong stay, then the right one, must never dead-end."""
import base64
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app import alerts, claim, db, i18n, icalsync, passport_photos, reporting
from app.routes import guest
from app.main import app
from tests.conftest import complete_guest_claim

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
    today = claim.prague_today()
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
        browser.cookies.set(guest.LANG_COOKIE, "en")
        page = browser.get(f"/l/{token}", follow_redirects=True)
        assert page.status_code == 200
        assert 'type="radio"' not in page.text
        assert f'href="/l/{token}/{wrong}?lang=en"' in page.text
        assert f'href="/l/{token}/{right}?lang=en"' in page.text
        assert "Which stay is yours?" in page.text
        assert "That’s my stay" in page.text
        assert "guest registration for" in page.text
    finally:
        _cleanup()


def test_single_visible_stay_still_uses_the_picker():
    token, stay, other = _make_apartment_with_stays()
    try:
        db.execute("DELETE FROM reservation WHERE id = ?", (other,))
        page = TestClient(app).get(f"/l/{token}?lang=en", follow_redirects=False)
        assert page.status_code == 200
        assert f'href="/l/{token}/{stay}?lang=en"' in page.text
        assert "Which stay is yours?" in page.text
        assert 'name="guest_email"' not in page.text
    finally:
        _cleanup()


def test_tapping_an_empty_stay_opens_the_form():
    token, wrong, _right = _make_apartment_with_stays()
    try:
        browser = TestClient(app)
        browser.cookies.set(guest.LANG_COOKIE, "en")
        claim_page = browser.get(f"/l/{token}/{wrong}", follow_redirects=True)
        assert claim_page.status_code == 200
        assert 'name="guest_email"' in claim_page.text
        complete_guest_claim(browser, token, wrong, party_size=2)
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
        browser.cookies.set(guest.LANG_COOKIE, "en")
        complete_guest_claim(browser, token, wrong, party_size=2)
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

        complete_guest_claim(browser, token, right, email="other@example.test", party_size=2)
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
        assert 'name="guest_email"' in form.text
        assert 'min="1"' in form.text
        assert 'max="60"' in form.text
        assert "required" in form.text
        assert 'value="2"' not in form.text

        skipped = browser.post(
            f"/l/{token}/{wrong}/party",
            data={"party_size": "2"},
            follow_redirects=False,
        )
        assert skipped.status_code == 303
        assert "claim_error" in skipped.headers["location"]
        assert db.query_one(
            "SELECT declared_guests FROM reservation WHERE id = ?", (wrong,)
        )["declared_guests"] is None

        saved = browser.post(
            f"/l/{token}/{wrong}/save",
            data=_form(party_size=""),
            follow_redirects=False,
        )
        assert saved.status_code == 303
        assert not db.query_one("SELECT 1 AS x FROM guest WHERE reservation_id = ?", (wrong,))
    finally:
        _cleanup()


def test_completed_party_can_add_another_person():
    token, wrong, _right = _make_apartment_with_stays()
    try:
        browser = TestClient(app)
        browser.cookies.set(guest.LANG_COOKIE, "en")
        complete_guest_claim(browser, token, wrong, party_size=1)
        saved = browser.post(
            f"/l/{token}/{wrong}/save",
            data=_form(party_size="1"),
            files=_passport_files(),
            follow_redirects=False,
        )
        assert saved.status_code == 303

        complete = browser.get(f"/l/{token}/{wrong}")
        assert f'action="/l/{token}/{wrong}/another?lang=en"' in complete.text
        assert "Add another person" in complete.text

        raised = browser.post(f"/l/{token}/{wrong}/another", follow_redirects=False)
        assert raised.status_code == 303
        assert raised.headers["location"].endswith(f"/l/{token}/{wrong}/new?lang=en")
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (wrong,))
        assert reservation["declared_guests"] == 2
    finally:
        _cleanup()


def test_save_says_saved_until_the_record_was_actually_reported():
    """Only a form that went out may be called "reported".

    ``locked`` is true for any signed, complete form, so it cannot stand in for
    "the police have this" — a manual-mode guest was told their record was
    reported the moment they signed it.
    """
    token, wrong, _right = _make_apartment_with_stays()
    try:
        browser = TestClient(app)
        browser.cookies.set(guest.LANG_COOKIE, "en")
        complete_guest_claim(browser, token, wrong, party_size=2)
        saved = browser.post(
            f"/l/{token}/{wrong}/save",
            data=_form(party_size="2"),
            files=_passport_files(),
            follow_redirects=False,
        )
        assert saved.status_code == 303

        page = browser.get(f"/l/{token}/{wrong}?lang=en&saved=1")
        assert i18n.STRINGS["en"]["saved_title"] in page.text
        assert i18n.STRINGS["en"]["saved_body"] in page.text
        assert i18n.STRINGS["en"]["reported_title"] not in page.text
        assert i18n.STRINGS["en"]["reported_body"] not in page.text

        db.execute(
            "UPDATE guest SET submit_state = ? WHERE reservation_id = ?",
            (reporting.SENT, wrong),
        )
        sent = browser.get(f"/l/{token}/{wrong}?lang=en&saved=1")
        assert i18n.STRINGS["en"]["reported_title"] in sent.text
        assert i18n.STRINGS["en"]["saved_title"] not in sent.text
    finally:
        _cleanup()


def test_the_last_step_offers_a_review_list_with_a_way_back():
    """The form locks the moment it is sent, so the guest gets a last look."""
    token, wrong, _right = _make_apartment_with_stays()
    try:
        browser = TestClient(app)
        browser.cookies.set(guest.LANG_COOKIE, "en")
        complete_guest_claim(browser, token, wrong, party_size=2)
        page = browser.get(f"/l/{token}/{wrong}", follow_redirects=True)
        assert page.status_code == 200
        assert "Check before you send" in page.text
        assert "these details are locked and only your host can change them" in page.text
        assert "data-wizard-review" in page.text
        assert 'data-edit-label="Change"' in page.text
        # Rows are read off the form's own labels and values, so the list ships
        # empty and stays hidden when the script never runs.
        assert '<dl class="g-summary-list g-review-list"></dl>' in page.text
        # It sits in the last step, ahead of the legal notice it is checking.
        assert page.text.index("data-wizard-review") < page.text.index('id="legal-notice"')

        cs_page = browser.get(f"/l/{token}/{wrong}?lang=cs", follow_redirects=True)
        assert cs_page.status_code == 200
        assert "Před odesláním zkontrolujte" in cs_page.text
        assert "změnit je může už jen hostitel" in cs_page.text
        assert 'data-edit-label="Změnit"' in cs_page.text
    finally:
        _cleanup()


def test_the_birth_date_field_reads_the_date_back_and_accepts_a_pasted_iso_date():
    """Digits alone cannot show a swapped day and month; the read-back can."""
    token, wrong, _right = _make_apartment_with_stays()
    try:
        browser = TestClient(app)
        browser.cookies.set(guest.LANG_COOKIE, "en")
        complete_guest_claim(browser, token, wrong, party_size=1)
        page = browser.get(f"/l/{token}/{wrong}", follow_redirects=True)
        assert page.status_code == 200
        assert 'placeholder="DD.MM.YYYY"' in page.text
        assert 'id="birth-date-readback"' in page.text
        assert 'aria-live="polite"' in page.text
        assert 'data-template="That is %(date)s."' in page.text
        assert 'data-locale="en"' in page.text

        cs_page = browser.get(f"/l/{token}/{wrong}?lang=cs", follow_redirects=True)
        assert cs_page.status_code == 200
        assert 'placeholder="DD.MM.RRRR"' in cs_page.text
        assert 'data-template="Tedy %(date)s."' in cs_page.text
        assert 'data-locale="cs"' in cs_page.text
    finally:
        _cleanup()


def test_the_birth_date_script_localises_the_readback_and_reorders_an_iso_paste():
    """There is no JS test harness here, so pin the two behaviours in the source."""
    source = (Path("app/static/signature.js")).read_text(encoding="utf-8")
    # "1990-07-04" read as eight digits becomes 19.90.0704 unless it is reordered.
    assert "fromIso" in source
    assert r"/^\s*(\d{4})-(\d{2})-(\d{2})\s*$/" in source
    assert 'input.setAttribute("data-review-value", pretty)' in source
    assert "new Intl.DateTimeFormat(locale" in source
    # 31/02 rolls over to March instead of failing, so the date is round-tripped.
    assert "date.getDate() !== day" in source


def test_the_passport_error_line_carries_the_message_the_wizard_needs():
    """The file input is hidden, so its "missing" text has to reach the wizard."""
    token, wrong, _right = _make_apartment_with_stays()
    try:
        browser = TestClient(app)
        browser.cookies.set(guest.LANG_COOKIE, "en")
        complete_guest_claim(browser, token, wrong, party_size=1)
        apartment = db.query_one(
            "SELECT id FROM apartment WHERE permalink_token = ?", (token,)
        )
        db.update(
            "apartment",
            apartment["id"],
            {"passport_photo_policy": "required_foreign"},
        )
        page = browser.get(f"/l/{token}/{wrong}", follow_redirects=True)
        assert page.status_code == 200
        assert 'id="passport-file-err"' in page.text
        assert 'role="alert"' in page.text
        assert 'data-missing="Please upload a photo of your passport or ID card."' in page.text
        assert 'id="passport-take-btn"' in page.text

        cs_page = browser.get(f"/l/{token}/{wrong}?lang=cs", follow_redirects=True)
        assert cs_page.status_code == 200
        assert (
            'data-missing="Nahrajte prosím fotografii pasu nebo občanského průkazu."'
            in cs_page.text
        )
    finally:
        _cleanup()


def test_a_hidden_file_input_fails_continue_with_a_visible_reason():
    """A browser cannot focus or bubble a hidden control, so Continue was mute."""
    source = (Path("app/static/signature.js")).read_text(encoding="utf-8")
    assert 'fields[i].type === "file" && fields[i].hidden' in source
    assert 'document.getElementById("passport-file-err")' in source
    assert 'fileErr.getAttribute("data-missing")' in source
    assert 'document.getElementById("passport-take-btn")' in source
    assert "takeBtn.focus()" in source


def test_the_wizard_gives_each_step_a_history_entry_so_back_does_not_lose_the_form():
    """An OS back gesture used to leave the page and discard everything typed."""
    source = (Path("app/static/signature.js")).read_text(encoding="utf-8")
    assert 'history.replaceState({ guestWizardStep: active }, "")' in source
    assert 'history.pushState({ guestWizardStep: active }, "")' in source
    assert 'window.addEventListener("popstate"' in source
    assert "typeof state.guestWizardStep !== \"number\"" in source
    assert "show(state.guestWizardStep, true)" in source


def test_the_passport_copy_speaks_to_the_guest_not_to_the_engineers():
    """The old help text explained the app's storage policy to the guest."""
    token, wrong, _right = _make_apartment_with_stays()
    try:
        browser = TestClient(app)
        browser.cookies.set(guest.LANG_COOKIE, "en")
        complete_guest_claim(browser, token, wrong, party_size=1)
        apartment = db.query_one(
            "SELECT id FROM apartment WHERE permalink_token = ?", (token,)
        )
        db.update(
            "apartment",
            apartment["id"],
            {"passport_photo_policy": "required_foreign"},
        )
        page = browser.get(f"/l/{token}/{wrong}", follow_redirects=True)
        assert page.status_code == 200
        assert (
            "Your host must check your details against your document. Take a photo of the page "
            "with your photo, or upload a PDF. Only your host can see it, and it is deleted after "
            "they check it."
        ) in page.text
        assert "A JPEG, PNG or WebP photo up to 5 MB, or a PDF up to 15 MB." in page.text
        assert "Choose your nationality in step 1 first." in page.text
        assert (
            "Foreign guests upload a photo of their passport or ID page (or a PDF). Only your host "
            "sees it, to compare it with what you entered. It is deleted after the check, "
            "otherwise 7 days after check-in, and never later than 30 days after upload. It is "
            "never sent to the police."
        ) in page.text
        # The internal storage policy is not the guest's problem.
        assert "stale-file sweep" not in page.text
        assert "Access in the app is restricted" not in page.text
        assert "authorised host users" not in page.text

        cs_page = browser.get(f"/l/{token}/{wrong}?lang=cs", follow_redirects=True)
        assert cs_page.status_code == 200
        assert (
            "Hostitel musí vaše údaje porovnat s dokladem. Vyfoťte stránku s fotografií, nebo "
            "nahrajte PDF. Uvidí ji jen hostitel a po kontrole se smaže."
        ) in cs_page.text
        assert "Fotka JPEG, PNG nebo WebP do 5 MB, nebo PDF do 15 MB." in cs_page.text
        assert "Nejdřív v kroku 1 vyberte státní občanství." in cs_page.text
        assert "pojistkou je plánované mazání" not in cs_page.text
    finally:
        _cleanup()


def test_the_legal_notice_talks_to_the_guest_instead_of_the_builder():
    """The final step used to explain the app's own reporting pipeline to the guest."""
    token, wrong, _right = _make_apartment_with_stays()
    try:
        browser = TestClient(app)
        browser.cookies.set(guest.LANG_COOKIE, "en")
        complete_guest_claim(browser, token, wrong, party_size=1)
        page = browser.get(f"/l/{token}/{wrong}", follow_redirects=True)
        assert page.status_code == 200
        assert "Please read this before you send." in page.text
        assert (
            "Everyone staying must be registered. Foreign guests are reported to the Foreign "
            "Police within three working days; Czech citizens only go into the house book. "
            "This is required by law."
        ) in page.text
        assert (
            "Enter everything exactly as in your passport or ID card. Your details may be "
            "reported automatically, before your host checks them, and false details can mean "
            "a fine for your host."
        ) in page.text
        assert (
            "Complete records of foreign guests may be sent to the Czech Police automatically — "
            "straight away or after a delay your host chooses. The same details stay in the house "
            "book for six years."
        ) in page.text
        assert (
            "My details are correct, and I have read the information above and the privacy "
            "notice."
        ) in page.text
        # The software-liability disclaimer belongs to the privacy page, not the guest's task.
        assert "does not replace legal advice" not in page.text
        assert "without an in-app verification step" not in page.text
        assert "without waiting for in-app identity verification" not in page.text

        cs_page = browser.get(f"/l/{token}/{wrong}?lang=cs", follow_redirects=True)
        assert cs_page.status_code == 200
        assert "Před odesláním si to prosím přečtěte." in cs_page.text
        assert (
            "Registrovat se musí každý ubytovaný. Cizince ubytovatel do tří pracovních dnů "
            "ohlásí cizinecké policii, občany ČR jen zapíše do domovní knihy. Vyžaduje to zákon."
        ) in cs_page.text
        assert (
            "Vše vyplňte přesně podle pasu nebo občanského průkazu. Údaje se mohou ohlásit "
            "automaticky ještě předtím, než je ubytovatel zkontroluje, a za nepravdivé údaje "
            "hrozí ubytovateli pokuta."
        ) in cs_page.text
        assert (
            "Kompletní záznamy cizinců se mohou Policii ČR odeslat automaticky — hned, nebo "
            "s odkladem, který nastaví ubytovatel. Stejné údaje zůstávají šest let v domovní "
            "knize."
        ) in cs_page.text
        assert (
            "Moje údaje jsou správné a přečetl(a) jsem si informace výše i zásady zpracování "
            "údajů."
        ) in cs_page.text
        assert "nenahrazují právní poradenství" not in cs_page.text
        assert "bez ověření v aplikaci" not in cs_page.text
    finally:
        _cleanup()


def test_the_phone_submit_button_is_actually_the_one_the_css_targets():
    """The sticky-submit rule named a child of <form>; the button lives one level deeper."""
    css = (Path(__file__).resolve().parents[1] / "app" / "static" / "guest.css").read_text()
    assert '[data-guest-step] > .g-btn[type="submit"]' in css
    assert 'form > .g-btn[type="submit"]' not in css


def test_czech_guest_validation_is_localized():
    token, wrong, _right = _make_apartment_with_stays()
    try:
        browser = TestClient(app)
        complete_guest_claim(browser, token, wrong, party_size=1)
        page = browser.post(
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
        complete_guest_claim(lead, token, stay, party_size=1)
        saved = lead.post(
            f"/l/{token}/{stay}/save",
            data=_form(party_size="1"),
            files=_passport_files(),
            follow_redirects=False,
        )
        assert saved.status_code == 303

        # A second browser without the claim cookie cannot raise the party.
        second = TestClient(app)
        hub = second.get(f"/l/{token}/{stay}", follow_redirects=True)
        assert hub.status_code == 200
        assert "already assigned" in hub.text.lower() or "přiřazena" in hub.text.lower() or 'name="guest_email"' in hub.text
        assert f'action="/l/{token}/{stay}/another' not in hub.text

        raised = lead.post(f"/l/{token}/{stay}/another", follow_redirects=False)
        assert raised.status_code == 303
        assert "/new" in raised.headers["location"]
        assert db.query_one(
            "SELECT declared_guests FROM reservation WHERE id = ?", (stay,)
        )["declared_guests"] == 2

        filled = lead.post(
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
        complete_guest_claim(first, token, stay, party_size=1)
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
        assert f"/{stay}" in response.headers["location"]
        assert "/new" not in response.headers.get("location", "")
        assert db.query_one(
            "SELECT COUNT(*) AS n FROM guest WHERE reservation_id = ?", (stay,)
        )["n"] == 1
    finally:
        _cleanup()


def test_every_guest_facing_validation_message_has_czech():
    """A Czech guest must never be handed an untranslated UbyPort rule."""
    from app import validation as v
    from app.validation_i18n import localize as _localize_message

    long_name = "X" * 80
    cases = [
        # (raw overrides, field we expect to complain about)
        ({"surname": ""}, "surname"),
        ({"surname": "Иванов"}, "surname"),
        ({"surname": long_name}, "surname"),
        ({"first_name": long_name}, "first_name"),
        ({"first_name": "李"}, "first_name"),
        ({"birth_date": ""}, "birth_date"),
        ({"birth_date": "31/02/1990"}, "birth_date"),
        ({"birth_date": "01/01/1850"}, "birth_date"),
        ({"birth_date": "01/13/1990"}, "birth_date"),
        ({"birth_date": "32/01/1990"}, "birth_date"),
        ({"birth_date": "01/01/2090"}, "birth_date"),
        ({"birth_date": "1/1/1990", "nationality": ""}, "nationality"),
        ({"nationality": "UK"}, "nationality"),
        ({"doc_number": ""}, "doc_number"),
        ({"doc_number": "AB12"}, "doc_number"),
        ({"doc_number": "P" * 40}, "doc_number"),
        ({"doc_number": "INPASS", "note": ""}, "note"),
        ({"visa_number": "V" * 20}, "visa_number"),
        ({"res_street": ""}, "res_street"),
        ({"res_street": long_name}, "res_street"),
        ({"res_street": "12345"}, "res_street"),
        ({"res_city": ""}, "res_city"),
        ({"res_city": long_name}, "res_city"),
        ({"res_city": "12345"}, "res_city"),
        ({"res_country": ""}, "res_country"),
        ({"res_country": "XYZ"}, "res_country"),
        ({"purpose": "77"}, "purpose"),
    ]

    checked = 0
    for overrides, field in cases:
        raw = {
            "surname": "Smith",
            "first_name": "John",
            "birth_date": "1.1.1990",
            "nationality": "GBR",
            "doc_number": "P1234567",
            "visa_number": "",
            "res_street": "Baker Street 221B",
            "res_city": "London",
            "res_country": "GBR",
            "purpose": "10",
            "note": "",
        }
        raw.update(overrides)
        values = v.normalise_guest(raw, clamp=False)
        issues = [i for i in v.validate_guest(values, raw=raw) if i.field == field]
        assert issues, f"expected a {field} issue for {overrides}"
        for issue in issues:
            czech = _localize_message(issue.message)
            assert czech != issue.message, (
                f"no Czech translation for {field}: {issue.message!r}"
            )
            checked += 1
    assert checked >= len(cases)


def test_guest_form_accepts_pdf_passport_attachment():
    token, wrong, _right = _make_apartment_with_stays()
    try:
        browser = TestClient(app)
        complete_guest_claim(browser, token, wrong, party_size=2)
        apartment = db.query_one(
            "SELECT id FROM apartment WHERE permalink_token = ?", (token,)
        )
        db.update(
            "apartment",
            apartment["id"],
            {"passport_photo_policy": "required_foreign"},
        )
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


def test_guest_form_ignores_passport_attachment_when_policy_off():
    token, wrong, _right = _make_apartment_with_stays()
    try:
        browser = TestClient(app)
        complete_guest_claim(browser, token, wrong, party_size=2)
        saved = browser.post(
            f"/l/{token}/{wrong}/save",
            data=_form(),
            files={"passport_photo": ("registration.pdf", MINIMAL_PDF, "application/pdf")},
            follow_redirects=False,
        )
        assert saved.status_code == 303, saved.text
        guest = db.query_one("SELECT * FROM guest WHERE reservation_id = ?", (wrong,))
        assert not guest["passport_photo_at"]
        assert not passport_photos.has_photo(guest["id"])
    finally:
        _cleanup()


def test_guest_english_and_czech_carry_the_same_keys():
    """A jet-lagged guest must not be shown a raw i18n key."""
    from app import i18n

    english = set(i18n.STRINGS["en"])
    czech = set(i18n.STRINGS["cs"])
    assert english - czech == set(), f"missing Czech: {sorted(english - czech)}"
    assert czech - english == set(), f"missing English: {sorted(czech - english)}"


def test_a_calendar_move_does_not_raise_a_resign_alert(monkeypatch):
    """Date changes file with the new stay; guests do not have to sign again."""
    db.init_db()
    _cleanup()
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert("legal_entity", {"name": "Nav Test", "created_at": now})
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Nav moved apartment",
            "permalink_token": TOKEN,
            "permalink_window_days": 90,
            "default_purpose": "10",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    feed_id = db.insert(
        "ical_feed",
        {
            "apartment_id": apartment_id,
            "url": "https://calendar.example/nav-moved.ics",
            "active": 1,
            "created_at": now,
        },
    )
    stay = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "ical_feed_id": feed_id,
            "source": "airbnb",
            "uid": "nav-moved",
            "date_from": (today + timedelta(days=2)).isoformat(),
            "date_to": (today + timedelta(days=5)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    moved_from = today + timedelta(days=20)
    moved_to = today + timedelta(days=23)
    moved = (
        "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\n"
        f"DTSTART;VALUE=DATE:{moved_from:%Y%m%d}\n"
        f"DTEND;VALUE=DATE:{moved_to:%Y%m%d}\n"
        "UID:nav-moved\nSUMMARY:Reserved\nEND:VEVENT\nEND:VCALENDAR\n"
    )
    monkeypatch.setattr(icalsync, "fetch_feed", lambda _url: moved)
    key = f"dates_changed_resign:{stay}"
    try:
        browser = TestClient(app)
        complete_guest_claim(browser, TOKEN, stay, party_size=2)
        assert browser.post(
            f"/l/{TOKEN}/{stay}/save",
            data=_form(party_size="2"),
            files=_passport_files(),
            follow_redirects=False,
        ).status_code == 303

        icalsync.sync_feed(
            db.query_one("SELECT * FROM ical_feed WHERE id = ?", (feed_id,))
        )
        assert db.query_one(
            "SELECT id FROM alert WHERE dedupe_key = ? AND resolved_at IS NULL", (key,)
        ) is None

        again = browser.post(
            f"/l/{TOKEN}/{stay}/save",
            data=_form(surname="Jones", first_name="Mary", party_size="2"),
            files=_passport_files(),
            follow_redirects=False,
        )
        assert again.status_code == 303, again.text
        assert db.query_one(
            "SELECT COUNT(*) AS n FROM guest WHERE reservation_id = ?", (stay,)
        )["n"] == 2
    finally:
        db.execute("DELETE FROM alert WHERE reservation_id = ?", (stay,))
        db.execute("DELETE FROM alert WHERE dedupe_key = ?", (f"feed_incomplete:{feed_id}",))
        _cleanup()


# --- W1.5: the declared headcount must not hold the filing open -----------

def _backdate_forms(reservation_id, hours):
    """Age every form on the stay as if nobody had touched it for ``hours``."""
    stale = (datetime.now(timezone.utc) - timedelta(hours=hours)).replace(
        microsecond=0
    ).isoformat()
    db.execute(
        "UPDATE guest SET created_at = ?, updated_at = ? WHERE reservation_id = ?",
        (stale, stale, reservation_id),
    )


def _one_signed_guest(browser, token, stay, *, party_size, surname="Smith"):
    complete_guest_claim(browser, token, stay, party_size=party_size)
    saved = browser.post(
        f"/l/{token}/{stay}/save",
        data=_form(surname=surname, party_size=str(party_size)),
        files=_passport_files(),
        follow_redirects=False,
    )
    assert saved.status_code == 303, saved.text
    assert db.query_one(
        "SELECT COUNT(*) AS n FROM guest WHERE reservation_id = ?", (stay,)
    )["n"] == 1


def test_a_raised_headcount_no_longer_holds_the_filing_open():
    """W1.5: the link holder declares 60 people and fills in one.

    The declared party is not a gate the guest link can hold shut. Once every
    form on file is complete and nobody has touched it for the quiet window, the
    stay is as final as it will ever be.
    """
    token, stay, _right = _make_apartment_with_stays()
    try:
        _one_signed_guest(TestClient(app), token, stay, party_size=60)

        # 1 of 60 signed, and the form is fresh: the gate still waits.
        assert reporting.refresh_registration_completed_at(stay) is None
        assert db.query_one(
            "SELECT registration_completed_at FROM reservation WHERE id = ?", (stay,)
        )["registration_completed_at"] is None

        _backdate_forms(stay, reporting.HEADCOUNT_QUIET_HOURS + 1)

        completed = reporting.refresh_registration_completed_at(stay)
        assert completed
        assert db.query_one(
            "SELECT registration_completed_at FROM reservation WHERE id = ?", (stay,)
        )["registration_completed_at"] == completed
    finally:
        _cleanup()


def test_the_quiet_window_never_files_a_half_filled_form():
    """Waiting is bounded; filing an unfinished form is not acceptable."""
    token, stay, _right = _make_apartment_with_stays()
    try:
        _one_signed_guest(TestClient(app), token, stay, party_size=60)
        db.execute("UPDATE reservation SET declared_guests = 1 WHERE id = ?", (stay,))
        # A second person started the form and never signed it.
        now = db.utcnow()
        db.insert(
            "guest",
            {
                "reservation_id": stay,
                "surname": "Unfinished",
                "created_at": now,
                "updated_at": now,
            },
        )
        _backdate_forms(stay, reporting.HEADCOUNT_QUIET_HOURS + 1)

        assert reporting.refresh_registration_completed_at(stay) is None
    finally:
        _cleanup()


def test_a_full_party_still_completes_without_waiting():
    """The ordinary path must not have been put behind the quiet window."""
    token, stay, _right = _make_apartment_with_stays()
    try:
        _one_signed_guest(TestClient(app), token, stay, party_size=1)

        assert reporting.refresh_registration_completed_at(stay)
    finally:
        _cleanup()


def test_a_short_party_is_flagged_once_the_stay_has_started():
    """W1.5: 'waiting for guest' and 'held open by the link' must differ."""
    token, stay, _right = _make_apartment_with_stays()
    key = f"headcount_mismatch:{stay}"
    try:
        _one_signed_guest(TestClient(app), token, stay, party_size=60)
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)

        reporting.check_deadlines(tomorrow)

        row = db.query_one(
            "SELECT * FROM alert WHERE dedupe_key = ? AND resolved_at IS NULL", (key,)
        )
        assert row, "a 1-of-60 party must not sit silently"
        assert row["level"] == "warning"
        assert row["reservation_id"] == stay
        assert "Waiting for guest forms" in row["detail"]
        card = alerts.present(row, "cs")
        assert "Čeká se na formuláře hostů" in card["display_detail"]
        assert "1/60" in card["display_detail"]

        # The host fixes the declared party; the warning is stale at once.
        db.execute("UPDATE reservation SET declared_guests = 1 WHERE id = ?", (stay,))
        reporting.check_deadlines(tomorrow)
        assert db.query_one(
            "SELECT resolved_at FROM alert WHERE dedupe_key = ?", (key,)
        )["resolved_at"]
    finally:
        db.execute("DELETE FROM alert WHERE dedupe_key = ?", (key,))
        _cleanup()


# --- AR-11: a save must not overwrite what the sweep just changed ----------


def test_a_save_while_the_sweep_holds_the_guest_is_refused():
    """AR-11: the request read a state the sweep may already be replacing.

    A submission_claim row means the sweep has this guest in flight. The guest
    edit must not overwrite the filing, and says so instead of silently losing
    the submitted record. The claim is only honoured while it is fresh (see the
    expired-claim test below).
    """
    token, stay, _right = _make_apartment_with_stays()
    guest_id = None
    try:
        browser = TestClient(app)
        # The shared TOKEN and a per-IP confirm bucket: this file already spends
        # most of the allowance, so reset it for this test's claim.
        db.execute("DELETE FROM rate_limit_event WHERE scope = 'claim_confirm'")
        complete_guest_claim(browser, token, stay, party_size=2)
        now = db.utcnow()
        guest_id = db.insert(
            "guest",
            {
                "reservation_id": stay,
                "surname": "OLD",
                "first_name": "Name",
                "nationality": "GBR",
                "submit_state": reporting.ERROR,
                "created_at": now,
                "updated_at": now,
            },
        )
        browser.cookies.set(guest.OWNED_COOKIE, guest._serializer().dumps([guest_id]))
        db.execute(
            "INSERT INTO submission_claim (guest_id, claim_token, claimed_at) "
            "VALUES (?, 'x', ?)",
            (guest_id, time.time()),
        )

        response = browser.post(
            f"/l/{token}/{stay}/save",
            data=_form(surname="NEW", guest_id=str(guest_id)),
            files=_passport_files(),
            follow_redirects=False,
        )

        assert response.status_code == 403, response.text
        row = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
        assert row["surname"] == "OLD"
    finally:
        if guest_id is not None:
            db.execute("DELETE FROM submission_claim WHERE guest_id = ?", (guest_id,))
        _cleanup()


def test_an_expired_claim_does_not_block_the_guest_save():
    """A claim left by a crashed worker must not strand the guest's own edit.

    Only the send path prunes claims, so a manual property would reject the
    guest for ever. A claim older than ``SUBMISSION_CLAIM_TTL_SECONDS`` is void.
    """
    token, stay, _right = _make_apartment_with_stays()
    guest_id = None
    try:
        browser = TestClient(app)
        db.execute("DELETE FROM rate_limit_event WHERE scope = 'claim_confirm'")
        complete_guest_claim(browser, token, stay, party_size=2)
        now = db.utcnow()
        guest_id = db.insert(
            "guest",
            {
                "reservation_id": stay,
                "surname": "OLD",
                "first_name": "Name",
                "nationality": "GBR",
                "submit_state": reporting.ERROR,
                "created_at": now,
                "updated_at": now,
            },
        )
        browser.cookies.set(guest.OWNED_COOKIE, guest._serializer().dumps([guest_id]))
        db.execute(
            "INSERT INTO submission_claim (guest_id, claim_token, claimed_at) "
            "VALUES (?, 'x', ?)",
            (guest_id, time.time() - reporting.SUBMISSION_CLAIM_TTL_SECONDS - 1),
        )

        response = browser.post(
            f"/l/{token}/{stay}/save",
            data=_form(surname="NEW", guest_id=str(guest_id)),
            files=_passport_files(),
            follow_redirects=False,
        )

        assert response.status_code == 303, response.text
        row = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
        assert row["surname"] == "NEW", "a stale claim must not block the guest's edit"
    finally:
        if guest_id is not None:
            db.execute("DELETE FROM submission_claim WHERE guest_id = ?", (guest_id,))
        _cleanup()


def test_only_the_claimants_device_may_change_the_headcount():
    """AR-20: a stranger with the link must not change a claimed stay's party.

    Once a device has claimed the stay, only that device may move the declared
    headcount; anyone else with the link is sent back.
    """
    token, stay, _right = _make_apartment_with_stays()
    try:
        claimant = TestClient(app)
        complete_guest_claim(claimant, token, stay, party_size=2)
        before = db.query_one(
            "SELECT declared_guests FROM reservation WHERE id = ?", (stay,)
        )["declared_guests"]
        assert before == 2

        stranger = TestClient(app)
        stranger.cookies.set(guest.LANG_COOKIE, "en")
        response = stranger.post(
            f"/l/{token}/{stay}/party",
            data={"party_size": "1"},
            follow_redirects=False,
        )

        assert response.status_code == 303, response.text
        after = db.query_one(
            "SELECT declared_guests FROM reservation WHERE id = ?", (stay,)
        )["declared_guests"]
        assert after == before
    finally:
        _cleanup()
