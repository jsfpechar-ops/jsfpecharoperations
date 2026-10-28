"""Brief 0411: billing core. Prices, entitlements, changes, founder slots, deletion."""
from __future__ import annotations

import secrets
from datetime import date

import pytest

from app import billing, config, db, retention


def _user() -> int:
    return db.insert(
        "user_account",
        {
            "username": f"billing-{secrets.token_hex(4)}",
            "password_hash": "x",
            "created_at": db.utcnow(),
        },
    )


@pytest.fixture
def owner():
    db.init_db()
    owner_id = _user()
    yield owner_id
    db.execute("DELETE FROM platform_invoice WHERE number LIKE 'TEST-0411-%'")
    db.execute("DELETE FROM founder_slot WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM billing_account WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


@pytest.fixture
def billing_on(monkeypatch):
    monkeypatch.setattr(config, "BILLING_ENABLED", True)


def _order(owner_id: int, **fields) -> None:
    billing.ensure_account(owner_id)
    values = {
        "status": "active", "plan": "standard", "billing_interval": "year",
        "apartments_billed": 1, "period_end": None,
    }
    values.update(fields)
    sets = ", ".join(f"{name} = ?" for name in values)
    db.execute(
        f"UPDATE billing_account SET {sets} WHERE owner_user_id = ?",
        (*values.values(), owner_id),
    )


@pytest.mark.parametrize(
    "n, month, month_max, year, year_max",
    [
        (1, 149, 229, 1190, 1908),
        (3, 447, 687, 3570, 5724),
        (5, 715, 1094, 5710, 9152),
        (12, 1488, 2220, 11880, 18712),
        (20, 2280, 3324, 18200, 27992),
    ],
)
def test_totals_match_the_strategy_table(n, month, month_max, year, year_max):
    assert billing.quote(n, "standard", "month")["total"] == month
    assert billing.quote(n, "max", "month")["total"] == month_max
    assert billing.quote(n, "standard", "year")["total"] == year
    assert billing.quote(n, "max", "year")["total"] == year_max


def test_addons_and_founder_price():
    assert billing.quote(2, "standard", "month", ttlock=True)["total"] == 298 + 80
    assert billing.quote(2, "max", "month", ttlock=True)["ttlock"] == 0
    assert billing.quote(1, "standard", "year", whitelabel=True)["total"] == 1190 + 5660
    assert billing.quote(6, "standard", "year", founder=True)["base"] == 890 * 6
    assert billing.quote(6, "standard", "month", founder=True)["base"] == 149 * 4 + 119 * 2


def test_billing_off_or_no_row_means_active_standard(owner, billing_on, monkeypatch):
    assert billing.entitlements(owner) == billing.UNBILLED
    monkeypatch.setattr(config, "BILLING_ENABLED", False)
    _order(owner, status="paused")
    assert billing.entitlements(owner) == billing.UNBILLED


def test_paused_still_reports_registered_guests(owner, billing_on):
    _order(owner, status="paused", plan="max")
    ent = billing.entitlements(owner)
    assert ent.ubyport_submit is True
    assert ent.read_only and not ent.ical_import
    assert ent.ai_multiplier == 0 and not ent.ttlock


def test_max_and_addons(owner, billing_on):
    _order(owner, plan="max")
    ent = billing.entitlements(owner)
    assert (ent.ai_multiplier, ent.ttlock, ent.priority_support) == (5, True, True)
    _order(owner, plan="standard", addon_ttlock=0)
    assert billing.entitlements(owner).ttlock is False
    _order(owner, plan="standard", addon_ttlock=1, addon_whitelabel=1)
    ent = billing.entitlements(owner)
    assert ent.ttlock and ent.whitelabel and ent.ai_multiplier == 1


def test_status_follows_the_state_machine(owner):
    billing.ensure_account(owner)
    assert billing.set_status(owner, "active") is False
    assert billing.set_status(owner, "trialing") is True
    assert billing.set_status(owner, "active") is True
    assert billing.set_status(owner, "trialing") is False
    assert billing.account(owner)["status"] == "active"


def test_an_added_apartment_bills_the_remaining_whole_months(owner):
    _order(owner, apartments_billed=3, period_end="2027-05-01")
    preview = billing.apply_change(owner, {"apartments": 4}, today=date(2026, 11, 1))
    assert preview["when"] == "now"
    assert (preview["months"], preview["supplementary_czk"], preview["carry_czk"]) == (6, 595, 0)
    assert billing.account(owner)["apartments_billed"] == 3
    billing.apply_change(owner, {"apartments": 4}, today=date(2026, 11, 1), confirm=True)
    assert billing.account(owner)["apartments_billed"] == 4


def test_max_upgrade_bills_the_revised_annual_extra(owner):
    _order(owner, period_end="2027-05-01")
    preview = billing.apply_change(owner, {"plan": "max"}, today=date(2026, 11, 1))
    assert preview["period_total_after"] == 1908
    assert (preview["months"], preview["supplementary_czk"], preview["carry_czk"]) == (6, 359, 0)


def test_under_fifty_kc_is_carried_to_the_next_invoice(owner):
    _order(owner, apartments_billed=1, period_end="2026-12-01")
    result = billing.apply_change(
        owner, {"addon_ttlock": 1}, today=date(2026, 11, 1), confirm=True
    )
    assert (result["supplementary_czk"], result["carry_czk"]) == (0, 40)
    row = billing.account(owner)
    assert row["addon_ttlock"] == 1 and row["carry_czk"] == 40


def test_a_downgrade_waits_for_the_next_period(owner):
    _order(owner, plan="max", apartments_billed=2, period_end="2027-05-01")
    result = billing.apply_change(owner, {"plan": "standard"}, confirm=True)
    assert result["when"] == "next_period" and result["supplementary_czk"] == 0
    row = billing.account(owner)
    assert row["plan"] == "max"
    assert row["pending_change_json"] == '{"plan": "standard"}'


def test_one_change_at_a_time(owner):
    _order(owner)
    with pytest.raises(ValueError):
        billing.apply_change(owner, {"apartments": 2, "plan": "max"})


def test_founder_slots_are_claimed_once_and_capped(owner, monkeypatch):
    left = billing.founder_slots_left()
    slot = billing.claim_founder_slot(owner)
    assert slot is not None
    assert billing.claim_founder_slot(owner) == slot
    assert billing.founder_slots_left() == max(0, left - 1)
    other = _user()
    try:
        used = db.query_one("SELECT COUNT(*) AS n FROM founder_slot")["n"]
        monkeypatch.setattr(config, "FOUNDER_SLOTS", used)
        assert billing.claim_founder_slot(other) is None
    finally:
        db.execute("DELETE FROM user_account WHERE id = ?", (other,))


def test_deleting_the_workspace_keeps_our_invoices(owner):
    _order(owner)
    slot = billing.claim_founder_slot(owner)
    db.execute(
        "INSERT INTO platform_invoice (owner_user_id, kind, seq_year, seq_no, number, vs, "
        "issue_date, due_date, period_from, period_to, total_haler, snapshot_json, created_at) "
        "VALUES (?, 'invoice', 1999, 411, 'TEST-0411-1', '19990411', '1999-01-01', "
        "'1999-01-15', '1999-01-01', '1999-12-31', 119000, '{}', ?)",
        (owner, db.utcnow()),
    )
    retention._delete_workspace(owner)
    kept = db.query_one("SELECT owner_user_id FROM platform_invoice WHERE number = 'TEST-0411-1'")
    assert kept is not None and kept["owner_user_id"] is None
    assert billing.account(owner) is None
    assert db.query_one("SELECT 1 FROM user_account WHERE id = ?", (owner,)) is None
    used = db.query_one("SELECT owner_user_id FROM founder_slot WHERE slot = ?", (slot,))
    assert used is not None and used["owner_user_id"] is None
    db.execute("DELETE FROM founder_slot WHERE slot = ?", (slot,))
