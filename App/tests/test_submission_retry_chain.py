"""Brief 0909: unanswered filings retry on a gap schedule; final notice after five attempts."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app import config, db, reporting
from test_stale_submission import (
    _batches,
    _crashed_filing,
    _guest_row,
    _purge_sweep_rows,
    _sweep_apartment,
)


@pytest.fixture(autouse=True)
def _purge():
    yield
    _purge_sweep_rows()


def _clone_submission(apartment_id, template_id, **changes):
    row = dict(db.query_one("SELECT * FROM submission WHERE id = ?", (template_id,)))
    row.pop("id", None)
    row.update({"apartment_id": apartment_id, **changes})
    return db.insert("submission", row)


def test_guest_id_order_does_not_split_a_chain(monkeypatch):
    db.init_db()
    apartment_id, sub_id, guest_id, owner_id = _sweep_apartment(monkeypatch)
    db.update("submission", sub_id, {
        "guest_ids": "[3,1]", "state": "outcome_unknown", "mode": "auto",
        "finished_at": db.utcnow(), "error_text": "read timed out",
    })
    later = _clone_submission(apartment_id, sub_id, guest_ids="[1,3]",
                              mode=reporting.AUTO_RESEND_MODE, retried_at=None)
    chains = reporting._unknown_chains(apartment_id)
    assert [[b["id"] for b in chain] for chain in chains] == [[sub_id, later]]


def test_a_host_send_with_the_same_guests_starts_a_fresh_chain(monkeypatch):
    db.init_db()
    apartment_id, sub_id, guest_id, owner_id = _sweep_apartment(monkeypatch)
    db.update("submission", sub_id, {
        "guest_ids": "[1,3]", "state": "outcome_unknown", "mode": "auto",
        "finished_at": db.utcnow(), "error_text": "read timed out",
    })
    _clone_submission(apartment_id, sub_id, guest_ids="[1,3]",
                      mode=reporting.AUTO_RESEND_MODE, retried_at=None)
    manual = _clone_submission(apartment_id, sub_id, guest_ids="[3,1]", mode="manual",
                               state="outcome_unknown", retried_at=None)
    chains = reporting._unknown_chains(apartment_id)
    assert [[b["id"] for b in chain] for chain in chains] == [[manual]]


def test_two_resends_of_one_due_chain_send_once(monkeypatch):
    db.init_db()
    apartment_id, sub_id, guest_id, owner_id = _sweep_apartment(monkeypatch)
    db.update("submission", sub_id, {
        "state": "outcome_unknown", "error_text": "read timed out",
        "finished_at": db.utcnow(), "retried_at": None,
    })
    db.execute("UPDATE guest SET submission_id = ? WHERE id = ?", (sub_id, guest_id))
    sent = []
    monkeypatch.setattr(reporting, "submit_for_apartment", lambda *a, **k: sent.append(k) or [])
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    latest = dict(db.query_one("SELECT * FROM submission WHERE id = ?", (sub_id,)))
    assert reporting._resend_unknown_chain(apartment, latest) is True
    assert reporting._resend_unknown_chain(apartment, latest) is False
    assert len(sent) == 1


def test_the_fifth_attempt_mails_the_host_and_pushes_once(monkeypatch):
    db.init_db()
    apartment_id, original, guest_id, owner_id, client = _crashed_filing(
        monkeypatch, ["timeout"] * 4
    )
    mails = {}
    pushes = {}

    def fake_mail(apartment, submission_id, **kw):
        # Stands in for the outbox: a repeated idempotency key adds no row.
        mails.setdefault(kw["idempotency_key"], (submission_id, kw))

    def fake_push(apartment, submission_id, key=None):
        pushes.setdefault(key, submission_id)

    monkeypatch.setattr(reporting.mail_notify, "submission_problem", fake_mail)
    monkeypatch.setattr(reporting.push, "filing_problem", fake_push)
    start = datetime.now(timezone.utc)
    clock = {"now": start}
    monkeypatch.setattr(reporting, "_clock", lambda: clock["now"])

    for offset in (timedelta(minutes=119), timedelta(minutes=121),
                   timedelta(hours=8, minutes=2), timedelta(hours=20, minutes=3)):
        clock["now"] = start + offset
        reporting.sweep(owner_user_id=owner_id)
    assert client.calls == 4
    fifth = _batches(apartment_id)[-1]["id"]
    assert mails == {} and pushes == {}, "nothing is sent before the chain reaches five batches"

    clock["now"] = start + timedelta(hours=20, minutes=30)
    reporting.sweep(owner_user_id=owner_id)
    key = f"submission_unanswered:{fifth}"
    assert list(mails) == [key]
    assert mails[key][0] == fifth
    assert mails[key][1]["cc_email"] == config.SUPPORT_EMAIL
    assert mails[key][1]["state"] == "unanswered"
    assert list(pushes) == [f"unanswered:{fifth}"]
    assert _guest_row(guest_id)["submission_id"] == fifth

    for offset in (timedelta(hours=21), timedelta(hours=22), timedelta(hours=60)):
        clock["now"] = start + offset
        reporting.sweep(owner_user_id=owner_id)
    assert list(mails) == [key] and list(pushes) == [f"unanswered:{fifth}"]
    assert client.calls == 4, "a chain at five batches is never resent"
    assert len(_batches(apartment_id)) == 5
