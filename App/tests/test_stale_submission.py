"""A batch left 'running' by a dead process is held for a person, not resent."""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import date, timedelta

import pytest

import base64

from app import alerts, db, reporting
from app.ubyport.client import SubmissionResult

def _purge_sweep_rows():
    owners = []
    for row in db.query(
        "SELECT id, owner_user_id FROM apartment WHERE permalink_token = ?", ("stale-sweep",)
    ):
        if row["owner_user_id"]:
            owners.append(row["owner_user_id"])
        db.execute("DELETE FROM alert WHERE apartment_id = ?", (row["id"],))
        db.execute("DELETE FROM submission WHERE apartment_id = ?", (row["id"],))
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN "
            "(SELECT id FROM reservation WHERE apartment_id = ?)",
            (row["id"],),
        )
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (row["id"],))
        db.execute("DELETE FROM apartment WHERE id = ?", (row["id"],))
    for owner_id in owners:
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM legal_entity WHERE name = 'Sweep stale'")
    db.execute("DELETE FROM user_account WHERE username = ?", ("stale-sweep-owner",))


@pytest.fixture(autouse=True)
def _purge_sweep_fixtures():
    yield
    try:
        _purge_sweep_rows()
    except sqlite3.OperationalError:
        pass


SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()


def _guest(reservation: int, name: str, now: str) -> int:
    return db.insert(
        "guest",
        {"reservation_id": reservation, "surname": name, "first_name": "Test",
         "nationality": "GBR", "created_at": now, "updated_at": now},
    )


def _batch(apartment: int, guests: list, now: str) -> int:
    return db.insert(
        "submission",
        {"apartment_id": apartment, "created_at": now, "mode": "auto",
         "state": "running", "guest_ids": json.dumps(guests)},
    )


def test_a_running_batch_without_a_live_claim_becomes_outcome_unknown():
    db.init_db()
    now = db.utcnow()
    apartment = db.insert("apartment", {"internal_name": "Stale flat", "created_at": now})
    reservation = db.insert(
        "reservation",
        {"apartment_id": apartment, "uid": "stale-1", "date_from": "2026-01-01",
         "date_to": "2026-01-03", "status": "active", "created_at": now, "updated_at": now},
    )
    dead, sending, moved_on = (_guest(reservation, n, now) for n in ("Dead", "Sending", "Moved"))
    # A fresh row counts as stale once its claim has lapsed: the age of the
    # row is not what matters, the lease is.
    dead_batch = _batch(apartment, [dead], now)
    live_batch = _batch(apartment, [sending], now)
    db.insert("submission_claim", {"guest_id": sending, "claim_token": "t", "claimed_at": time.time()})
    old_batch = _batch(apartment, [moved_on], now)
    newer = db.insert(
        "submission",
        {"apartment_id": apartment, "created_at": now, "mode": "auto",
         "state": "error", "guest_ids": json.dumps([moved_on])},
    )
    db.execute("UPDATE guest SET submission_id = ? WHERE id = ?", (newer, moved_on))

    assert reporting.recover_stale_submissions(apartment) == 2

    def state(sid):
        return db.query_one("SELECT state FROM submission WHERE id = ?", (sid,))["state"]

    def pointer(gid):
        return db.query_one("SELECT submission_id FROM guest WHERE id = ?", (gid,))["submission_id"]

    assert state(dead_batch) == "outcome_unknown"
    assert state(old_batch) == "outcome_unknown"
    assert state(live_batch) == "running"
    assert pointer(dead) == dead_batch
    assert pointer(sending) is None
    assert pointer(moved_on) == newer, "a newer batch keeps the guest's pointer"
    assert reporting.apartment_in_doubt(apartment)


def test_recovery_alone_never_submits(monkeypatch):
    db.init_db()
    now = db.utcnow()
    apartment = db.insert("apartment", {"internal_name": "No send", "created_at": now})
    reservation = db.insert(
        "reservation",
        {"apartment_id": apartment, "uid": "solo", "date_from": "2026-01-01",
         "date_to": "2026-01-03", "status": "active", "created_at": now, "updated_at": now},
    )
    guest_id = _guest(reservation, "Alone", now)
    batch = _batch(apartment, [guest_id], now)
    calls = []

    monkeypatch.setattr(reporting, "submit_batch", lambda *a, **k: calls.append("batch") or {})
    monkeypatch.setattr(
        reporting,
        "submit_for_apartment",
        lambda *a, **k: calls.append("apartment") or [],
    )

    assert reporting.recover_stale_submissions(apartment) == 1
    assert db.query_one("SELECT state FROM submission WHERE id = ?", (batch,))["state"] == "outcome_unknown"
    assert calls == []


