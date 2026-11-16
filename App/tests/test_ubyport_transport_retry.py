"""Retry policy for definite UbyPort failures (brief A1b P1).

The policy is a pure function over the apartment's submission rows, newest first,
so these tests need no database.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app import alerts, config, reporting
from app.ubyport import faults

UTC = timezone.utc
NOW = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)


def _row(minutes_ago, cause="dial", state="transport_error"):
    return {
        "state": state,
        "cause": cause,
        "finished_at": (NOW - timedelta(minutes=minutes_ago)).isoformat(),
    }


def test_policy_constants():
    assert reporting.TRANSPORT_ESCALATE_AFTER == 3
    assert reporting.TRANSPORT_DAILY_CAP == 24


def test_backoff_gaps_10_30_60():
    # The next try is the last finished_at plus the gap for the chain length n.
    one = [_row(5)]
    two = [_row(5), _row(40)]
    three = [_row(5), _row(40), _row(90)]
    five = [_row(5), _row(40), _row(90), _row(150), _row(200)]
    assert reporting.transport_backoff_from_rows(one, NOW) == NOW + timedelta(minutes=5)
    assert reporting.transport_backoff_from_rows(two, NOW) == NOW + timedelta(minutes=25)
    assert reporting.transport_backoff_from_rows(three, NOW) == NOW + timedelta(minutes=55)
    assert reporting.transport_backoff_from_rows(five, NOW) == NOW + timedelta(minutes=55)


def test_daily_cap_moves_next_try_to_next_day():
    # 24 attempts finished today (Prague): the next try is 00:10 Prague tomorrow,
    # which is 23:10 UTC on 16 November (Prague is UTC+1 in November).
    twenty_four = [_row(m) for m in range(1, 25)]
    twenty_three = [_row(m) for m in range(1, 24)]
    assert reporting.transport_backoff_from_rows(twenty_four, NOW) == datetime(
        2026, 11, 16, 23, 10, tzinfo=UTC
    )
    # Newest row 1 min ago, chain of 23 (gap 60 min), below the cap: 12:59 UTC.
    assert reporting.transport_backoff_from_rows(twenty_three, NOW) == NOW + timedelta(
        minutes=59
    )


def test_manual_sends_do_not_count_toward_the_daily_cap():
    manual = [dict(_row(m), mode="manual_bulk") for m in range(1, 25)]
    # 24 manual rows: no cap, the gap for n=24 (60 min) applies from the newest row.
    assert reporting.transport_backoff_from_rows(manual, NOW) == NOW + timedelta(minutes=59)


def test_chain_resets_after_success():
    rows = [_row(5), _row(10, state="ok"), _row(20)]
    assert reporting.transport_backoff_from_rows(rows, NOW) == NOW + timedelta(minutes=5)


def test_auth_still_pauses_and_is_not_backed_off_as_transport():
    # An auth row at the head is not part of the transport chain: no gate here.
    assert reporting.transport_backoff_from_rows([_row(5, cause="auth")], NOW) is None
    # An auth row older than the chain ends the chain at that row.
    rows = [_row(5), _row(10, cause="auth")]
    assert reporting.transport_backoff_from_rows(rows, NOW) == NOW + timedelta(minutes=5)


def test_no_chain_means_no_backoff():
    assert reporting.transport_backoff_from_rows([], NOW) is None
    assert reporting.transport_backoff_from_rows([_row(5, state="ok")], NOW) is None


def test_fault_http_code_for():
    assert faults.code_for("http4xx", "HTTP 404") == "http_404"
    assert faults.code_for("redirect", "HTTP 302") == "http_302"
    assert faults.code_for("fault", "clean fault text") is None
    assert faults.code_for("dial", "") is None


# --- checks on the real send path (SQLite test schema) -----------------------

from app.ubyport.client import UbyportTransportError  # noqa: E402
from tests.test_submission_retry_cap import _cleanup, _seed  # noqa: E402


class _TransportDown:
    """A register that cannot be reached: every send is a definite transport failure."""

    def submit(self, _header, guests):
        raise UbyportTransportError("connection refused", cause="dial")


class _FaultDown:
    """UbyPort answers with a fault: a definite failure, the kind the alert streak counts."""

    def submit(self, _header, guests):
        raise UbyportTransportError("fault", cause="fault", detail="")


def _send(apartment, guest_id, monkeypatch, mode="auto", client=_TransportDown):
    monkeypatch.setattr(reporting, "client_for", lambda *_a, **_k: client())
    pairs = reporting.collect_sendable(apartment["id"], ignore_automation=True)
    assert guest_id in [guest["id"] for guest, _ in pairs]
    return reporting.submit_batch(apartment, pairs, mode=mode)


def test_escalation_alert_and_mail_once_at_three(monkeypatch):
    apartment, _res, guest_id = _seed("tok-a1b-escalate", auto=True)
    mails = []
    monkeypatch.setattr(
        reporting.mail_notify, "submission_problem", lambda *_a, **kw: mails.append(kw)
    )
    try:
        for _ in range(2):
            _send(apartment, guest_id, monkeypatch, client=_FaultDown)
        keyed = [kw for kw in mails if str(kw.get("idempotency_key") or "").startswith(
            "submission_transport_repeated:")]
        assert keyed == [], "no support copy before the third failure"
        _send(apartment, guest_id, monkeypatch, client=_FaultDown)
        keyed = [kw for kw in mails if str(kw.get("idempotency_key") or "").startswith(
            "submission_transport_repeated:")]
        assert len(keyed) == 1
        assert keyed[0]["cc_email"] == config.SUPPORT_EMAIL
        assert alerts.open_alert(f"submission_transport_repeated:{apartment['id']}")
    finally:
        _cleanup(apartment["id"])


def test_manual_send_ignores_backoff(monkeypatch):
    apartment, _res, guest_id = _seed("tok-a1b-manual", auto=True)
    # The seeded stay has no UbyPort login; the setup check is not under test here.
    monkeypatch.setattr(reporting.validation, "validate_apartment", lambda _ap: [])
    monkeypatch.setattr(reporting.db, "decrypt_secret", lambda _enc: "pw")
    monkeypatch.setattr(reporting, "client_for", lambda *_a, **_k: _TransportDown())
    try:
        for _ in range(3):
            _send(apartment, guest_id, monkeypatch)
        # Three failures in a row hold the automatic path back.
        held = reporting.submit_for_apartment(apartment["id"])
        assert held and held[0]["state"] == "backoff"
        # A host's manual send is not held back.
        sent = reporting.submit_for_apartment(apartment["id"], ignore_automation=True)
        assert sent and all(result["state"] != "backoff" for result in sent)
    finally:
        _cleanup(apartment["id"])


def test_cause_and_error_code_stored(monkeypatch):
    # Where the schema has the A1b columns (PostgreSQL after goose 00018) the
    # cause and the fault-table key are written; the SQLite schema has neither,
    # so nothing is written there and the row still records transport_error.
    monkeypatch.setattr(config, "DB_BACKEND", "postgresql")
    assert reporting._transport_cause_fields("http4xx", "HTTP 404") == {
        "cause": "http4xx", "error_code": "http_404"}
    assert reporting._transport_cause_fields("dial", "") == {"cause": "dial", "error_code": None}
    monkeypatch.setattr(config, "DB_BACKEND", "sqlite")
    assert reporting._transport_cause_fields("dial", "") == {}


def test_outcome_unknown_retry_schedule_unchanged():
    assert tuple(reporting.UNKNOWN_RETRY_GAPS) == (
        timedelta(minutes=30), timedelta(hours=2), timedelta(hours=6), timedelta(hours=12))
    assert reporting.UNKNOWN_MAX_ATTEMPTS == 5
    # An outcome_unknown row is never part of the transport chain.
    row = {"state": "outcome_unknown", "cause": "", "mode": "auto", "finished_at": NOW.isoformat()}
    assert reporting.transport_backoff_from_rows([row], NOW) is None


def test_prague_cap_next_day_across_dst_changes():
    # 26 October 2026: Prague returns to CET, so 00:10 on 26 October is 23:10 UTC on 25 October.
    # 30 March 2026: Prague is on CEST, so 00:10 on 30 March is 22:10 UTC on 29 March.
    for day_now, expected in [
        (datetime(2026, 10, 25, 12, 0, tzinfo=UTC), datetime(2026, 10, 25, 23, 10, tzinfo=UTC)),
        (datetime(2026, 3, 29, 12, 0, tzinfo=UTC), datetime(2026, 3, 29, 22, 10, tzinfo=UTC)),
    ]:
        rows = [
            {"state": "transport_error", "cause": "dial", "mode": "auto",
             "finished_at": (day_now - timedelta(minutes=m)).isoformat()}
            for m in range(1, 25)
        ]
        assert reporting.transport_backoff_from_rows(rows, day_now) == expected


def test_auto_resend_is_not_held_back_by_backoff(monkeypatch):
    apartment, _res, guest_id = _seed("tok-a1b-resend", auto=True)
    monkeypatch.setattr(reporting.validation, "validate_apartment", lambda _ap: [])
    monkeypatch.setattr(reporting.db, "decrypt_secret", lambda _enc: "pw")
    try:
        for _ in range(3):
            _send(apartment, guest_id, monkeypatch, client=_FaultDown)
        # The backoff is in force for an automatic send ...
        assert reporting.submit_for_apartment(apartment["id"])[0]["state"] == "backoff"
        # ... and an unknown-outcome resend still goes out.
        monkeypatch.setattr(reporting, "client_for", lambda *_a, **_k: _TransportDown())
        result = reporting.submit_for_apartment(apartment["id"], mode=reporting.AUTO_RESEND_MODE)
        assert all(r["state"] != "backoff" for r in result)
    finally:
        _cleanup(apartment["id"])
