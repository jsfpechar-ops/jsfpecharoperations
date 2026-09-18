"""Amazon SES sender unit tests (mocked boto3)."""
from __future__ import annotations

import itertools
import json

import pytest

from app import db, mail

_KEY_SEQ = itertools.count(1)


class _FakeSesClient:
    def __init__(self):
        self.calls = []

    def send_email(self, **kwargs):
        self.calls.append(kwargs)
        return {"MessageId": "ses-message-123"}


def _queue_row(*, payload: dict, cc_email: str | None = None) -> dict:
    db.init_db()
    now = db.utcnow()
    outbox_id = db.insert(
        "email_outbox",
        {
            "idempotency_key": f"ses-test:{next(_KEY_SEQ)}",
            "kind": "claim",
            "to_email": "guest@example.com",
            "cc_email": cc_email,
            "subject": "Continue your Prague guest registration",
            "payload": json.dumps(payload),
            "state": mail.QUEUED,
            "attempts": 0,
            "next_attempt_at": now,
            "created_at": now,
            "updated_at": now,
        },
    )
    return db.query_one("SELECT * FROM email_outbox WHERE id = ?", (outbox_id,))


def test_send_ses_builds_expected_request(monkeypatch):
    fake = _FakeSesClient()
    monkeypatch.setattr(mail.config, "MAIL_BACKEND", "ses")
    monkeypatch.setattr(mail.config, "MAIL_FROM", "noreply@ubyhost.com")
    monkeypatch.setattr(mail.config, "SES_REGION", "eu-central-1")
    monkeypatch.setattr(mail.config, "AWS_ACCESS_KEY_ID", "AKIATEST")
    monkeypatch.setattr(mail.config, "AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setattr(mail, "_ses_client", lambda: fake)

    row = _queue_row(
        payload={
            "text": "Open https://ubyhost.com/l/x/1/claim#c=secret",
            "lang": "en",
            "reply_to": "Host Contact <host@claim.test>",
        },
        cc_email="host@claim.test",
    )
    provider_id = mail._send_ses(row)

    assert provider_id == "ses-message-123"
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["Source"] == "noreply@ubyhost.com"
    assert call["Destination"]["ToAddresses"] == ["guest@example.com"]
    assert call["Destination"]["CcAddresses"] == ["host@claim.test"]
    assert call["ReplyToAddresses"] == ["host@claim.test"]
    assert call["Message"]["Subject"]["Data"].startswith("Continue")
    assert "#c=secret" in call["Message"]["Body"]["Text"]["Data"]


def test_send_ses_omits_reply_to_when_absent(monkeypatch):
    fake = _FakeSesClient()
    monkeypatch.setattr(mail.config, "MAIL_BACKEND", "ses")
    monkeypatch.setattr(mail.config, "MAIL_FROM", "noreply@ubyhost.com")
    monkeypatch.setattr(mail, "_ses_client", lambda: fake)

    row = _queue_row(payload={"text": "hello", "lang": "en"})
    mail._send_ses(row)
    assert "ReplyToAddresses" not in fake.calls[0]


def test_drain_ses_marks_sent(monkeypatch):
    fake = _FakeSesClient()
    monkeypatch.setattr(mail.config, "MAIL_BACKEND", "ses")
    monkeypatch.setattr(mail.config, "MAIL_FROM", "noreply@ubyhost.com")
    monkeypatch.setattr(mail, "_ses_client", lambda: fake)

    db.init_db()
    db.execute("DELETE FROM email_outbox")
    row = _queue_row(payload={"text": "body", "reply_to": "host@claim.test"})
    summary = mail.drain(limit=4)
    assert summary["sent"] == 1
    updated = db.query_one("SELECT * FROM email_outbox WHERE id = ?", (row["id"],))
    assert updated["state"] == mail.SENT
    assert updated["provider_id"] == "ses-message-123"


def test_validate_mail_env_requires_ses_credentials(monkeypatch):
    monkeypatch.setattr(mail.config, "MAIL_FROM", "")
    monkeypatch.setattr(mail.config, "AWS_ACCESS_KEY_ID", "")
    monkeypatch.setattr(mail.config, "AWS_SECRET_ACCESS_KEY", "")
    with pytest.raises(mail.MailConfigError, match="incomplete"):
        mail.validate_mail_env(
            backend="ses",
            deployment="production",
        )


def test_validate_mail_env_refuses_ses_outside_production():
    with pytest.raises(mail.MailConfigError, match="only allowed on production"):
        mail.validate_mail_env(backend="ses", deployment="staging")
