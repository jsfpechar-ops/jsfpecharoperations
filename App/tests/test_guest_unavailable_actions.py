"""UX-118 (audit A-31): what the dead-end guest page still offers."""
import html
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from starlette.requests import Request

from app import auth, claim, db, i18n
from app.main import app
from app.routes import guest as guest_routes

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"
TOKEN = "unavailableact"
ENTITY = "Unavailable Action Test"
ADMIN_USERNAME = "unavailable-action-admin"

NO_RESTART = ("form_locked", "already_filed", "not_yours")
RESTARTABLE = ("no_stays", "bad_link", "stay_gone", "form_expired", "rate_limited")


def _read(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def _request(path: str = "/l/unavailableact") -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "server": ("testserver", 80),
            "root_path": "",
            "path": path,
            "query_string": b"",
            "headers": [],
        }
    )


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
    return auth.create_account(f"{ADMIN_USERNAME}@example.test", "Unavailable action admin", role="admin", username=ADMIN_USERNAME)


def _seed() -> int:
    """One apartment with one upcoming stay, so the page keeps its host footer."""
    db.init_db()
    _cleanup()
    owner_id = _ensure_admin()
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert(
        "legal_entity",
        {
            "name": ENTITY,
            "seat": "Praha 4",
            "contact_email": "unavailable@unavailableact.test",
            "owner_user_id": owner_id,
            "created_at": now,
        },
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": owner_id,
            "internal_name": "Unavailable action flat",
            "city_en": "Prague",
            "permalink_token": TOKEN,
            "permalink_window_days": 30,
            "active": 1,
            "created_at": now,
        },
    )
    return db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "airbnb",
            "uid": "unavailable-action-1",
            "date_from": (today + timedelta(days=4)).isoformat(),
            "date_to": (today + timedelta(days=6)).isoformat(),
            "summary": "Unavailable action reservation",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
    )


def _page(reason: str, lang: str = "en", *, token: str | None = TOKEN) -> str:
    response = guest_routes._unavailable(_request(), lang, reason, 404, token)
    return html.unescape(response.body.decode("utf-8"))


def test_the_why_fold_is_gone_from_the_dead_end_page():
    template = _read("guest/unavailable.html")
    assert "_why.html" not in template


def test_only_the_reasons_that_can_be_restarted_offer_it():
    assert guest_routes._NO_RESTART_REASONS == frozenset(NO_RESTART)
    _seed()
    try:
        for reason in RESTARTABLE:
            page = _page(reason)
            assert i18n.STRINGS["en"]["start_over"] in page, reason
        for reason in NO_RESTART:
            page = _page(reason)
            assert i18n.STRINGS["en"]["start_over"] not in page, reason
            # the reason itself is still spelled out, and the host footer stays
            assert i18n.STRINGS["en"][f"{reason}_title"] in page, reason
            assert i18n.STRINGS["en"][f"{reason}_help"] in page, reason
    finally:
        _cleanup()


def test_a_tokenless_dead_end_never_offers_start_again():
    _seed()
    try:
        page = _page("bad_link", token=None)
        assert i18n.STRINGS["en"]["start_over"] not in page
        assert i18n.STRINGS["en"]["bad_link_title"] in page
    finally:
        _cleanup()


def test_the_czech_page_hides_it_the_same_way():
    _seed()
    try:
        assert i18n.STRINGS["cs"]["start_over"] not in _page("form_locked", "cs")
        assert i18n.STRINGS["cs"]["start_over"] in _page("stay_gone", "cs")
    finally:
        _cleanup()


def test_the_live_stay_gone_page_still_offers_start_again():
    _seed()
    try:
        response = TestClient(app).get(f"/l/{TOKEN}/999999?lang=en")
        assert response.status_code == 404
        assert i18n.STRINGS["en"]["start_over"] in response.text
        assert i18n.STRINGS["en"]["stay_gone_title"] in response.text
    finally:
        _cleanup()
