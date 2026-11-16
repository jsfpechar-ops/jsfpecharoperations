"""Retry policy for definite UbyPort failures (brief A1b P1).

The policy is a pure function over the apartment's submission rows, newest first,
so these tests need no database.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app import reporting
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
