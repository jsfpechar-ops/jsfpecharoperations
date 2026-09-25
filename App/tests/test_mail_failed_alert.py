"""A failed send is named in words, not in outbox codes [E-21].

The card used to say "Guest e-mail could not be sent (reminder_host)": the
wrong recipient - most outbox kinds are addressed to the host - and a raw code
the host has no way to read.
"""
from __future__ import annotations

import json

import pytest

from app import alerts, host_i18n, mail


def _card(kind, lang):
    row = {
        "kind": "mail_failed",
        "message": "stored english log copy",
        "detail": "stored english detail",
        "params": json.dumps(
            {"kind": kind, "to": "g@example.test", "error": "boom"}, ensure_ascii=False
        ),
    }
    return alerts.present(row, lang)


def test_the_card_no_longer_calls_every_failed_mail_a_guest_mail():
    en = _card("reminder_host", "en")
    assert en["display_title"] == "E-mail could not be sent (reminder to the host)."
    assert "Guest" not in en["display_title"]


def test_the_card_names_the_mail_in_the_hosts_language():
    cs = _card("reminder_host", "cs")
    assert cs["display_title"] == "E-mail se nepodařilo odeslat (připomínka ubytovateli)."


@pytest.mark.parametrize("kind", mail.KINDS)
def test_no_outbox_code_ever_reaches_the_card(kind):
    for lang in ("en", "cs"):
        shown = _card(kind, lang)
        assert kind not in shown["display_title"], (kind, lang)
        assert "notification." not in shown["display_title"], (kind, lang)


@pytest.mark.parametrize("kind", mail.KINDS)
def test_every_outbox_kind_has_a_name_in_both_languages(kind):
    key = f"notification.mail_kind.{kind}"
    for lang in ("en", "cs"):
        assert key in host_i18n.STRINGS[lang], (kind, lang)


def test_an_unknown_kind_falls_back_to_its_code_not_to_a_missing_key():
    """Invoice kinds will land in this outbox; they must not print a key."""
    en = _card("invoice_request_host", "en")
    assert en["display_title"] == "E-mail could not be sent (invoice_request_host)."
    assert "notification." not in en["display_title"]


def test_a_card_raised_before_this_release_keeps_its_stored_copy():
    row = {
        "kind": "mail_failed",
        "message": "Guest e-mail could not be sent (reminder_host).",
        "detail": "To g@example.test: boom",
    }
    shown = alerts.present(row, "cs")
    assert shown["display_title"] == "Guest e-mail could not be sent (reminder_host)."
    assert "%(" not in shown["display_title"]


def _boom(_row):
    raise RuntimeError("provider refused")


def test_the_send_loop_stores_the_code_and_renders_a_name(monkeypatch):
    """The outbox row keeps the code; only the card the host reads is worded."""
    row = {
        "id": 4711,
        "kind": "reminder_host",
        "to_email": "guest@example.test",
        "attempts": 7,
        "apartment_id": 1,
        "reservation_id": 2,
        "payload_json": "{}",
    }
    raised = {}
    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    monkeypatch.setattr(mail, "backend_name", lambda: "console")
    monkeypatch.setattr(mail, "_send_console", _boom)
    monkeypatch.setattr(mail.db, "query", lambda *a, **k: [row])
    monkeypatch.setattr(mail.db, "update", lambda *a, **k: None)
    monkeypatch.setattr(
        alerts, "raise_alert", lambda *a, **k: raised.update({"args": a, "kwargs": k})
    )

    summary = mail.drain()

    assert summary["failed"] == 1
    assert raised["args"][2] == "E-mail could not be sent (reminder_host)."
    assert raised["kwargs"]["params"]["kind"] == "reminder_host"

    stored = {
        "kind": "mail_failed",
        "message": raised["args"][2],
        "detail": raised["args"][3],
        "params": json.dumps(raised["kwargs"]["params"], ensure_ascii=False),
    }
    assert alerts.present(stored, "cs")["display_title"] == (
        "E-mail se nepodařilo odeslat (připomínka ubytovateli)."
    )
