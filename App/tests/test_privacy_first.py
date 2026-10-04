"""WP27 (privacy first): the app sets no cookie beyond the strictly necessary set.

The brand says "no tracking cookies". This test makes that claim checkable: it
crawls every parameter-free GET page anonymously and signed in (host and
platform admin), walks a guest through the PIN, claim and form, switches the
language, and records the name of every ``Set-Cookie`` header the app sent. The
set must equal ``cookie_inventory.STRICTLY_NECESSARY_COOKIES``, which is what
the privacy page publishes. A new cookie, from any route, fails here until it
is justified, documented in ``cookie_inventory.py`` and added to the set.
"""
from __future__ import annotations

import base64
import io
import re
from datetime import timedelta
from http.cookies import SimpleCookie
from typing import Iterable, Set

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import auth, claim, cookie_inventory, db, i18n, landing_i18n, public_guides
from app.main import app
from tests.conftest import complete_guest_claim

TOKEN = "privacyfirsttoken"
PIN = "2468"
PASSWORD = "Privacy-First-Pass-1"
_PATH_PARAM = re.compile(r"\{[^}]+\}")


def _png_data_url() -> str:
    buffer = io.BytesIO()
    image = Image.new("RGB", (300, 120), "white")
    for x in range(20, 280):
        image.putpixel((x, 60), (0, 0, 0))
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _get_paths() -> Set[str]:
    """Every GET path without a path parameter, nested routers included."""
    found: Set[str] = set()

    def walk(routes: Iterable, prefix: str = "") -> None:
        for route in routes:
            nested = getattr(route, "original_router", None)
            if nested is not None:
                context = getattr(route, "include_context", None)
                walk(nested.routes, prefix + (getattr(context, "prefix", "") or ""))
                continue
            path = getattr(route, "path", None)
            methods = getattr(route, "methods", None) or ()
            if path is None:
                continue
            if "GET" in methods and not _PATH_PARAM.search(path):
                found.add(prefix + path)
            elif hasattr(route, "routes") and not methods and not path.startswith("/static"):
                walk(route.routes, prefix + path)

    walk(app.router.routes)
    return found


class _Recorder:
    """Collect the cookie names of every response a client receives."""

    def __init__(self) -> None:
        self.names: Set[str] = set()

    def __call__(self, response) -> None:
        for header in response.headers.get_list("set-cookie"):
            parsed = SimpleCookie()
            parsed.load(header)
            self.names.update(parsed.keys())

    def client(self) -> TestClient:
        client = TestClient(app)
        client.event_hooks["response"].append(self)
        return client


def _cleanup() -> None:
    apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
    if apartment:
        stays = "(SELECT id FROM reservation WHERE apartment_id = ?)"
        db.execute(f"DELETE FROM reservation_claim WHERE reservation_id IN {stays}", (apartment["id"],))
        db.execute(f"DELETE FROM guest WHERE reservation_id IN {stays}", (apartment["id"],))
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],))
        db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))
        db.execute("DELETE FROM legal_entity WHERE id = ?", (apartment["legal_entity_id"],))


def _account(username: str, role: str) -> int:
    """Accounts are kept between tests: audit rows point at them."""
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (username,))
    if row:
        return int(row["id"])
    return auth.create_account(
        username, PASSWORD, username.title(), role=role, must_change_password=False
    )


