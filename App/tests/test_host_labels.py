"""No stored slug or portal name reaches the host as a label.

``reservation.source`` is ``manual``/``ical``/a portal slug, ``guest.entered_by``
is ``guest``/``host``, and ``submission.mode`` is a snake_case slug. All three
used to be printed straight into the page, so a Czech host read "manual" and
"Manual bulk". They are labels now, which means they have to be translated
rather than humanised.
"""
from __future__ import annotations

import html
from datetime import date, timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import auth, db, host_i18n, reporting, templating
from app.main import app

TOKEN = "hostlabelstoken"
PASSWORD = "Host-Labels-Password-123"
USERNAME = "host-labels-admin"

SOURCE_KEYS = ["stays.source.manual", "stays.source.ical"]
ENTERED_BY_KEYS = [
    "stay.detail.guests.entered_by.guest",
    "stay.detail.guests.entered_by.host",
    "stay.detail.guests.entered_by.import",
]
MODE_KEYS = [
    "reports.mode.auto",
    "reports.mode.auto_resend",
    "reports.mode.manual",
    "reports.mode.manual_bulk",
    "reports.mode.manual_resend",
    "reports.mode.completion_immediate",
    "reports.mode.demo",
]
# Every slug the app actually writes into submission.mode.
WRITTEN_MODES = [
    "manual",
    "manual_bulk",
    "manual_resend",
    "auto",
    "auto_resend",
    "completion_immediate",
    "demo",
]


class _FakeRequest:
    """Just enough of a Request for ``host_i18n.lang_from_request``."""

    def __init__(self, lang: str):
        self.query_params = {"lang": lang}
        self.cookies: dict[str, str] = {}
        self.state = SimpleNamespace(lang=None)


def _render(template_source: str, lang: str, **context) -> str:
    return (
        templating.templates.env.from_string(template_source)
        .render(request=_FakeRequest(lang), **context)
    )


def _source_label(source, lang="en") -> str:
    return _render("{{ source_label(r) }}", lang, r={"source": source})


def _entered_by_label(value, lang="en") -> str:
    return _render("{{ entered_by_label(v) }}", lang, v=value)


def _report_mode_label(mode, lang="en") -> str:
    return _render("{{ report_mode_label(m) }}", lang, m=mode)


def _ensure_admin() -> int:
    db.init_db()
    account = db.query_one("SELECT * FROM user_account WHERE username = ?", (USERNAME,))
    if not account:
        return auth.create_account(
            USERNAME,
            PASSWORD,
            "Host labels admin",
            role="admin",
            must_change_password=False,
        )
    return account["id"]


def _browser(lang: str) -> TestClient:
    _ensure_admin()
    client = TestClient(app)
    response = client.post(
        f"/login?lang={lang}",
        data={"username": USERNAME, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client


def _cleanup():
    apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
    if not apartment:
        return
    db.execute(
        "DELETE FROM guest WHERE reservation_id IN "
        "(SELECT id FROM reservation WHERE apartment_id = ?)",
        (apartment["id"],),
    )
    db.execute("DELETE FROM submission WHERE apartment_id = ?", (apartment["id"],))
    db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))


def _seed() -> dict:
    """A manual direct booking, an iCal stay, and one guest of each origin."""
    db.init_db()
    _cleanup()
    owner_id = _ensure_admin()
    now = db.utcnow()
    today = date.today()
    apartment_id = db.insert(
        "apartment",
        {
            "owner_user_id": owner_id,
            "internal_name": "Labels flat",
            "permalink_token": TOKEN,
            "automation_mode": "manual",
            "default_purpose": "10",
            "active": 1,
            "created_at": now,
        },
    )
    direct_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": "labels-direct",
            "date_from": (today + timedelta(days=5)).isoformat(),
            "date_to": (today + timedelta(days=7)).isoformat(),
            "summary": None,
            "status": "cancelled",
            "created_at": now,
            "updated_at": now,
        },
    )
    portal_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "airbnb",
            "uid": "labels-portal",
            "date_from": (today + timedelta(days=20)).isoformat(),
            "date_to": (today + timedelta(days=22)).isoformat(),
            "summary": "Airbnb reservation",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    for entered_by in ("host", "guest"):
        db.insert(
            "guest",
            {
                "reservation_id": portal_id,
                "surname": f"Guest{entered_by.upper()}",
                "first_name": "Test",
                "nationality": "CZE",
                "purpose": "10",
                "entered_by": entered_by,
                "submit_state": reporting.PENDING,
                "created_at": now,
                "updated_at": now,
            },
        )
    db.insert(
        "submission",
        {
            "apartment_id": apartment_id,
            "mode": "manual_bulk",
            "state": "sent",
            "created_at": now,
            "finished_at": now,
        },
    )
    return {"apartment_id": apartment_id, "direct_id": direct_id, "portal_id": portal_id}


