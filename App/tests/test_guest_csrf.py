"""Guest forms need CSRF proof in every deployment, not only in production."""
from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import auth, claim, db, security
from app.main import app
from app.routes import guest as guest_routes

GUEST_SESSION_COOKIES = (
    auth.PIN_COOKIE,
    guest_routes.CLAIM_COOKIE,
    guest_routes.OWNED_COOKIE,
)

TOKEN = "guestcsrf-token"
PIN = "4321"
GUEST_TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates" / "guest"

# Every POST form a guest can reach, with the template that renders it. The
# test below fails if this list and the templates disagree in either direction,
# so a new guest form has to be registered here and carry the token.
GUEST_POST_FORMS = [
    ("assigned.html", "/l/{{ token }}/{{ reservation.id }}/party?lang={{ lang }}"),
    ("claim.html", "/l/{{ token }}/{{ reservation.id }}/party?lang={{ lang }}"),
    ("confirm.html", "/l/{{ token }}/{{ reservation.id }}/claim/confirm?lang={{ lang }}"),
    ("form.html", "/l/{{ token }}/{{ reservation.id }}/save?lang={{ lang }}"),
    ("pin.html", "/l/{{ token }}/pin?lang={{ lang }}"),
    ("stay.html", "/l/{{ token }}/{{ reservation.id }}/party?lang={{ lang }}"),
    ("stay.html", "/l/{{ token }}/{{ reservation.id }}/another?lang={{ lang }}"),
    ("stay.html", "/l/{{ token }}/{{ reservation.id }}/another?lang={{ lang }}"),
]

FORM_OPEN_RE = re.compile(r"<form\b[^>]*>", re.I)
META_TOKEN_RE = re.compile(r'<meta name="csrf-token" content="([^"]+)"')


def _cleanup():
    apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
    if not apartment:
        return
    db.execute(
        "DELETE FROM reservation_claim WHERE reservation_id IN "
        "(SELECT id FROM reservation WHERE apartment_id = ?)",
        (apartment["id"],),
    )
    db.execute(
        "DELETE FROM guest WHERE reservation_id IN "
        "(SELECT id FROM reservation WHERE apartment_id = ?)",
        (apartment["id"],),
    )
    db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))
    db.execute("DELETE FROM legal_entity WHERE id = ?", (apartment["legal_entity_id"],))


def _stay_id() -> int:
    db.init_db()
    _cleanup()
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert("legal_entity", {"name": "CSRF test", "created_at": now})
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "CSRF flat",
            "permalink_token": TOKEN,
            "permalink_pin": PIN,
            "permalink_window_days": 14,
            "default_purpose": "10",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    return db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": "guest-csrf-stay",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )


def _snapshot(stay_id: int):
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (stay_id,))
    guests = db.query("SELECT id FROM guest WHERE reservation_id = ?", (stay_id,))
    return reservation["declared_guests"], len(guests)


def _token_from_page(client: TestClient, url: str) -> str:
    match = META_TOKEN_RE.search(client.get(url).text)
    assert match, f"{url} should render a csrf-token meta tag"
    return match.group(1)


def _form_blocks(text: str):
    """Yield ``(action, body)`` for each POST form in a rendered template."""
    for chunk in text.split("</form>"):
        opening = None
        for match in FORM_OPEN_RE.finditer(chunk):
            opening = match
        if opening is None or 'method="post"' not in opening.group(0).lower():
            continue
        action = re.search(r'action="([^"]*)"', opening.group(0))
        yield (action.group(1) if action else ""), chunk[opening.end():]


def test_every_guest_post_form_carries_the_token():
    """A guest form without the token would 403 the guest who filled it in."""
    found = []
    for path in sorted(GUEST_TEMPLATES.glob("*.html")):
        for action, body in _form_blocks(path.read_text(encoding="utf-8")):
            found.append((path.name, action))
            assert 'name="_csrf"' in body, (
                f"{path.name} posts to {action} without a _csrf input. Add "
                '<input type="hidden" name="_csrf" value="{{ csrf_token }}"> as the '
                "first child of the form, and register the form in GUEST_POST_FORMS."
            )
    assert sorted(found) == sorted(GUEST_POST_FORMS), (
        "The set of guest POST forms changed. Register the new form in "
        "GUEST_POST_FORMS and give it a _csrf input; do not drop the check."
    )


def test_a_token_from_the_rendered_page_is_accepted():
    """The token a guest's own page rendered works, cookie and all."""
    stay_id = _stay_id()
    try:
        client = TestClient(app)
        token = _token_from_page(client, f"/l/{TOKEN}/{stay_id}")
        assert client.cookies.get(security.CSRF_COOKIE)
        accepted = client.post(
            f"/l/{TOKEN}/pin",
            data={"pin": PIN, "return_to": f"/l/{TOKEN}", "_csrf": token},
            follow_redirects=False,
        )
        assert accepted.status_code == 303, accepted.text
        assert auth.PIN_COOKIE in client.cookies
    finally:
        _cleanup()


