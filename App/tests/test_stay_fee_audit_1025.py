"""1025 stay-fee audit: every number the guest sees, the QR amount and the host register agree.

Rules (zákon 565/1990 Sb., docs/UbyHost_workplan/04_legal_positions.md §8): counted days
are (arrival, departure]; over 60 nights is out of scope; a day is exempt while the
guest is under 18 on it; a resident of the property's obec pays nothing; the host's
decision wins; amount = liable days x rate, whole CZK.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
from datetime import date, timedelta

import pytest

from app import config, db, payments, stay_fee
from app.routes import guest as guest_routes

SIG = "data:image/png;base64,AAAA"
OWNER = "stay-fee-audit-1025"
RATE = 30


@pytest.fixture(autouse=True)
def _gate_on(monkeypatch):
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)


# --- pure engine -------------------------------------------------------------

def _g(**kw):
    base = {"id": 1, "stay_from": None, "stay_to": None, "birth_date": "01011990",
            "fee_host_decision": None, "fee_host_reason": None,
            "res_country": "DEU", "res_city": "Berlin"}
    base.update(kw)
    return base


def _whole(guest, res, apartment=None):
    share = stay_fee.guest_period(guest, res, date.min, date.max, apartment=apartment)
    return None if share is None else (share["liable_nights"], share["exempt_nights"], share["status"])


def test_arrival_day_is_not_counted_departure_day_is():
    assert _whole(_g(), {"date_from": "2026-07-01", "date_to": "2026-07-04"}) == (3, 0, "liable")
    assert _whole(_g(), {"date_from": "2026-07-01", "date_to": "2026-07-02"}) == (1, 0, "liable")
    assert _whole(_g(), {"date_from": "2026-07-01", "date_to": "2026-07-01"}) is None  # same-day: nothing


def test_sixty_nights_is_the_last_stay_in_scope_and_sixty_one_is_out():
    start = date(2026, 3, 1)
    sixty = {"date_from": start.isoformat(), "date_to": (start + timedelta(days=60)).isoformat()}
    sixty_one = {"date_from": start.isoformat(), "date_to": (start + timedelta(days=61)).isoformat()}
    assert _whole(_g(), sixty) == (60, 0, "liable")
    assert _whole(_g(), sixty_one) == (0, 0, "not_subject")
    assert stay_fee.THRESHOLD_NIGHTS == 60  # §3a: "nejvýše 60 po sobě jdoucích kalendářních dnů"


@pytest.mark.parametrize("birth,liable,exempt", [
    ("05072008", 3, 0),   # 18 on arrival day 05.07: every counted day liable
    ("06072008", 3, 0),   # 18 on the first counted day
    ("07072008", 2, 1),   # turns 18 during the stay: only the days from the birthday
    ("09072008", 0, 3),   # 18 on the day after departure: all exempt
    ("00002008", 3, 0),   # unknown day and month: 01.01.2008, adult by July 2026
    ("00002010", 0, 3),   # 01.01.2010: minor
    ("29022008", 3, 0),   # leap-day birthday, adult since 01.03.2026
])
def test_under_18_is_decided_per_counted_day(birth, liable, exempt):
    res = {"date_from": "2026-07-05", "date_to": "2026-07-08"}
    assert _whole(_g(birth_date=birth), res)[:2] == (liable, exempt)


# --- one reservation end to end ----------------------------------------------

def _cleanup():
    for row in db.query("SELECT id FROM user_account WHERE username = ?", (OWNER,)):
        oid = row["id"]
        db.execute("DELETE FROM guest WHERE reservation_id IN (SELECT r.id FROM reservation r "
                   "JOIN apartment a ON a.id = r.apartment_id WHERE a.owner_user_id = ?)", (oid,))
        db.execute("DELETE FROM reservation WHERE apartment_id IN "
                   "(SELECT id FROM apartment WHERE owner_user_id = ?)", (oid,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture
def flat():
    db.init_db()
    _cleanup()
    oid = db.insert("user_account", {"username": OWNER, "password_hash": "x",
                                     "display_name": "Audit", "created_at": db.utcnow()})
    entity = db.insert("legal_entity", {"name": "Audit s.r.o.", "owner_user_id": oid,
                                        "iban": "CZ6508000000192000145399",
                                        "created_at": db.utcnow()})
    aid = db.insert("apartment", {
        "internal_name": "Audit flat", "owner_user_id": oid, "legal_entity_id": entity,
        "addr_obec": "Praha", "stay_fee_rate_czk": RATE, "stay_fee_vs": "1234567890",
        "stay_fee_cadence": "monthly", "stay_fee_collect": 1, "stay_fee_guest_rails": "iban",
        "permalink_token": "tok-audit-1025", "created_at": db.utcnow()})
    try:
        yield aid
    finally:
        _cleanup()


def _apt(aid):
    return db.query_one("SELECT * FROM apartment WHERE id = ?", (aid,))


def _stay(aid, date_from, date_to, guests, source=None):
    now = db.utcnow()
    rid = db.insert("reservation", {"apartment_id": aid, "uid": f"audit-{date_from}-{len(guests)}",
                                    "date_from": date_from, "date_to": date_to, "status": "active",
                                    "created_at": now, "updated_at": now,
                                    **({"source": source} if source else {})})
    for i, extra in enumerate(guests):
        values = {"reservation_id": rid, "first_name": f"G{i}", "surname": "Audit",
                  "birth_date": "01011990", "nationality": "DEU", "res_country": "DEU",
                  "res_city": "Berlin", "signature_png": SIG, "created_at": now, "updated_at": now}
        values.update(extra)
        db.insert("guest", values)
    return db.query_one("SELECT * FROM reservation WHERE id = ?", (rid,))


def _register_total(apartment, first_month, months):
    total = nights = 0
    month = first_month
    for _ in range(months):
        period = stay_fee.property_period(apartment, month, live_only=True)
        total += period["total_czk"]
        nights += period["liable_nights"]
        month = stay_fee.shift_month(month, 1)
    return total, nights


def test_group_pay_panel_qr_and_register_agree(flat, monkeypatch):
    # 29 Jul -> 3 Aug: 5 counted days (30, 31 Jul; 1, 2, 3 Aug), across a month end.
    res = _stay(flat, "2026-07-29", "2026-08-03", [
        {},                                                      # adult: 5
        {"birth_date": "01012015"},                              # child: 0
        {"birth_date": "31072008"},                              # 18 on 31 Jul: 30 Jul exempt, 4 liable
        {"res_country": "CZE", "res_city": "Praha 7", "nationality": "CZE"},  # same obec: 0
        {"fee_host_decision": "exempt", "fee_host_reason": "ZTP/P"},           # host: 0
        {"stay_from": "2026-07-31", "stay_to": "2026-08-02"},   # own shorter stay: 2
        {"signature_png": None},                                 # unsigned: not counted
        {"archived_at": db.utcnow()},                            # archived: not counted
    ])
    apartment = _apt(flat)
    captured = {}
    real = payments.spayd

    def spy(account, amount, vs, message, bic=""):
        captured.update(amount=amount, vs=vs, message=message)
        return real(account, amount, vs, message, bic)

    monkeypatch.setattr(payments, "spayd", spy)
    panel = guest_routes._fee_pay_panel(apartment, res, lambda key, **kw: key)
    expected_nights = 5 + 4 + 2
    assert panel["total"] == expected_nights * RATE
    assert sum(person["amount"] for person in panel["persons"]) == panel["total"]
    assert sorted(person["days"] for person in panel["persons"]) == [2, 4, 5]
    assert captured["amount"] == panel["total"]
    assert captured["vs"] == str(res["id"]) == panel["vs"]
    assert payments.spayd("CZ6508000000192000145399", panel["total"], "1", "x").count(
        f"AM:{panel['total']}.00") == 1
    # The council register (July + August) sums to exactly what the guests were asked for.
    assert _register_total(apartment, date(2026, 7, 1), 2) == (panel["total"], expected_nights)
    july = stay_fee.property_period(apartment, date(2026, 7, 1), live_only=True)
    assert july["liable_nights"] == 2 + 1  # adult 30 + 31 Jul, the new adult 31 Jul only


def test_pay_panel_uses_the_rate_at_payment_time(flat):
    """Nothing is stored at registration: a rate change before payment changes the
    amount, and the open register period follows the same rate (no mismatch)."""
    res = _stay(flat, "2026-07-10", "2026-07-12", [{}])
    db.execute("UPDATE apartment SET stay_fee_rate_czk = 45 WHERE id = ?", (flat,))
    apartment = _apt(flat)
    panel = guest_routes._fee_pay_panel(apartment, res, lambda key, **kw: key, qr_ok=False)
    assert panel["total"] == 2 * 45 == stay_fee.property_period(apartment, date(2026, 7, 1),
                                                                  live_only=True)["total_czk"]


def test_out_of_scope_and_demo_stays_ask_for_nothing(flat):
    apartment = _apt(flat)
    long_stay = _stay(flat, "2026-03-01", "2026-05-01", [{}])  # 61 nights
    assert guest_routes._fee_pay_panel(apartment, long_stay, lambda key, **kw: key) is None
    assert guest_routes._fee_estimate(apartment, long_stay, {}) is None
    demo = _stay(flat, "2026-07-10", "2026-07-12", [{}], source="demo")
    assert guest_routes._fee_pay_panel(apartment, demo, lambda key, **kw: key) is None
    # Bug fixed in 1025: the form used to show an estimate for the demo stay.
    assert guest_routes._fee_estimate(apartment, demo, {}) is None


def test_each_device_sees_the_same_single_group_total(flat):
    """One reservation, one total, one VS: the panel is the same for every guest,
    so paying it once settles everyone (no per-device double charge)."""
    res = _stay(flat, "2026-07-10", "2026-07-12", [{}, {}])
    apartment = _apt(flat)
    one = guest_routes._fee_pay_panel(apartment, res, lambda key, **kw: key, qr_ok=False)
    two = guest_routes._fee_pay_panel(apartment, res, lambda key, **kw: key, qr_ok=False)
    assert one == two and one["total"] == 2 * 2 * RATE


# --- the form estimate (Check step) --------------------------------------------

APARTMENT = {"stay_fee_collect": 1, "stay_fee_rate_czk": RATE, "addr_obec": "Praha",
             "legal_entity_id": None}
RES = {"id": 7, "date_from": "2026-07-01", "date_to": "2026-07-05"}  # 4 counted days


def _stored(**kw):
    row = {"id": 5, "stay_from": None, "stay_to": None, "birth_date": "01011990",
           "res_country": "DEU", "res_city": "Berlin", "fee_host_decision": None}
    row.update(kw)
    return row


def test_estimate_matches_the_engine_for_typed_values():
    for values, days in [
        ({"birth_date": "01.01.1990"}, 4),
        ({"birth_date": "03.07.2008"}, 3),          # 18 on 3 Jul: 2 Jul exempt, 3-5 Jul liable
        ({"birth_date": "01.01.2015"}, 0),
        ({"res_country": "CZE", "res_city": "Praha 2"}, 0),
    ]:
        result = guest_routes._fee_estimate(APARTMENT, RES, values)
        assert (result["days"] if result else 0) == days, values


def test_edit_page_estimate_uses_the_stored_record():
    """Bug fixed in 1025: the edit page opens with empty values, so the estimate
    priced a stored child, a same-obec resident, a host exemption and a guest's own
    shorter stay as a full adult stay over the booking dates."""
    est = lambda guest: guest_routes._fee_estimate(APARTMENT, RES, {}, guest)
    assert est(_stored())["amount"] == 4 * RATE
    assert est(_stored(birth_date="01012015")) is None
    assert est(_stored(res_country="CZE", res_city="Praha 5")) is None
    assert est(_stored(fee_host_decision="exempt")) is None
    assert est(_stored(stay_from="2026-07-02", stay_to="2026-07-04"))["amount"] == 2 * RATE
    # What the guest types on the page still wins over the stored record.
    assert guest_routes._fee_estimate(APARTMENT, RES, {"birth_date": "01.01.1990"},
                                      _stored(birth_date="01012015"))["days"] == 4


def test_box_is_kept_hidden_when_the_typed_values_owe_nothing():
    """So the script can show it again when the guest corrects a birth date."""
    box = guest_routes._fee_box(APARTMENT, RES, {"birth_date": "01.01.2015"})
    assert box["hidden"] is True and box["live"] == {"from": "2026-07-01", "to": "2026-07-05",
                                                     "rate": RATE}
    assert guest_routes._fee_box(APARTMENT, RES, {"birth_date": "01.01.1990"})["hidden"] is False
    # A host decision is final: no box and no script recalculation.
    assert guest_routes._fee_box(APARTMENT, RES, {}, _stored(fee_host_decision="exempt")) is None
    charged = guest_routes._fee_box(APARTMENT, RES, {}, _stored(fee_host_decision="charge"))
    assert charged["live"] is None and charged["days"] == 4
    # Out of scope for everyone: no box.
    long_res = {"id": 8, "date_from": "2026-03-01", "date_to": "2026-05-01"}
    assert guest_routes._fee_box(APARTMENT, long_res, {"birth_date": "01.01.2015"}) is None


def test_form_script_counts_days_like_the_engine():
    """signature.js recomputes the estimate as the birth date is typed; it must give
    the same liable days as stay_fee.guest_period for every birth date and stay."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node missing")
    src = (pathlib.Path(guest_routes.__file__).resolve().parents[1] / "static" / "signature.js").read_text()
    body = src[src.index("function feeBirth(text)"):src.index("function feeObecResident(box)")]
    stays = [("2026-07-01", "2026-07-05"), ("2026-12-30", "2027-01-02"), ("2028-02-27", "2028-03-02")]
    births = ["01.01.1990", "02.07.2008", "03.07.2008", "05.07.2008", "06.07.2008", "31.12.2008",
              "01.01.2009", "00.00.2008", "00.07.2008", "29.02.2010", "28.02.2010", "01.03.2010",
              "00.00.0000", "31.02.2008", "12.13.2008", "", "01.01.15", "01.01.85", "01.01"]
    cases = [(s, e, b) for s, e in stays for b in births]
    js = body + (";const out=[];for (const [f,t,b] of %s) out.push(feeLiableDays({from:f,to:t},feeBirth(b)));"
                 "console.log(JSON.stringify(out));" % json.dumps(cases))
    got = json.loads(subprocess.run([node, "-e", js], capture_output=True, text=True, check=True).stdout)
    want = []
    for start, end, birth in cases:
        result = guest_routes._fee_estimate(APARTMENT, {"id": 1, "date_from": start, "date_to": end},
                                            {"birth_date": birth})
        want.append(result["days"] if result else 0)
    assert got == want


