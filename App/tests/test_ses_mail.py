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
    assert call["Source"] == "UbyHost <noreply@ubyhost.com>"
    assert call["Destination"]["ToAddresses"] == ["guest@example.com"]
    assert call["Destination"]["CcAddresses"] == ["host@claim.test"]
    assert call["ReplyToAddresses"] == ["host@claim.test"]
    assert call["Message"]["Subject"]["Data"].startswith("Continue")
    assert "#c=secret" in call["Message"]["Body"]["Text"]["Data"]


def test_the_from_line_carries_a_display_name(monkeypatch):
    """A bare address in From is a bulk-mail tell; the name must be there."""
    fake = _FakeSesClient()
    monkeypatch.setattr(mail.config, "MAIL_BACKEND", "ses")
    monkeypatch.setattr(mail.config, "MAIL_FROM", "noreply@ubyhost.com")
    monkeypatch.setattr(mail, "_ses_client", lambda: fake)

    mail._send_ses(_queue_row(payload={"text": "hello"}))
    assert fake.calls[0]["Source"] == "UbyHost <noreply@ubyhost.com>"


def test_an_operator_supplied_from_name_is_left_alone(monkeypatch):
    fake = _FakeSesClient()
    monkeypatch.setattr(mail.config, "MAIL_BACKEND", "ses")
    monkeypatch.setattr(mail.config, "MAIL_FROM", "Ubytovani Novy <mail@example.test>")
    monkeypatch.setattr(mail, "_ses_client", lambda: fake)

    mail._send_ses(_queue_row(payload={"text": "hello"}))
    assert fake.calls[0]["Source"] == "Ubytovani Novy <mail@example.test>"


def test_display_from_is_a_no_op_for_an_unusable_value():
    assert mail.display_from("") == ""
    assert mail.display_from("not-an-address") == "not-an-address"


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


def test_two_concurrent_drains_deliver_each_row_once(monkeypatch):
    """AR-25: a row is claimed as ``sending`` before the provider is called.

    The console sender re-enters ``drain`` on its first call, standing in for a
    second worker that read the same ``queued`` rows at the same moment. The
    compare-and-set claim must keep each row from going out twice.
    """
    db.init_db()
    db.execute("DELETE FROM email_outbox")
    monkeypatch.setattr(mail.config, "MAIL_BACKEND", "console")

    now = db.utcnow()
    ids = [
        db.insert(
            "email_outbox",
            {
                "idempotency_key": f"drain-claim:{next(_KEY_SEQ)}",
                "kind": "claim",
                "to_email": "guest@example.com",
                "subject": "subject",
                "payload": json.dumps({"text": "body"}),
                "state": mail.QUEUED,
                "attempts": 0,
                "next_attempt_at": now,
                "created_at": now,
                "updated_at": now,
            },
        )
        for _ in range(4)
    ]

    delivered = []
    reentered = {"done": False}

    def sender(row):
        delivered.append(row["id"])
        if not reentered["done"]:
            reentered["done"] = True
            mail.drain(limit=4)
        return f"console-{row['id']}"

    monkeypatch.setattr(mail, "_send_console", sender)

    mail.drain(limit=4)

    assert len(delivered) == len(set(delivered)) == len(ids)
    states = {
        row["id"]: row["state"]
        for row in db.query("SELECT id, state FROM email_outbox")
    }
    assert set(states.values()) == {mail.SENT}
