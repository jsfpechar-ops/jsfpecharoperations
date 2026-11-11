"""1120: the guest-details mail switch and the DPA version gate behind full_details."""
from __future__ import annotations

import pytest

from app import auth, db, guest_mail_pref

USERNAME = "guest-mail-pref-owner"


def _cleanup():
    for user in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        db.execute("DELETE FROM legal_acceptance WHERE user_account_id = ?", (user["id"],))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user["id"],))
        db.execute("DELETE FROM user_account WHERE id = ?", (user["id"],))


@pytest.fixture
def owner():
    db.init_db()
    _cleanup()
    owner_id = auth.create_account(
        "guest-mail-pref-owner@example.test", "Pref Demo", role="host", username=USERNAME
    )
    try:
        yield owner_id
    finally:
        _cleanup()


def _accept_dpa(owner_id, version):
    db.execute(
        "INSERT INTO legal_acceptance "
        "(user_account_id, document, version, accepted_at, method, ip, user_agent) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (owner_id, "dpa", version, db.utcnow(), "clickwrap", "", ""),
    )


def test_the_switch_is_on_by_default(owner):
    assert guest_mail_pref.switch_on(owner) is True


def test_on_with_dpa_1_7_accepted_gives_false(owner):
    _accept_dpa(owner, "1.7")
    assert guest_mail_pref.full_details(owner) is False


def test_on_with_dpa_1_8_accepted_gives_true(owner):
    _accept_dpa(owner, "1.8")
    assert guest_mail_pref.full_details(owner) is True


def test_on_with_dpa_2_0_accepted_gives_true(owner):
    _accept_dpa(owner, "2.0")
    assert guest_mail_pref.full_details(owner) is True


def test_off_with_dpa_1_8_accepted_gives_false(owner):
    _accept_dpa(owner, "1.8")
    guest_mail_pref.set_full_details(owner, False, actor=USERNAME)
    assert guest_mail_pref.switch_on(owner) is False
    assert guest_mail_pref.full_details(owner) is False
    guest_mail_pref.set_full_details(owner, True, actor=USERNAME)
    assert guest_mail_pref.full_details(owner) is True


def test_no_acceptance_row_gives_false(owner):
    assert guest_mail_pref.full_details(owner) is False


def test_a_malformed_version_counts_as_not_accepted(owner):
    _accept_dpa(owner, "one.eight")
    assert guest_mail_pref.full_details(owner) is False


def test_an_unknown_account_gives_false():
    db.init_db()
    assert guest_mail_pref.full_details(999999999) is False