def test_the_party_the_guest_declared_is_recorded_with_a_valid_token():
    stay_id = _stay_id()
    try:
        client = TestClient(app)
        token = _token_from_page(client, f"/l/{TOKEN}/{stay_id}")
        accepted = client.post(
            f"/l/{TOKEN}/{stay_id}/party",
            data={"party_size": "2", "guest_email": "csrf@example.test", "_csrf": token},
            follow_redirects=False,
        )
        assert accepted.status_code == 303, accepted.text
        assert "claim_sent=1" in accepted.headers["location"]
        assert db.query_one(
            "SELECT reservation_id FROM reservation_claim WHERE reservation_id = ?", (stay_id,)
        )
    finally:
        _cleanup()


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/l/{token}/pin", {"pin": PIN, "return_to": f"/l/{TOKEN}"}),
        ("/l/{token}/{stay}/party", {"party_size": "2", "guest_email": "g@example.test"}),
        ("/l/{token}/{stay}/another", {}),
        ("/l/{token}/{stay}/claim/confirm", {"secret": "whatever"}),
        ("/l/{token}/{stay}/save", {"first_name": "Eve", "last_name": "Test"}),
    ],
)
def test_guest_posts_without_a_token_are_refused_and_change_nothing(path, payload):
    stay_id = _stay_id()
    try:
        before = _snapshot(stay_id)
        client = TestClient(app)
        refused = client.post(
            path.format(token=TOKEN, stay=stay_id) + "?lang=en",
            data={**payload, "_csrf": ""},
            follow_redirects=False,
        )
        assert refused.status_code == 403, refused.text
        # The CSRF page, not the route's own "stay gone"/"not yours" gate: the
        # guard has to run before the handler touches anything.
        assert "This form timed out" in refused.text
        assert _snapshot(stay_id) == before
        assert not [c for c in GUEST_SESSION_COOKIES if c in client.cookies]
    finally:
        _cleanup()


def test_a_token_from_another_browser_is_refused():
    """Copying the token without the matching cookie must not be enough."""
    stay_id = _stay_id()
    try:
        other = TestClient(app)
        stolen = _token_from_page(other, f"/l/{TOKEN}/{stay_id}")
        attacker = TestClient(app)
        attacker.get(f"/l/{TOKEN}/{stay_id}")  # a valid cookie of its own
        refused = attacker.post(
            f"/l/{TOKEN}/{stay_id}/party",
            data={"party_size": "2", "_csrf": stolen},
            follow_redirects=False,
        )
        assert refused.status_code == 403, refused.text
        assert db.query_one(
            "SELECT declared_guests FROM reservation WHERE id = ?", (stay_id,)
        )["declared_guests"] is None
    finally:
        _cleanup()


def test_a_cross_site_post_without_proof_is_refused():
    stay_id = _stay_id()
    try:
        client = TestClient(app)
        client.get(f"/l/{TOKEN}/{stay_id}")
        refused = client.post(
            f"/l/{TOKEN}/{stay_id}/party",
            data={"party_size": "2", "_csrf": ""},
            headers={"Origin": "https://evil.example"},
            follow_redirects=False,
        )
        assert refused.status_code == 403, refused.text
        assert db.query_one(
            "SELECT declared_guests FROM reservation WHERE id = ?", (stay_id,)
        )["declared_guests"] is None
    finally:
        _cleanup()


def test_the_guest_refusal_is_an_actionable_page_not_a_bare_403():
    stay_id = _stay_id()
    try:
        client = TestClient(app)
        client.get(f"/l/{TOKEN}/{stay_id}?lang=en")
        refused = client.post(
            f"/l/{TOKEN}/{stay_id}/party?lang=en",
            data={"party_size": "2", "_csrf": ""},
            follow_redirects=False,
        )
        assert refused.status_code == 403
        assert refused.headers["content-type"].startswith("text/html")
        assert "This form timed out" in refused.text
        assert f'href="/l/{TOKEN}?lang=en"' in refused.text
        # The page itself carries a fresh cookie and token, so reloading works.
        assert client.cookies.get(security.CSRF_COOKIE)
        assert _token_from_page(client, f"/l/{TOKEN}/{stay_id}")
    finally:
        _cleanup()


def test_the_guest_refusal_is_translated():
    stay_id = _stay_id()
    try:
        client = TestClient(app)
        client.get(f"/l/{TOKEN}/{stay_id}?lang=cs")
        refused = client.post(
            f"/l/{TOKEN}/{stay_id}/party?lang=cs",
            data={"party_size": "2", "_csrf": ""},
            follow_redirects=False,
        )
        assert refused.status_code == 403
        assert "Tomuto formuláři vypršela platnost" in refused.text
    finally:
        _cleanup()