def _sweep_apartment(monkeypatch):
    now = db.utcnow()
    today = date.today()
    stay_from = (today - timedelta(days=2)).isoformat()
    stay_to = (today + timedelta(days=1)).isoformat()
    owner_id = db.insert(
        "user_account",
        {
            "username": "stale-sweep-owner",
            "password_hash": "x",
            "role": "host",
            "active": 1,
            "created_at": now,
        },
    )
    entity_id = db.insert(
        "legal_entity",
        {"name": "Sweep stale", "seat": "Praha", "ico": "12345678", "created_at": now},
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": owner_id,
            "internal_name": "Sweep flat",
            "city_en": "Prague",
            "permalink_token": "stale-sweep",
            "automation_mode": "immediate",
            "submit_after_hours": 0,
            "default_purpose": "10",
            "active": 1,
            "created_at": now,
        },
    )
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "uid": "sw-1",
            "date_from": stay_from,
            "date_to": stay_to,
            "status": "active",
            "expected_guests_override": 1,
            "registration_completed_at": now,
            "created_at": now,
            "updated_at": now,
        },
    )
    guest_id = db.insert(
        "guest",
        {
            "reservation_id": reservation_id,
            "surname": "Retry",
            "first_name": "Once",
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
    submission_id = db.insert(
        "submission",
        {
            "apartment_id": apartment_id,
            "created_at": now,
            "mode": "auto",
            "state": "outcome_unknown",
            "guest_ids": json.dumps([guest_id]),
            "error_text": "stopped",
        },
    )
    db.execute(
        "UPDATE guest SET submission_id = ? WHERE id = ?",
        (submission_id, guest_id),
    )

    class FakeClient:
        def submit(self, _header, _guests):  # noqa: ARG002
            return SubmissionResult(
                endpoint="test",
                request_xml="<request/>",
                response_xml="<response/>",
                pseudo_stamp="ok",
            )

    monkeypatch.setattr(reporting, "client_for", lambda *_a, **_k: FakeClient())
    monkeypatch.setattr(reporting.validation, "validate_apartment", lambda _a: [])
    return apartment_id, submission_id, guest_id, owner_id


def test_automation_skips_a_guest_while_they_still_point_at_outcome_unknown(monkeypatch):
    """A partial retry (retried_at set, pointer not cleared) must not reopen the sweep."""
    db.init_db()
    apartment_id, submission_id, guest_id, _owner_id = _sweep_apartment(monkeypatch)
    db.update("submission", submission_id, {"retried_at": db.utcnow()})
    assert db.query_one(
        "SELECT submission_id FROM guest WHERE id = ?", (guest_id,)
    )["submission_id"] == submission_id
    assert reporting.collect_sendable(apartment_id) == []


def test_sweep_retries_an_outcome_unknown_batch_once(monkeypatch):
    db.init_db()
    apartment_id, submission_id, guest_id, owner_id = _sweep_apartment(monkeypatch)
    batches = []
    real_submit = reporting.submit_batch

    def track_batch(apartment, pairs, mode="auto", env=None):  # noqa: ARG001
        batches.append(len(pairs))
        return real_submit(apartment, pairs, mode=mode, env=env)

    monkeypatch.setattr(reporting, "submit_batch", track_batch)

    reporting.sweep(owner_user_id=owner_id)
    assert batches == [1]
    assert db.query_one("SELECT retried_at FROM submission WHERE id = ?", (submission_id,))["retried_at"]
    assert db.query_one("SELECT submit_state FROM guest WHERE id = ?", (guest_id,))["submit_state"] == reporting.SENT

    reporting.sweep(owner_user_id=owner_id)
    assert batches == [1], "a second sweep must not resend the same interrupted batch"


def test_sweep_skips_retry_while_auth_failed(monkeypatch):
    db.init_db()
    apartment_id, submission_id, _guest_id, owner_id = _sweep_apartment(monkeypatch)
    alerts.raise_alert(
        "critical",
        "ubyport_auth_failed",
        "Auth failed",
        "Bad password",
        dedupe_key=f"ubyport_auth_failed:{apartment_id}",
        apartment_id=apartment_id,
    )
    batches = []
    monkeypatch.setattr(
        reporting,
        "submit_batch",
        lambda *a, **k: batches.append(1) or {"submitted": 0, "state": "noop"},
    )
    reporting.sweep(owner_user_id=owner_id)
    assert batches == []
    assert db.query_one("SELECT retried_at FROM submission WHERE id = ?", (submission_id,))["retried_at"] is None


def test_sweep_skips_retry_when_ubyport_setup_is_incomplete(monkeypatch):
    db.init_db()
    apartment_id, submission_id, _guest_id, owner_id = _sweep_apartment(monkeypatch)
    monkeypatch.setattr(
        reporting.validation,
        "validate_apartment",
        lambda _a: ["uby_ws_password"],
    )
    batches = []
    monkeypatch.setattr(
        reporting,
        "submit_batch",
        lambda *a, **k: batches.append(1) or {"submitted": 0, "state": "noop"},
    )
    reporting.sweep(owner_user_id=owner_id)
    assert batches == []
    assert db.query_one("SELECT retried_at FROM submission WHERE id = ?", (submission_id,))["retried_at"] is None


def test_immediate_guest_save_does_not_run_the_scheduler_retry(monkeypatch):
    db.init_db()
    apartment_id, submission_id, guest_id, _owner_id = _sweep_apartment(monkeypatch)
    batches = []
    monkeypatch.setattr(
        reporting,
        "submit_batch",
        lambda *a, **k: batches.append(1) or {"submitted": 0, "state": "noop"},
    )
    reporting.submit_for_apartment(apartment_id, mode="completion_immediate")
    assert batches == []
    assert db.query_one("SELECT retried_at FROM submission WHERE id = ?", (submission_id,))["retried_at"] is None


# --- WP31: exactly one automatic resend per interrupted filing ---------------


class _ScriptedClient:
    """Answers each submit with the next scripted outcome and counts the calls."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def submit(self, _header, guests):
        self.calls += 1
        outcome = self.outcomes.pop(0) if self.outcomes else "timeout"
        if outcome == "timeout":
            from app.ubyport.client import UbyportOutcomeUnknownError

            raise UbyportOutcomeUnknownError("read timed out")
        return SubmissionResult(
            endpoint="test",
            request_xml="<request/>",
            response_xml="<response/>",
            pseudo_stamp="ok" if outcome == "ok" else "",
            record_errors=["150"] * len(guests) if outcome == "duplicate" else [],
        )


def _crashed_filing(monkeypatch, outcomes):
    """A stay whose first automatic send died mid-flight, plus a scripted UbyPort."""
    apartment_id, submission_id, guest_id, owner_id = _sweep_apartment(monkeypatch)
    # The process died while the batch was on the wire: running, no live claim.
    db.update("submission", submission_id, {"state": "running", "error_text": None})
    db.execute("UPDATE guest SET submission_id = NULL WHERE id = ?", (guest_id,))
    client = _ScriptedClient(outcomes)
    monkeypatch.setattr(reporting, "client_for", lambda *_a, **_k: client)
    return apartment_id, submission_id, guest_id, owner_id, client


def _batches(apartment_id):
    return db.query(
        "SELECT id, mode, state, retried_at FROM submission WHERE apartment_id = ? ORDER BY id",
        (apartment_id,),
    )


def _guest_row(guest_id):
    return db.query_one(
        "SELECT submit_state, submission_id FROM guest WHERE id = ?", (guest_id,)
    )


def test_a_crashed_filing_is_resent_exactly_once(monkeypatch):
    db.init_db()
    apartment_id, original, guest_id, owner_id, client = _crashed_filing(monkeypatch, ["ok"])

    reporting.sweep(owner_user_id=owner_id)

    assert client.calls == 1
    rows = _batches(apartment_id)
    assert [r["id"] for r in rows][0] == original
    assert rows[0]["state"] == "outcome_unknown" and rows[0]["retried_at"]
    assert rows[1]["mode"] == reporting.AUTO_RESEND_MODE
    assert rows[1]["state"] == "ok"
    assert _guest_row(guest_id)["submit_state"] == reporting.SENT

    reporting.sweep(owner_user_id=owner_id)
    assert client.calls == 1


def test_an_unclear_resend_is_never_resent_automatically(monkeypatch):
    db.init_db()
    apartment_id, original, guest_id, owner_id, client = _crashed_filing(
        monkeypatch, ["timeout", "timeout", "timeout", "timeout"]
    )
    mails = []
    monkeypatch.setattr(
        reporting.mail_notify,
        "submission_problem",
        lambda _apartment, submission_id, **kw: mails.append((submission_id, kw["state"])),
    )

    for _ in range(3):
        reporting.sweep(owner_user_id=owner_id)

    # One resend in three sweeps, not one per sweep.
    assert client.calls == 1
    rows = _batches(apartment_id)
    assert len(rows) == 2
    resend = rows[1]
    assert resend["mode"] == reporting.AUTO_RESEND_MODE
    assert resend["state"] == "outcome_unknown"
    assert resend["retried_at"] is None
    guest = _guest_row(guest_id)
    assert guest["submit_state"] == reporting.PENDING
    assert guest["submission_id"] == resend["id"], "the guest stays held on the unclear resend"
    assert reporting.apartment_in_doubt(apartment_id)
    assert alerts.open_alert(f"submission_outcome_unknown:{apartment_id}"), "the host is alerted"
    assert mails == [(resend["id"], "transport_error")], "and mailed once, for the resend"


def test_a_crash_during_the_resend_is_not_resent_again(monkeypatch):
    db.init_db()
    apartment_id, original, guest_id, owner_id, client = _crashed_filing(monkeypatch, [])
    reporting.recover_stale_submissions(apartment_id)
    # The resend itself is cut off: its row is left running with no claim.
    resend = db.insert(
        "submission",
        {"apartment_id": apartment_id, "created_at": db.utcnow(),
         "mode": reporting.AUTO_RESEND_MODE, "state": "running",
         "guest_ids": json.dumps([guest_id])},
    )
    db.update("submission", original, {"retried_at": db.utcnow()})
    db.execute("UPDATE guest SET submission_id = NULL WHERE id = ?", (guest_id,))

    for _ in range(3):
        reporting.sweep(owner_user_id=owner_id)

    assert client.calls == 0
    assert db.query_one("SELECT state FROM submission WHERE id = ?", (resend,))["state"] == "outcome_unknown"
    assert _guest_row(guest_id)["submission_id"] == resend
    assert alerts.open_alert(f"submission_outcome_unknown:{apartment_id}")


def test_the_host_can_still_send_by_hand_after_an_unclear_resend(monkeypatch):
    db.init_db()
    apartment_id, original, guest_id, owner_id, client = _crashed_filing(
        monkeypatch, ["timeout", "ok"]
    )
    reporting.sweep(owner_user_id=owner_id)
    reporting.sweep(owner_user_id=owner_id)
    assert client.calls == 1

    # The host's send button: ignore_automation, as routes/admin.py passes it.
    results = reporting.submit_for_apartment(
        apartment_id, only_guest_ids=[guest_id], mode="manual", ignore_automation=True
    )
    assert [r["state"] for r in results] == ["ok"]
    assert client.calls == 2
    assert _guest_row(guest_id)["submit_state"] == reporting.SENT
    assert not reporting.apartment_in_doubt(apartment_id)
    assert not alerts.open_alert(f"submission_outcome_unknown:{apartment_id}")
    modes = [r["mode"] for r in _batches(apartment_id)]
    assert modes == ["auto", reporting.AUTO_RESEND_MODE, "manual"]

    reporting.sweep(owner_user_id=owner_id)
    assert client.calls == 2, "a filed guest is never sent again"


def test_an_unclear_manual_send_still_gets_its_one_automatic_resend(monkeypatch):
    db.init_db()
    apartment_id, original, guest_id, owner_id, client = _crashed_filing(
        monkeypatch, ["timeout", "timeout", "ok"]
    )
    reporting.sweep(owner_user_id=owner_id)
    reporting.submit_for_apartment(
        apartment_id, only_guest_ids=[guest_id], mode="manual", ignore_automation=True
    )
    assert client.calls == 2
    # The host's send is not the automatic one: its unclear answer is resent once.
    reporting.sweep(owner_user_id=owner_id)
    reporting.sweep(owner_user_id=owner_id)
    assert client.calls == 3
    assert _guest_row(guest_id)["submit_state"] == reporting.SENT
    modes = [r["mode"] for r in _batches(apartment_id)]
    assert modes == ["auto", reporting.AUTO_RESEND_MODE, "manual", reporting.AUTO_RESEND_MODE]


@pytest.mark.parametrize("answer", ["ok", "duplicate"])
def test_an_accepted_resend_resolves_everything(monkeypatch, answer):
    db.init_db()
    apartment_id, original, guest_id, owner_id, client = _crashed_filing(monkeypatch, [answer])
    reporting.recover_stale_submissions(apartment_id)
    assert alerts.open_alert(f"submission_outcome_unknown:{apartment_id}")

    reporting.sweep(owner_user_id=owner_id)

    assert client.calls == 1
    resend = _batches(apartment_id)[1]
    # Duplicate answer code 150 means the register already holds the record.
    assert resend["state"] == ("ok" if answer == "ok" else "ok_duplicate")
    guest = _guest_row(guest_id)
    assert guest["submit_state"] == reporting.SENT
    assert guest["submission_id"] == resend["id"]
    assert not reporting.apartment_in_doubt(apartment_id)
    assert not alerts.open_alert(f"submission_outcome_unknown:{apartment_id}")

    for _ in range(2):
        reporting.sweep(owner_user_id=owner_id)
    assert client.calls == 1
