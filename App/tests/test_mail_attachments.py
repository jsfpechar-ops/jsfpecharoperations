"""0204: stay-fee mail carries the sealed PDF and an inline QR image (mocked SES)."""
from __future__ import annotations

import email
import email.policy
import json
import itertools

import pytest

from app import db, mail, payments, stay_fee_filing

_KEY_SEQ = itertools.count(1000)
_FILING = {"id": 7, "period_key": "2026-10"}
_SPAYD = "SPD*1.0*ACC:CZ6501000000000000000001*AM:100.00*CC:CZK"


class _FakeSesClient:
    def __init__(self):
        self.calls = []

    def send_email(self, **kwargs):
        self.calls.append(kwargs)
        return {"MessageId": "ses-message-attach"}


def _queue_row(*, payload: dict, kind: str = "claim") -> dict:
    db.init_db()
    now = db.utcnow()
    outbox_id = db.insert(
        "email_outbox",
        {
            "idempotency_key": f"attach-test:{next(_KEY_SEQ)}",
            "kind": kind,
            "to_email": "guest@example.com",
            "cc_email": "host@claim.test",
            "subject": "Stay fee for October",
            "payload": json.dumps(payload),
            "state": mail.QUEUED,
            "attempts": 0,
            "next_attempt_at": now,
            "created_at": now,
            "updated_at": now,
        },
    )
    return db.query_one("SELECT * FROM email_outbox WHERE id = ?", (outbox_id,))


def _ses_setup(monkeypatch, ses_fake: _FakeSesClient, sesv2_fake: _FakeSesClient) -> None:
    monkeypatch.setattr(mail.config, "MAIL_BACKEND", "ses")
    monkeypatch.setattr(mail.config, "MAIL_FROM", "noreply@ubyhost.com")
    monkeypatch.setattr(mail.config, "SES_REGION", "eu-central-1")
    monkeypatch.setattr(mail.config, "AWS_ACCESS_KEY_ID", "AKIATEST")
    monkeypatch.setattr(mail.config, "AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setattr(mail, "_ses_client", lambda: ses_fake)
    monkeypatch.setattr(mail, "_sesv2_client", lambda: sesv2_fake)


def _patch_filing(monkeypatch, row) -> None:
    real_query_one = db.query_one

    def fake_query_one(sql, params=()):
        if "stay_fee_filing" in sql:
            return row
        return real_query_one(sql, params)

    monkeypatch.setattr(mail.db, "query_one", fake_query_one)
    monkeypatch.setattr(stay_fee_filing, "pdf_bytes", lambda r: b"%PDF-1.4 test")
    monkeypatch.setattr(payments, "qr_png_bytes", lambda s: b"\x89PNG\r\n\x1a\nfake")


def test_ses_raw_message_carries_pdf_qr_and_reply_to(monkeypatch):
    ses_fake, sesv2_fake = _FakeSesClient(), _FakeSesClient()
    _ses_setup(monkeypatch, ses_fake, sesv2_fake)
    _patch_filing(monkeypatch, _FILING)
    row = _queue_row(payload={
        "text": "Your stay fee is attached.",
        "html": "<p>Your stay fee is attached.</p><img src=\"cid:stayfeeqr\">",
        "lang": "en",
        "reply_to": "Host Contact <host@claim.test>",
        "stay_fee_filing_id": _FILING["id"],
        "qr_spayd": _SPAYD,
    })

    assert mail._send_ses(row) == "ses-message-attach"
    assert ses_fake.calls == []
    assert len(sesv2_fake.calls) == 1
    call = sesv2_fake.calls[0]
    raw = call["Content"]["Raw"]["Data"]
    assert isinstance(raw, bytes)

    msg = email.message_from_bytes(raw, policy=email.policy.default)
    assert "host@claim.test" in str(msg["Reply-To"])
    parts = list(msg.walk())
    pdfs = [p for p in parts if p.get_content_type() == "application/pdf"]
    assert len(pdfs) == 1
    assert pdfs[0].get_filename() == "poplatek-z-pobytu-2026-10.pdf"
    pngs = [p for p in parts if p.get_content_type() == "image/png"]
    assert len(pngs) == 1
    assert pngs[0]["Content-ID"] == "<stayfeeqr>"
    types = {p.get_content_type() for p in parts}
    assert "text/plain" in types
    assert "text/html" in types


def test_payload_without_attachments_still_uses_v1_send(monkeypatch):
    ses_fake, sesv2_fake = _FakeSesClient(), _FakeSesClient()
    _ses_setup(monkeypatch, ses_fake, sesv2_fake)
    row = _queue_row(payload={"text": "Plain mail.", "lang": "en"})

    assert mail._send_ses(row) == "ses-message-attach"
    assert sesv2_fake.calls == []
    assert len(ses_fake.calls) == 1
    assert "Content" not in ses_fake.calls[0]


def test_missing_filing_raises_config_error(monkeypatch):
    ses_fake, sesv2_fake = _FakeSesClient(), _FakeSesClient()
    _ses_setup(monkeypatch, ses_fake, sesv2_fake)
    _patch_filing(monkeypatch, None)
    row = _queue_row(payload={
        "text": "Your stay fee is attached.",
        "stay_fee_filing_id": 99,
    })

    with pytest.raises(mail.MailConfigError):
        mail._send_ses(row)
    assert ses_fake.calls == []
    assert sesv2_fake.calls == []


def test_console_log_ends_with_attachment_note(monkeypatch):
    monkeypatch.setattr(mail.config, "MAIL_BACKEND", "console")
    _patch_filing(monkeypatch, _FILING)
    row = _queue_row(payload={
        "text": "Your stay fee is attached.",
        "stay_fee_filing_id": _FILING["id"],
        "qr_spayd": _SPAYD,
    })

    assert mail._send_console(row) == f"console:{row['id']}"
    logged = db.query_one(
        "SELECT body_text FROM console_mail_log WHERE outbox_id = ?", (row["id"],)
    )
    assert logged["body_text"].endswith(
        "\n\n[Attachments: poplatek-z-pobytu-2026-10.pdf, qr-platba.png]"
    )
