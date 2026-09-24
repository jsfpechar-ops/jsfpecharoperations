"""Reviewer reproductions (not for merge)."""
from __future__ import annotations

from app import db, icalsync, reporting
from app.ubyport.client import SubmissionResult
from tests.test_submission_retry_cap import (
    BOUND, RefusingClient, _attempts, _cleanup, _fail, _seed, _stuck_alerts, host,  # noqa
)
from tests.test_icalsync import _calendar, _feed_db, _stays, _sync_now, _vevent


class Accept:
    calls = 0

    def __init__(self, receipt="UERGLTE="):
        self.receipt = receipt

    def submit(self, _h, guests):
        Accept.calls += 1
        return SubmissionResult("t", "<r/>", "<r/>", record_errors=[""] * len(guests),
                                receipt_pdf=self.receipt, pseudo_stamp="S")


class Dup:
    def __init__(self, receipt=""):
        self.receipt = receipt

    def submit(self, _h, guests):
        return SubmissionResult("t", "<r/>", "<r/>", record_errors=[";150;"] * len(guests),
                                receipt_pdf=self.receipt)


def _send(ap, monkeypatch, client, allow_resend=False):
    monkeypatch.setattr(reporting, "client_for", lambda *_a, **_k: client)
    pairs = reporting.collect_sendable(ap["id"], ignore_automation=True, allow_resend=allow_resend)
    return reporting.submit_batch(ap, pairs, mode="manual")


def _g(gid):
    return db.query_one("SELECT * FROM guest WHERE id = ?", (gid,))


def test_receipt_pointer_lost_on_second_duplicate(monkeypatch):
    ap, _r, gid = _seed("rv-rcpt1")
    try:
        s1 = _send(ap, monkeypatch, Accept())["submission_id"]
        assert _g(gid)["receipt_submission_id"] == s1
        _send(ap, monkeypatch, Dup(), allow_resend=True)
        assert _g(gid)["receipt_submission_id"] == s1
        _send(ap, monkeypatch, Dup(), allow_resend=True)
        print("after 2nd dup receipt_submission_id =", _g(gid)["receipt_submission_id"], "expected", s1)
        assert _g(gid)["receipt_submission_id"] == s1
    finally:
        _cleanup(ap["id"])


def test_receipt_pointer_moves_to_a_duplicate_only_submission(monkeypatch):
    ap, _r, gid = _seed("rv-rcpt2")
    try:
        s1 = _send(ap, monkeypatch, Accept())["submission_id"]
        s2 = _send(ap, monkeypatch, Dup(receipt="RVJS"), allow_resend=True)["submission_id"]
        _send(ap, monkeypatch, Dup(receipt="RVJS"), allow_resend=True)
        print("s1", s1, "s2", s2, "now", _g(gid)["receipt_submission_id"])
        assert _g(gid)["receipt_submission_id"] == s1
    finally:
        _cleanup(ap["id"])


def test_guest_side_correction_leaves_record_capped_and_card_clears(monkeypatch):
    ap, res, gid = _seed("rv-guestfix", auto=True)
    try:
        for _ in range(BOUND):
            _fail(ap, gid, monkeypatch)
        assert len(_stuck_alerts(ap["id"])) == 1
        # What routes/guest.py writes when the guest re-saves the form, through
        # the same helper the route uses, so the reset cannot drift from the
        # route's own condition.
        payload = {"submit_state": reporting.PENDING, "last_errors": None,
                   "doc_number": "P7654321", "updated_at": db.utcnow()}
        if reporting.guest_correction_resets_attempts(_g(gid)):
            payload["submit_attempts"] = 0
        db.update("guest", gid, payload)
        print("attempts after guest fix:", _attempts(gid))
        swept = [g["id"] for g, _ in reporting.collect_sendable(ap["id"])]
        print("sweep offers:", swept)
        reporting.clear_stuck_alert_if_recovered(res["id"])
        print("stuck cards open:", len(_stuck_alerts(ap["id"])))
        assert gid in swept
    finally:
        _cleanup(ap["id"])


