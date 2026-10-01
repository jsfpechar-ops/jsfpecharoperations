"""Host-only stay-fee calculator: nights split by period, the automatic rules,
host decisions, VS grouping, blocking issues, payment QR, register CSV, PDF."""
from __future__ import annotations

import io
from datetime import date

import pytest
from pypdf import PdfReader

from app import db, stay_fee, stay_fee_remittance_pdf, validation

SIG = "data:image/png;base64,AAAA"
OWNER = "stay-fee-calc-host"
AUG = date(2026, 8, 1)


# --- pure --------------------------------------------------------------------

def test_nights_split_by_month_without_double_counting():
    start, end = date(2026, 8, 30), date(2026, 9, 3)          # 4 counted days
    aug = stay_fee.period_bounds("monthly", AUG)
    sep = stay_fee.period_bounds("monthly", date(2026, 9, 1))
    assert stay_fee.nights_in(start, end, *aug) == 1           # 31 Aug
    assert stay_fee.nights_in(start, end, *sep) == 3           # 1–3 Sep
    assert stay_fee.nights_in(date(2026, 9, 10), date(2026, 9, 14), *sep) == 4


def test_period_bounds_and_labels():
    assert stay_fee.period_bounds("monthly", date(2028, 2, 1)) == (date(2028, 2, 1), date(2028, 2, 29))
    assert stay_fee.period_bounds("quarterly", date(2026, 8, 1)) == (date(2026, 7, 1), date(2026, 9, 30))
    assert stay_fee.period_bounds("quarterly", date(2026, 12, 1)) == (date(2026, 10, 1), date(2026, 12, 31))
    assert stay_fee.period_label_cs("monthly", AUG) == "Srpen 2026"
    assert stay_fee.period_label_cs("quarterly", AUG) == "3. čtvrtletí 2026"


def test_period_complete():
    assert stay_fee.period_complete("monthly", AUG, date(2026, 9, 1))
    assert not stay_fee.period_complete("monthly", AUG, date(2026, 8, 31))
    assert not stay_fee.period_complete("quarterly", AUG, date(2026, 9, 15))


@pytest.mark.parametrize("raw,expected", [("2026-08", date(2026, 8, 1)), ("2026-13", None),
                                          ("", None), ("2026/08", None), ("abcd-ef", None)])
def test_parse_month(raw, expected):
    assert stay_fee.parse_month(raw) == expected


def test_clamp_rate_and_doc_type_and_age():
    assert (stay_fee.clamp_rate("75"), stay_fee.clamp_rate("abc"), stay_fee.clamp_rate("21")) == (50, 0, 21)
    assert stay_fee.default_doc_type("CZE") == "op" and stay_fee.default_doc_type("DEU") == "pas"
    assert validation.age_on(date(2008, 9, 12), date(2026, 9, 10)) == 17
    assert validation.age_on(date(2008, 9, 10), date(2026, 9, 10)) == 18


def _g(**kw):
    base = {"id": 1, "stay_from": None, "stay_to": None, "birth_date": "01011990",
            "fee_host_decision": None, "fee_host_reason": None}
    base.update(kw)
    return base


SEP = stay_fee.period_bounds("monthly", date(2026, 9, 1))
RES = {"date_from": "2026-09-10", "date_to": "2026-09-14"}


@pytest.mark.parametrize("guest,res,period,liable,exempt,status", [
    (_g(), RES, SEP, 4, 0, "liable"),                                             # E1
    (_g(birth_date="12092008"), RES, SEP, 3, 1, "liable"),                         # E2 birthday split
    (_g(birth_date="10092008"), RES, SEP, 4, 0, "liable"),                        # 18 on arrival
    (_g(birth_date="00002015"), RES, SEP, 0, 4, "exempt"),                        # 01.01.2015
    (_g(birth_date="00000000"), RES, SEP, 4, 0, "liable"),                        # unknown = adult
    (_g(fee_host_decision="exempt", fee_host_reason="ZTP/P"), RES, SEP, 0, 4, "exempt"),  # E5
    (_g(birth_date="12092008", fee_host_decision="charge"), RES, SEP, 3, 1, "liable"),     # E6 no minor days
    (_g(fee_host_decision="bogus"), RES, SEP, 4, 0, "liable"),
    # 59 nights in scope; 60 nights still calculated (finalize needs scope ruling).
    (_g(), {"date_from": "2026-08-01", "date_to": "2026-09-29"}, SEP, 29, 0, "liable"),
    (_g(), {"date_from": "2026-08-01", "date_to": "2026-09-30"}, SEP, 30, 0, "liable"),
    (_g(), {"date_from": "2026-08-01", "date_to": "2026-10-01"}, SEP, 0, 0, "not_subject"),
])
def test_guest_rules(guest, res, period, liable, exempt, status):
    share = stay_fee.guest_period(guest, res, *period)
    assert (share["liable_nights"], share["exempt_nights"], share["status"]) == (liable, exempt, status)


