"""Regression tests for TOTP and Turnstile hardening."""
from __future__ import annotations

from types import SimpleNamespace

import pyotp
import requests

from app import auth, config, db, turnstile


def test_totp_and_recovery_codes_are_single_use():
    db.init_db()
    username = "two-factor-test"
    db.execute("DELETE FROM user_account WHERE username = ?", (username,))
    user_id = auth.create_account(
        username, "Secure-Password-123", "Two Factor", must_change_password=False
    )
    try:
        secret = auth.new_totp_secret()
        recovery = auth.new_recovery_codes()
        auth.enable_totp(user_id, secret, recovery)
        account = db.query_one("SELECT * FROM user_account WHERE id = ?", (user_id,))
        assert auth.verify_second_factor(account, pyotp.TOTP(secret).now())

        account = db.query_one("SELECT * FROM user_account WHERE id = ?", (user_id,))
        assert auth.verify_second_factor(account, recovery[0])
        account = db.query_one("SELECT * FROM user_account WHERE id = ?", (user_id,))
        assert not auth.verify_second_factor(account, recovery[0])
    finally:
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def test_turnstile_requires_success_action_and_hostname(monkeypatch):
    monkeypatch.setattr(config, "DEPLOYMENT", "production")
    monkeypatch.setattr(config, "TURNSTILE_ENABLED", True)
    monkeypatch.setattr(config, "TURNSTILE_SECRET", "secret")
    monkeypatch.setattr(config, "TURNSTILE_HOSTNAMES", {"ubyhost.com"})
    request = SimpleNamespace(client=SimpleNamespace(host="203.0.113.4"))

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"success": True, "action": "host_login", "hostname": "ubyhost.com"}

    monkeypatch.setattr(turnstile.requests, "post", lambda *args, **kwargs: Response())
    assert turnstile.verify(request, "token", "host_login")
    assert not turnstile.verify(request, "token", "guest_pin")


def test_production_hosts_without_totp_are_sent_to_setup(monkeypatch):
    db.init_db()
    username = "two-factor-required"
    db.execute("DELETE FROM user_account WHERE username = ?", (username,))
    user_id = auth.create_account(
        username, "Secure-Password-123", "Required", must_change_password=False
    )
    try:
        account = db.query_one("SELECT * FROM user_account WHERE id = ?", (user_id,))
        request = SimpleNamespace(
            state=SimpleNamespace(user_account=account, session_payload={}),
            url=SimpleNamespace(path="/"),
            cookies={},
        )
        monkeypatch.setattr(config, "DEPLOYMENT", "production")
        response = auth.require_login(request)
        assert response is not None
        assert response.headers["location"] == "/account/2fa/setup"
    finally:
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def _turnstile_down(monkeypatch, host="203.0.113.9"):
    """Put Turnstile in production mode with a verifier that cannot be reached."""
    monkeypatch.setattr(config, "DEPLOYMENT", "production")
    monkeypatch.setattr(config, "TURNSTILE_ENABLED", True)
    monkeypatch.setattr(config, "TURNSTILE_SECRET", "secret")
    monkeypatch.setattr(config, "TURNSTILE_HOSTNAMES", {"ubyhost.com"})

    def explode(*args, **kwargs):
        raise requests.ConnectionError("turnstile is down")

    monkeypatch.setattr(turnstile.requests, "post", explode)
    return SimpleNamespace(client=SimpleNamespace(host=host))


def _forget_turnstile_state():
    db.execute("DELETE FROM rate_limit_event WHERE scope = ?", ("turnstile_unreachable",))
    db.execute("DELETE FROM alert WHERE kind = ?", ("turnstile_unavailable",))


def test_a_turnstile_outage_does_not_block_the_guest(monkeypatch):
    """An unreachable verifier is not evidence that the guest is a bot [F27]."""
    db.init_db()
    _forget_turnstile_state()
    request = _turnstile_down(monkeypatch)
    try:
        assert turnstile.verify(request, "token", "guest_pin") is True

        alert = db.query_one(
            "SELECT * FROM alert WHERE kind = ? AND resolved_at IS NULL",
            ("turnstile_unavailable",),
        )
        assert alert is not None, "the host has to be told the check was skipped"
        assert alert["level"] == "warning"
    finally:
        _forget_turnstile_state()


def test_the_fail_open_is_bounded_per_source_address(monkeypatch):
    """Fail-open has to end, or it is not a fallback but a bypass."""
    db.init_db()
    _forget_turnstile_state()
    request = _turnstile_down(monkeypatch)
    try:
        allowed = [
            turnstile.verify(request, "token", "guest_pin")
            for _ in range(turnstile._UNREACHABLE_MAX_ATTEMPTS)
        ]
        assert allowed == [True] * turnstile._UNREACHABLE_MAX_ATTEMPTS
        assert turnstile.verify(request, "token", "guest_pin") is False

        # A different address gets its own budget: an outage must not shut the
        # whole site out for the guests who happen to arrive after the fifth.
        other = _turnstile_down(monkeypatch, host="198.51.100.7")
        assert turnstile.verify(other, "token", "guest_pin") is True

        # One open alert per action, refreshed rather than duplicated.
        rows = db.query(
            "SELECT id FROM alert WHERE kind = ? AND resolved_at IS NULL",
            ("turnstile_unavailable",),
        )
        assert len(rows) == 1
    finally:
        _forget_turnstile_state()


def test_a_rejected_challenge_is_not_failed_open(monkeypatch):
    """Only an unreachable verifier fails open; a real refusal still refuses."""
    db.init_db()
    _forget_turnstile_state()
    monkeypatch.setattr(config, "DEPLOYMENT", "production")
    monkeypatch.setattr(config, "TURNSTILE_ENABLED", True)
    monkeypatch.setattr(config, "TURNSTILE_SECRET", "secret")
    monkeypatch.setattr(config, "TURNSTILE_HOSTNAMES", {"ubyhost.com"})

    class Rejected:
        def raise_for_status(self):
            return None

        def json(self):
            return {"success": False, "action": "guest_pin", "hostname": "ubyhost.com"}

    monkeypatch.setattr(turnstile.requests, "post", lambda *args, **kwargs: Rejected())
    request = SimpleNamespace(client=SimpleNamespace(host="203.0.113.11"))
    try:
        assert turnstile.verify(request, "token", "guest_pin") is False
        assert not db.query(
            "SELECT id FROM alert WHERE kind = ?", ("turnstile_unavailable",)
        )
    finally:
        _forget_turnstile_state()


def test_an_unparseable_reply_is_treated_as_unreachable(monkeypatch):
    """A proxy error page is not a verdict on the guest either."""
    db.init_db()
    _forget_turnstile_state()
    monkeypatch.setattr(config, "DEPLOYMENT", "production")
    monkeypatch.setattr(config, "TURNSTILE_ENABLED", True)
    monkeypatch.setattr(config, "TURNSTILE_SECRET", "secret")
    monkeypatch.setattr(config, "TURNSTILE_HOSTNAMES", {"ubyhost.com"})

    class NotJson:
        def raise_for_status(self):
            return None

        def json(self):
            raise ValueError("Expecting value: line 1 column 1 (char 0)")

    monkeypatch.setattr(turnstile.requests, "post", lambda *args, **kwargs: NotJson())
    request = SimpleNamespace(client=SimpleNamespace(host="203.0.113.12"))
    try:
        assert turnstile.verify(request, "token", "guest_pin") is True
    finally:
        _forget_turnstile_state()
