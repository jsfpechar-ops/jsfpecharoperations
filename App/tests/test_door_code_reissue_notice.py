"""1156, 1157b: the host is told once, without the PIN, after a lost door code is replaced."""
from __future__ import annotations

import json

import pytest

from app import alerts, db, door_codes, host_i18n, mail_notify, ttlock
from tests.test_door_code_ambiguous_delete import _delete_then, _tick, world  # noqa: F401
from tests.test_door_code_lost_pin import _revive, _revive_after_lease, _row

KIND = "door_code_reissued"
REAL_NOTICE = mail_notify.door_code_notice  # the world fixture replaces it with a no-op


def _open_cards(stay):
    return db.query(
        "SELECT * FROM alert WHERE kind LIKE ? AND reservation_id = ? AND resolved_at IS NULL",
        (KIND + "%", stay),
    )


def _guest_email(stay, email="guest@example.test"):
    """The guest has registered with an e-mail address (the re-issued code goes there)."""
    now = db.utcnow()
    db.insert(
        "reservation_claim",
        {"reservation_id": stay, "state": "claimed", "email": email, "token_version": 0,
         "claimed_at": now, "created_at": now, "updated_at": now},
    )


def _owner(row):
    return db.query_one(
        "SELECT a.owner_user_id FROM door_code dc JOIN apartment a ON a.id = dc.apartment_id "
        "WHERE dc.id = ?",
        (row,),
    )["owner_user_id"]


@pytest.fixture
def notices(monkeypatch):
    seen: list = []
    monkeypatch.setattr(
        door_codes.mail_notify, "door_code_notice", lambda row_id, variant: seen.append((row_id, variant))
    )
    return seen


def test_a_lost_race_re_issue_tells_the_host_once(world, monkeypatch, notices):  # noqa: F811
    lock, stay, row, sent = world
    _guest_email(stay)
    monkeypatch.setattr(door_codes, "_lock_code_state", lambda *a, **k: door_codes.PIN_PRESENT)
    _revive_after_lease(monkeypatch, lock, stay, row)
    door_codes._revoke_one(row)
    assert _row(row)["state"] == door_codes.ISSUED
    cards = _open_cards(stay)
    assert len(cards) == 1 and cards[0]["level"] == "info" and cards[0]["kind"] == KIND
    assert cards[0]["dedupe_key"] == f"{KIND}:{stay}"
    assert notices == [(row, "reissued")]
    assert sent == [row]


def test_an_ambiguous_delete_re_issue_tells_the_host_once(world, monkeypatch, notices):  # noqa: F811
    lock, stay, row, sent = world
    _guest_email(stay)
    _delete_then(monkeypatch, lock, ttlock.TTLockError("timeout", kind="network"))
    door_codes._revoke_one(row)
    _revive(stay)
    _tick()
    assert _row(row)["state"] == door_codes.ISSUED
    assert len(_open_cards(stay)) == 1
    assert notices == [(row, "reissued")]


def test_no_re_issue_means_no_notice(world, notices):  # noqa: F811
    lock, stay, row, sent = world
    db.execute("UPDATE door_code SET state = ? WHERE id = ?", (door_codes.ISSUED, row))
    door_codes._reissue_lost_pin(row, "pid-1", _owner(row))  # the stay is still cancelled
    assert _row(row)["state"] == door_codes.ISSUED
    assert _open_cards(stay) == [] and notices == []


def test_a_second_re_issue_keeps_one_open_card(world, notices):  # noqa: F811
    lock, stay, row, sent = world
    _revive(stay)
    db.execute("UPDATE door_code SET state = ? WHERE id = ?", (door_codes.ISSUED, row))
    owner = _owner(row)
    door_codes._reissue_lost_pin(row, "pid-1", owner)
    new_id = _row(row)["provider_code_id"]
    door_codes._reissue_lost_pin(row, new_id, owner)
    assert len(_open_cards(stay)) == 1
    assert _row(row)["state"] == door_codes.ISSUED


def test_a_failing_notice_does_not_stop_the_re_issue(world, monkeypatch, notices):  # noqa: F811
    lock, stay, row, sent = world

    def boom(*a, **k):
        raise RuntimeError("alert table locked")

    monkeypatch.setattr(alerts, "raise_alert", boom)
    _revive(stay)
    db.execute("UPDATE door_code SET state = ? WHERE id = ?", (door_codes.ISSUED, row))
    door_codes._reissue_lost_pin(row, "pid-1", _owner(row))
    assert _row(row)["state"] == door_codes.ISSUED and lock.made == 1


def test_the_card_and_the_mail_never_hold_the_pin(world, monkeypatch):  # noqa: F811
    lock, stay, row, sent = world
    _guest_email(stay)
    monkeypatch.setattr(door_codes.mail_notify, "door_code_notice", REAL_NOTICE)
    db.execute("DELETE FROM email_outbox WHERE reservation_id = ?", (stay,))
    _revive(stay)
    db.execute("UPDATE door_code SET state = ? WHERE id = ?", (door_codes.ISSUED, row))
    door_codes._reissue_lost_pin(row, "pid-1", _owner(row))
    card = json.dumps(dict(_open_cards(stay)[0]), default=str)
    mails = db.query(
        "SELECT * FROM email_outbox WHERE reservation_id = ? AND idempotency_key LIKE ?",
        (stay, "%:reissued"),
    )
    assert len(mails) == 1
    everything = card + json.dumps(dict(mails[0]), default=str)
    assert "4821937" not in everything and "5550000" not in everything
    db.execute("DELETE FROM email_outbox WHERE reservation_id = ?", (stay,))


def test_a_failed_new_code_sends_no_notice(world, notices):  # noqa: F811
    lock, stay, row, sent = world
    _guest_email(stay)
    _revive(stay)
    db.execute("UPDATE door_code SET state = ? WHERE id = ?", (door_codes.ISSUED, row))
    lock.fail_create = ttlock.TTLockError("cloud down", kind="transient")
    door_codes._reissue_lost_pin(row, "pid-1", _owner(row))
    assert _row(row)["state"] != door_codes.ISSUED and lock.made == 0
    assert _open_cards(stay) == [] and notices == []


def test_a_stay_without_a_guest_email_says_the_guest_sees_the_code_on_the_stay_page(world, notices):  # noqa: F811
    lock, stay, row, sent = world
    _revive(stay)
    db.execute("UPDATE door_code SET state = ? WHERE id = ?", (door_codes.ISSUED, row))
    door_codes._reissue_lost_pin(row, "pid-1", _owner(row))
    cards = _open_cards(stay)
    assert len(cards) == 1 and cards[0]["kind"] == KIND + "_no_email"
    assert notices == [(row, "reissued_no_email")]


@pytest.mark.parametrize("lang,mailed", [("en", "e-mail"), ("cs", "e-mailem"), ("vi", "e-mail")])
def test_the_copy_exists_in_every_host_language(lang, mailed):
    for suffix in ("", "_no_email"):
        for key in (
            f"notification.door_code_reissued{suffix}.title",
            f"notification.door_code_reissued{suffix}.detail",
            f"mail.door_code_notice.reissued{suffix}.subject",
            f"mail.door_code_notice.reissued{suffix}.body",
        ):
            text = host_i18n.translate(lang, key, property="Loft", date="11.09.2026")
            assert text != key and "%(" not in text and "—" not in text
            if key.endswith((".detail", ".body")):
                assert (mailed in text) == (suffix == ""), key
    title = host_i18n.translate(lang, "notification.door_code_reissued.title", property="Loft", date="d")
    assert "Loft" in title
