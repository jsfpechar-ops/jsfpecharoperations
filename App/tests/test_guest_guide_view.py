"""0344: the guest side of the guest guide, both doors."""
from __future__ import annotations

import io
import pathlib
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import auth, claim, config, db, guest_guide, guide_photos, guide_token, mail, rate_limit
from app.main import app
from app.routes.guest_guide_view import QR_MAX_VIEWS, booked_level
from tests.conftest import login_as

TOKEN = "guideviewtok0344"
TEMPLATES = pathlib.Path(__file__).resolve().parents[1] / "app" / "templates" / "guest"


def _jpeg() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (640, 480), (120, 90, 60)).save(out, format="JPEG")
    return out.getvalue()


@pytest.fixture
def ws(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "guide.sqlite3")
    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    monkeypatch.setattr(guide_photos, "PHOTOS_DIR", tmp_path / "guide_photos")
    monkeypatch.setattr(auth, "staging_no_login", lambda: False)
    db.init_db()
    owner = auth.create_account("view-owner@example.test", "View owner", username="view-owner", role="host")
    other = auth.create_account("view-other@example.test", "Other owner", username="view-other", role="host")
    now = db.utcnow()

    def home(name, user, token):
        return db.insert("apartment", {
            "owner_user_id": user, "internal_name": name, "active": 1, "created_at": now,
            "automation_mode": "manual", "permalink_token": token, "permalink_window_days": 14,
        })
    mine = home("Vivus / 3", owner, TOKEN)
    foreign = home("Other flat", other, "otherflattok0344")
    for apt in (mine, foreign):
        guest_guide.ensure_defaults(db.query_one("SELECT * FROM apartment WHERE id = ?", (apt,)))
    yield {"home": mine, "foreign": foreign, "client": TestClient(app)}


def _cards(apt_id):
    return {r["kind"]: r for r in guest_guide.items(apt_id)}


def _go_live(apt_id, **fields):
    """Fill every must-have card so the guide is live; extra kinds get the given fields."""
    cards = _cards(apt_id)
    for kind in guest_guide.MUST_HAVE:
        guest_guide.save(apt_id, cards[kind]["id"], {"steps": f"Do the {kind} thing"})
    for kind, values in fields.items():
        guest_guide.save(apt_id, cards[kind]["id"], values)
    assert guest_guide.progress(apt_id)["live"]
    return _cards(apt_id)


