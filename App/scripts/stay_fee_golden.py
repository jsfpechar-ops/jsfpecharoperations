"""Write go/internal/stayfee/testdata/stay_fee_golden.json from the real Python.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/stay_fee_golden.py

It seeds a throwaway SQLite database with the fixed rows in seed(), runs the stay-fee
calculation that stay_fee_auto.check and stay_fee_filing.save use (everything but
the PDF) for every case in CASES, and records the inputs and the outputs.
go/internal/stayfee/golden_test.go feeds the same seed to the Go package and compares.
Encrypted guest fields are seeded as plain text here (the Python helpers encrypt them),
so the file holds no Fernet token and is byte-stable. Invented data only.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "stayfee" / "testdata" / "stay_fee_golden.json"

STAMP = "2026-09-01T00:00:00+00:00"
SIG = "data:image/png;base64,AAAA"


def entity(eid, name, **kw):
    row = {"id": eid, "name": name, "seat": "", "ico": "", "contact_email": "", "iban": "",
           "bank_account": "", "signature_png": "", "signature_name": ""}
    row.update(kw)
    return row


def apartment(aid, name, rate, **kw):
    row = {"id": aid, "internal_name": name, "stay_fee_rate_czk": rate,
           "legal_entity_id": None, "stay_fee_cadence": "monthly", "stay_fee_vs": "",
           "stay_fee_authority_name": "", "stay_fee_authority_address": "",
           "stay_fee_authority_contact": "", "stay_fee_payee": "", "stay_fee_instruction": "",
           "stay_fee_council_account": "", "stay_fee_council_iban": "",
           "stay_fee_scope_rule": "", "stay_fee_scope_reference": "",
           "stay_fee_collect": 0, "stay_fee_guest_rails": "", "stay_fee_guest_default_rail": "",
           "stay_fee_guest_revolut_link": "", "stay_fee_guest_cash_note": "",
           "addr_obec": "", "city_en": "", "addr_street": "", "addr_house_no": "",
           "addr_orient_no": "", "addr_zip": "", "archived_at": None}
    row.update(kw)
    return row


def reservation(rid, aid, start, end, status="active", source="ical"):
    return {"id": rid, "apartment_id": aid, "date_from": start, "date_to": end,
            "status": status, "source": source}


def guest(gid, rid, surname, first, birth, nat, **kw):
    row = {"id": gid, "reservation_id": rid, "surname": surname, "first_name": first,
           "birth_date": birth, "nationality": nat, "doc_type": None, "doc_number": "X1234567",
           "res_street": "Hlavní 1", "res_city": "Berlin", "res_country": "DEU",
           "stay_from": None, "stay_to": None, "fee_host_decision": None,
           "fee_host_reason": "", "signature_png": SIG, "restricted_at": None,
           "archived_at": None}
    row.update(kw)
    return row


def adjustment(aid, apt, key, direction, mode, bed_days, reason, reversed_at=None):
    return {"id": aid, "apartment_id": apt, "period_key": key, "direction": direction,
            "mode": mode, "bed_days": bed_days, "reason": reason, "reversed_at": reversed_at}


def filing(fid, apt, key, version, cadence, rate, liable, exempt, due, **kw):
    row = {"id": fid, "apartment_id": apt, "period_key": key, "version": version,
           "cadence": cadence, "rate_czk": rate, "liable_days": liable, "exempt_days": exempt,
           "total_due_czk": due, "total_collected_czk": due, "payload": None,
           "created_at": STAMP, "superseded_at": None, "sent_at": None,
           "sent_message_id": None, "paid_at": None}
    row.update(kw)
    return row


def seed():
    iban = "CZ6508000000192000145399"
    entities = [
        entity(1, "Host Alpha s.r.o.", seat="Praha 1, Nová 1", ico="12345678",
               contact_email="alpha@example.test", iban=iban, signature_png=SIG,
               signature_name="Jan Alpha"),
        entity(2, "Beta Host", bank_account="19-2000145399/0800", seat="Brno"),
        entity(3, "Gamma Host", bank_account="124/0100"),
        entity(4, "   "),
    ]
    apts = [
        apartment(1, "Alpha Flat", 21, legal_entity_id=1, stay_fee_vs="VS 1234-5",
                  stay_fee_authority_name="Město Praha", stay_fee_authority_address="Mariánské nám. 2",
                  stay_fee_authority_contact="poplatky@example.test", stay_fee_payee=" Praha 1 pokladna ",
                  stay_fee_instruction="Platba do 15. dne", stay_fee_council_account="123456789/0800",
                  stay_fee_council_iban=iban, addr_obec="Praha 1", addr_street="Nová",
                  addr_house_no="1", addr_orient_no="2", addr_zip="11000", stay_fee_collect=1,
                  stay_fee_guest_rails="qr,cash", stay_fee_guest_default_rail="revolut"),
        apartment(2, "Beta Q", 25, legal_entity_id=2, stay_fee_cadence="quarterly",
                  stay_fee_vs="777", stay_fee_authority_name="Město Brno",
                  stay_fee_council_iban=iban, stay_fee_council_account="1/0100", addr_obec="Brno-střed",
                  stay_fee_scope_rule="calendar_days", stay_fee_scope_reference="Rozhodnutí 12/2026",
                  stay_fee_collect=1, stay_fee_guest_rails="iban,revolut",
                  stay_fee_guest_revolut_link="https://revolut.me/example", addr_zip="60200"),
        apartment(3, "Gamma NoVS", 15, legal_entity_id=3, stay_fee_collect=1, stay_fee_guest_rails="iban",
                  city_en="Praha"),
        apartment(4, "Delta NoEntity", 10, stay_fee_vs="99", stay_fee_authority_name="Obec"),
        apartment(5, "Epsilon Off", 0, legal_entity_id=1, stay_fee_collect=1, stay_fee_guest_rails="cash"),
        apartment(6, "Zeta Archived", 10, legal_entity_id=4, stay_fee_collect=1,
                  stay_fee_guest_rails="cash", archived_at=STAMP),
        apartment(7, "Eta Drift", 30, legal_entity_id=1, stay_fee_vs="7", stay_fee_authority_name="Obec 7",
                  stay_fee_council_iban=iban, addr_obec="Plzeň"),
        apartment(8, "Theta Overlap", 12, legal_entity_id=1, stay_fee_vs="8",
                  stay_fee_authority_name="Obec 8", stay_fee_council_iban=iban,
                  stay_fee_collect=1, stay_fee_guest_rails="cash", stay_fee_guest_cash_note="Cash at door"),
    ]
    rates = [
        {"apartment_id": 2, "effective_from": "2000-01-01", "rate_czk": 20},
        {"apartment_id": 2, "effective_from": "2026-08-16", "rate_czk": 25},
        {"apartment_id": 7, "effective_from": "2000-01-01", "rate_czk": 20},
    ]
    res = [
        reservation(1, 1, "2026-07-28", "2026-08-03"),
        reservation(2, 1, "2026-08-29", "2026-09-02"),
        reservation(3, 1, "2026-08-10", "2026-08-14"),
        reservation(4, 1, "2026-08-15", "2026-08-20"),
        reservation(5, 1, "2026-08-17", "2026-08-24"),
        reservation(6, 1, "2026-08-05", "2026-08-08", status="cancelled"),
        reservation(7, 1, "2026-08-05", "2026-08-08", source="demo"),
        reservation(8, 1, "2026-05-01", "2026-08-10"),
        reservation(9, 1, "2026-06-20", "2026-08-19"),
        reservation(10, 1, "2026-08-05", "2026-08-08"),
        reservation(11, 1, "2026-09-10", "2026-09-12"),
        reservation(12, 1, "2026-07-01", "2026-07-05"),
        reservation(20, 2, "2026-07-10", "2026-07-15"),
        reservation(21, 2, "2026-08-14", "2026-08-19"),
        reservation(22, 2, "2026-07-01", "2026-08-30"),
        reservation(23, 2, "2026-09-25", "2026-10-03"),
        reservation(30, 3, "2026-08-01", "2026-08-04"),
        reservation(40, 4, "2026-08-01", "2026-08-04"),
        reservation(50, 5, "2026-08-01", "2026-08-04"),
        reservation(70, 7, "2026-08-01", "2026-08-04"),
        reservation(80, 8, "2026-08-01", "2026-08-06"),
    ]
    guests = [
        guest(1, 1, "Novak", "Jan", "15051985", "SVK", res_city="Bratislava", res_country="SVK"),
        guest(2, 1, "Kid", "Eva", "01012015", "SVK", res_city="Bratislava", res_country="SVK",
              signature_png=None),
        guest(3, 2, "Praha5", "Petr", "01011990", "CZE", res_city="Praha 5", res_country="CZE",
              signature_png=None, doc_type="op"),
        guest(4, 2, "Brno", "Jana", "05051980", "CZE", res_city="Brno", res_country="CZE",
              signature_png=None),
        guest(5, 3, "Child", "Max", "01012015", "DEU", signature_png=None),
        guest(6, 3, "Exempt", "Rolf", "03031970", "DEU", fee_host_decision="exempt",
              fee_host_reason="Invalidní průkaz ZTP", signature_png="imported", doc_type="xx"),
        guest(7, 3, "Charge", "Kai", "02022012", "DEU", fee_host_decision="charge",
              signature_png="data:image/jpeg;base64,BBB"),
        guest(8, 3, 'Quote; "Jr"', "Hans", "00001990", "DEU", restricted_at=STAMP,
              fee_host_decision="exempt", fee_host_reason="Důvod; s čárkou"),
        guest(9, 4, "=SUM(A1)", "Zoë", "00000000", "UKR", doc_number="INPASS",
              doc_type="zadatel_docasna_ochrana", res_country="UKR", res_city="Kyjev"),
        guest(10, 5, "Eighteen", "Tom", "20082008", "GBR", signature_png="imported",
              res_country="gbr", res_city="London", doc_type="pas"),
        guest(11, 8, "Long", "Stay", "10101970", "NLD"),
        guest(12, 3, "Archived", "Old", "10101970", "NLD", archived_at=STAMP),
        guest(13, 9, "Sixty", "Nights", "10101970", "AUT", doc_type="prechodny_pobyt"),
        guest(14, 10, "Override", "Dee", "10101970", "FRA", stay_from="2026-08-06", stay_to="2026-08-07"),
        guest(15, 10, "Bad", "Range", "10101970", "FRA", stay_from="2026-08-09", stay_to="2026-08-09"),
        guest(16, 6, "Cancelled", "Res", "10101970", "FRA"),
        guest(17, 7, "Demo", "Res", "10101970", "FRA"),
        guest(18, 11, "Outside", "Sep", "10101970", "FRA"),
        guest(19, 12, "Outside", "Jul", "10101970", "FRA"),
        guest(20, 20, "Early", "Jul", "10101980", "DEU"),
        guest(21, 21, "Mid", "Aug", "10101980", "DEU"),
        guest(22, 22, "Sixty", "Two", "10101980", "DEU"),
        guest(23, 23, "Edge", "Sep", "10101980", "DEU", signature_png=""),
        guest(30, 30, "Gamma", "Guest", "10101980", "DEU", signature_png=None),
        guest(40, 40, "Delta", "Guest", "10101980", "DEU"),
        guest(50, 50, "Epsilon", "Guest", "10101980", "DEU"),
        guest(70, 70, "Eta", "Guest", "10101980", "DEU"),
        guest(80, 80, "Theta", "Guest", "10101980", "DEU"),
    ]
    adjs = [
        adjustment(1, 1, "2026-08", "add", "people", 3, "Host not recorded"),
        adjustment(2, 1, "2026-08", "remove", "bed_days", 1, "Late cancellation"),
        adjustment(3, 1, "2026-08", "add", "bed_days", 50, "Reversed", reversed_at=STAMP),
        adjustment(4, 1, "2026-07", "add", "bed_days", 9, "Other period"),
        adjustment(5, 2, "2026-Q3", "remove", "bed_days", 12, "Refund"),
    ]
    payload = json.dumps({
        "collected": {"80": 60},
        "lines": [{"guest_id": 80, "stay_from": "2026-08-01", "stay_to": "2026-08-06", "nights": 5,
                   "liable_nights": 5, "exempt_nights": 0, "status": "liable", "auto_minor": False,
                   "auto_obec_resident": False, "decision": None, "reason": "",
                   "threshold_nights": False, "amount_czk": 60, "rate_nights": [[12, 5]],
                   "reservation_id": 80, "name": "Guest Theta", "restricted": False,
                   "res_country": "DEU", "res_city": "Berlin"}],
        "rate_segments": [[12, 5]],
        "adjustments": [],
    }, sort_keys=True)
    filings = [
        filing(1, 1, "2026-07", 1, "monthly", 21, 4, 1, 84),
        filing(2, 8, "2026-Q3", 1, "quarterly", 12, 3, 0, 36, superseded_at=STAMP),
        filing(3, 8, "2026-Q3", 2, "quarterly", 12, 5, 0, 60, payload=payload,
               sent_at="2026-09-05T08:00:00+00:00", sent_message_id="msg-1"),
        filing(4, 7, "2026-04", 1, "monthly", 20, 2, 0, 40),
    ]
    return {"legal_entities": entities, "apartments": apts, "rates": rates,
            "reservations": res, "guests": guests, "adjustments": adjs, "filings": filings}


def case(name, apt, month, today, cadence=None, rate=None, live_only=True):
    return {"name": name, "apartment_id": apt, "month": month, "today": today,
            "cadence": cadence, "rate": rate, "live_only": live_only}


CASES = [
    case("alpha_august", 1, "2026-08-01", "2026-09-17"),
    case("alpha_august_midmonth_arg", 1, "2026-08-15", "2026-09-17"),
    case("alpha_august_flat30", 1, "2026-08-01", "2026-09-17", rate=30),
    case("alpha_q3_overlap", 1, "2026-08-01", "2026-10-20", cadence="quarterly"),
    case("alpha_running", 1, "2026-08-01", "2026-08-20"),
    case("alpha_september", 1, "2026-09-01", "2026-10-05"),
    case("alpha_february_empty", 1, "2026-02-01", "2026-03-10"),
    case("alpha_bogus_cadence", 1, "2026-08-01", "2026-09-17", cadence="bogus"),
    case("beta_q3", 2, "2026-07-01", "2026-10-20"),
    case("beta_q3_midquarter_arg", 2, "2026-08-20", "2026-10-20"),
    case("beta_august_monthly", 2, "2026-08-01", "2026-09-17", cadence="monthly"),
    case("beta_q3_flat40", 2, "2026-07-01", "2026-10-20", rate=40),
    case("beta_q4_edge", 2, "2026-10-01", "2027-01-10"),
    case("gamma_no_vs", 3, "2026-08-01", "2026-09-17"),
    case("delta_no_entity", 4, "2026-08-01", "2026-09-17"),
    case("epsilon_inactive", 5, "2026-08-01", "2026-09-17"),
    case("eta_drift", 7, "2026-08-01", "2026-09-17"),
    case("theta_live_overlap", 8, "2026-08-01", "2026-09-17"),
    case("theta_frozen", 8, "2026-08-01", "2026-09-17", live_only=False),
    case("alpha_frozen_july", 1, "2026-07-01", "2026-09-17", live_only=False),
    case("alpha_not_frozen", 1, "2026-08-01", "2026-09-17", live_only=False),
]

MONTH_ARGS = ["2026-01-15", "2026-11-30", "2027-12-01", "2026-03-01"]
PARSE_MONTH = ["2026-08", "2026-8", "1999-12", "abcd-ef", "", None, "2026-13", " 2026-08 ", "2026-00",
               "2026/08", "²026-08"]
CZK_RAW = ["12", "²", "", " 7 ", "1.5", None, "0", "007", "99999", "１２"]
AMOUNTS = [0, 5, 999, 1000, 1234, 1234567, -5]
OBEC_TEXTS = ["Praha 5", "Prague", "Hlavní město Praha", "praha - řepy", "Praha-východ", "Praha-Východ Hlavice",
              "Brno-venkov", "Městys Albrechtice", "Město Albrechtice", "Plzeň 3", "Plzen", "Pilsen",
              "Ústí nad Labem", "Ústí nad Labem 2", "Usti nad Orlici", "Ostrava – Poruba", "Mahrisch Ostrau",
              "  Brno  ", "Brno,Židenice", "Praha (Smíchov)", "Praha Smíchov", "Praha nad Vltavou",
              "Hl. m. Praha", "HL M PRAHA 1", "Karlsbad", "Zlín", "Zlin 4", "Dečín", "", None, "Kladno-Rozdělov"]
BIRTHS = ["15051985", "00001990", "00000000", "15.05.1985", "15/5/1985", "1.2.1990", "31041990", "abc",
          "", None, "12345", "00131990", "29022001", "00002000", "15|05|1985"]
FILING_KEYS = [["monthly", "2026-08-01"], ["quarterly", "2026-08-17"], ["quarterly", "2026-12-31"],
               ["monthly", "2026-01-01"]]
ANCHORS = ["2026-08", "2026-Q3", "2026-Q1", "2025-Q4", "2026-13", "bad"]
SHIFTS = [["2026-01-01", -1], ["2026-12-01", 1], ["2026-03-01", -15], ["2026-03-01", 14], ["2026-08-17", -3]]
COUNTED = [["2026-07-28", "2026-08-03", "2026-08-01", "2026-08-31"],
           ["2026-08-05", "2026-08-05", "2026-08-01", "2026-08-31"],
           ["2026-07-01", "2026-09-30", "2026-08-01", "2026-08-31"],
           ["2026-08-31", "2026-09-02", "2026-08-01", "2026-08-31"],
           ["2026-08-01", "2026-08-02", "2026-08-01", "2026-08-31"]]
SPAYD = [["CZ6508000000192000145399", 100, "123", "Stay fee 5"], ["CZ6508000000192000145399", 7, "9", "Příliš žlutý"]]


def iso(value):
    return value.isoformat() if isinstance(value, date) else value


def ser(obj):
    if isinstance(obj, dict):
        return {key: ser(val) for key, val in obj.items() if key not in ("apartment", "anchor")}
    if isinstance(obj, (list, tuple)):
        return [ser(item) for item in obj]
    if isinstance(obj, date):
        return obj.isoformat()
    return obj


def load(db, data):
    for row in data["legal_entities"]:
        db.execute(
            "INSERT INTO legal_entity (id, name, seat, ico, contact_email, iban, bank_account, "
            "signature_png_enc, signature_name, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (row["id"], row["name"], row["seat"], row["ico"], row["contact_email"], row["iban"],
             row["bank_account"], db.encrypt_field(row["signature_png"]), row["signature_name"], STAMP))
    for row in data["apartments"]:
        db.insert("apartment", {**row, "created_at": STAMP})
    for row in data["rates"]:
        db.execute("INSERT INTO stay_fee_rate (apartment_id, rate_czk, effective_from, created_at) "
                   "VALUES (?, ?, ?, ?)", (row["apartment_id"], row["rate_czk"], row["effective_from"], STAMP))
    for row in data["reservations"]:
        db.insert("reservation", {**row, "uid": f"uid-{row['id']}", "created_at": STAMP,
                                  "updated_at": STAMP})
    for row in data["guests"]:
        db.insert("guest", {**row, "created_at": STAMP, "updated_at": STAMP})
    for row in data["adjustments"]:
        plain = dict(row)
        reason = plain.pop("reason")
        db.insert("stay_fee_adjustment", {**plain, "reason_enc": db.encrypt_field(reason),
                                          "created_at": STAMP})
    for row in data["filings"]:
        plain = dict(row)
        payload = plain.pop("payload")
        db.insert("stay_fee_filing", {**plain, "payload_enc": db.encrypt_field(payload) if payload else None})


def adjustment_view(rows):
    return [{key: row[key] for key in ("id", "direction", "mode", "bed_days", "delta", "reason")}
            for row in rows]


def period_view(period):
    if period is None:
        return None
    view = ser(period)
    view["adjustments"] = adjustment_view(period.get("adjustments") or [])
    return view


def apartment_view(db, apartment_id):
    return db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))


def run_case(db, cfg, c):
    from app import stay_fee, stay_fee_auto, stay_fee_filing

    apartment = apartment_view(db, c["apartment_id"])
    month = date.fromisoformat(c["month"])
    today = date.fromisoformat(c["today"])
    out = {}
    period = stay_fee.property_period(apartment, month, live_only=c["live_only"],
                                      cadence=c["cadence"], rate=c["rate"])
    out["period"] = period_view(period)
    if not c["live_only"]:
        return out
    checked = stay_fee_auto.check(apartment, month, today, cadence=c["cadence"], rate=c["rate"])
    group = checked["group"]
    out["group"] = ser(group)
    out["group"]["periods"] = [period_view(p) for p in group["periods"]]
    out["issues"] = checked["issues"]
    out["key"] = checked["key"]
    out["unsigned_query"] = stay_fee.unsigned_stays(apartment["id"], group["first"], group["last"])
    out["unsigned_shortcut"] = stay_fee.unsigned_stays(apartment["id"], group["first"], group["last"],
                                                       checked["period"])
    out["payment"] = _payment(stay_fee, group)
    rows = []
    csv_text = ""
    if checked["period"] is not None:
        rows = stay_fee.register_rows(checked["period"])
        csv_text = base64.b64encode(stay_fee.register_csv(rows)).decode()
    out["register_rows"] = rows
    out["register_csv_b64"] = csv_text
    try:
        out["hlaseni"] = ser(stay_fee.hlaseni(group, today))
    except TypeError:
        out["hlaseni"] = None
    return out


def _payment(stay_fee, group):
    from app import payments

    anchor = group["anchor"]
    iban = anchor["stay_fee_council_iban"] or ""
    if not iban:
        return None
    # qr_data_uri needs the qrcode package and is not ported; the rest is payment_details.
    original = payments.qr_data_uri
    payments.qr_data_uri = lambda payload: ""
    try:
        details = stay_fee.payment_details(group)
    finally:
        payments.qr_data_uri = original
    details.pop("qr", None)
    return details


def apartment_checks(db, cfg, data):
    from app import stay_fee

    out = []
    for row in data["apartments"]:
        apartment = apartment_view(db, row["id"])
        entry = {"apartment_id": row["id"], "is_active": stay_fee.is_active(apartment),
                 "cadence_of": stay_fee.cadence_of(apartment), "vs_of": stay_fee.vs_of(apartment),
                 "usable_rail_keys": stay_fee.usable_rail_keys(apartment),
                 "payout_account": list(stay_fee.payout_account(apartment))}
        for flag in (True, False):
            cfg.STAY_FEE_GUEST_PAY = flag
            entry["no_pay_way_on" if flag else "no_pay_way_off"] = stay_fee.no_pay_way(apartment)
        cfg.STAY_FEE_GUEST_PAY = True
        out.append(entry)
    return out


def helpers(db, data):
    from app import stay_fee, stay_fee_filing, stay_fee_adjustment, stay_fee_rate, payments

    out = {}
    out["shift_month"] = [[m, d, iso(stay_fee.shift_month(date.fromisoformat(m), d))] for m, d in SHIFTS]
    out["previous_month"] = [[m, iso(stay_fee.previous_month(date.fromisoformat(m)))] for m in MONTH_ARGS]
    out["period_bounds"] = [[cad, m, [iso(x) for x in stay_fee.period_bounds(cad, date.fromisoformat(m))]]
                            for cad in ("monthly", "quarterly") for m in MONTH_ARGS]
    out["month_key"] = [[m, stay_fee.month_key(date.fromisoformat(m))] for m in MONTH_ARGS]
    out["period_label_cs"] = [[cad, m, stay_fee.period_label_cs(cad, date.fromisoformat(m))]
                              for cad in ("monthly", "quarterly") for m in MONTH_ARGS]
    out["period_complete"] = [[cad, m, t, stay_fee.period_complete(cad, date.fromisoformat(m), date.fromisoformat(t))]
                              for cad in ("monthly", "quarterly") for m in ("2026-08-01",)
                              for t in ("2026-08-31", "2026-09-01", "2026-09-30", "2026-10-01")]
    out["parse_month"] = [[v, iso(stay_fee.parse_month(v))] for v in PARSE_MONTH]
    out["parse_czk_int"] = [[v, stay_fee.parse_czk_int(v)] for v in CZK_RAW]
    out["clamp_rate"] = [[v, stay_fee.clamp_rate(v)] for v in CZK_RAW + ["50", "51", "1000"]]
    out["format_czk"] = [[v, stay_fee.format_czk(v)] for v in AMOUNTS]
    out["counted_days_in"] = [[*row, stay_fee.counted_days_in(*[date.fromisoformat(x) for x in row])]
                              for row in COUNTED]
    out["obec_key"] = [[v, stay_fee._obec_key(v)] for v in OBEC_TEXTS]
    out["fold_text"] = [[v, stay_fee.fold_text(v)] for v in OBEC_TEXTS]
    out["conservative_birth"] = [[v, iso(stay_fee.conservative_birth(v))] for v in BIRTHS]
    out["default_doc_type"] = [[v, stay_fee.default_doc_type(v)] for v in ("CZE", "cze", "DEU", "", None)]
    out["period_key"] = [[cad, m, stay_fee_filing.period_key(cad, date.fromisoformat(m))] for cad, m in FILING_KEYS]
    out["overlap_keys"] = [[cad, m, stay_fee_filing.overlap_keys(cad, date.fromisoformat(m))] for cad, m in FILING_KEYS]
    anchors = []
    for key in ANCHORS:
        try:
            anchors.append([key, iso(stay_fee_filing.period_anchor({"period_key": key}))])
        except ValueError:
            anchors.append([key, "error"])
    out["period_anchor"] = anchors
    out["spayd"] = [[a, b, c, d, payments.spayd(a, b, c, d)] for a, b, c, d in SPAYD]
    out["net_bed_days"] = [[a, k, stay_fee_adjustment.net_bed_days(a, k)]
                           for a, k in ((1, "2026-08"), (1, "2026-07"), (2, "2026-Q3"), (3, "2026-08"))]
    # Filing read side.
    reads = []
    for apt in (1, 2, 7, 8):
        for key in ("2026-07", "2026-08", "2026-Q3", "2026-04"):
            row = stay_fee_filing.latest(apt, key)
            reads.append({"call": "latest", "apartment_id": apt, "key": key,
                          "id": row["id"] if row else None})
        for month in ("2026-04-10", "2026-07-01", "2026-08-20", "2026-09-30"):
            row = stay_fee_filing.covering(apt, date.fromisoformat(month))
            reads.append({"call": "covering", "apartment_id": apt, "key": month,
                          "id": row["id"] if row else None})
        for cad in ("monthly", "quarterly"):
            row = stay_fee_filing.foreign_overlap(apt, cad, date.fromisoformat("2026-08-01"))
            reads.append({"call": "foreign_overlap:" + cad, "apartment_id": apt, "key": "2026-08-01",
                          "id": row["id"] if row else None})
    out["filing_reads"] = reads
    corr = []
    for fid in (1, 2, 3, 4):
        row = db.query_one("SELECT * FROM stay_fee_filing WHERE id = ?", (fid,))
        apartment = apartment_view(db, row["apartment_id"])
        corr.append({"filing_id": fid, "rate": stay_fee_filing.correction_rate(apartment, row)})
    out["correction_rate"] = corr
    out["schedule_uniform"] = []
    for apt in (1, 2, 7):
        apartment = apartment_view(db, apt)
        schedule = stay_fee_rate.schedule_for(apartment)
        for first, last in (("2026-08-01", "2026-08-31"), ("2026-08-16", "2026-08-31"),
                            ("2026-07-01", "2026-09-30"), ("2026-08-15", "2026-08-16")):
            out["schedule_uniform"].append({
                "apartment_id": apt, "first": first, "last": last,
                "uniform": stay_fee_rate.is_uniform(schedule, date.fromisoformat(first), date.fromisoformat(last)),
                "rate_last": stay_fee_rate.rate_on(schedule, date.fromisoformat(last))})
    return out


def render() -> str:
    from app import config, db

    config.STAY_FEE_GUEST_PAY = True
    db.init_db()
    data = seed()
    load(db, data)
    golden = {
        "seed": data,
        "cases": [{**c, "out": run_case(db, config, c)} for c in CASES],
        "apartment_checks": apartment_checks(db, config, data),
        "helpers": helpers(db, data),
    }
    return json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "stay_fee_golden.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    os.environ.setdefault("UBYHOST_STAY_FEE_GUEST_PAY", "on")
    sys.path.insert(0, str(APP))
    main()
