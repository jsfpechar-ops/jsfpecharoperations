"""BE-1/FE-1: acceptance evidence on every login path, behind a clickwrap screen.

Before this, the only acceptance evidence was free text on the non-2FA login
path, and production (which forces 2FA) recorded none at all. These tests use
the conftest fixture ``real_acceptance_pending`` to switch the gate back on;
for the rest of the suite it is stubbed so fixture hosts keep landing where
their tests expect.
"""
from __future__ import annotations

import re
from pathlib import Path

import pyotp
from fastapi.testclient import TestClient

from app import acceptance, auth, config, db, host_i18n
from app.main import app
from tests.conftest import login_as

PASSWORD = "Secure-Password-123"
HOST_I18N = Path(__file__).resolve().parents[1] / "app" / "host_i18n.py"

CHECKBOX_RE = re.compile(r'<input[^>]*name="accept"[^>]*>')


def _cleanup(*usernames: str) -> None:
    for username in usernames:
        for row in db.query("SELECT id FROM user_account WHERE username = ?", (username,)):
            user_id = row["id"]
            db.execute("DELETE FROM legal_acceptance WHERE user_account_id = ?", (user_id,))
            db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
            db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
            db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
            db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
            db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def _make(username: str, *, two_factor: bool = False, role: str = "host") -> tuple[int, str]:
    db.init_db()
    _cleanup(username)
    user_id = auth.create_account(f"{username}@example.test", "Acceptance", role=role, username=username)
    if not two_factor:
        return user_id, ""
    secret = auth.new_totp_secret()
    auth.enable_totp(user_id, secret, auth.new_recovery_codes())
    return user_id, secret


def _login(client: TestClient, username: str, lang: str = "en"):
    return login_as(client, username, url=f"/login?lang={lang}", follow_redirects=False)


def _checkbox(html: str) -> str:
    match = CHECKBOX_RE.search(html)
    assert match, html
    return match.group(0)


def test_the_clickwrap_text_is_the_approved_wording_in_both_languages():
    assert host_i18n.translate("en", "account.accept.checkbox") == (
        "I have read and agree to the Terms of Service, the Data Processing "
        "Agreement and the Privacy Policy listed above."
    )
    czech = host_i18n.translate("cs", "account.accept.checkbox")
    assert czech and czech != "account.accept.checkbox"
    assert source_marker_present()


def source_marker_present() -> bool:
    """Rule 6: the legal-gated key carries a ``# LEGAL-REVIEW`` marker."""
    source = HOST_I18N.read_text(encoding="utf-8")
    index = source.index('"account.accept.checkbox"')
    return "# LEGAL-REVIEW" in source[max(0, index - 200) : index]


def test_a_fresh_login_is_sent_to_the_screen_and_posting_records_three_rows(
    real_acceptance_pending,
):
    user_id, _ = _make("accept-fresh")
    client = TestClient(app)
    assert _login(client, "accept-fresh").status_code == 303

    page = client.get("/", follow_redirects=False)
    assert page.status_code == 303
    assert page.headers["location"].startswith("/account/accept")

    screen = client.get("/account/accept")
    assert screen.status_code == 200, screen.text
    assert "checked" not in _checkbox(screen.text)
    for document in acceptance.DOCUMENTS:
        assert f'href="/{document}?lang=en"' in screen.text, document

    empty = client.post("/account/accept", data={"next": "/"}, follow_redirects=False)
    assert empty.status_code == 422
    assert acceptance.pending(user_id) == ["terms", "privacy", "dpa"]

    done = client.post(
        "/account/accept", data={"accept": "1", "next": "/housebook"}, follow_redirects=False
    )
    assert done.status_code == 303
    assert done.headers["location"] == "/housebook"

    rows = acceptance.accepted(user_id)
    assert {row["document"] for row in rows} == {"terms", "privacy", "dpa"}
    assert {row["method"] for row in rows} == {"clickwrap"}
    versions = acceptance.current_versions()
    assert {row["version"] for row in rows} == set(versions.values())
    assert acceptance.pending(user_id) == []

    audit = db.query_one(
        "SELECT detail FROM audit WHERE action = 'legal_accepted' AND owner_user_id = ?",
        (user_id,),
    )
    assert audit and "method=clickwrap" in audit["detail"]
    assert PASSWORD not in audit["detail"]