def test_box_markup_carries_the_live_data_and_hidden_flag():
    from html import unescape
    from app.templating import templates
    from app import i18n
    tpl = templates.env.get_template("guest/_fee_estimate.html")
    t = i18n.translator("cs")
    rule = guest_routes._fee_obec_rule(APARTMENT)
    shown = tpl.render(t=t, fee_estimate=guest_routes._fee_box(APARTMENT, RES, {}), fee_obec_rule=rule)
    assert ' hidden' not in shown.split(">")[0] and "120 Kč" in shown and "4 nocí × 30 Kč" in shown
    live = json.loads(unescape(shown.split('data-fee-live="')[1].split('"')[0]))
    assert live == {"from": "2026-07-01", "to": "2026-07-05", "rate": RATE}
    assert 'data-fee-amount="{amount} Kč"' in shown and 'data-fee-calc="{days} nocí × 30 Kč"' in shown
    assert "data-obec-rule=" in shown
    hidden = tpl.render(t=t, fee_estimate=guest_routes._fee_box(APARTMENT, RES, {"birth_date": "01.01.2015"}),
                        fee_obec_rule=rule)
    assert hidden.split(">")[0].count(" hidden") == 1
    decided = tpl.render(t=t, fee_estimate=guest_routes._fee_box(APARTMENT, RES, {},
                                                                 _stored(fee_host_decision="charge")),
                         fee_obec_rule=rule)
    assert "data-fee-live" not in decided and "data-obec-rule" not in decided
