"""A filing UbyPort did not take also reaches the host by e-mail.

The in-app alert only helps someone who is looking at the app, and the whole
point of the automatic send is that nobody is. These tests cover the message
that closes that gap: that it goes out on the failures and not on the
successes, that it carries a working link back to the stay, and that its
markup is escaped, light-mode and branded as ``docs/LOGO.md`` requires.
"""
from __future__ import annotations

import base64
import json
import re
from datetime import date, timedelta

import pytest

from app import config, db, host_i18n, mail, mail_notify, reporting
from app.ubyport.client import SubmissionResult, UbyportTransportError

RECIPIENT = "host@mailnotify.test"

# A key the host catalogue is missing renders as its own name, because
# ``host_i18n.lookup`` falls back to the key. Requiring at least two dots keeps
# ordinary prose ("…by e-mail.") out of the match.
RAW_KEY = re.compile(r"\bmail\.[a-z0-9_]+(?:\.[a-z0-9_]+)+")

SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()


@pytest.fixture(autouse=True)
def _no_leftovers():
    """Leave the shared database as it was found.

    Other tests pick "the first apartment in the table", so a stray row here
    surfaces as an unrelated failure somewhere else in the suite.
    """
    _purge()
    yield
    _purge()


def _purge():
    db.init_db()
    for row in db.query(
        "SELECT id FROM apartment WHERE permalink_token LIKE 'mailnotify%'"
    ):
        apartment_id = row["id"]
        db.execute("DELETE FROM alert WHERE apartment_id = ?", (apartment_id,))
        db.execute("DELETE FROM submission WHERE apartment_id = ?", (apartment_id,))
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN"
            " (SELECT id FROM reservation WHERE apartment_id = ?)",
            (apartment_id,),
        )
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment_id,))
        db.execute("DELETE FROM email_outbox WHERE apartment_id = ?", (apartment_id,))
        db.execute("DELETE FROM apartment WHERE id = ?", (apartment_id,))
    db.execute(
        "DELETE FROM email_outbox WHERE idempotency_key LIKE 'submission_problem:%'"
    )
    db.execute("DELETE FROM console_mail_log WHERE to_email = ?", (RECIPIENT,))
    db.execute("DELETE FROM legal_entity WHERE name = 'Mail Notify'")


def _seed(
    token: str = "mailnotify1",
    *,
    contact_email: str | None = RECIPIENT,
    summary: str = "Novák family",
):
    db.init_db()
    now = db.utcnow()
    today = date.today()
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Mail Notify",
            "seat": "Praha",
            "ico": "12345678",
            "contact_email": contact_email,
            "created_at": now,
        },
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Riverside Loft",
            "city_en": "Prague",
            "permalink_token": token,
            "automation_mode": "manual",
            "submit_after_hours": 24,
            "default_purpose": "10",
            "active": 1,
            "created_at": now,
        },
    )
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": f"stay-{token}",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "summary": summary,
            "status": "active",
            "expected_guests_override": 1,
            "created_at": now,
            "updated_at": now,
        },
    )
    guest_id = db.insert(
        "guest",
        {
            "reservation_id": reservation_id,
            "surname": "Smith",
            "first_name": "John",
            "birth_date": "01011990",
            "nationality": "GBR",
            "doc_number": "P1234567",
            "res_street": "Street 1",
            "res_city": "London",
            "res_country": "GBR",
            "purpose": "10",
            "is_lead": 1,
            "entered_by": "host",
            "signature_png": SIGNATURE,
            "signed_at": now,
            "identity_verified_at": now,
            "submit_state": reporting.PENDING,
            "created_at": now,
            "updated_at": now,
        },
    )
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    reservation = db.query_one(
        "SELECT * FROM reservation WHERE id = ?", (reservation_id,)
    )
    return apartment, reservation, guest_id


def _outbox(kind: str = "submission_problem"):
    return db.query(
        "SELECT * FROM email_outbox WHERE kind = ? ORDER BY id", (kind,)
    )


def _payload(row):
    return json.loads(row["payload"])


