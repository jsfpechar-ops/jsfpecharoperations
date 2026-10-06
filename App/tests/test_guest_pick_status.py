"""UX-115 (audit A-28): the stay-picker status wording, colour and hero."""
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app import auth, claim, db, i18n
from app.main import app
from app.routes import guest as guest_routes

APP = Path(__file__).resolve().parents[1] / "app"
TEMPLATES = APP / "templates"
STATIC = APP / "static"
TOKEN = "pickstatus"
ENTITY = "Pick Status Test"
ADMIN_USERNAME = "pick-status-admin"

AUDIT_COPY = {
    "en": {
        "stay_not_started": "Not started yet",
        "stay_arriving_today": "Arriving today",
        "stay_ongoing": "Ongoing",
    },
    "cs": {
        "stay_not_started": "Zatím nezačato",
        "stay_arriving_today": "Příjezd dnes",
        "stay_ongoing": "Právě probíhá",
    },
}


def _read(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


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
    db.execute(
        "DELETE FROM legal_entity WHERE name = ? AND id NOT IN "
        "(SELECT legal_entity_id FROM apartment WHERE legal_entity_id IS NOT NULL)",
        (ENTITY,),
    )


def _ensure_admin() -> int:
    db.init_db()
    account = db.query_one("SELECT * FROM user_account WHERE username = ?", (ADMIN_USERNAME,))
    if account:
        return account["id"]
    return auth.create_account(f"{ADMIN_USERNAME}@example.test", "Pick status admin", role="admin", username=ADMIN_USERNAME)


def _seed() -> int:
    """One apartment with a stay that arrives today and one later in the window."""
    db.init_db()
    _cleanup()
    owner_id = _ensure_admin()
    now = db.utcnow()
    entity_id = db.insert(
        "legal_entity",
        {
            "name": ENTITY,
            "seat": "Praha 1",
            "contact_email": "pick@pickstatus.test",
            "owner_user_id": owner_id,
            "created_at": now,
        },
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": owner_id,
            "internal_name": "Pick status flat",
            "city_en": "Prague",
            "permalink_token": TOKEN,
            "permalink_window_days": 30,
            "active": 1,
            "created_at": now,
        },
    )
    return apartment_id


def _stay(apartment_id: int, uid: str, start_offset: int, end_offset: int) -> int:
    today = claim.prague_today()
    now = db.utcnow()
    return db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "airbnb",
            "uid": uid,
            "date_from": (today + timedelta(days=start_offset)).isoformat(),
            "date_to": (today + timedelta(days=end_offset)).isoformat(),
            "summary": "Pick status reservation",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )


def _page(lang: str = "en", *, claimed: int | None = None) -> str:
    client = TestClient(app)
    if claimed is not None:
        client.cookies.set(
            guest_routes.CLAIM_COOKIE,
            guest_routes._claim_serializer().dumps({str(claimed): 0}),
        )
    response = client.get(f"/l/{TOKEN}?lang={lang}")
    assert response.status_code == 200
    return response.text


def test_the_audit_copy_is_shipped_in_both_languages():
    for lang, expected in AUDIT_COPY.items():
        for key, value in expected.items():
            assert i18n.STRINGS[lang][key] == value, f"{lang}.{key}"


def test_the_hero_kicker_is_dropped_from_the_template_and_the_dictionary():
    template = _read("guest/pick.html")
    assert "g-question-kicker" not in template
    assert "arrival_kicker" not in template
    for lang in ("en", "cs"):
        assert "arrival_kicker" not in i18n.STRINGS[lang]


def test_arriving_today_is_checked_before_ongoing():
    template = _read("guest/pick.html")
    arriving = template.index("row.arriving_today")
    ongoing = template.index("row.ongoing")
    assert arriving < ongoing


def test_every_status_uses_the_muted_colour():
    template = _read("guest/pick.html")
    for key in ("stay_arriving_today", "stay_ongoing", "stay_not_started"):
        assert f'<span class="g-lane-status quiet">{{{{ t(\'{key}\') }}}}</span>' in template
    css = (STATIC / "guest.css").read_text(encoding="utf-8")
    assert ".g-lane-status.ongoing" not in css
    assert ".g-lane-status.quiet { color: var(--g-muted) !important; font-weight: 500; }" in css


def test_a_later_stay_is_not_started_yet():
    apartment_id = _seed()
    try:
        _stay(apartment_id, "pick-later", 6, 8)
        page = _page()
        assert i18n.STRINGS["en"]["stay_not_started"] in page
        assert i18n.STRINGS["en"]["stay_arriving_today"] not in page
    finally:
        _cleanup()


def test_a_stay_arriving_today_says_so_instead_of_ongoing():
    apartment_id = _seed()
    try:
        _stay(apartment_id, "pick-today", 0, 2)
        page = _page()
        assert i18n.STRINGS["en"]["stay_arriving_today"] in page
        assert f">{i18n.STRINGS['en']['stay_ongoing']}<" not in page
        czech = _page("cs")
        assert i18n.STRINGS["cs"]["stay_arriving_today"] in czech
    finally:
        _cleanup()


def test_a_stay_already_under_way_still_reads_ongoing():
    apartment_id = _seed()
    try:
        stay_id = _stay(apartment_id, "pick-started", -1, 2)
        page = _page(claimed=stay_id)
        assert i18n.STRINGS["en"]["stay_ongoing"] in page
        assert i18n.STRINGS["en"]["stay_arriving_today"] not in page
    finally:
        _cleanup()
