"""A resent link for a finished stay does not promise a form [E-25].

"Send me the link again" is offered on the assigned-stay screen even when every
form is already in. The mail still said "You will enter the details of every
guest of this stay and then sign", so the guest opened a link expecting work
that was already done.
"""
from __future__ import annotations

import json

import pytest

from app import claim, db, i18n, mail_notify, reporting
from tests.test_claim_mail import TOKEN, _cleanup, _seed

LANGS = ("en", "cs")
DONE = {
    lang: i18n.STRINGS[lang]["mail_claim_next_done"] for lang in LANGS
}
PROMISE = {
    lang: i18n.STRINGS[lang]["mail_claim_next_body"] for lang in LANGS
}


def _content(lang, *, stay_complete):
    return mail_notify.build_claim_link(
        lang=lang,
        property_name="Claim Facility",
        dates="1 Jan 2026 \u2013 4 Jan 2026",
        link="https://example.test/l/tok/1/claim#c=secret",
        resend=True,
        stay_complete=stay_complete,
    )


@pytest.mark.parametrize("lang", LANGS)
def test_a_finished_stay_is_not_told_to_fill_anything_in(lang):
    content = _content(lang, stay_complete=True)
    assert DONE[lang] in content["text"]
    assert DONE[lang] in content["html"]
    assert PROMISE[lang] not in content["text"]
    assert PROMISE[lang] not in content["html"]


@pytest.mark.parametrize("lang", LANGS)
def test_an_unfinished_stay_still_gets_the_ordinary_next_steps(lang):
    content = _content(lang, stay_complete=False)
    assert PROMISE[lang] in content["text"]
    assert DONE[lang] not in content["text"]


def test_the_heading_and_the_expiry_do_not_change_with_completeness():
    before = _content("en", stay_complete=False)
    after = _content("en", stay_complete=True)
    assert before["subject"] == after["subject"]
    assert i18n.STRINGS["en"]["mail_claim_resend_heading"] in after["html"]
    assert i18n.STRINGS["en"]["mail_claim_expiry_resend"] in after["html"]


def test_the_done_copy_exists_in_both_languages():
    for lang in LANGS:
        assert DONE[lang]
        assert "mail_claim_next_done" in i18n.STRINGS[lang]


@pytest.mark.parametrize(
    "progress,expected",
    [
        ({"expected": 2, "filled": 2, "incomplete": []}, True),
        ({"expected": 2, "filled": 1, "incomplete": []}, False),
        ({"expected": None, "filled": 1, "incomplete": []}, False),
        ({"expected": 2, "filled": 2, "incomplete": [{"id": 9}]}, False),
    ],
)
def test_completeness_reads_the_same_progress_the_dashboard_shows(
    monkeypatch, progress, expected
):
    monkeypatch.setattr(reporting, "reservation_progress", lambda _r: progress)
    assert claim._stay_forms_complete({"id": 1}) is expected


def test_a_progress_failure_falls_back_to_the_ordinary_copy(monkeypatch):
    """The link matters more than the wording: never lose the mail over this."""

    def _boom(_r):
        raise RuntimeError("no such column")

    monkeypatch.setattr(reporting, "reservation_progress", _boom)
    assert claim._stay_forms_complete({"id": 1}) is False


def _outbox_payload():
    row = db.query_one("SELECT * FROM email_outbox ORDER BY id DESC")
    assert row
    return json.loads(row["payload"])


def _resend(reservation, apartment, *, email, party_size, lang):
    """Resend past the production guards: a test wants the mail, not the wait."""
    claim.ensure_row(int(reservation["id"]))
    db.execute("DELETE FROM rate_limit_event")
    db.execute(
        "UPDATE reservation_claim SET updated_at = ? WHERE reservation_id = ?",
        ("2000-01-01T00:00:00+00:00", reservation["id"]),
    )
    return claim.start_claim(
        reservation,
        apartment,
        email=email,
        party_size=party_size,
        lang=lang,
        resend=True,
    )


def test_the_resent_link_the_guest_receives_carries_the_done_copy(monkeypatch):
    current, _past, _far, _apartment_id = _seed()
    try:
        reservation = db.query_one(
            "SELECT * FROM reservation WHERE id = ?", (current,)
        )
        apartment = db.query_one(
            "SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,)
        )
        monkeypatch.setattr(
            reporting,
            "reservation_progress",
            lambda _r: {"expected": 1, "filled": 1, "incomplete": []},
        )
        ok, err, _secret = _resend(
            reservation, apartment, email="done@claim.test", party_size=1, lang="cs"
        )
        assert ok, err
        payload = _outbox_payload()
        assert i18n.STRINGS["cs"]["mail_claim_next_done"] in payload["text"]
        assert i18n.STRINGS["cs"]["mail_claim_next_body"] not in payload["text"]
    finally:
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        _cleanup()


def test_an_unfinished_stay_still_sends_the_form_promise(monkeypatch):
    current, _past, _far, _apartment_id = _seed()
    try:
        reservation = db.query_one(
            "SELECT * FROM reservation WHERE id = ?", (current,)
        )
        apartment = db.query_one(
            "SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,)
        )
        monkeypatch.setattr(
            reporting,
            "reservation_progress",
            lambda _r: {"expected": 2, "filled": 1, "incomplete": []},
        )
        ok, err, _secret = _resend(
            reservation, apartment, email="open@claim.test", party_size=2, lang="cs"
        )
        assert ok, err
        payload = _outbox_payload()
        assert i18n.STRINGS["cs"]["mail_claim_next_body"] in payload["text"]
        assert i18n.STRINGS["cs"]["mail_claim_next_done"] not in payload["text"]
    finally:
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        _cleanup()


def test_the_first_link_for_a_stay_the_host_filled_in_is_not_a_form_promise(
    monkeypatch,
):
    """A hand-entered stay gets the same honesty, not just the resend path."""
    current, _past, _far, _apartment_id = _seed()
    try:
        reservation = db.query_one(
            "SELECT * FROM reservation WHERE id = ?", (current,)
        )
        apartment = db.query_one(
            "SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,)
        )
        monkeypatch.setattr(
            reporting,
            "reservation_progress",
            lambda _r: {"expected": 1, "filled": 1, "incomplete": []},
        )
        ok, err, _secret = claim.start_claim(
            reservation,
            apartment,
            email="hand@claim.test",
            party_size=1,
            lang="en",
        )
        assert ok, err
        payload = _outbox_payload()
        assert i18n.STRINGS["en"]["mail_claim_next_done"] in payload["text"]
    finally:
        db.execute("DELETE FROM console_mail_log")
        db.execute("DELETE FROM email_outbox")
        _cleanup()


def test_the_done_copy_names_no_guest_count_and_no_dead_link():
    """The audit's copy is one sentence; nothing else leaks in beside it."""
    assert DONE["en"] == (
        "Everyone is already registered. The link just opens your stay page."
    )
    assert DONE["cs"] == (
        "Všichni už jsou zaregistrovaní \u2013 odkaz jen otevře stránku vašeho pobytu."
    )
    for lang in LANGS:
        assert "%(" not in DONE[lang]