class _RejectingClient:
    """Answers every record with one UbyPort error code."""

    def __init__(self, code: str = ";112;"):
        self.code = code

    def submit(self, _header, _guests):
        return SubmissionResult(
            endpoint="test",
            request_xml="<request/>",
            response_xml="<response/>",
            record_errors=[self.code],
        )


class _FailingClient:
    def submit(self, _header, _guests):
        raise UbyportTransportError("connection reset by peer")


def _submit(monkeypatch, apartment, *, client, mode="manual"):
    monkeypatch.setattr(reporting, "client_for", lambda *_a, **_k: client)
    monkeypatch.setattr(reporting.validation, "validate_apartment", lambda _a: [])
    pairs = reporting.collect_sendable(apartment["id"], ignore_automation=True)
    return reporting.submit_batch(apartment, pairs, mode=mode), pairs


def test_a_rejected_report_emails_the_host(monkeypatch):
    apartment, _reservation, _guest_id = _seed("mailnotify1")

    result, _pairs = _submit(monkeypatch, apartment, client=_RejectingClient())

    assert result["state"] == "error"
    rows = _outbox()
    assert len(rows) == 1, "a batch the register refused must reach the host by mail"
    row = rows[0]
    assert row["to_email"] == RECIPIENT
    assert row["apartment_id"] == apartment["id"]
    assert "Riverside Loft" in row["subject"]
    payload = _payload(row)
    assert payload["text"].strip()
    assert payload["html"].strip()


def test_a_transport_failure_emails_the_host(monkeypatch):
    apartment, _reservation, _guest_id = _seed("mailnotify2")

    result, _pairs = _submit(monkeypatch, apartment, client=_FailingClient())

    assert result["state"] == "transport_error"
    rows = _outbox()
    assert len(rows) == 1
    payload = _payload(rows[0])
    explanation = "could not deliver the guest report"
    assert explanation in payload["text"]
    assert explanation in payload["html"]
    # The transport reason is its own key. If it is missing from the host
    # catalogue the host reads the key itself under "What UbyPort reported".
    assert "mail.submission_problem.reason_transport" not in payload["text"]
    assert "mail.submission_problem.reason_transport" not in payload["html"]
    assert "The connection to UbyPort failed" in payload["text"]
    assert "The connection to UbyPort failed" in payload["html"]
    for part in ("text", "html"):
        leaked = RAW_KEY.search(payload[part])
        assert leaked is None, f"{part} shows a raw key: {leaked.group(0)}"
    # The raw exception is deliberately not host copy: it belongs in the alert
    # and on the submission, where someone can act on the detail, not in a
    # message the host reads on a phone.
    assert "connection reset by peer" not in payload["html"]
    alert = db.query_one(
        "SELECT * FROM alert WHERE apartment_id = ? AND kind = 'submission_transport'",
        (apartment["id"],),
    )
    assert alert is not None
    assert "connection reset by peer" in alert["detail"]


def test_a_successful_report_sends_no_email(monkeypatch):
    apartment, _reservation, _guest_id = _seed("mailnotify3")

    class Client:
        def submit(self, _header, _guests):
            return SubmissionResult(
                endpoint="test",
                request_xml="<request/>",
                response_xml="<response/>",
                pseudo_stamp="STAMP-1",
                receipt_pdf="UEsDBAoAAAAAAA==",
            )

    result, _pairs = _submit(monkeypatch, apartment, client=Client())

    assert result["state"] == "ok"
    assert _outbox() == [], "a report that was accepted must not alarm the host"


def test_the_email_links_back_to_the_stay_and_the_dorucenka(monkeypatch):
    apartment, reservation, _guest_id = _seed("mailnotify4")

    result, _pairs = _submit(monkeypatch, apartment, client=_RejectingClient())

    payload = _payload(_outbox()[0])
    stay_url = f"{config.PUBLIC_BASE_URL}/reservations/{reservation['id']}"
    receipt_url = f"{config.PUBLIC_BASE_URL}/submissions/{result['submission_id']}"
    for part in ("text", "html"):
        assert stay_url in payload[part], f"{part} must link to the stay"
        assert receipt_url in payload[part], f"{part} must link to the Doručenka"
    assert "Novák family" in payload["html"]