def test_the_two_factor_login_path_records_acceptance(real_acceptance_pending):
    user_id, secret = _make("accept-2fa", two_factor=True)
    client = TestClient(app)

    challenge = _login(client, "accept-2fa")
    assert challenge.status_code == 200
    pending = re.search(r'name="pending" value="([^"]+)"', challenge.text)
    assert pending, challenge.text

    done = client.post(
        "/login/2fa",
        data={"pending": pending.group(1), "code": pyotp.TOTP(secret).now()},
        follow_redirects=False,
    )
    assert done.status_code == 303

    gate = client.get("/", follow_redirects=False)
    assert gate.status_code == 303
    assert gate.headers["location"].startswith("/account/accept")

    client.post("/account/accept", data={"accept": "1", "next": "/"}, follow_redirects=False)
    assert acceptance.pending(user_id) == []


def test_a_version_bump_makes_only_that_document_pending(monkeypatch, real_acceptance_pending):
    user_id, _ = _make("accept-bump")
    client = TestClient(app)
    _login(client, "accept-bump")
    client.post("/account/accept", data={"accept": "1", "next": "/"}, follow_redirects=False)
    assert acceptance.pending(user_id) == []

    monkeypatch.setattr(config, "TERMS_VERSION", "9.9")
    assert acceptance.pending(user_id) == ["terms"]
    gate = client.get("/", follow_redirects=False)
    assert gate.status_code == 303
    assert gate.headers["location"].startswith("/account/accept")


def test_the_screen_is_translated_and_unchecked_in_czech(real_acceptance_pending):
    _make("accept-cs")
    client = TestClient(app)
    _login(client, "accept-cs", lang="cs")
    screen = client.get("/account/accept?lang=cs")
    assert screen.status_code == 200, screen.text
    assert "checked" not in _checkbox(screen.text)
    for document in acceptance.DOCUMENTS:
        assert f'href="/{document}?lang=cs"' in screen.text, document
    assert host_i18n.translate("cs", "account.accept.checkbox") in screen.text
    assert 'name="_csrf"' in screen.text


def test_an_impersonating_admin_is_not_sent_to_the_screen(real_acceptance_pending):
    admin_id, _ = _make("accept-admin", role="admin")
    target_id, _ = _make("accept-target")
    client = TestClient(app)

    assert _login(client, "accept-admin").status_code == 303
    # The admin accepts; the target never does.
    client.post("/account/accept", data={"accept": "1", "next": "/"}, follow_redirects=False)
    assert acceptance.pending(admin_id) == []
    assert acceptance.pending(target_id) == ["terms", "privacy", "dpa"]

    started = client.post(
        f"/admin/users/{target_id}/impersonate",
            data={"reason": "Support ticket 123"},
            follow_redirects=False
    )
    assert started.status_code == 303
    page = client.get("/", follow_redirects=False)
    assert page.status_code == 200, page.text
    assert "Previewing workspace" in page.text

    _cleanup("accept-admin", "accept-target")


def test_backfill_turns_legacy_login_rows_into_acceptance(real_acceptance_pending):
    user_id, _ = _make("accept-backfill")
    db.execute(
        "INSERT INTO audit (at, actor, action, detail, owner_user_id) VALUES (?, ?, ?, ?, ?)",
        (
            "2026-01-02T03:04:05+00:00",
            "accept-backfill",
            "login",
            "terms_v1.0 privacy_v1.1 dpa_v1.2 accepted",
            user_id,
        ),
    )

    assert acceptance.backfill_from_audit() >= 3
    rows = db.query(
        "SELECT document, version, method FROM legal_acceptance WHERE user_account_id = ?",
        (user_id,),
    )
    assert {(r["document"], r["version"], r["method"]) for r in rows} == {
        ("terms", "1.0", "backfill"),
        ("privacy", "1.1", "backfill"),
        ("dpa", "1.2", "backfill"),
    }
    assert acceptance.backfill_from_audit() == 0