def _fixture():
    db.init_db()
    _cleanup()
    host_id = _account("privacyfirst-host", "host")
    _account("privacyfirst-admin", "admin")
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert(
        "legal_entity", {"name": "Privacy first", "owner_user_id": host_id, "created_at": now}
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": host_id,
            "internal_name": "Privacy flat",
            "permalink_token": TOKEN,
            "permalink_pin": PIN,
            "permalink_window_days": 14,
            "default_purpose": "10",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    stay_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": "privacy-first-stay",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    return stay_id, apartment_id


def _crawl(client: TestClient, paths: Iterable[str]) -> None:
    for path in sorted(paths):
        for lang in ("en", "cs"):
            client.get(f"{path}?lang={lang}", follow_redirects=True)


def _sign_in(client: TestClient, username: str) -> None:
    response = client.post(
        "/login?lang=en",
        data={"username": username, "password": PASSWORD, "remember": "1"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text


@pytest.fixture
def guest_pin_on(monkeypatch):
    monkeypatch.setattr("app.config.GUEST_PIN_REQUIRED", True)


def test_a_full_crawl_sets_exactly_the_strictly_necessary_cookies(guest_pin_on):
    stay_id, apartment_id = _fixture()
    recorder = _Recorder()
    paths = _get_paths()
    assert {"/", "/privacy", "/cenik", "/jak-to-funguje", "/housebook", "/settings"} <= paths
    try:
        # Public and auth pages, anonymous.
        guides = {f"/pruvodce/{slug}" for slug in public_guides.GUIDES}
        _crawl(recorder.client(), paths | guides)

        # Host app and platform admin, signed in, then signed out.
        for username in ("privacyfirst-host", "privacyfirst-admin"):
            host = recorder.client()
            _sign_in(host, username)
            _crawl(host, paths | {f"/reservations/{stay_id}", f"/apartments/{apartment_id}"})
            host.post("/language", data={"lang": "cs", "next": "/"}, follow_redirects=True)
            host.post("/logout", follow_redirects=True)

        # Guest: PIN, stay page, claim, form, confirmation, privacy notice.
        guest = recorder.client()
        guest.get(f"/l/{TOKEN}?lang=cs", follow_redirects=True)
        pinned = guest.post(
            f"/l/{TOKEN}/pin?lang=en",
            data={"pin": PIN, "return_to": f"/l/{TOKEN}"},
            follow_redirects=False,
        )
        assert pinned.status_code == 303, pinned.text
        guest.get(f"/l/{TOKEN}/{stay_id}?lang=en", follow_redirects=True)
        complete_guest_claim(guest, TOKEN, stay_id, party_size=1)
        saved = guest.post(
            f"/l/{TOKEN}/{stay_id}/save?lang=en",
            data={
                "surname": "Novak",
                "first_name": "Demo",
                "birth_date": "1.1.1990",
                "nationality": "CZE",
                "doc_number": "123456789",
                "res_street": "Demo Street 1",
                "res_city": "Demo City",
                "res_country": "CZE",
                "purpose": "10",
                "party_size": "1",
                "signature": _png_data_url(),
                "legal_ack": "1",
            },
            follow_redirects=True,
        )
        assert saved.status_code == 200, saved.text
        guest.get(f"/l/{TOKEN}/privacy?lang=cs", follow_redirects=True)
    finally:
        _cleanup()

    assert recorder.names == cookie_inventory.STRICTLY_NECESSARY_COOKIES, (
        "The app set a cookie outside the documented strictly necessary set, or the "
        "crawl no longer reaches one of them. A new cookie needs a purpose, a lifetime "
        "and a row in cookie_inventory.py, and UbyHost sets no tracking cookie. "
        f"Unexpected: {sorted(recorder.names - cookie_inventory.STRICTLY_NECESSARY_COOKIES)}; "
        f"not reached: {sorted(cookie_inventory.STRICTLY_NECESSARY_COOKIES - recorder.names)}"
    )


def test_the_strictly_necessary_set_is_the_first_party_cookie_inventory():
    assert cookie_inventory.STRICTLY_NECESSARY_COOKIES == {
        "ubyhost_session",
        "ubyhost_csrf",
        "ubyhost_lang",
        "ubyhost_pin",
        "ubyhost_owned",
        "ubyhost_claim",
        "ubyhost_guest_lang",
    }


def test_the_privacy_first_section_is_on_the_marketing_pages():
    db.init_db()
    client = TestClient(app)
    for path in ("/", "/cenik", "/jak-to-funguje"):
        for lang in ("en", "cs"):
            html = client.get(f"{path}?lang={lang}").text
            strings = landing_i18n.LANDING_STRINGS[lang]
            assert strings["privacy_first.title"] in html, (path, lang)
            assert 'href="/privacy?lang=' + lang + '"' in html, (path, lang)
            for name in ("law", "cookies", "trackers", "photos"):
                assert strings[f"privacy_first.{name}.title"] in html, (path, lang, name)


def test_the_privacy_first_line_is_on_the_privacy_and_guest_pages():
    stay_id, _apartment_id = _fixture()
    try:
        client = TestClient(app)
        for lang in ("en", "cs"):
            line = landing_i18n.LANDING_STRINGS[lang]["privacy_first.line"]
            assert line in client.get(f"/privacy?lang={lang}").text, lang
            guest_line = i18n.STRINGS[lang]["privacy_first_line"]
            page = client.get(f"/l/{TOKEN}/{stay_id}?lang={lang}", follow_redirects=True).text
            assert guest_line in page, lang
            notice = client.get(f"/l/{TOKEN}/privacy?lang={lang}", follow_redirects=True).text
            assert guest_line in notice, lang
    finally:
        _cleanup()


def test_the_claims_never_say_no_cookies_in_absolute_terms():
    """The app does use strictly necessary cookies; the copy says "no tracking"."""
    for lang in ("en", "cs"):
        texts = [v for k, v in landing_i18n.LANDING_STRINGS[lang].items() if k.startswith("privacy_first")]
        texts.append(i18n.STRINGS[lang]["privacy_first_line"])
        for text in texts:
            lowered = text.lower()
            assert "no cookies" not in lowered and "žádné cookies" not in lowered, text
            assert "bez cookies" not in lowered, text