def test_the_email_uses_the_logo_docs_logo_md_names_for_mail():
    """The horizontal JPEG, at the documented width, by absolute URL.

    docs/LOGO.md names ubyhost-logo.jpg for e-mail because its white canvas is
    baked in; the transparent PNGs assume mix-blend-mode and are wrong here.
    Mail clients cannot resolve a relative path, so the URL has to be absolute.
    """
    content = mail_notify.build_submission_problem(
        property_name="Riverside Loft",
        state="error",
        reason="112: critical transmission error",
        transport=False,
        stays=[],
        submission_id=None,
        lang="en",
    )
    html = content["html"]
    assert f'src="{config.PUBLIC_BASE_URL}/static/ubyhost-logo.jpg"' in html
    assert 'width="180"' in html
    assert 'alt="UbyHost"' in html
    assert "ubyhost-logo.png" not in html
    assert "ubyhost-mark.png" not in html
    assert "ubyhost-logo-stacked.png" not in html


def test_the_email_is_light_mode_only():
    content = mail_notify.build_submission_problem(
        property_name="Riverside Loft",
        state="error",
        reason="112",
        transport=False,
        stays=[],
        submission_id=None,
        lang="en",
    )
    html = content["html"]
    assert "prefers-color-scheme" not in html
    assert "color-scheme" not in html
    assert "@media" not in html
    assert "background:#f7f7f5" in html


def test_operator_text_and_police_text_are_escaped_in_the_markup():
    """A property name and a server message are both untrusted markup."""
    content = mail_notify.build_submission_problem(
        property_name='<script>alert(1)</script>',
        state="error",
        reason='<img src=x onerror="alert(2)">',
        transport=False,
        stays=[
            {
                "id": 7,
                "date_from": "2026-09-11",
                "date_to": "2026-09-14",
                "summary": "<b>bold</b>",
                "apartment_id": 1,
                "property_name": "<i>flat</i>",
            }
        ],
        submission_id=3,
        lang="en",
    )
    html = content["html"]
    assert "<script>" not in html
    assert "<img src=x" not in html
    assert "<b>bold</b>" not in html
    assert "<i>flat</i>" not in html
    assert "&lt;script&gt;" in html
    # The link still works, and the text alternative is readable rather than
    # full of entities.
    assert "/reservations/7" in html
    assert "<script>" in content["text"]


def test_the_same_failure_twice_in_a_day_emails_once(monkeypatch):
    apartment, _reservation, _guest_id = _seed("mailnotify6")

    _submit(monkeypatch, apartment, client=_RejectingClient())
    # The guest stays retryable, so the sweep offers the record again.
    _submit(monkeypatch, apartment, client=_RejectingClient())

    assert len(_outbox()) == 1, "a second identical failure must not re-send the e-mail"


def test_no_contact_address_means_no_mail_and_no_failure(monkeypatch):
    apartment, _reservation, _guest_id = _seed(
        "mailnotify7", contact_email=None
    )

    result, _pairs = _submit(monkeypatch, apartment, client=_RejectingClient())

    assert result["state"] == "error"
    assert _outbox() == []
    # The in-app alert is the channel that still works without an address.
    alert = db.query_one(
        "SELECT * FROM alert WHERE apartment_id = ? AND kind = 'submission_rejected'",
        (apartment["id"],),
    )
    assert alert is not None


def test_a_broken_composer_does_not_fail_the_filing(monkeypatch):
    apartment, _reservation, _guest_id = _seed("mailnotify8")

    def _boom(**_kwargs):
        raise RuntimeError("template blew up")

    monkeypatch.setattr(mail_notify, "build_submission_problem", _boom)

    result, _pairs = _submit(monkeypatch, apartment, client=_RejectingClient())

    assert result["state"] == "error", "a notification must never decide the filing"
    assert _outbox() == []


