"""Writing guest POSTs must be rate limited, and the limits must not vanish.

`/save`, `/party` and `/another` all change stored data and had no limit at all,
while `rate_limit.blocked` returned False for an empty key — a limit that
disappears exactly when the caller cannot be named.
"""
from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import claim, db, i18n, rate_limit
from app.main import app
from app.routes.guest import GUEST_POST_MAX_ATTEMPTS
from tests.conftest import complete_guest_claim

TOKEN = "ratelimit-token"
SCOPES = ("guest_save", "guest_party", "guest_another")
SCRATCH_SCOPE = "w39-unit-test"


def _cleanup():
    db.execute(
        "DELETE FROM rate_limit_event WHERE scope IN (?, ?, ?, ?)",
        (*SCOPES, SCRATCH_SCOPE),
    )
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
    db.execute("DELETE FROM legal_entity WHERE id = ?", (apartment["legal_entity_id"],))


def _stay() -> int:
    db.init_db()
    _cleanup()
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert("legal_entity", {"name": "Rate limit test", "created_at": now})
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Rate limit flat",
            "permalink_token": TOKEN,
            "permalink_pin": "135790",
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
            "uid": "rate-limit-stay",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )


def test_blocked_refuses_an_empty_key_instead_of_vanishing():
    """The old short-circuit made an unnameable caller exempt from the limit."""
    db.init_db()
    assert rate_limit.blocked(SCRATCH_SCOPE, "", 1) is True

    assert rate_limit.blocked(SCRATCH_SCOPE, "203.0.113.1", 1) is False
    rate_limit.record(SCRATCH_SCOPE, "203.0.113.1")
    assert rate_limit.blocked(SCRATCH_SCOPE, "203.0.113.1", 1) is True


def test_a_missing_client_address_still_produces_a_key():
    """`client_key` must never hand `blocked` an empty key.

    Together with the test above this is the whole of the audit's point: the
    fallback has to be a truthy shared bucket, not a falsy string that would
    disable the limit.
    """
    db.init_db()
    assert rate_limit.client_key(SimpleNamespace(client=None)) == rate_limit.UNIDENTIFIED_CLIENT
    assert (
        rate_limit.client_key(SimpleNamespace(client=SimpleNamespace(host="")))
        == rate_limit.UNIDENTIFIED_CLIENT
    )
    key = rate_limit.client_key(SimpleNamespace(client=None), f"guest:{TOKEN}")
    assert key == f"{rate_limit.UNIDENTIFIED_CLIENT}:guest:{TOKEN}"
    assert key
    assert rate_limit.blocked(SCRATCH_SCOPE, key, 1) is False


@pytest.mark.parametrize("path", ["save", "party", "another"])
def test_writing_guest_posts_are_rate_limited(path):
    """Every mutating guest POST gets a budget, and a translated refusal."""
    stay_id = _stay()
    try:
        client = TestClient(app)
        for attempt in range(GUEST_POST_MAX_ATTEMPTS):
            response = client.post(
                f"/l/{TOKEN}/{stay_id}/{path}?lang=en", data={}, follow_redirects=False
            )
            assert response.status_code != 429, (
                f"attempt {attempt + 1} of {GUEST_POST_MAX_ATTEMPTS} was refused early"
            )

        blocked = client.post(
            f"/l/{TOKEN}/{stay_id}/{path}?lang=en", data={}, follow_redirects=False
        )
        assert blocked.status_code == 429
        assert i18n.translator("en")("rate_limited_title") in blocked.text

        czech = client.post(
            f"/l/{TOKEN}/{stay_id}/{path}",
            data={},
            params={"lang": "cs"},
            follow_redirects=False,
        )
        assert czech.status_code == 429
        assert i18n.translator("cs")("rate_limited_title") in czech.text
    finally:
        _cleanup()


def test_the_guest_post_budget_is_per_address_and_per_link():
    """One guest spending their allowance must not lock out the next one."""
    stay_id = _stay()
    try:
        client = TestClient(app)
        for _ in range(GUEST_POST_MAX_ATTEMPTS):
            client.post(f"/l/{TOKEN}/{stay_id}/another", data={}, follow_redirects=False)
        assert (
            client.post(
                f"/l/{TOKEN}/{stay_id}/another", data={}, follow_redirects=False
            ).status_code
            == 429
        )

        # A different source address is a different bucket...
        other = TestClient(app, client=("198.51.100.5", 50000))
        assert (
            other.post(
                f"/l/{TOKEN}/{stay_id}/another", data={}, follow_redirects=False
            ).status_code
            != 429
        )
        assert other.post(
            f"/l/{TOKEN}/{stay_id}/another", data={}, follow_redirects=False
        ).status_code != 429

        # ...and so is a different scope, so a guest fixing their form cannot
        # exhaust the allowance for the headcount buttons.
        assert (
            client.post(
                f"/l/{TOKEN}/{stay_id}/party", data={}, follow_redirects=False
            ).status_code
            != 429
        )
    finally:
        _cleanup()


def test_a_normal_guest_flow_does_not_trip_the_limit():
    """The budget has to be loose enough that a real guest never sees it."""
    stay_id = _stay()
    try:
        client = TestClient(app)
        complete_guest_claim(client, TOKEN, stay_id)
        for _ in range(5):
            response = client.post(
                f"/l/{TOKEN}/{stay_id}/party",
                data={"party_size": "2"},
                follow_redirects=False,
            )
            assert response.status_code == 303, response.text

        used = rate_limit._count("guest_party", f"testclient:guest:{TOKEN}", 15 * 60)
        assert used == 5
        assert used < GUEST_POST_MAX_ATTEMPTS
    finally:
        _cleanup()