def test_the_new_labels_ship_in_both_languages():
    keys = SOURCE_KEYS + ENTERED_BY_KEYS + MODE_KEYS
    for key in keys:
        assert key in host_i18n.STRINGS["en"], f"{key} missing from English"
        assert key in host_i18n.STRINGS["cs"], f"{key} missing from Czech"
        english = host_i18n.STRINGS["en"][key]
        czech = host_i18n.STRINGS["cs"][key]
        assert english.strip() and czech.strip(), f"{key} is blank in one language"
        if key.endswith("import"):
            # "Import" is the same word in both languages on purpose.
            continue
        assert english != czech, f"{key} is untranslated"


def test_a_direct_booking_is_named_in_the_hosts_language():
    assert _source_label("manual", "en") == "Direct booking"
    assert _source_label("manual", "cs") == "Přímá rezervace"


def test_a_portal_is_named_the_way_the_host_reads_it_on_the_portal():
    for lang in ("en", "cs"):
        assert _source_label("airbnb", lang) == "Airbnb"
        assert _source_label("booking", lang) == "Booking.com"


def test_a_calendar_import_is_named_rather_than_called_ical():
    assert _source_label("ical", "en") == "Calendar import"
    assert _source_label("ical", "cs") == "Import z kalendáře"


def test_an_unrecognised_source_never_renders_a_translation_key():
    assert _source_label("new_portal", "en") == "New portal"
    assert "stays.source." not in _source_label("new_portal", "en")


def test_who_entered_a_guest_record_is_a_word_not_a_slug():
    assert _entered_by_label("guest", "en") == "Guest"
    assert _entered_by_label("host", "en") == "You"
    assert _entered_by_label("import", "en") == "Import"
    assert _entered_by_label("guest", "cs") == "Host"
    assert _entered_by_label("host", "cs") == "Vy"


def test_every_report_mode_the_app_writes_has_a_translation():
    for mode in WRITTEN_MODES:
        for lang in ("en", "cs"):
            text = host_i18n.translate(lang, f"reports.mode.{mode}")
            assert text != f"reports.mode.{mode}", f"{mode} has no {lang} translation"
            assert text.strip()


def test_an_unknown_report_mode_never_renders_a_translation_key():
    assert "reports.mode." not in _report_mode_label("brand_new_mode", "en")


def test_a_cancelled_stay_is_labelled_in_the_hosts_language():
    _seed()
    try:
        english = _browser("en").get("/reservations?status=cancelled&range=all")
        assert english.status_code == 200
        assert "Cancelled" in english.text
        assert ">cancelled<" not in english.text

        czech = _browser("cs").get("/reservations?status=cancelled&range=all")
        assert czech.status_code == 200
        assert "Zrušený" in czech.text
        assert ">cancelled<" not in czech.text
    finally:
        _cleanup()


def test_the_stays_list_names_the_source_instead_of_dumping_the_column():
    _seed()
    try:
        page = _browser("en").get("/reservations?status=all&range=all")
        assert page.status_code == 200
        assert "Direct booking" in page.text
        assert "Airbnb" in page.text
        # The portal's own event title is not the Source column any more.
        assert "Airbnb reservation" not in page.text
        assert ">manual<" not in page.text
    finally:
        _cleanup()


def test_the_stay_page_lede_names_the_source_too():
    seeded = _seed()
    try:
        page = _browser("en").get(f"/reservations/{seeded['direct_id']}")
        assert page.status_code == 200
        assert "Direct booking" in page.text
    finally:
        _cleanup()


def test_the_guest_cards_say_who_typed_the_record():
    seeded = _seed()
    try:
        english = _browser("en").get(f"/reservations/{seeded['portal_id']}")
        assert english.status_code == 200
        assert "Entered by" in english.text
        assert ">You<" in english.text
        assert ">Guest<" in english.text

        czech = _browser("cs").get(f"/reservations/{seeded['portal_id']}")
        assert czech.status_code == 200
        assert ">Vy<" in czech.text
        assert ">Host<" in czech.text
    finally:
        _cleanup()


def test_the_submissions_list_translates_the_mode():
    _seed()
    try:
        english = _browser("en").get("/submissions")
        assert english.status_code == 200
        assert host_i18n.translate("en", "reports.mode.manual_bulk") in english.text
        assert "Manual bulk" not in english.text

        czech = _browser("cs").get("/submissions")
        assert czech.status_code == 200
        assert html.unescape(host_i18n.translate("cs", "reports.mode.manual_bulk")) in czech.text
    finally:
        _cleanup()


def test_a_stay_created_by_hand_stores_no_english_summary():
    seeded = _seed()
    from_date = (date.today() + timedelta(days=40)).isoformat()
    try:
        response = _browser("en").post(
            "/reservations",
            data={
                "apartment_id": seeded["apartment_id"],
                "date_from": from_date,
                "date_to": (date.today() + timedelta(days=42)).isoformat(),
            },
            follow_redirects=False,
        )
        assert response.status_code in (302, 303)
        created = db.query_one(
            "SELECT * FROM reservation WHERE apartment_id = ? AND date_from = ?",
            (seeded["apartment_id"], from_date),
        )
        assert created is not None
        assert not created["summary"], "a hand-made stay must not carry an English summary"
        assert created["source"] == "manual"
    finally:
        _cleanup()