def test_guest_outside_period_is_none():
    assert stay_fee.guest_period(_g(), RES, *stay_fee.period_bounds("monthly", AUG)) is None


# --- DB ----------------------------------------------------------------------

def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    db.execute("DELETE FROM guest WHERE reservation_id IN (SELECT r.id FROM reservation r "
               "JOIN apartment a ON a.id = r.apartment_id WHERE a.owner_user_id = ?)", (oid,))
    db.execute("DELETE FROM reservation WHERE apartment_id IN "
               "(SELECT id FROM apartment WHERE owner_user_id = ?)", (oid,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture
def owner():
    db.init_db()
    _cleanup()
    oid = db.insert("user_account", {"username": OWNER, "password_hash": "x",
                                     "display_name": "Calc", "created_at": db.utcnow()})
    try:
        yield oid
    finally:
        _cleanup()


def _entity(oid, **kw):
    values = {"name": "Josef Novák (demo)", "seat": "Ukázková 1, Praha 3", "ico": "27074358",
              "owner_user_id": oid, "created_at": db.utcnow()}
    values.update(kw)
    return db.insert("legal_entity", values)


_n = [0]


def _apartment(oid, entity_id, name, rate=50, vs="1234567890", cadence="monthly", **kw):
    _n[0] += 1
    values = {"internal_name": name, "owner_user_id": oid, "legal_entity_id": entity_id,
              "stay_fee_rate_czk": rate, "stay_fee_vs": vs, "stay_fee_cadence": cadence,
              "stay_fee_authority_name": "Městská část Praha 3",
              "stay_fee_council_account": "19-2000781379/0800",
              "stay_fee_council_iban": "CZ3008000000192000781379",
              "permalink_token": f"tok-{_n[0]}", "created_at": db.utcnow()}
    values.update(kw)
    return db.insert("apartment", values)


def _stay(apt, date_from, date_to, guests, status="active"):
    _n[0] += 1
    now = db.utcnow()
    rid = db.insert("reservation", {"apartment_id": apt, "uid": f"u{_n[0]}", "date_from": date_from,
                                    "date_to": date_to, "status": status,
                                    "created_at": now, "updated_at": now})
    for i, extra in enumerate(guests):
        values = {"reservation_id": rid, "first_name": f"G{i}", "surname": "Test",
                  "birth_date": "01011990", "nationality": "DEU", "signature_png": SIG,
                  "created_at": now, "updated_at": now}
        values.update(extra)
        db.insert("guest", values)
    return rid


def _apt(aid):
    return db.query_one("SELECT * FROM apartment WHERE id = ?", (aid,))


def test_property_period_counts(owner):
    ent = _entity(owner)
    aid = _apartment(owner, ent, "Apartmán Vinohrady")
    _stay(aid, "2026-08-10", "2026-08-14", [{}, {}, {"birth_date": "01012015"}])
    _stay(aid, "2026-08-30", "2026-09-03", [{}])
    _stay(aid, "2026-08-20", "2026-08-22", [{"signature_png": None}])        # unsigned
    _stay(aid, "2026-08-20", "2026-08-25", [{}], status="cancelled")
    _stay(aid, "2026-08-20", "2026-08-25", [{"archived_at": db.utcnow()}])  # archived guest
    period = stay_fee.property_period(_apt(aid), AUG)
    assert (period["liable_nights"], period["exempt_nights"], period["total_czk"]) == (9, 4, 450)
    assert stay_fee.property_period(_apt(aid), date(2026, 9, 1))["liable_nights"] == 3


def test_quarterly_period(owner):
    ent = _entity(owner)
    aid = _apartment(owner, ent, "Chata u lesa", rate=21, cadence="quarterly", vs="555")
    _stay(aid, "2026-07-10", "2026-07-12", [{}])
    _stay(aid, "2026-09-28", "2026-10-02", [{}])
    period = stay_fee.property_period(_apt(aid), AUG)
    assert period["label"] == "3. čtvrtletí 2026"
    assert (period["liable_nights"], period["total_czk"]) == (4, 84)


def test_each_facility_has_its_own_report_even_with_shared_vs(owner):
    ent = _entity(owner)
    a = _apartment(owner, ent, "A")
    b = _apartment(owner, ent, "B")
    c = _apartment(owner, ent, "C", vs="999")
    for aid in (a, b, c):
        _stay(aid, "2026-08-10", "2026-08-12", [{}])
    group = stay_fee.report_group(_apt(a), AUG)
    assert [p["apartment"]["internal_name"] for p in group["periods"]] == ["A"]
    assert group["total_czk"] == 100
    assert stay_fee.report_group(_apt(b), AUG)["total_czk"] == 100
    assert stay_fee.report_group(_apt(c), AUG)["total_czk"] == 100
    assert stay_fee.report_issues(group, date(2026, 9, 1)) == []


def test_issues_block_the_report(owner):
    ent = _entity(owner, name="")
    aid = _apartment(owner, ent, "X", vs="", stay_fee_authority_name="")
    issues = stay_fee.report_issues(stay_fee.report_group(_apt(aid), AUG), date(2026, 8, 20))
    assert set(issues) == {"stay_fees.issue.period_running", "stay_fees.issue.no_vs",
                           "stay_fees.issue.no_authority", "stay_fees.issue.no_payer"}


def test_payment_qr(owner):
    ent = _entity(owner)
    aid = _apartment(owner, ent, "Q")
    _stay(aid, "2026-08-10", "2026-08-12", [{}])
    pay = stay_fee.payment_details(stay_fee.report_group(_apt(aid), AUG))
    assert pay["spayd"] == ("SPD*1.0*ACC:CZ3008000000192000781379*AM:100.00*CC:CZK"
                            "*X-VS:1234567890*MSG:POPLATEK Z POBYTU 1234567890")
    assert pay["qr"].startswith("data:image/png;base64,")
    aid2 = _apartment(owner, ent, "NoAcc", vs="7", stay_fee_council_iban=None)
    assert stay_fee.payment_details(stay_fee.report_group(_apt(aid2), AUG)) is None


def test_register_csv(owner):
    ent = _entity(owner)
    aid = _apartment(owner, ent, "R")
    _stay(aid, "2026-08-10", "2026-08-14", [{"nationality": "CZE"}, {"birth_date": "01012015"},
                                            {"restricted_at": db.utcnow()}])
    rows = stay_fee.register_rows(stay_fee.property_period(_apt(aid), AUG))
    assert rows[0]["doc_type"] == "Občanský průkaz" and rows[1]["doc_type"] == "Cestovní pas"
    assert rows[1]["exempt_reason"] == "mladší 18 let"
    assert rows[2]["surname"] == "Test" and stay_fee.RESTRICTED_NOTE in rows[2]["exempt_reason"]
    data = stay_fee.register_csv(rows)
    assert data.startswith("﻿".encode()) and b";" in data
    assert data.decode("utf-8-sig").splitlines()[0].split(";") == [l for _, l in stay_fee.REGISTER_COLUMNS]


def test_hlaseni_pdf(owner):
    ent = _entity(owner, signature_name="Josef Novák")
    aid = _apartment(owner, ent, "Apartmán Vinohrady", stay_fee_payee="MČ Praha 3",
                     addr_street="Dlouhá", addr_house_no="12", addr_zip="13000", addr_obec="Praha 3")
    _stay(aid, "2026-08-01", "2026-08-11", [{}] * 8 + [{"birth_date": "01012015"}] * 3)
    group = stay_fee.report_group(_apt(aid), AUG)
    data = stay_fee.hlaseni(group, date(2026, 9, 12))
    text = PdfReader(io.BytesIO(stay_fee_remittance_pdf.render(data))).pages[0].extract_text()
    for expected in ("Městská část Praha 3", "za srpen 2026", "Josef Novák (demo)", "VS 1234567890",
                     "IČO 27074358", "Apartmán Vinohrady", "Dlouhá 12, 13000 Praha 3",
                     "80 lůžkodnů podléhá poplatku", "30 lůžkodnů osvobozeno", "4 000 Kč",
                     "MČ PRAHA 3", "Mladší 18 let", "3 os.", "Datum: 12. 9. 2026", "UbyHost", "Strana 1"):
        assert expected in text, expected
    assert "srpna" not in text


def test_quarterly_pdf_title(owner):
    ent = _entity(owner)
    aid = _apartment(owner, ent, "Chata u lesa", rate=21, cadence="quarterly", vs="555")
    _stay(aid, "2026-07-10", "2026-07-12", [{}])
    data = stay_fee.hlaseni(stay_fee.report_group(_apt(aid), AUG), date(2026, 10, 3))
    text = PdfReader(io.BytesIO(stay_fee_remittance_pdf.render(data))).pages[0].extract_text()
    assert "ČTVRTLETNÍ HLÁŠENÍ" in text and "za 3. čtvrtletí 2026" in text and "42 Kč" in text


def test_pdf_lists_one_property_per_report(owner):
    ent = _entity(owner)
    c = _apartment(owner, ent, "C")
    _stay(c, "2026-08-10", "2026-08-12", [{}])
    data = stay_fee.hlaseni(stay_fee.report_group(_apt(c), AUG), date(2026, 9, 1))
    assert [r["property_name"] for r in data["rows"]] == ["C"]
    assert data["total_czk"] == 100


def test_zero_period_renders(owner):
    ent = _entity(owner)
    aid = _apartment(owner, ent, "Zero")
    data = stay_fee.hlaseni(stay_fee.report_group(_apt(aid), AUG), date(2026, 9, 1))
    assert data["total_czk"] == 0
    text = PdfReader(io.BytesIO(stay_fee_remittance_pdf.render(data))).pages[0].extract_text()
    assert "nevznikla povinnost" in text and "0 Kč" in text


def _report(**kw):
    base = {"payer_name": "Demo s.r.o.", "recipient_name": "Úřad", "vs": "1",
            "period_start": "2026-08-01", "period_end": "2026-08-31", "issued_on": "2026-09-01",
            "rows": [{"property_name": "X", "liable_nights": 2, "rate_czk": 50, "amount_czk": 100}],
            "liable_nights": 2, "exempt_nights": 0, "total_czk": 100, "not_charged": []}
    base.update(kw)
    return base


@pytest.mark.parametrize("bad", [
    {"recipient_name": ""}, {"vs": ""}, {"total_czk": 90}, {"period_end": "2026-08-30"},
    {"cadence": "quarterly"},                                   # Aug..Aug is not a quarter
    {"rows": [{"property_name": "X", "liable_nights": 2, "rate_czk": 50, "amount_czk": 90}]},
    {"exempt_nights": 3, "not_charged": [{"reason": "x", "count": 1, "nights": 2}]},
])
def test_pdf_refuses_bad_reports(bad):
    with pytest.raises(ValueError):
        stay_fee_remittance_pdf.render(_report(**bad))


def test_pdf_plurals_and_many_rows_paginate():
    one = _report(rows=[{"property_name": "X", "liable_nights": 1, "rate_czk": 50, "amount_czk": 50}],
                  liable_nights=1, total_czk=50,
                  not_charged=[{"reason": "Mladší 18 let", "count": 1, "nights": 3}], exempt_nights=3)
    text = PdfReader(io.BytesIO(stay_fee_remittance_pdf.render(one))).pages[0].extract_text()
    assert "1 lůžkoden podléhá" in text and "3 lůžkodny osvobozeno" in text
    many = _report(rows=[{"property_name": f"P{i}", "liable_nights": 2, "rate_czk": 50,
                          "amount_czk": 100} for i in range(18)], liable_nights=36, total_czk=1800)
    reader = PdfReader(io.BytesIO(stay_fee_remittance_pdf.render(many)))
    assert len(reader.pages) > 1
    for number, page in enumerate(reader.pages, start=1):
        assert f"Strana {number}" in page.extract_text()


def test_legacy_reset_runs_once(owner):
    ent = _entity(owner)
    aid = _apartment(owner, ent, "Legacy")
    db.execute("DELETE FROM settings WHERE key = 'stay_fee_remittance_reset_done'")
    db.init_db()
    assert _apt(aid)["stay_fee_rate_czk"] == 0
    db.update("apartment", aid, {"stay_fee_rate_czk": 30})
    db.init_db()
    assert _apt(aid)["stay_fee_rate_czk"] == 30
