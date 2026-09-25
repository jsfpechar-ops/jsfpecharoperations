"""Counted strings use the form their number needs.

Czech has three forms where English has two, and the app printed one form
whatever the number was: a Czech host read "3 nocí" and "1 kalendářů" on the
Stays list, and an English host read "1 nights". ``tp()`` (and
``flash_plural`` for the flashes) picks ``.one``, ``.few`` or the bare key --
which is the *many* form -- from the count.

``host_i18n.lookup`` renders a key's raw text when the key is missing, so a
typo in a variant name would ship as "stay.detail.ready_count.one" on the page
rather than raising. These tests read the catalogue directly as well as the
rendered page, so a missing variant cannot pass.
"""
from __future__ import annotations

import base64
import html
from datetime import date, timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import auth, db, host_i18n, reporting, templating
from app.main import app
from app.routes.admin_helpers import flash_plural, plural_param

TOKEN = "pluralhelpertoken"
PASSWORD = "Plural-Helper-Password-123"
USERNAME = "plural-helper-admin"

SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()

# Every key that varies with a count, and the forms it has to ship.
COUNTED_KEYS = [
    "stays.table.nights",
    "stay.detail.ready_count",
    "settings.retention.delete",
    "flash.feeds.added",
    "flash.feeds.synced",
    "flash.reservations.sent",
    "flash.reservations.sent.stays",
    "flash.reservations.accepted",
    "flash.reservations.reported",
    "flash.error.rejected",
    "deadline.arrives_days",
    "deadline.days_left",
    "deadline.overdue_days",
]


class _FakeRequest:
    """Just enough of a Request for ``host_i18n.lang_from_request``."""

    def __init__(self, lang: str):
        self.query_params = {"lang": lang}
        self.cookies: dict[str, str] = {}
        self.state = SimpleNamespace(lang=None)


def _tp(base: str, n: int, lang: str = "en") -> str:
    return templating.templates.env.from_string("{{ tp(base, n) }}").render(
        request=_FakeRequest(lang), base=base, n=n
    )


def _ensure_admin() -> int:
    db.init_db()
    account = db.query_one("SELECT * FROM user_account WHERE username = ?", (USERNAME,))
    if not account:
        return auth.create_account(
            USERNAME,
            PASSWORD,
            "Plural helper admin",
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


def _seed(nights: int = 3, pending: int = 1) -> dict:
    """One manual stay of ``nights`` nights with ``pending`` signed guests."""
    db.init_db()
    _cleanup()
    owner_id = _ensure_admin()
    now = db.utcnow()
    today = date.today()
    apartment_id = db.insert(
        "apartment",
        {
            "owner_user_id": owner_id,
            "internal_name": "Plural flat",
            "permalink_token": TOKEN,
            "automation_mode": "manual",
            "default_purpose": "10",
            "active": 1,
            "created_at": now,
        },
    )
    arrival = today + timedelta(days=5)
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": f"plural-helper-{nights}",
            "date_from": arrival.isoformat(),
            "date_to": (arrival + timedelta(days=nights)).isoformat(),
            "summary": None,
            "status": "active",
            "expected_guests_override": pending,
            "created_at": now,
            "updated_at": now,
        },
    )
    for index in range(pending):
        db.insert(
            "guest",
            {
                "reservation_id": reservation_id,
                "surname": f"Guest{index}",
                "first_name": "Test",
                "birth_date": "01011990",
                "nationality": "GBR",
                "doc_number": f"P123456{index}",
                "res_street": "Street 1",
                "res_city": "London",
                "res_country": "GBR",
                "purpose": "10",
                "is_lead": 1 if index == 0 else 0,
                "entered_by": "host",
                "signature_png": SIGNATURE,
                "signed_at": now,
                "submit_state": reporting.PENDING,
                "created_at": now,
                "updated_at": now,
            },
        )
    return {"apartment_id": apartment_id, "reservation_id": reservation_id}


def test_one_takes_the_one_form():
    assert host_i18n.plural_key("stays.table.nights", 1) == "stays.table.nights.one"


def test_two_to_four_take_the_few_form():
    for n in (2, 3, 4):
        assert host_i18n.plural_key("stays.table.nights", n) == "stays.table.nights.few"


def test_zero_and_five_take_the_bare_key():
    for n in (0, 5, 11):
        assert host_i18n.plural_key("stays.table.nights", n) == "stays.table.nights"


def test_nights_read_correctly_in_english():
    assert _tp("stays.table.nights", 1) == "1 night"
    assert _tp("stays.table.nights", 3) == "3 nights"
    assert _tp("stays.table.nights", 5) == "5 nights"


def test_nights_read_correctly_in_czech():
    assert _tp("stays.table.nights", 1, "cs") == "1 noc"
    assert _tp("stays.table.nights", 3, "cs") == "3 noci"
    assert _tp("stays.table.nights", 5, "cs") == "5 nocí"


