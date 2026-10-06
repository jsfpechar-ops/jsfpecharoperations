"""Task 0003: where a login link may appear when no mail is delivered.

Local development shows it on the page. Staging is a public site, so it never
does: the working link goes to the process log, which only the operator reads.
"""
from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, mail
from app.main import app

EMAIL = "env-link@example.test"


@pytest.fixture
def account(monkeypatch):
    db.init_db()
    monkeypatch.setattr(mail, "backend_name", lambda: "console")
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    db.execute("DELETE FROM user_account WHERE email = ?", (EMAIL,))
    user_id = auth.create_account(EMAIL, "Env Host", username="env-link-host")
    yield user_id
    db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM console_mail_log WHERE to_email = ?", (EMAIL,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def _ask(monkeypatch, deployment):
    monkeypatch.setattr(config, "DEPLOYMENT", deployment)
    return TestClient(app).post("/login?lang=en", data={"email": EMAIL})


def test_local_development_shows_the_link_on_the_page(monkeypatch, account):
    page = _ask(monkeypatch, "local")
    assert page.status_code == 200
    assert 'href="/login/link?t=' in page.text


def test_staging_never_shows_the_link_but_logs_it(monkeypatch, account, caplog):
    caplog.set_level(logging.WARNING, logger=mail.log.name)
    page = _ask(monkeypatch, "staging")
    assert page.status_code == 200
    assert "/login/link?t=" not in page.text
    logged = [r.getMessage() for r in caplog.records if "staging login_link link" in r.getMessage()]
    assert len(logged) == 1
    assert "/login/link?t=" in logged[0]
    assert EMAIL not in logged[0]


def test_other_mail_kinds_are_not_logged_on_staging(monkeypatch, caplog):
    monkeypatch.setattr(config, "DEPLOYMENT", "staging")
    caplog.set_level(logging.WARNING, logger=mail.log.name)
    mail._log_staging_link({"kind": "claim_link", "to_email": EMAIL},
                           {"text": "https://x.test/c?t=abc"})
    assert not [r for r in caplog.records if "staging" in r.getMessage()]
