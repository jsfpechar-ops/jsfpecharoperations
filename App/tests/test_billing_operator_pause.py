"""Brief 1141: billing.operator_pause and billing_order.place_for_operator, behaviour."""
from __future__ import annotations

import pytest

from app import billing, billing_order, db
from tests.test_billing_order import BUYER, _set, _values, host  # noqa: F401


def _audits(owner: int) -> int:
    return db.query_one(
        "SELECT COUNT(*) AS n FROM audit WHERE action = ? AND owner_user_id = ?",
        ("billing_status", owner),
    )["n"]


def _status(owner: int) -> str:
    return billing.account(owner)["status"]


@pytest.mark.parametrize("start", ["trial_pending", "trialing"])
def test_operator_pause_moves_to_paused_with_one_audit(host, start):
    owner = host["owner"]
    _set(owner, status=start)
    before = _audits(owner)
    assert billing.operator_pause(owner, actor="op") is True
    assert _status(owner) == "paused"
    assert _audits(owner) == before + 1


@pytest.mark.parametrize("start", ["paused", "active", "overdue", "canceling"])
def test_operator_pause_refuses_other_states_without_audit(host, start):
    owner = host["owner"]
    _set(owner, status=start)
    before = _audits(owner)
    assert billing.operator_pause(owner, actor="op") is False
    assert _status(owner) == start
    assert _audits(owner) == before


@pytest.mark.parametrize("start", ["active", "overdue", "canceling"])
def test_place_for_operator_with_no_plan_in_a_live_state_is_already_ordered(host, start):
    owner = host["owner"]
    _set(owner, status=start, plan=None)
    with pytest.raises(ValueError, match="already_ordered"):
        billing_order.place_for_operator(owner, _values(), actor="op")
    assert _status(owner) == start