def test_the_ready_count_reads_correctly_in_both_languages():
    assert _tp("stay.detail.ready_count", 1) == "Ready to report: 1 guest."
    assert _tp("stay.detail.ready_count", 4) == "Ready to report: 4 guests."
    assert _tp("stay.detail.ready_count", 1, "cs") == "Připraven k hlášení — hostů: 1."
    assert _tp("stay.detail.ready_count", 5, "cs") == "Připraveno k hlášení — hostů: 5."


def test_every_counted_key_ships_all_three_forms_in_both_languages():
    for lang in ("en", "cs"):
        for base in COUNTED_KEYS:
            for key in (base, f"{base}.one", f"{base}.few"):
                assert key in host_i18n.STRINGS[lang], f"{lang} is missing {key}"


def test_the_flashes_read_correctly_in_both_languages():
    english = _FakeRequest("en")
    assert flash_plural(english, "flash.feeds.added", 1) == "Calendar added. 1 stay imported."
    assert flash_plural(english, "flash.feeds.added", 4) == "Calendar added. 4 stays imported."
    assert flash_plural(english, "flash.reservations.accepted", 1) == "1 guest accepted."
    assert flash_plural(english, "flash.error.rejected", 1).startswith(
        "UbyPort rejected 1 guest record —"
    )

    czech = _FakeRequest("cs")
    assert (
        flash_plural(czech, "flash.feeds.added", 1)
        == "Kalendář byl přidán. Importován 1 pobyt."
    )
    assert (
        flash_plural(czech, "flash.feeds.added", 2)
        == "Kalendář byl přidán. Importovány 2 pobyty."
    )
    assert (
        flash_plural(czech, "flash.feeds.added", 5)
        == "Kalendář byl přidán. Importováno 5 pobytů."
    )
    assert flash_plural(czech, "flash.reservations.accepted", 1) == "Přijato 1 host."
    assert flash_plural(czech, "flash.reservations.accepted", 3) == "Přijato 3 hosté."


def test_a_flash_with_two_counts_agrees_both_of_them():
    english = _FakeRequest("en")
    assert flash_plural(
        english,
        "flash.reservations.sent",
        1,
        guests=1,
        stays=plural_param(english, "flash.reservations.sent.stays", 2),
    ) == "Sent 1 guest record across 2 stays."
    assert flash_plural(
        english,
        "flash.reservations.sent",
        3,
        guests=3,
        stays=plural_param(english, "flash.reservations.sent.stays", 1),
    ) == "Sent 3 guest records across 1 stay."

    czech = _FakeRequest("cs")
    assert flash_plural(
        czech,
        "flash.reservations.sent",
        3,
        guests=3,
        stays=plural_param(czech, "flash.reservations.sent.stays", 2),
    ) == "Odeslány 3 záznamy hostů v 2 pobytech."
    assert flash_plural(
        czech,
        "flash.reservations.sent",
        5,
        guests=5,
        stays=plural_param(czech, "flash.reservations.sent.stays", 1),
    ) == "Odesláno 5 záznamů hostů v 1 pobytu."


def test_the_sync_flash_keeps_its_other_tallies():
    request = _FakeRequest("en")
    assert flash_plural(
        request, "flash.feeds.synced", 1, created=1, updated=0, cancelled=0
    ) == "Synced 1 calendar: 1 new, 0 updated, 0 cancelled."


def test_no_counted_string_still_shows_a_plural_hack():
    for lang in ("en", "cs"):
        for base in COUNTED_KEYS:
            for key in (base, f"{base}.one", f"{base}.few"):
                text = host_i18n.STRINGS[lang][key]
                assert "(s)" not in text, f"{lang} {key} still has an (s) hack"
                assert "(ů)" not in text, f"{lang} {key} still has an (ů) hack"


def test_the_stays_list_shows_the_czech_few_form():
    _seed(nights=3)
    try:
        page = _browser("cs").get("/reservations")
        assert page.status_code == 200
        assert "3 noci" in page.text
        assert "3 nocí" not in page.text
    finally:
        _cleanup()


def test_the_stays_list_shows_the_czech_one_form():
    _seed(nights=1)
    try:
        page = _browser("cs").get("/reservations")
        assert page.status_code == 200
        assert "1 noc" in page.text
        assert "1 nocí" not in page.text
    finally:
        _cleanup()


def test_the_stays_list_shows_the_english_one_form():
    _seed(nights=1)
    try:
        page = _browser("en").get("/reservations")
        assert page.status_code == 200
        assert "1 night" in page.text
        assert "1 nights" not in page.text
    finally:
        _cleanup()


def test_the_stay_detail_shows_the_singular_ready_count():
    seeded = _seed(nights=3, pending=1)
    try:
        page = _browser("en").get(f"/reservations/{seeded['reservation_id']}")
        assert page.status_code == 200
        assert "Ready to report: 1 guest." in page.text
        assert "guest record(s)" not in page.text
    finally:
        _cleanup()


def test_the_stay_detail_shows_the_czech_ready_count():
    seeded = _seed(nights=3, pending=2)
    try:
        page = _browser("cs").get(f"/reservations/{seeded['reservation_id']}")
        assert page.status_code == 200
        assert "Připraveno k hlášení — hostů: 2." in html.unescape(page.text)
        assert "záznam(ů)" not in page.text
    finally:
        _cleanup()
