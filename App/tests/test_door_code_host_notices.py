"""1166: three door-code problems that left the host in the dark now tell the host, once, without the PIN.

An unconfirmed revived code (warning card, one mail), a date move that cannot reach the lock
(one mail, the hourly retry goes on) and the config kind (the reason sends the host to support).
"""
from __future__ import annotations

import json

import pytest

from app import alerts, config, db, door_codes, host_i18n, mail_notify, ttlock
from tests.test_door_code_ambiguous_delete import _delete_then, _tick, world  # noqa: F401
from tests.test_door_code_lost_pin import _expire_lease, _revive, _row
from tests.test_door_codes_safeguards import _env  # noqa: F401
from tests.test_ttlock_lock_setup import _code_row, _moved_stay, _refuse

REAL_NOTICE = mail_notify.door_code_notice  # the world fixture replaces it with a no-op
KIND = "door_code_pin_unverified"
PIN = "4821937"


def _cards(stay):
    return db.query(
        "SELECT * FROM alert WHERE kind = ? AND reservation_id = ? AND resolved_at IS NULL", (KIND, stay)
    )


def _mails(stay, variant):
    return db.query(
        "SELECT * FROM email_outbox WHERE reservation_id = ? AND idempotency_key LIKE ?",
        (stay, f"%:{variant}"),
    )


def _unverified(world, monkeypatch):  # noqa: F811
    """A delete timed out, the stay is back and every lookup fails: three ticks give up."""
    lock, stay, row, sent = world
    _delete_then(monkeypatch, lock, ttlock.TTLockError("timeout", kind="network"))
    door_codes._revoke_one(row)
    _revive(stay)
    lock.lookup_error = ttlock.TTLockError("busy", kind="transient")
    _tick()
    _expire_lease(row)
    _tick()
    return lock, stay, row


@pytest.fixture
def notices(monkeypatch):
    seen: list = []
    monkeypatch.setattr(
        door_codes.mail_notify, "door_code_notice", lambda row_id, variant: seen.append((row_id, variant))
    )
    return seen


def test_a_code_that_stays_unconfirmed_raises_one_warning_card_and_one_notice(world, monkeypatch, notices):  # noqa: F811
    lock, stay, row = _unverified(world, monkeypatch)
    assert _cards(stay) == [] and notices == []  # two failed lookups: still held back
    _expire_lease(row)
    _tick()
    assert _row(row)["state"] == door_codes.ISSUED
    cards = _cards(stay)
    assert len(cards) == 1 and cards[0]["level"] == "warning"
    assert cards[0]["dedupe_key"] == f"{KIND}:{stay}"
    assert notices == [(row, "pin_unverified")]


def test_a_lookup_that_works_in_time_tells_the_host_nothing(world, monkeypatch, notices):  # noqa: F811
    lock, stay, row = _unverified(world, monkeypatch)
    lock.lookup_error = None
    lock.pins["pid-1"] = PIN
    _expire_lease(row)
    _tick()
    assert _cards(stay) == [] and notices == []


def test_the_card_and_the_mail_hold_no_pin_and_the_mail_is_idempotent(world, monkeypatch):  # noqa: F811
    lock, stay, row = _unverified(world, monkeypatch)
    monkeypatch.setattr(door_codes.mail_notify, "door_code_notice", REAL_NOTICE)
    db.execute("DELETE FROM email_outbox WHERE reservation_id = ?", (stay,))
    _expire_lease(row)
    _tick()
    mails = _mails(stay, "pin_unverified")
    assert len(mails) == 1 and mails[0]["cc_email"] == config.SUPPORT_EMAIL
    everything = json.dumps(dict(mails[0]), default=str) + json.dumps(dict(_cards(stay)[0]), default=str)
    assert PIN not in everything and "TTLock app" in everything
    mail_notify.door_code_notice(row, "pin_unverified")
    assert len(_mails(stay, "pin_unverified")) == 1
    db.execute("DELETE FROM email_outbox WHERE reservation_id = ?", (stay,))


