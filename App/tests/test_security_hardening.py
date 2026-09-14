"""Regression tests for TOTP and Turnstile hardening."""
from __future__ import annotations

from types import SimpleNamespace

import pyotp

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