def test_the_console_backend_keeps_the_html_part(monkeypatch):
    """Staging is console-only, so the HTML has to survive the console path."""
    apartment, _reservation, _guest_id = _seed("mailnotify9")
    _submit(monkeypatch, apartment, client=_RejectingClient())

    monkeypatch.setattr(mail, "backend_name", lambda: "console")
    summary = mail.drain(limit=5)

    assert summary["sent"] >= 1
    logged = db.query_one(
        "SELECT * FROM console_mail_log WHERE to_email = ? ORDER BY id DESC", (RECIPIENT,)
    )
    assert logged is not None
    assert logged["body_text"]
    assert logged["body_html"]
    assert f"{config.PUBLIC_BASE_URL}/static/ubyhost-logo.jpg" in logged["body_html"]

    messages = mail.recent_console_messages(apartment["owner_user_id"])
    assert any(item.get("body_html") for item in messages)


def test_the_ses_message_carries_both_a_text_and_an_html_part(monkeypatch):
    class FakeSes:
        def __init__(self):
            self.calls = []

        def send_email(self, **kwargs):
            self.calls.append(kwargs)
            return {"MessageId": "ses-1"}

    fake = FakeSes()
    monkeypatch.setattr(mail.config, "MAIL_BACKEND", "ses")
    monkeypatch.setattr(mail.config, "MAIL_FROM", "noreply@ubyhost.com")
    monkeypatch.setattr(mail, "_ses_client", lambda: fake)

    content = mail_notify.build_submission_problem(
        property_name="Riverside Loft",
        state="error",
        reason="112: critical transmission error",
        transport=False,
        stays=[],
        submission_id=None,
        lang="en",
    )
    outbox_id = mail.enqueue(
        kind="submission_problem",
        idempotency_key="ses-html-test:1",
        to_email=RECIPIENT,
        subject=content["subject"],
        payload={"text": content["text"], "html": content["html"], "lang": "en"},
    )
    assert outbox_id is not None
    row = db.query_one("SELECT * FROM email_outbox WHERE id = ?", (outbox_id,))
    try:
        mail._send_ses(row)
        body = fake.calls[0]["Message"]["Body"]
        assert body["Text"]["Data"].strip(), "the text alternative must always be sent"
        assert body["Html"]["Data"].strip()
        assert "ubyhost-logo.jpg" in body["Html"]["Data"]
        assert body["Html"]["Charset"] == "UTF-8"
    finally:
        db.execute("DELETE FROM email_outbox WHERE id = ?", (outbox_id,))


def test_a_mail_without_html_still_sends_as_plain_text(monkeypatch):
    """The four existing kinds carry no HTML part and must be unaffected."""
    class FakeSes:
        def __init__(self):
            self.calls = []

        def send_email(self, **kwargs):
            self.calls.append(kwargs)
            return {"MessageId": "ses-2"}

    fake = FakeSes()
    monkeypatch.setattr(mail.config, "MAIL_BACKEND", "ses")
    monkeypatch.setattr(mail.config, "MAIL_FROM", "noreply@ubyhost.com")
    monkeypatch.setattr(mail, "_ses_client", lambda: fake)

    outbox_id = mail.enqueue(
        kind="claim",
        idempotency_key="ses-text-only:1",
        to_email=RECIPIENT,
        subject="Plain",
        payload={"text": "Plain body", "lang": "en"},
    )
    row = db.query_one("SELECT * FROM email_outbox WHERE id = ?", (outbox_id,))
    try:
        mail._send_ses(row)
        body = fake.calls[0]["Message"]["Body"]
        assert "Html" not in body
        assert body["Text"]["Data"] == "Plain body"
    finally:
        db.execute("DELETE FROM email_outbox WHERE id = ?", (outbox_id,))


def test_the_new_strings_exist_in_both_languages():
    keys = [key for key in host_i18n.STRINGS["en"] if key.startswith("mail.submission_problem.")]
    assert keys, "the notification strings went missing"
    for key in keys:
        for lang in ("en", "cs"):
            text = host_i18n.translate(lang, key, property="Riverside Loft")
            assert text and text != key, (lang, key)


def test_the_submission_problem_kind_is_registered():
    """enqueue raises on an unknown kind, so the registration is load-bearing."""
    assert "submission_problem" in mail.KINDS
