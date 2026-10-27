"""Standard keeps Leon Lite; Max scales the same assistant and handoff by five."""
from __future__ import annotations

import pytest

from app import ai, billing, config, db, havel, leon
from tests.ai_fake import FakeClient, reply
from tests.test_0376_ai_gates import _host_post, ws  # noqa: F401
from tests.test_leon import _stay


def _owner(ws):
    return int(db.query_one("SELECT owner_user_id FROM apartment WHERE id = ?", (ws["home"],))["owner_user_id"])


def _plan(ws, status="active", plan="standard"):
    owner = _owner(ws)
    billing.ensure_account(owner)
    db.execute("UPDATE billing_account SET status = ?, plan = ? WHERE owner_user_id = ?", (status, plan, owner))


def _switch_on(ws):
    db.execute("UPDATE apartment SET leon_enabled = 1, leon_terms_version = ? WHERE id = ?",
               (leon.LEON_TERMS_VERSION, ws["home"]))


@pytest.mark.parametrize("status,plan,allowed,multiplier", [
    ("active", "standard", True, 1),
    ("overdue", "standard", True, 1),
    ("canceling", "standard", True, 1),
    ("active", "max", True, 5),
    ("overdue", "max", True, 5),
    ("canceling", "max", True, 5),
    ("paused", "max", False, 0),
    ("trial_pending", None, True, 1),
    ("trialing", None, True, 1),
])
def test_leon_access_is_separate_from_havel(ws, monkeypatch, status, plan, allowed, multiplier):
    monkeypatch.setattr(config, "BILLING_ENABLED", True)
    _plan(ws, status, plan)
    ent = billing.entitlements(_owner(ws))
    assert ent.leon is allowed
    assert ent.ubyport_submit is True
    assert havel.plan_multiplier(_owner(ws)) == multiplier
    assert leon.plan_multiplier(ws["home"]) == (multiplier if allowed else 0)
    assert ai.enabled_for_property("leon", ws["home"]) is allowed


def test_free_legacy_and_billing_off_keep_leon(ws, monkeypatch):
    monkeypatch.setattr(config, "BILLING_ENABLED", True)
    assert billing.entitlements(_owner(ws)).leon
    assert leon.plan_multiplier(ws["home"]) == 1
    _plan(ws, "paused", "standard")
    monkeypatch.setattr(config, "BILLING_ENABLED", False)
    assert billing.entitlements(_owner(ws)).leon
    assert ai.enabled_for_property("leon", ws["home"])
    assert leon.plan_multiplier(ws["home"]) == 1


def test_standard_can_enable_and_try_leon_lite_through_host_routes(ws, monkeypatch):
    monkeypatch.setattr(config, "BILLING_ENABLED", True)
    _plan(ws)
    base = f"/apartments/{ws['home']}/leon"
    assert "data-leon-card" in ws["host"].get(f"/apartments/{ws['home']}?lang=en").text
    for path in (base, base + "/setup", base + "/setup/try"):
        assert ws["host"].get(path).status_code == 200
    assert _host_post(ws["host"], base, {"action": "on", "terms": "1"}).status_code == 303
    assert db.query_one("SELECT leon_enabled FROM apartment WHERE id = ?", (ws["home"],))["leon_enabled"] == 1
    _plan(ws, plan="max")
    assert ws["host"].get(base + "/setup/try").status_code == 200


@pytest.mark.parametrize("door", ["qr", "stay"])
def test_pausing_keeps_history_and_hands_guest_to_host_without_inference(ws, monkeypatch, door):
    monkeypatch.setattr(config, "BILLING_ENABLED", True)
    _plan(ws, plan="max")
    _switch_on(ws)
    if door == "qr":
        url = f"/g/{ws['token']}/leon"
    else:
        db.execute("UPDATE apartment SET permalink_token = ? WHERE id = ?", ("billing-leon-stay", ws["home"]))
        rid = _stay(ws["home"], 0)
        url = f"/l/billing-leon-stay/{rid}/guide/leon"
    monkeypatch.setattr(config, "ai_monthly_usd", lambda feature: 10.0)
    monkeypatch.setattr(config, "ai_key_daily_usd", lambda feature: 0.0)
    fake = FakeClient([reply({"kind": "ask_host", "reply": "", "sources": [],
                              "host_summary": "Guest asks about arrival.", "upset": False})])
    ai.set_client_for_tests(fake)
    assert ws["guest"].post(url, data={"message": "Where do I collect my keys?"}).status_code == 200
    assert len(fake.calls) == 1
    history = ws["guest"].get(url).json()["messages"]
    _plan(ws, "paused", "max")
    response = ws["guest"].post(url, data={"message": "Can you arrange a late checkout?"})
    assert response.status_code == 200
    assert response.json()["kind"] == "passed" and response.json()["asked_host"]
    assert len(fake.calls) == 1
    after = ws["guest"].get(url).json()["messages"]
    assert after[:len(history)] == history
    assert len(after) > len(history)
    assert db.query_one("SELECT COUNT(*) AS n FROM guest_question WHERE apartment_id = ?", (ws["home"],))["n"] >= 1


def test_paused_direct_core_calls_cannot_infer_or_spend_a_try(ws, monkeypatch):
    monkeypatch.setattr(config, "BILLING_ENABLED", True)
    _plan(ws, "paused", "standard")
    _switch_on(ws)
    def forbidden(*args, **kwargs):
        pytest.fail("Paused account must not reach the model call")
    monkeypatch.setattr(ai, "call", forbidden)
    chat = leon.qr_chat(ws["home"], leon.new_cookie_id(), "en")
    result = leon.reply(chat, "Where are the keys?", level="everyone", property_name="Flat",
                        host_name="Host", address_key="billing-leon")
    assert result["kind"] == "passed" and result["question_id"]
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (ws["home"],))
    left = leon.try_left(ws["home"])
    result = leon.try_reply(apartment, "Where are the keys?", lang="en", host_name="Host")
    assert result["kind"] == "passed" and result["would_ask"]
    assert leon.try_left(ws["home"]) == left


@pytest.mark.parametrize("plan,allowance", [("standard", 1), ("max", 5)])
def test_leon_capacity_is_shared_for_the_stay_and_exhaustion_hands_off(ws, monkeypatch, plan, allowance):
    monkeypatch.setattr(config, "BILLING_ENABLED", True)
    monkeypatch.setenv("UBYHOST_LEON_STAY_MAX", "1")
    monkeypatch.setattr(config, "ai_monthly_usd", lambda feature: 10.0)
    monkeypatch.setattr(config, "ai_key_daily_usd", lambda feature: 0.0)
    _plan(ws, plan=plan)
    _switch_on(ws)
    rid = _stay(ws["home"], 0)
    first = leon.stay_chat(ws["home"], rid, "en")
    second = leon.stay_chat(ws["home"], rid, "en")
    assert first["id"] == second["id"]
    fake = FakeClient([reply({"kind": "unclear", "reply": "", "sources": [],
                              "host_summary": None, "upset": False}) for _ in range(allowance)])
    ai.set_client_for_tests(fake)
    for index in range(allowance):
        result = leon.reply(first if index % 2 == 0 else second,
                            f"Where is the reception desk number {index}?",
                            level="booked", property_name="Flat", host_name="Host",
                            address_key="shared-stay")
        assert result["kind"] == "unclear"
    assert len(fake.calls) == allowance
    result = leon.reply(second, "Can you arrange a late checkout?",
                        level="booked", property_name="Flat", host_name="Host",
                        address_key="shared-stay")
    assert result["kind"] == "passed" and result["question_id"]
    assert len(fake.calls) == allowance