def test_cap_bypassed_by_unrelated_stay_edit_in_immediate_mode(monkeypatch):
    ap, res, gid = _seed("rv-immediate", auto=True)
    try:
        for _ in range(BOUND):
            _fail(ap, gid, monkeypatch)
        db.update("apartment", ap["id"], {"automation_mode": "immediate"})
        monkeypatch.setattr(reporting.validation, "validate_apartment", lambda *_a, **_k: [])
        before = db.query_one("SELECT COUNT(*) n FROM submission WHERE apartment_id=?", (ap["id"],))["n"]
        monkeypatch.setattr(reporting, "client_for", lambda *_a, **_k: RefusingClient())
        # What /reservations/{id}/quick-edit (summary change), archiving another
        # guest, or another guest saving their form all call.
        for _ in range(5):
            reporting.submit_stay_if_complete(ap["id"], res["id"])
        after = db.query_one("SELECT COUNT(*) n FROM submission WHERE apartment_id=?", (ap["id"],))["n"]
        print("extra refused submissions:", after - before, "attempts:", _attempts(gid))
        assert after == before
    finally:
        _cleanup(ap["id"])


def test_toctou_double_filing(monkeypatch):
    ap, _r, gid = _seed("rv-race", auto=True)
    try:
        Accept.calls = 0
        monkeypatch.setattr(reporting.validation, "validate_apartment", lambda *_a, **_k: [])
        monkeypatch.setattr(reporting, "client_for", lambda *_a, **_k: Accept())
        stale = reporting.collect_sendable(ap["id"])          # worker B reads
        assert stale
        reporting.submit_for_apartment(ap["id"])               # worker A files + releases
        assert _g(gid)["submit_state"] == reporting.SENT
        token, claimed = reporting.claim_sendable(stale)       # worker B claims
        if claimed:
            reporting.submit_batch(ap, claimed, mode="auto")
        reporting.release_sendable_claim(token)
        print("register calls:", Accept.calls)
        assert Accept.calls == 1
    finally:
        _cleanup(ap["id"])


def test_submission_detail_rewrites_history(host, monkeypatch):
    ap, _r, gid = _seed("rv-detail")
    try:
        s1 = _send(ap, monkeypatch, RefusingClient())["submission_id"]
        _send(ap, monkeypatch, Accept())
        page = host.get(f"/submissions/{s1}").text
        refused_row = "pill green" in page
        print("S1 (refused 112) detail shows green Accepted pill:", refused_row)
        assert not refused_row
    finally:
        _cleanup(ap["id"])


def test_synthetic_uid_shifts_when_an_earlier_twin_leaves(monkeypatch, tmp_path):
    a = _vevent("", "2099-05-01", "2099-05-03", summary="Reserved")
    b = _vevent("", "2099-05-10", "2099-05-12", summary="Reserved")
    c = _vevent("", "2099-05-20", "2099-05-22", summary="Reserved")
    apartment_id, feed_id = _feed_db(tmp_path, monkeypatch, "rvshift", _calendar([a, b, c]))
    _sync_now(feed_id)
    by_date = {s["date_from"]: s for s in _stays(apartment_id)}
    now = db.utcnow()
    gid = db.insert("guest", {"reservation_id": by_date["2099-05-10"]["id"], "surname": "B-guest",
                              "stay_from": "2099-05-10", "stay_to": "2099-05-12",
                              "submit_state": "pending", "created_at": now, "updated_at": now})
    # Booking A is cancelled upstream and simply disappears from the feed.
    monkeypatch.setattr(icalsync, "fetch_feed", lambda _u: _calendar([b, c]))
    stats = _sync_now(feed_id)
    rows = {s["id"]: (s["date_from"], s["status"]) for s in _stays(apartment_id)}
    print("REV stats", stats, "rows", rows)
    g = _g(gid)
    print("B-guest now on reservation", g["reservation_id"], rows.get(g["reservation_id"]))
    assert rows[g["reservation_id"]] == ("2099-05-10", "active")