def test_a_failing_notice_does_not_stop_the_revival(world, monkeypatch):  # noqa: F811
    lock, stay, row = _unverified(world, monkeypatch)

    def boom(*a, **k):
        raise RuntimeError("alert table locked")

    monkeypatch.setattr(alerts, "raise_alert", boom)
    _expire_lease(row)
    _tick()
    assert _row(row)["state"] == door_codes.ISSUED


def test_a_lock_setup_failure_on_a_move_mails_the_host_once_and_keeps_retrying(monkeypatch):
    stay, _ = _moved_stay(monkeypatch)
    db.execute("DELETE FROM email_outbox WHERE reservation_id = ?", (stay,))
    monkeypatch.setattr(ttlock, "create_period_code", _refuse(-3034))
    door_codes.reconcile()
    first = _mails(stay, "moved_failed")
    assert len(first) == 1 and first[0]["cc_email"] == config.SUPPORT_EMAIL
    assert "lock_setup:-3034" in json.dumps(dict(first[0]), default=str)
    assert _code_row(stay)["next_attempt_at"] is not None
    db.execute("UPDATE door_code SET next_attempt_at = NULL WHERE reservation_id = ?", (stay,))
    door_codes.reconcile()  # the hourly retry fails again
    assert len(_mails(stay, "moved_failed")) == 1
    row = _code_row(stay)
    assert row["last_error"] == "lock_setup:-3034" and row["next_attempt_at"] is not None
    db.execute("DELETE FROM email_outbox WHERE reservation_id = ?", (stay,))


def test_a_busy_cloud_on_a_move_sends_no_mail(monkeypatch):
    stay, _ = _moved_stay(monkeypatch)
    db.execute("DELETE FROM email_outbox WHERE reservation_id = ?", (stay,))
    monkeypatch.setattr(
        ttlock, "create_period_code",
        lambda *a, **k: (_ for _ in ()).throw(ttlock.TTLockError("busy", kind="transient")),
    )
    door_codes.reconcile()
    assert _mails(stay, "moved_failed") == [] and _code_row(stay)["next_attempt_at"] is not None


@pytest.mark.parametrize("lang,word", [("en", "UbyHost side"), ("cs", "straně UbyHost"), ("vi", "phía UbyHost")])
def test_the_config_kind_sends_the_host_to_support(lang, word):
    for token in ("config:-4063", "config:30008", "period_taken:config:30008"):
        text = mail_notify._door_code_reason(lang, token)
        assert word in text and config.SUPPORT_EMAIL in text and text.endswith(f"[{token}]")
        assert text != mail_notify._door_code_reason(lang, "reauth")


@pytest.mark.parametrize("lang,gateway", [("en", "gateway"), ("cs", "bráně"), ("vi", "gateway")])
def test_the_lock_setup_reason_is_one_clause_inside_the_reason_template(lang, gateway):
    text = mail_notify._door_code_reason(lang, "lock_setup:-3034").split(" [")[0]
    assert ". " not in text and ":" not in text and text[0].islower()
    assert "TTLock" in text and gateway in text
    body = host_i18n.translate(lang, "mail.door_code_notice.failed.body", date="d", reason=text)
    assert text in body


@pytest.mark.parametrize("lang", ["en", "cs", "vi"])
def test_the_new_copy_exists_in_every_host_language(lang):
    for key in (
        "notification.door_code_pin_unverified.title",
        "notification.door_code_pin_unverified.detail",
        "mail.door_code_notice.pin_unverified.subject",
        "mail.door_code_notice.pin_unverified.body",
        "mail.door_code_notice.moved_failed.subject",
        "mail.door_code_notice.moved_failed.body",
        "mail.door_code_reason.support",
    ):
        text = host_i18n.translate(lang, key, property="Loft", date="11.09.2026", reason="r", support="s@x.test")
        assert text != key and "%(" not in text and "\u2014" not in text, key
        if lang != "en":
            assert text != host_i18n.translate("en", key, property="Loft", date="11.09.2026", reason="r", support="s@x.test")
