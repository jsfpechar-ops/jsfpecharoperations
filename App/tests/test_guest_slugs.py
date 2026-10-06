"""Readable guest links (WP19): /l/{readable}-{code} beside /l/{token}.

The token stays the secret every guest-side control is keyed on. These tests
pin what a guest and a host can see: both links open the same pages, an
earlier slug redirects, a wrong code is a 404, and the PIN cookie and the
lockout do not care which of the two links the guest used.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth, claim, db, guest_slug, rate_limit
from app.main import app
from tests.conftest import login_as

TOKEN = "slugtesttoken23456789"
PIN = "731905"
USERNAME = "slug-host"


@pytest.fixture
def pin_required(monkeypatch):
    monkeypatch.setattr("app.config.GUEST_PIN_REQUIRED", True)


def _cleanup():
    # By owner too: "Generate a new link" replaces permalink_token, and a
    # leftover apartment makes demo.seed() (test_demo_seed) refuse to seed.
    for row in db.query(
        "SELECT id, legal_entity_id FROM apartment WHERE permalink_token = ? "
        "OR owner_user_id IN (SELECT id FROM user_account WHERE username = ?)",
        (TOKEN, USERNAME),
    ):
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (row["id"],))
        db.execute("DELETE FROM alert WHERE apartment_id = ?", (row["id"],))
        db.execute("DELETE FROM apartment WHERE id = ?", (row["id"],))
        db.execute("DELETE FROM legal_entity WHERE id = ?", (row["legal_entity_id"],))
    db.execute("DELETE FROM rate_limit_event")


def _owner() -> int:
    """The host account is kept between tests: other rows reference it."""
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    if row:
        return int(row["id"])
    return auth.create_account(f"{USERNAME}@example.test", "Slug Host", username=USERNAME)


@pytest.fixture
def flat():
    """One property named in Czech, with a stay starting today."""
    db.init_db()
    _cleanup()
    now = db.utcnow()
    today = claim.prague_today()
    owner = _owner()
    entity = db.insert("legal_entity", {"name": "Slug s.r.o.", "owner_user_id": owner, "created_at": now})
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity,
            "owner_user_id": owner,
            "internal_name": "Vinohrady Studio – Žižkov",
            "permalink_token": TOKEN,
            "permalink_pin": PIN,
            "permalink_window_days": 14,
            "default_purpose": "10",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    stay = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": "slug-test-stay",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=2)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    slug = guest_slug.ensure(apartment)
    try:
        yield {"id": apartment_id, "stay": stay, "slug": slug, "owner": owner}
    finally:
        _cleanup()


def _host_client() -> TestClient:
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    return client


# --- slug generation -------------------------------------------------------

def test_czech_names_are_folded_to_plain_letters():
    assert guest_slug.readable_part("Příliš žluťoučký kůň úpěl ďábelské ódy") == (
        "prilis-zlutoucky-kun-upel-dabelske-ody"
    )
    assert guest_slug.readable_part("Byt U Tří Růží, 2+kk") == "byt-u-tri-ruzi-2-kk"
    assert guest_slug.readable_part("ŘEČNÍ  Ťulpas -- Ďáblice") == "recni-tulpas-dablice"
    assert guest_slug.readable_part("Straße Łódź Ørsted") == "strasse-lodz-orsted"


def test_the_readable_part_is_cut_at_a_word_boundary():
    name = "Apartmán s výhledem na Pražský hrad a Karlův most"
    readable = guest_slug.readable_part(name)
    assert len(readable) <= guest_slug.READABLE_MAX
    assert readable == "apartman-s-vyhledem-na-prazsky-hrad-a"
    # Exactly at the limit nothing is dropped.
    assert guest_slug.readable_part("a" * 40) == "a" * 40
    # One word longer than the limit has no boundary, so it is cut hard.
    assert guest_slug.readable_part("b" * 55) == "b" * 40


def test_reserved_words_are_never_a_readable_part():
    for word in ("pin", "claim", "party", "privacy", "another", "new", "edit", "save", "confirm"):
        assert guest_slug.validate_readable(word) == (word, "reserved")
        assert guest_slug.validate_readable(word.upper())[1] == "reserved"
    assert guest_slug.validate_readable("pin flat") == ("pin-flat", "")
    # A property called "Party" still gets a link, just not that word.
    assert guest_slug._generated_readable("Party") == guest_slug.FALLBACK_READABLE


def test_a_name_with_nothing_usable_is_rejected_or_falls_back():
    assert guest_slug.validate_readable("  ★ — ★ ") == ("", "empty")
    assert guest_slug._generated_readable("★") == guest_slug.FALLBACK_READABLE


def test_the_code_uses_the_token_alphabet_and_six_characters(flat):
    readable, code = flat["slug"].rsplit("-", 1)
    assert readable == "vinohrady-studio-zizkov"
    assert len(code) == 6
    assert set(code) <= set(auth.PERMALINK_ALPHABET)


def test_the_migration_gives_every_property_a_slug(flat):
    db.execute("DELETE FROM apartment_slug WHERE apartment_id = ?", (flat["id"],))
    db.init_db()
    first = guest_slug.current(flat["id"])
    assert first and first.startswith("vinohrady-studio-zizkov-")
    db.init_db()  # idempotent: the existing slug is kept
    assert guest_slug.current(flat["id"]) == first
    assert db.query_one(
        "SELECT COUNT(*) AS n FROM apartment_slug WHERE apartment_id = ?", (flat["id"],)
    )["n"] == 1


def test_deleting_the_property_removes_its_slugs(flat):
    db.execute("DELETE FROM reservation WHERE apartment_id = ?", (flat["id"],))
    db.execute("DELETE FROM apartment WHERE id = ?", (flat["id"],))
    assert guest_slug.lookup(flat["slug"]) is None


# --- routing ---------------------------------------------------------------

def test_the_old_token_link_still_opens_the_picker(flat):
    page = TestClient(app).get(f"/l/{TOKEN}?lang=en")
    assert page.status_code == 200
    # A token visitor's own links stay on the token.
    assert f"/l/{TOKEN}/{flat['stay']}" in page.text


def test_the_current_slug_opens_the_same_picker(flat):
    page = TestClient(app).get(f"/l/{flat['slug']}?lang=en", follow_redirects=False)
    assert page.status_code == 200
    assert f"/l/{flat['slug']}/{flat['stay']}" in page.text
    assert f"/l/{TOKEN}" not in page.text


def test_every_sub_route_resolves_the_slug(flat):
    client = TestClient(app)
    privacy = client.get(f"/l/{flat['slug']}/privacy?lang=en", follow_redirects=False)
    assert privacy.status_code == 200
    stay = client.get(f"/l/{flat['slug']}/{flat['stay']}?lang=en", follow_redirects=False)
    # Mail is on in tests, so an unclaimed stay shows the claim page in place.
    assert stay.status_code == 200
    assert f"/l/{flat['slug']}/{flat['stay']}/party" in stay.text


def test_an_old_slug_redirects_permanently_to_the_current_one(flat):
    new = guest_slug.rename(flat["id"], "garden-loft")
    assert new == "garden-loft-" + guest_slug.code_of(flat["slug"])
    client = TestClient(app)
    for suffix in ("", "/privacy", f"/{flat['stay']}", f"/{flat['stay']}/new"):
        response = client.get(f"/l/{flat['slug']}{suffix}?lang=cs&x=1", follow_redirects=False)
        assert response.status_code == 301, suffix
        assert response.headers["location"] == f"/l/{new}{suffix}?lang=cs&x=1"
        assert response.headers["cache-control"] == "no-store"
    assert client.get(f"/l/{new}?lang=en", follow_redirects=False).status_code == 200


def test_renaming_back_reuses_the_earlier_slug(flat):
    guest_slug.rename(flat["id"], "garden-loft")
    back = guest_slug.rename(flat["id"], guest_slug.readable_of(flat["slug"]))
    assert back == flat["slug"]
    assert TestClient(app).get(f"/l/{flat['slug']}", follow_redirects=False).status_code == 200


def test_matching_is_case_insensitive_and_lands_on_lower_case(flat):
    response = TestClient(app).get(f"/l/{flat['slug'].upper()}?lang=en", follow_redirects=False)
    assert response.status_code == 301
    assert response.headers["location"] == f"/l/{flat['slug']}?lang=en"


def test_a_wrong_code_is_not_found(flat):
    readable = guest_slug.readable_of(flat["slug"])
    code = guest_slug.code_of(flat["slug"])
    wrong = "".join("z" if ch != "z" else "y" for ch in code)
    client = TestClient(app)
    for key in (f"{readable}-{wrong}", f"other-name-{code}", readable, f"{readable}-{code}x"):
        assert client.get(f"/l/{key}", follow_redirects=False).status_code == 404, key
        assert client.get(f"/l/{key}/privacy", follow_redirects=False).status_code == 404, key


def test_an_archived_property_is_not_found_by_slug_either(flat):
    db.update("apartment", flat["id"], {"archived_at": db.utcnow()})
    assert TestClient(app).get(f"/l/{flat['slug']}", follow_redirects=False).status_code == 404


def test_a_post_on_an_old_slug_is_served_not_redirected(flat, pin_required):
    guest_slug.rename(flat["id"], "garden-loft")
    response = TestClient(app).post(
        f"/l/{flat['slug']}/pin",
        data={"pin": PIN, "return_to": f"/l/{flat['slug']}"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/l/garden-loft-")


# --- PIN continuity and lockout -----------------------------------------

def _enter_pin(client: TestClient, key: str, pin: str = PIN):
    return client.post(
        f"/l/{key}/pin",
        data={"pin": pin, "return_to": f"/l/{key}"},
        follow_redirects=False,
    )


def test_a_pin_entered_on_the_token_link_opens_the_slug_link(flat, pin_required):
    client = TestClient(app)
    assert "pin" in client.get(f"/l/{flat['slug']}?lang=en").text.lower()
    assert _enter_pin(client, TOKEN).status_code == 303
    page = client.get(f"/l/{flat['slug']}?lang=en", follow_redirects=False)
    assert page.status_code == 200
    assert f'action="/l/{flat["slug"]}/pin' not in page.text
    assert f"/l/{flat['slug']}/{flat['stay']}" in page.text


def test_a_pin_entered_on_the_slug_link_opens_the_token_link(flat, pin_required):
    client = TestClient(app)
    assert _enter_pin(client, flat["slug"]).status_code == 303
    page = client.get(f"/l/{TOKEN}?lang=en", follow_redirects=False)
    assert page.status_code == 200
    assert f'action="/l/{TOKEN}/pin' not in page.text


def test_the_pin_cookie_carries_the_token_not_the_slug(flat, pin_required):
    client = TestClient(app)
    response = _enter_pin(client, flat["slug"])
    raw = response.cookies.get(auth.PIN_COOKIE) or client.cookies.get(auth.PIN_COOKIE)
    payload = auth._pin_serializer().loads(raw)
    assert payload["token"] == TOKEN
    assert payload["pin"] == auth.pin_fingerprint(TOKEN, PIN)


def test_wrong_pins_count_against_one_budget_on_both_links(flat, pin_required):
    client = TestClient(app)
    assert _enter_pin(client, TOKEN, "000000").status_code == 200
    assert _enter_pin(client, flat["slug"], "000000").status_code == 200
    assert _enter_pin(client, flat["slug"].upper(), "000000").status_code == 200
    lock_key = f"{TOKEN}:{auth.pin_fingerprint(TOKEN, PIN)}"
    assert rate_limit.pin_failure_count(f"testclient:{TOKEN}") == 3
    assert rate_limit._count("pin_fail_token", lock_key, rate_limit._PIN_TOKEN_LOCK_SECONDS) == 3
    # Nothing was counted under the slug, so switching links resets nothing.
    assert rate_limit.pin_failure_count(f"testclient:{flat['slug']}") == 0


def test_a_link_locked_on_the_token_is_locked_on_the_slug(flat, pin_required):
    lock_key = f"{TOKEN}:{auth.pin_fingerprint(TOKEN, PIN)}"
    for _ in range(rate_limit._PIN_TOKEN_MAX_FAILURES):
        rate_limit.record_pin_failure(f"198.51.100.7:{TOKEN}", lock_key)
    response = _enter_pin(TestClient(app), flat["slug"])
    assert response.status_code == 200
    assert auth.PIN_COOKIE not in response.cookies


# --- host side -------------------------------------------------------------

def test_the_guest_links_page_and_stay_page_copy_the_slug(flat):
    client = _host_client()
    links = client.get("/guest-links?lang=en").text
    assert f"/l/{flat['slug']}" in links
    assert f"/l/{TOKEN}" not in links
    detail = client.get(f"/reservations/{flat['stay']}?lang=en").text
    assert f"/l/{flat['slug']}/{flat['stay']}" in detail
    listing = client.get("/reservations?range=all&lang=en").text
    assert f"/l/{flat['slug']}/{flat['stay']}" in listing


def test_the_host_renames_the_readable_part_and_keeps_the_code(flat):
    client = _host_client()
    form = client.get(f"/apartments/{flat['id']}?lang=en").text
    assert 'name="guest_link_name"' in form
    assert 'value="vinohrady-studio-zizkov"' in form
    response = client.post(
        f"/apartments/{flat['id']}",
        data={"internal_name": "Vinohrady Studio – Žižkov", "guest_link_name": "Zahradní Loft"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    current = guest_slug.current(flat["id"])
    assert current == "zahradni-loft-" + guest_slug.code_of(flat["slug"])
    assert guest_slug.lookup(flat["slug"])["is_current"] == 0


def test_the_host_cannot_pick_a_reserved_or_empty_name(flat):
    client = _host_client()
    for value, key in (("Claim", "flash.error.link_name_reserved"), ("★★", "flash.error.link_name_empty")):
        response = client.post(
            f"/apartments/{flat['id']}",
            data={"internal_name": "Vinohrady Studio – Žižkov", "guest_link_name": value},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "err=" in response.headers["location"]
        assert guest_slug.current(flat["id"]) == flat["slug"]


def test_a_new_link_retires_every_slug(flat):
    guest_slug.rename(flat["id"], "garden-loft")
    old_current = guest_slug.current(flat["id"])
    client = _host_client()
    response = client.post(f"/apartments/{flat['id']}/regenerate-link", follow_redirects=False)
    assert response.status_code == 303
    fresh = guest_slug.current(flat["id"])
    assert fresh.startswith("garden-loft-") and fresh != old_current
    guest = TestClient(app)
    for gone in (flat["slug"], old_current, TOKEN):
        assert guest.get(f"/l/{gone}", follow_redirects=False).status_code == 404, gone
    assert guest.get(f"/l/{fresh}", follow_redirects=False).status_code == 200
