"""Write go/internal/billing/testdata/engine_golden.json from the real Python.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt):

    .venv/bin/python scripts/billing_engine_golden.py

It seeds a throwaway SQLite database per scenario (the fixed rows in USERS plus
the scenario's own account, apartments and invoices), runs one function of
app.billing, app.billing_order or app.billing_trial, and records the return
value or the ValueError code, the billing_account row afterwards, the audit rows
and the calls the engine made to the invoicer. billing_invoices.issue_for_period,
issue_supplementary, storno and send are replaced by a recorder, so no PDF or
mail is made. Recorder answers: issue_for_period 1000 + n, issue_supplementary
2000 + n (n counts calls of that kind in the scenario, from 1), storno 3000 +
invoice id, send nothing.

go/internal/billing/engine_test.go seeds PostgreSQL from the same file, runs the
Go engine with a recording Invoicer of the same answers and compares everything.
App/tests/test_billing_engine_golden.py fails when this file is stale.

updated_at is not comparable: a row records "seed" when it still has SEED_STAMP,
else "run". The audit "at" column is not recorded. A scenario with actor_ctx runs after
db.set_current_actor, as auth.py does for a signed-in request.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "billing" / "testdata" / "engine_golden.json"

STAMP = "2026-09-01T00:00:00+00:00"
TODAY = "2026-11-13"

USERS = [
    {"id": 1, "username": "owner1@example.test"},
    {"id": 2, "username": "owner2@example.test"},
    {"id": 7, "username": "ann"},
]

ACCOUNT_COLUMNS = [
    "status", "plan", "billing_interval", "payment_method", "founder", "addon_ttlock",
    "addon_whitelabel", "apartments_billed", "trial_started_at", "trial_ends_at",
    "period_start", "period_end", "cancel_at_period_end", "pending_change_json",
    "carry_czk", "buyer_name", "buyer_street", "buyer_city", "buyer_zip", "buyer_ico",
    "buyer_dic", "buyer_email", "discount_percent", "discount_reason",
]
INT_COLUMNS = {
    "founder", "addon_ttlock", "addon_whitelabel", "apartments_billed",
    "cancel_at_period_end", "carry_czk", "discount_percent",
}
INVOICE_COLUMNS = [
    "id", "owner_user_id", "kind", "seq_year", "seq_no", "number", "vs", "issue_date",
    "due_date", "period_from", "period_to", "total_haler", "voided", "paid_on",
    "snapshot_json", "created_at",
]

MONTH = {
    "status": "active", "plan": "standard", "billing_interval": "month",
    "apartments_billed": 3, "period_start": "2026-11-01", "period_end": "2026-11-30",
}
YEAR = {
    "status": "active", "plan": "standard", "billing_interval": "year",
    "apartments_billed": 3, "period_start": "2026-01-01", "period_end": "2026-12-31",
}
TRIAL = {"status": "trialing", "trial_started_at": "2026-10-21T10:00:00+00:00",
         "trial_ends_at": "2026-11-20T10:00:00+00:00"}
PAUSED = {"status": "paused"}

GOOD_VALUES = {
    "plan": "standard", "billing_interval": "year", "addon_ttlock": False,
    "addon_whitelabel": False, "buyer_name": "Novak s.r.o.", "buyer_street": "Dlouha 1",
    "buyer_city": "Praha", "buyer_zip": "11000", "buyer_ico": "", "buyer_dic": "",
    "buyer_email": "novak@example.test",
}
FULL_VALUES = {
    **GOOD_VALUES, "plan": "max", "billing_interval": "month", "addon_ttlock": True,
    "buyer_ico": "27082440", "buyer_dic": "CZ27082440",
}


def _inv(iid, owner, kind, pfrom, pto, *, voided=0, paid=None):
    return {
        "id": iid, "owner_user_id": owner, "kind": kind, "seq_year": 2026, "seq_no": iid,
        "number": f"2026{iid:04d}", "vs": f"2026{iid:04d}", "issue_date": "2026-09-01",
        "due_date": "2026-09-15", "period_from": pfrom, "period_to": pto,
        "total_haler": 44700, "voided": voided, "paid_on": paid, "snapshot_json": "{}",
        "created_at": STAMP,
    }


def _s(name, call, *, account=None, apartments=(0, 0), invoices=(), today=TODAY, owner=1, actor_ctx=None):
    """actor_ctx: {"user_id", "username", "impersonating"} as auth.py gives db.set_current_actor."""
    return {
        "name": name, "owner": owner, "today": today, "account": account,
        "apartments": list(apartments), "invoices": list(invoices), "call": call,
        "actor_ctx": actor_ctx,
    }

ANN = {"user_id": 7, "username": "ann", "impersonating": False}
ANN_INSIDE = {"user_id": 7, "username": "ann", "impersonating": True}


def _c(fn, **args):
    return {"fn": fn, "args": args}


def _chg(change, confirm=True, actor="host"):
    return _c("apply_change", owner=1, change=change, confirm=confirm, actor=actor)


def _disc(percent, reason="", actor="operator:ann"):
    return _c("apply_discount", owner=1, percent=percent, reason=reason, actor=actor)


def _form(**kw):
    base = {
        "plan": "standard", "billing_interval": "year", "buyer_name": "Novak",
        "buyer_street": "Dlouha 1", "buyer_city": "Praha", "buyer_zip": "110 00",
        "buyer_email": "a@example.test",
    }
    base.update(kw)
    return {k: v for k, v in base.items() if v is not None}


DISCOUNT_INVOICES = [
    _inv(11, 1, "invoice", "2026-09-01", "2026-09-30"),
    _inv(12, 1, "invoice", "2026-08-01", "2026-08-31", paid="2026-08-10"),
    _inv(13, 1, "invoice", "2026-07-01", "2026-07-31", voided=1),
    _inv(14, 1, "supplementary", "2026-09-05", "2026-09-30"),
    _inv(15, 2, "invoice", "2026-09-01", "2026-09-30"),
    _inv(16, 1, "invoice", "2026-10-01", "2026-10-31"),
]

LONG_REASON = "x" * 150 + "  " + "y" * 150

SCENARIOS = [
    # --- account, ensure_account, apartment_count, period_end
    _s("account_none", _c("account", owner=1)),
    _s("account_present", _c("account", owner=1), account={**YEAR, "buyer_name": "Novak"}),
    _s("ensure_account_creates", _c("ensure_account", owner=1)),
    _s("ensure_account_keeps_existing", _c("ensure_account", owner=1), account={**TRIAL}),
    _s("apartment_count_active_only", _c("apartment_count", owner=1), apartments=(3, 2)),
    *[
        _s(f"period_end_{start}_{interval}", _c("period_end", start=start, interval=interval))
        for start, interval in [
            ("2026-01-31", "month"), ("2026-01-15", "month"), ("2026-12-31", "month"),
            ("2026-12-01", "month"), ("2026-11-13", "year"), ("2024-02-29", "year"),
            ("2026-03-31", "month"), ("2026-05-31", "month"),
        ]
    ],
    # --- set_status
    _s("set_status_unknown", _c("set_status", owner=1, new="gone", actor="system"), account={**TRIAL}),
    _s("set_status_trialing_to_active", _c("set_status", owner=1, new="active", actor="system"), account={**TRIAL}),
    _s("set_status_trial_pending_to_trialing", _c("set_status", owner=1, new="trialing", actor="system"),
       account={"status": "trial_pending"}),
    _s("set_status_trial_pending_to_paused_refused", _c("set_status", owner=1, new="paused", actor="system"),
       account={"status": "trial_pending"}),
    _s("set_status_no_account", _c("set_status", owner=1, new="active", actor="system")),
    _s("set_status_active_to_overdue", _c("set_status", owner=1, new="overdue", actor="system"), account={**MONTH}),
    _s("set_status_overdue_to_paused", _c("set_status", owner=1, new="paused", actor="operator:ann"),
       account={**MONTH, "status": "overdue"}),
    _s("set_status_paused_to_active", _c("set_status", owner=1, new="active", actor="operator:ann"),
       account={**MONTH, "status": "paused"}),
    _s("set_status_canceling_to_active", _c("set_status", owner=1, new="active", actor="host"),
       account={**MONTH, "status": "canceling"}),
    _s("set_status_active_to_trialing_refused", _c("set_status", owner=1, new="trialing", actor="system"),
       account={**MONTH}),
    _s("set_status_same_state_refused", _c("set_status", owner=1, new="active", actor="system"), account={**MONTH}),
    # --- operator_pause
    _s("operator_pause_trial_pending", _c("operator_pause", owner=1, actor="operator:ann"),
       account={"status": "trial_pending"}),
    _s("operator_pause_trialing", _c("operator_pause", owner=1, actor="operator:ann"), account={**TRIAL}),
    _s("operator_pause_already_paused", _c("operator_pause", owner=1, actor="operator:ann"), account={**PAUSED}),
    _s("operator_pause_active_refused", _c("operator_pause", owner=1, actor="operator:ann"), account={**MONTH}),
    _s("operator_pause_no_account", _c("operator_pause", owner=1, actor="operator:ann")),
    # --- apply_change
    _s("change_two_keys", _chg({"apartments": 4, "plan": "max"}), account={**MONTH}),
    _s("change_unknown_key", _chg({"colour": 4}), account={**MONTH}),
    _s("change_empty", _chg({}), account={**MONTH}),
    _s("change_no_account", _chg({"apartments": 4})),
    _s("change_no_plan", _chg({"apartments": 4}), account={"status": "trialing"}),
    _s("change_whitelabel_unavailable", _chg({"addon_whitelabel": 1}), account={**MONTH}),
    _s("change_whitelabel_off_allowed", _chg({"addon_whitelabel": 0}), account={**MONTH}),
    _s("change_whitelabel_kept_in_quote", _chg({"apartments": 5}), account={**MONTH, "addon_whitelabel": 1}),
    _s("change_unknown_plan", _chg({"plan": "gold"}), account={**MONTH}),
    _s("change_none_same_value", _chg({"apartments": 3}), account={**MONTH}),
    _s("change_none_same_addon", _chg({"addon_ttlock": 0}), account={**MONTH}),
    _s("change_month_rise_preview", _chg({"apartments": 5}, confirm=False), account={**MONTH}),
    _s("change_month_rise_confirm", _chg({"apartments": 5}), account={**MONTH}),
    _s("change_month_plan_to_max", _chg({"plan": "max"}), account={**MONTH}),
    _s("change_month_ttlock_on", _chg({"addon_ttlock": 1}), account={**MONTH}),
    _s("change_month_drop_pending", _chg({"apartments": 2}), account={**MONTH}),
    _s("change_month_drop_preview", _chg({"apartments": 2}, confirm=False), account={**MONTH}),
    _s("change_max_to_standard_pending", _chg({"plan": "standard"}), account={**MONTH, "plan": "max"}),
    _s("change_ttlock_off_merges_pending", _chg({"addon_ttlock": 0}),
       account={**MONTH, "addon_ttlock": 1, "pending_change_json": "{\"apartments\": 2}"}),
    _s("change_interval_to_year", _chg({"billing_interval": "year"}), account={**MONTH}),
    _s("change_interval_same_goes_next_period", _chg({"billing_interval": "month"}), account={**MONTH}),
    _s("change_year_rise_supplementary_preview", _chg({"apartments": 6}, confirm=False), account={**YEAR}),
    _s("change_year_rise_supplementary_confirm", _chg({"apartments": 6}), account={**YEAR}),
    _s("change_year_rise_carry_confirm", _chg({"apartments": 4}),
       account={**YEAR, "discount_percent": 90, "carry_czk": 5}),
    _s("change_year_rise_no_months_left", _chg({"apartments": 6}),
       account={**YEAR, "period_end": "2026-11-30"}),
    _s("change_year_rise_no_period_end", _chg({"apartments": 6}), account={**YEAR, "period_end": None}),
    _s("change_year_rise_half_even_tie", _chg({"apartments": 6}, confirm=False), account={**YEAR}),
    _s("change_year_rise_four_months", _chg({"addon_ttlock": 1}, confirm=False),
       account={**YEAR, "apartments_billed": 1, "discount_percent": 49, "period_end": "2027-03-31"},
       today="2026-11-13"),
    # delta * months / 12 is x.5 with x even: half-to-even rounds down, half-up would not.
    _s("change_year_half_even_exactly_50", _chg({"apartments": 4}),
       account={**YEAR, "discount_percent": 83, "period_end": "2027-02-28"}),
    _s("change_year_half_even_carry_44", _chg({"apartments": 4}),
       account={**YEAR, "discount_percent": 85, "period_end": "2027-02-28"}),
    _s("change_year_half_even_294", _chg({"apartments": 4}, confirm=False),
       account={**YEAR, "discount_percent": 1, "period_end": "2027-02-28"}),
    _s("change_year_months_day_borrow", _chg({"apartments": 6}, confirm=False),
       account={**YEAR, "period_end": "2027-02-10"}, today="2026-11-13"),
    _s("change_year_drop_pending", _chg({"apartments": 2}), account={**YEAR}),
    _s("change_with_discount_month", _chg({"apartments": 5}), account={**MONTH, "discount_percent": 15}),
    # --- apply_discount
    _s("discount_set_reissues_unpaid", _disc(20, "  Friend of the house  "), account={**MONTH},
       invoices=DISCOUNT_INVOICES),
    _s("discount_clear_to_zero", _disc(0, ""), account={**MONTH, "discount_percent": 20, "discount_reason": "old"},
       invoices=[_inv(11, 1, "invoice", "2026-09-01", "2026-09-30")]),
    _s("discount_zero_keeps_reason", _disc(0, "kept note"), account={**MONTH}),
    _s("discount_long_reason_cut", _disc(10, LONG_REASON), account={**MONTH},
       invoices=[_inv(11, 1, "invoice", "2026-09-01", "2026-09-30")]),
    _s("discount_czech_reason", _disc(100, "Sleva pro věrného zákazníka"), account={**YEAR}),
    _s("discount_out_of_range_high", _disc(101, "x"), account={**MONTH}),
    _s("discount_out_of_range_low", _disc(-1, "x"), account={**MONTH}),
    _s("discount_reason_missing", _disc(10, "   "), account={**MONTH}),
    _s("discount_no_plan", _disc(10, "x"), account={"status": "trialing"}),
    _s("discount_no_account", _disc(10, "x")),
    _s("discount_range_checked_before_reason", _disc(150, ""), account={**MONTH}),
    # --- place
    _s("place_trialing", _c("place", owner=1, values=FULL_VALUES), account={**TRIAL}, apartments=(2, 1)),
    _s("place_trial_pending_no_trial_end", _c("place", owner=1, values=GOOD_VALUES),
       account={"status": "trial_pending", "pending_change_json": "{\"plan\": \"max\"}"}, apartments=(2, 0)),
    _s("place_paused_year_issues_invoice", _c("place", owner=1, values=GOOD_VALUES), account={**PAUSED},
       apartments=(2, 0)),
    _s("place_paused_month_end_of_february", _c("place", owner=1, values={**GOOD_VALUES, "billing_interval": "month"}),
       account={**PAUSED}, apartments=(0, 0), today="2026-01-31"),
    _s("place_paused_ttlock_max", _c("place", owner=1, values=FULL_VALUES), account={**PAUSED}, apartments=(11, 0)),
    _s("place_active_refused", _c("place", owner=1, values=GOOD_VALUES), account={**MONTH}),
    _s("place_overdue_refused", _c("place", owner=1, values=GOOD_VALUES), account={**MONTH, "status": "overdue"}),
    _s("place_no_account", _c("place", owner=1, values=GOOD_VALUES)),
    _s("place_whitelabel_unavailable", _c("place", owner=1, values={**GOOD_VALUES, "addon_whitelabel": True}),
       account={**PAUSED}),
    _s("place_whitelabel_granted_kept", _c("place", owner=1, values={**GOOD_VALUES, "addon_whitelabel": True}),
       account={**PAUSED, "addon_whitelabel": 1}, apartments=(1, 0)),
    # --- place_for_operator
    _s("operator_place_fresh_host", _c("place_for_operator", owner=1, values=GOOD_VALUES, actor="operator:ann"),
       apartments=(2, 0)),
    _s("operator_place_trialing_host", _c("place_for_operator", owner=1, values=FULL_VALUES, actor="operator:ann"),
       account={**TRIAL}, apartments=(1, 0)),
    _s("operator_place_paused_host", _c("place_for_operator", owner=1, values=GOOD_VALUES, actor="operator:ann"),
       account={**PAUSED}, apartments=(1, 0)),
    _s("operator_place_already_ordered", _c("place_for_operator", owner=1, values=GOOD_VALUES, actor="operator:ann"),
       account={**MONTH}),
    _s("operator_place_active_without_plan",
       _c("place_for_operator", owner=1, values=GOOD_VALUES, actor="operator:ann"),
       account={"status": "active"}),
    _s("operator_place_whitelabel_unavailable",
       _c("place_for_operator", owner=1, values={**GOOD_VALUES, "addon_whitelabel": True}, actor="operator:ann"),
       account={**PAUSED}),
    _s("operator_place_whitelabel_unavailable_fresh",
       _c("place_for_operator", owner=1, values={**GOOD_VALUES, "addon_whitelabel": True}, actor="operator:ann")),
    # --- change (order layer)
    _s("order_change_year_rise_issues_supplementary", _c("change", owner=1, field="apartments", value=6, confirm=True),
       account={**YEAR}),
    _s("order_change_year_half_even_exactly_50",
       _c("change", owner=1, field="apartments", value=4, confirm=True),
       account={**YEAR, "discount_percent": 83, "period_end": "2027-02-28"}),
    _s("order_change_year_rise_preview", _c("change", owner=1, field="apartments", value=6, confirm=False),
       account={**YEAR}),
    _s("order_change_year_rise_carry_no_invoice", _c("change", owner=1, field="apartments", value=4, confirm=True),
       account={**YEAR, "discount_percent": 90}),
    _s("order_change_month_rise_no_invoice", _c("change", owner=1, field="plan", value="max", confirm=True),
       account={**MONTH}),
    _s("order_change_drop_pending_no_invoice", _c("change", owner=1, field="apartments", value=2, confirm=True),
       account={**YEAR}),
    _s("order_change_no_plan", _c("change", owner=1, field="apartments", value=2, confirm=True), account={**TRIAL}),
    _s("order_change_whitelabel_unavailable", _c("change", owner=1, field="addon_whitelabel", value=1, confirm=True),
       account={**YEAR}),
    # --- cancel, resume
    _s("cancel_active", _c("cancel", owner=1), account={**MONTH}),
    _s("cancel_trialing_refused", _c("cancel", owner=1), account={**TRIAL}),
    _s("cancel_no_account", _c("cancel", owner=1)),
    _s("resume_canceling", _c("resume", owner=1), account={**MONTH, "status": "canceling", "cancel_at_period_end": 1}),
    _s("resume_active_refused", _c("resume", owner=1), account={**MONTH}),
    _s("resume_paused_goes_active_too", _c("resume", owner=1), account={**MONTH, "status": "paused"}),
    # --- extend_trial
    _s("extend_trial_running", _c("extend_trial", owner=1, days=7, actor="operator:ann"), account={**TRIAL}),
    _s("extend_trial_past_end_clamps_to_today", _c("extend_trial", owner=1, days=10, actor="operator:ann"),
       account={**TRIAL, "trial_ends_at": "2026-11-01T10:00:00+00:00"}),
    _s("extend_trial_end_is_today", _c("extend_trial", owner=1, days=1, actor="operator:ann"),
       account={**TRIAL, "trial_ends_at": "2026-11-13"}),
    _s("extend_trial_max_days", _c("extend_trial", owner=1, days=365, actor="operator:ann"), account={**TRIAL}),
    _s("extend_trial_zero_days", _c("extend_trial", owner=1, days=0, actor="operator:ann"), account={**TRIAL}),
    _s("extend_trial_negative_days", _c("extend_trial", owner=1, days=-3, actor="operator:ann"), account={**TRIAL}),
    _s("extend_trial_too_many_days", _c("extend_trial", owner=1, days=366, actor="operator:ann"), account={**TRIAL}),
    _s("extend_trial_bad_days_before_account", _c("extend_trial", owner=1, days=0, actor="operator:ann")),
    _s("extend_trial_not_trialing", _c("extend_trial", owner=1, days=5, actor="operator:ann"), account={**MONTH}),
    _s("extend_trial_no_account", _c("extend_trial", owner=1, days=5, actor="operator:ann")),
    _s("extend_trial_no_end_date", _c("extend_trial", owner=1, days=5, actor="operator:ann"),
       account={"status": "trialing"}),
    # --- with a signed-in actor (db.set_current_actor): "host" becomes the username, ids are filled
    _s("ctx_operator_place_fresh_host", _c("place_for_operator", owner=1, values=GOOD_VALUES, actor="operator:ann"),
       apartments=(2, 0), actor_ctx=ANN),
    _s("ctx_operator_place_impersonating", _c("place_for_operator", owner=1, values=FULL_VALUES, actor="operator:ann"),
       account={**TRIAL}, apartments=(1, 0), actor_ctx=ANN_INSIDE),
    _s("ctx_cancel_active", _c("cancel", owner=1), account={**MONTH}, actor_ctx=ANN),
    _s("ctx_cancel_active_impersonating", _c("cancel", owner=1), account={**MONTH}, actor_ctx=ANN_INSIDE),
    _s("ctx_resume_canceling", _c("resume", owner=1), account={**MONTH, "status": "canceling"}, actor_ctx=ANN),
    _s("ctx_set_status_named_actor_kept", _c("set_status", owner=1, new="active", actor="system"),
       account={**TRIAL}, actor_ctx=ANN),
    _s("ctx_set_status_host_replaced", _c("set_status", owner=1, new="active", actor="host"),
       account={**TRIAL}, actor_ctx=ANN),
    _s("ctx_place_paused_year", _c("place", owner=1, values=GOOD_VALUES), account={**PAUSED},
       apartments=(2, 0), actor_ctx=ANN),
    _s("ctx_apply_change_host_replaced", _chg({"apartments": 5}), account={**MONTH}, actor_ctx=ANN),
    _s("ctx_discount_named_actor", _disc(10, "loyal"), account={**MONTH}, actor_ctx=ANN_INSIDE),
    _s("ctx_extend_trial", _c("extend_trial", owner=1, days=7, actor="operator:ann"), account={**TRIAL},
       actor_ctx=ANN),
    # --- read_form
    _s("form_valid", _c("read_form", form=_form())),
    _s("form_valid_full", _c("read_form", form=_form(
        plan="max", billing_interval="month", addon_ttlock="1", addon_whitelabel="1",
        buyer_ico="27082440", buyer_dic=" CZ27082440 ", buyer_zip=" 110 00 ",
        buyer_email="Name <Host@Example.CZ>", buyer_name="  Novák & syn  "))),
    _s("form_empty", _c("read_form", form={})),
    _s("form_bad_plan_and_interval", _c("read_form", form=_form(plan="gold", billing_interval="week"))),
    _s("form_blank_required", _c("read_form", form=_form(buyer_name="  ", buyer_street="", buyer_city=None))),
    _s("form_zip_short", _c("read_form", form=_form(buyer_zip="1100"))),
    _s("form_zip_letters", _c("read_form", form=_form(buyer_zip="11a00"))),
    _s("form_zip_fullwidth_digits", _c("read_form", form=_form(buyer_zip="１１０００"))),
    _s("form_zip_six", _c("read_form", form=_form(buyer_zip="110 000"))),
    _s("form_ico_bad_checksum", _c("read_form", form=_form(buyer_ico="12345678"))),
    _s("form_ico_short", _c("read_form", form=_form(buyer_ico="123"))),
    _s("form_ico_letters", _c("read_form", form=_form(buyer_ico="2708244a"))),
    _s("form_ico_remainder_zero_and_one", _c("read_form", form=_form(buyer_ico="25596641"))),
    _s("form_email_missing", _c("read_form", form=_form(buyer_email=None))),
    _s("form_email_no_tld", _c("read_form", form=_form(buyer_email="a@b"))),
    _s("form_email_two_addresses", _c("read_form", form=_form(buyer_email="a@b.cz, c@d.cz"))),
    _s("form_email_angle_with_name", _c("read_form", form=_form(buyer_email="Josef <JOSEF@X.CZ>"))),
    _s("form_email_text_after_angle", _c("read_form", form=_form(buyer_email="<a@b.cz> junk"))),
    _s("form_email_too_long", _c("read_form", form=_form(buyer_email="a" * 250 + "@x.cz"))),
    _s("form_email_spaces_inside", _c("read_form", form=_form(buyer_email="a b@x.cz"))),
    _s("form_addon_flags_only_one_counts", _c("read_form", form=_form(addon_ttlock="0", addon_whitelabel="true"))),
]


def _row(owner):
    from app import db

    row = db.query_one("SELECT * FROM billing_account WHERE owner_user_id = ?", (owner,))
    return dict(row) if row else None


def _acct(row, collapse):
    """The comparable columns of a billing_account row."""
    if row is None:
        return None
    out = {"owner_user_id": int(row["owner_user_id"])}
    for col in ACCOUNT_COLUMNS:
        value = row[col]
        if value is None:
            value = 0 if col in INT_COLUMNS else ("" if collapse else None)
        out[col] = int(value) if col in INT_COLUMNS else value
    out["updated_at"] = "seed" if row["updated_at"] == STAMP else "run"
    return out


def _reset(db) -> None:
    for table in ("audit", "platform_invoice", "billing_account", "apartment"):
        db.execute(f"DELETE FROM {table}")


def _seed(db, sc) -> None:
    owner = sc["owner"]
    acc = sc["account"]
    if acc is not None:
        cols = ["owner_user_id", "updated_at"] + list(acc)
        vals = [owner, STAMP] + list(acc.values())
        marks = ", ".join("?" for _ in cols)
        db.execute(f"INSERT INTO billing_account ({', '.join(cols)}) VALUES ({marks})", vals)
    active, inactive = sc["apartments"]
    aid = 0
    for flag, count in ((1, active), (0, inactive)):
        for _ in range(count):
            aid += 1
            db.execute(
                "INSERT INTO apartment (id, owner_user_id, internal_name, active, created_at) VALUES (?, ?, ?, ?, ?)",
                (aid, owner, f"flat {aid}", flag, STAMP),
            )
    if active:
        # An apartment of another host never counts.
        db.execute(
            "INSERT INTO apartment (id, owner_user_id, internal_name, active, created_at) VALUES (?, ?, ?, 1, ?)",
            (900, 2 if owner == 1 else 1, "foreign", STAMP),
        )
    for inv in sc["invoices"]:
        marks = ", ".join("?" for _ in INVOICE_COLUMNS)
        db.execute(
            f"INSERT INTO platform_invoice ({', '.join(INVOICE_COLUMNS)}) VALUES ({marks})",
            [inv[c] for c in INVOICE_COLUMNS],
        )


class _Recorder:
    def __init__(self):
        self.calls = []
        self.issued = 0
        self.supplementary = 0

    def issue_for_period(self, owner, period_from, period_to, *, today):
        self.issued += 1
        self.calls.append(["issue_for_period", owner, period_from, period_to, today.isoformat()])
        return 1000 + self.issued

    def issue_supplementary(self, owner, *, amount_czk, description, period_from, period_to, today):
        self.supplementary += 1
        self.calls.append(["issue_supplementary", owner, amount_czk, description,
                           period_from, period_to, today.isoformat()])
        return 2000 + self.supplementary

    def storno(self, invoice_id, *, reason, today):
        self.calls.append(["storno", invoice_id, reason, today.isoformat()])
        return 3000 + invoice_id

    def send(self, invoice_id):
        self.calls.append(["send", invoice_id])
        return None


def _run(sc, rec):
    from app import billing, billing_order, billing_trial

    fn = sc["call"]["fn"]
    a = sc["call"]["args"]
    day = date.fromisoformat(sc["today"])
    if fn == "account":
        return _acct(billing.account(a["owner"]), True)
    if fn == "ensure_account":
        return _acct(billing.ensure_account(a["owner"]), True)
    if fn == "apartment_count":
        return billing.apartment_count(a["owner"])
    if fn == "period_end":
        return billing_trial.period_end(date.fromisoformat(a["start"]), a["interval"]).isoformat()
    if fn == "set_status":
        return billing.set_status(a["owner"], a["new"], actor=a["actor"])
    if fn == "operator_pause":
        return billing.operator_pause(a["owner"], actor=a["actor"])
    if fn == "apply_change":
        return billing.apply_change(a["owner"], a["change"], today=day, confirm=a["confirm"], actor=a["actor"])
    if fn == "apply_discount":
        return billing.apply_discount(a["owner"], a["percent"], reason=a["reason"], actor=a["actor"], today=day)
    if fn == "place":
        return billing_order.place(a["owner"], a["values"], today=day)
    if fn == "place_for_operator":
        return billing_order.place_for_operator(a["owner"], a["values"], actor=a["actor"], today=day)
    if fn == "change":
        return billing_order.change(a["owner"], a["field"], a["value"], confirm=a["confirm"], today=day)
    if fn == "cancel":
        return billing_order.cancel(a["owner"])
    if fn == "resume":
        return billing_order.resume(a["owner"])
    if fn == "extend_trial":
        return billing_order.extend_trial(a["owner"], a["days"], actor=a["actor"], today=day)
    if fn == "read_form":
        values, errors = billing_order.read_form(a["form"])
        return {"values": values, "errors": errors}
    raise SystemExit(f"unknown fn {fn}")


def render() -> str:
    """Run every scenario on a fresh database and return the golden JSON text."""
    from app import billing_invoices, db

    db.init_db()
    for user in USERS:
        db.execute(
            "INSERT INTO user_account (id, username, password_hash, role, created_at) VALUES (?, ?, 'x', 'host', ?)",
            (user["id"], user["username"], STAMP),
        )
    names = [sc["name"] for sc in SCENARIOS]
    assert len(names) == len(set(names)), "duplicate scenario name"
    out = []
    for sc in SCENARIOS:
        _reset(db)
        _seed(db, sc)
        rec = _Recorder()
        saved = {n: getattr(billing_invoices, n) for n in ("issue_for_period", "issue_supplementary", "storno", "send")}
        for n in saved:
            setattr(billing_invoices, n, getattr(rec, n))
        entry = {k: sc[k] for k in ("name", "owner", "today", "account", "apartments", "invoices", "call",
                                    "actor_ctx")}
        ctx = sc["actor_ctx"]
        if ctx:
            db.set_current_actor(ctx["user_id"], ctx["username"], impersonating=ctx["impersonating"])
        try:
            entry["result"] = _run(sc, rec)
        except ValueError as exc:
            entry["error"] = str(exc).split(":")[0].strip()
        finally:
            db.set_current_actor(None)
            for n, f in saved.items():
                setattr(billing_invoices, n, f)
        entry["account_after"] = _acct(_row(sc["owner"]), False)
        entry["audit"] = [
            {"action": r["action"], "detail": r["detail"], "actor": r["actor"],
             "owner_user_id": r["owner_user_id"], "actor_user_id": r["actor_user_id"],
             "impersonator_user_id": r["impersonator_user_id"]}
            for r in db.query(
                "SELECT action, detail, actor, owner_user_id, actor_user_id, impersonator_user_id "
                "FROM audit ORDER BY id")
        ]
        entry["invoicer"] = rec.calls
        out.append(entry)
    from app import billing, billing_order

    tables = {
        "statuses": list(billing.STATUSES),
        "transitions": {k: sorted(v) for k, v in billing.TRANSITIONS.items()},
        "plans": list(billing.PLANS),
        "intervals": list(billing.INTERVALS),
        "orderable": list(billing_order.ORDERABLE),
        "buyer_fields": list(billing_order.BUYER_FIELDS),
        "change_columns": dict(billing.CHANGE_COLUMNS),
        "supplementary_min_czk": billing.SUPPLEMENTARY_MIN_CZK,
    }
    golden = {"stamp": STAMP, "users": USERS, "tables": tables, "scenarios": out}
    return json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    if os.environ.get("UBYHOST_DATABASE_URL"):
        sys.exit("refusing to run: UBYHOST_DATABASE_URL is set; this script wipes tables")
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ["UBYHOST_DATA_DIR"] = str(tmp)
    os.environ["UBYHOST_DB"] = str(tmp / "billing_engine_golden.sqlite3")
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    sys.path.insert(0, str(APP))
    main()