def _stay(apt_id, start_in_days, nights=2):
    start = claim.prague_today() + timedelta(days=start_in_days)
    return db.insert("reservation", {
        "apartment_id": apt_id, "uid": f"g0344-{start_in_days}", "source": "airbnb", "status": "active",
        "date_from": start.isoformat(), "date_to": (start + timedelta(days=nights)).isoformat(),
        "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })


def _qr(ws):
    return guide_token.ensure(ws["home"])


HARDENED = {"cache-control": "no-store", "x-robots-tag": "noindex, nofollow", "referrer-policy": "no-referrer"}


def _assert_hardened(response):
    for name, value in HARDENED.items():
        assert response.headers.get(name) == value, (name, response.headers.get(name))


# --- the QR token ------------------------------------------------------------

def test_the_token_is_long_random_created_once_and_rotates(ws):
    first = guide_token.ensure(ws["home"])
    assert len(first) >= 32 and first == guide_token.ensure(ws["home"])
    second = guide_token.rotate(ws["home"])
    assert second != first and guide_token.current(ws["home"]) == second
    assert guide_token.apartment_for(first) is None
    assert guide_token.apartment_for(second)["id"] == ws["home"]
    assert guide_token.apartment_for("") is None and guide_token.apartment_for("x" * 65) is None


def test_opening_the_host_guide_page_creates_the_token(ws):
    assert guide_token.current(ws["home"]) is None
    client = ws["client"]
    assert login_as(client, "view-owner", url="/login?lang=en", follow_redirects=False).status_code == 303
    assert client.get(f"/apartments/{ws['home']}/guide").status_code == 200
    assert guide_token.current(ws["home"])


def test_unknown_and_rotated_tokens_are_a_plain_404(ws):
    client = ws["client"]
    old = _qr(ws)
    _go_live(ws["home"])
    assert client.get(f"/g/{old}").status_code == 200
    guide_token.rotate(ws["home"])
    for token in (old, "nonsense", "a" * 100, TOKEN):
        response = client.get(f"/g/{token}?lang=en")
        assert response.status_code == 404, token
        assert "Vivus" not in response.text and "guide_" not in response.text
        _assert_hardened(response)
    assert client.get(f"/g/{old}/photos/1/1").status_code == 404


def test_a_guide_that_is_not_live_shows_the_not_ready_page(ws):
    response = ws["client"].get(f"/g/{_qr(ws)}?lang=en")
    assert response.status_code == 200
    assert "data-guide-not-ready" in response.text
    assert "This guide is not ready yet" in response.text
    assert "data-guide-card" not in response.text
    _assert_hardened(response)
    czech = ws["client"].get(f"/g/{_qr(ws)}?lang=cs")
    assert "Tento průvodce ještě není hotový" in czech.text


# --- what each level sees -------------------------------------------------------

def _seed_levels(ws):
    cards = _go_live(
        ws["home"],
        wifi={"location": "Hall cupboard", "steps": "Open the cupboard\nRead the sticker", "watch_out": "Do not unplug the router", "video_url": "https://example.test/wifi"},
        keys={"steps": "Spare key in box 7", "visibility": "booked"},
        trash={"steps": "Bins are in the yard", "visibility": "host"},
        hot_water={"steps": "Fill the tank"},
    )
    db.update("guide_item", cards["hot_water"]["id"], {"state": "check"})  # a draft
    guest_guide.skip(ws["home"], cards["house_rules"]["id"])
    return _cards(ws["home"])


def test_the_qr_page_shows_everyone_cards_only(ws):
    _seed_levels(ws)
    response = ws["client"].get(f"/g/{_qr(ws)}?lang=en")
    assert response.status_code == 200
    body = response.text
    _assert_hardened(response)
    assert "Wi-Fi" in body and "Hall cupboard" in body
    assert '<ol class="g-guide-steps">' in body and "<li>Read the sticker</li>" in body
    assert 'class="g-guide-warn"' in body and "Do not unplug the router" in body
    assert 'href="https://example.test/wifi"' in body
    for hidden in ("Spare key in box 7", "Bins are in the yard", "Fill the tank", "House rules"):
        assert hidden not in body, hidden
    assert "data-guide-window-note" not in body
    assert "guide_" not in body  # every key has copy
    assert f"/l/{TOKEN}" not in body  # the stay link token never leaks onto the public page
    # Must-have topics come in TOPICS order: arrival before wifi before heating.
    assert body.index("Arrival") < body.index("Wi-Fi") < body.index("Heating")


def test_the_czech_qr_page_is_czech(ws):
    _seed_levels(ws)
    body = ws["client"].get(f"/g/{_qr(ws)}?lang=cs").text
    assert "<h1>Váš průvodce</h1>" in body and "Příjezd" in body and "Pozor:" in body and "Nic o vás se tu neukládá." in body


def test_booked_level_window_edges():
    today = claim.prague_today()

    def stay(start, nights=2):
        s = today + timedelta(days=start)
        return {"date_from": s.isoformat(), "date_to": (s + timedelta(days=nights)).isoformat()}
    assert booked_level(stay(2), today) == "everyone"
    assert booked_level(stay(1), today) == "booked"  # the day before check-in
    assert booked_level(stay(0), today) == "booked"
    assert booked_level(stay(-2), today) == "booked"  # checkout day
    assert booked_level(stay(-3), today) == "everyone"  # checked out yesterday
    assert booked_level({"date_from": "", "date_to": None}, today) == "everyone"


@pytest.mark.parametrize("start_in_days,level", [(2, "everyone"), (1, "booked"), (-1, "booked"), (-2, "booked"), (-3, "everyone")])
def test_the_stay_door_follows_the_window(ws, start_in_days, level):
    _seed_levels(ws)
    reservation_id = _stay(ws["home"], start_in_days)
    response = ws["client"].get(f"/l/{TOKEN}/{reservation_id}/guide?lang=en")
    assert response.status_code == 200, response.text[:300]
    body = response.text
    _assert_hardened(response)
    assert "Hall cupboard" in body
    assert ("Spare key in box 7" in body) == (level == "booked")
    assert ("data-guide-window-note" in body) == (level == "everyone")
    for hidden in ("Bins are in the yard", "Fill the tank"):
        assert hidden not in body


def test_the_stay_door_keeps_the_stay_page_checks(ws):
    _seed_levels(ws)
    reservation_id = _stay(ws["home"], 0)
    client = ws["client"]
    assert client.get(f"/l/{TOKEN}/{reservation_id + 100}/guide").status_code == 404
    assert client.get(f"/l/wrongtoken/{reservation_id}/guide").status_code == 404
    foreign_stay = _stay(ws["foreign"], 0)
    assert client.get(f"/l/{TOKEN}/{foreign_stay}/guide").status_code == 404
    db.update("reservation", reservation_id, {"status": "cancelled"})
    assert client.get(f"/l/{TOKEN}/{reservation_id}/guide").status_code == 404


def test_the_stay_door_says_not_ready_until_live(ws):
    reservation_id = _stay(ws["home"], 0)
    response = ws["client"].get(f"/l/{TOKEN}/{reservation_id}/guide?lang=en")
    assert response.status_code == 200 and "data-guide-not-ready" in response.text


def test_the_stay_page_links_to_the_guide():
    stay = (TEMPLATES / "stay.html").read_text(encoding="utf-8")
    assert 'href="/l/{{ token }}/{{ reservation.id }}/guide?lang={{ lang }}"' in stay
    assert "t('guide_title')" in stay


# --- photos --------------------------------------------------------------------

def _photos(ws):
    cards = _seed_levels(ws)
    wifi = guide_photos.add(ws["home"], cards["wifi"]["id"], _jpeg(), "image/jpeg")
    keys_photo = guide_photos.add(ws["home"], cards["keys"]["id"], _jpeg(), "image/jpeg")
    return cards, wifi, keys_photo


def test_photos_follow_the_card_level_on_both_doors(ws):
    cards, wifi, keys_photo = _photos(ws)
    client = ws["client"]
    qr = _qr(ws)
    page = client.get(f"/g/{qr}")
    assert f"/g/{qr}/photos/{cards['wifi']['id']}/{wifi}" in page.text
    shown = client.get(f"/g/{qr}/photos/{cards['wifi']['id']}/{wifi}")
    assert shown.status_code == 200 and shown.headers["content-type"] == "image/jpeg"
    assert shown.headers["cache-control"] == "private, max-age=3600"
    assert shown.headers["x-robots-tag"] == "noindex" and shown.headers["referrer-policy"] == "no-referrer"
    # A booked card's photo: never through the QR door.
    assert client.get(f"/g/{qr}/photos/{cards['keys']['id']}/{keys_photo}").status_code == 404
    # The photo id alone is not enough: it must sit on the card named in the URL.
    assert client.get(f"/g/{qr}/photos/{cards['wifi']['id']}/{keys_photo}").status_code == 404
    assert client.get(f"/g/{qr}/photos/{cards['heating']['id']}/{wifi}").status_code == 404
    # The stay door: booked photo inside the window, not outside it.
    inside = _stay(ws["home"], 0)
    outside = _stay(ws["home"], 5)
    assert client.get(f"/l/{TOKEN}/{inside}/guide/photos/{cards['keys']['id']}/{keys_photo}").status_code == 200
    assert client.get(f"/l/{TOKEN}/{outside}/guide/photos/{cards['keys']['id']}/{keys_photo}").status_code == 404
    assert client.get(f"/l/{TOKEN}/{outside}/guide/photos/{cards['wifi']['id']}/{wifi}").status_code == 200


def test_a_photo_of_another_property_is_not_found(ws):
    cards, wifi, _ = _photos(ws)
    foreign_token = guide_token.ensure(ws["foreign"])
    _go_live(ws["foreign"])
    assert ws["client"].get(f"/g/{foreign_token}/photos/{cards['wifi']['id']}/{wifi}").status_code == 404


# --- rate limit ----------------------------------------------------------------

def test_the_qr_page_is_rate_limited_per_address(ws):
    _go_live(ws["home"])
    client = ws["client"]
    qr = _qr(ws)
    key = rate_limit.client_key(_request_stub(), "guide_qr")  # TestClient's peer address
    for _ in range(QR_MAX_VIEWS):
        rate_limit.record("guide_qr", key)
    response = client.get(f"/g/{qr}?lang=en")
    assert response.status_code == 429
    _assert_hardened(response)
    db.execute("DELETE FROM rate_limit_event WHERE scope = 'guide_qr'", ())
    assert client.get(f"/g/{qr}").status_code == 200


def _request_stub():
    class _Client:
        host = "testclient"

    class _Request:
        client = _Client()
    return _Request()


def test_the_qr_page_shows_the_host_name_but_not_phone_or_email(ws):
    entity = db.insert("legal_entity", {
        "name": "Jana Fiktivni", "contact_email": "jana@example.test", "contact_phone": "+420 600 000 000",
        "created_at": db.utcnow(),
    })
    db.execute("UPDATE apartment SET legal_entity_id = ? WHERE id = ?", (entity, ws["home"]))
    _go_live(ws["home"])
    body = ws["client"].get(f"/g/{_qr(ws)}?lang=en").text
    assert "Jana Fiktivni" in body
    assert "jana@example.test" not in body and "600 000 000" not in body
