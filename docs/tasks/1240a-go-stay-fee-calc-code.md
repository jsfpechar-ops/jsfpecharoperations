# 1240a: code blocks of brief 1240 (do not read; the brief's step 0 helper copies them)

Payload of [brief 1240](1240-go-stay-fee-calc.md). Each block is one file, byte for byte; the heading gives its path and sha256. Do not edit.

### Block 1: `App/scripts/stay_fee_golden.py` sha256 `6bdd94a48504ac7d886e2152e5a3f18fad7c45e7f76350f9ec40a2116e1a1f9e`

````python
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
````

### Block 2: `go/internal/stayfee/calc.go` sha256 `aae92cff2665d1255ea7e062a026a3a43af5a407642985621d71eead4ad7f8a2`

````go
// Package stayfee is the Go port of the stay-fee calculation in
// App/app/stay_fee.py, stay_fee_rate.py, stay_fee_adjustment.py and the read
// side of stay_fee_filing.py (brief 1240). It reproduces, from database rows,
// everything stay_fee_auto.check and stay_fee_filing.save need except the PDF.
//
// The package is split in two layers. The pure layer (this file, report.go and
// the key functions of filing.go) takes plain structs and does no I/O. The thin
// loader (loader.go and the Load* functions of filing.go) reads rows through a
// Querier (a *pgxpool.Pool or a pgx.Tx) and decrypts guest fields through a
// Decrypter; nothing runs at package init and no constructor touches the
// database. testdata/stay_fee_golden.json, written by App/scripts/stay_fee_golden.py
// from the real Python, pins both layers.
//
// Known differences, all outside the golden cases: Python's str.isdigit() also
// accepts digits outside 0-9 (superscripts, full-width) where this port is
// ASCII-only (ParseMonth, ParseCZKInt, VSOf, birth-date digits); str.upper()
// special cases other than the German sharp s are not ported; the combining
// mark test uses the canonical combining class like unicodedata.combining but
// \s in the municipality folding is ASCII after the whitespace collapse.
// Python's schedule_for defaults "today" to date.today() (the server's local
// date); here the caller passes it (ScheduleToday).
package stayfee

import (
	"fmt"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
	"unicode"

	"golang.org/x/text/unicode/norm"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// Constants of stay_fee.py. Decisions, ExemptCategories, ScopeRules and
// Cadences are read-only: do not modify them.
// nbsp and bom are built from code points so no invisible character sits in the source.
var (
	nbsp = string(rune(0xA0))
	bom  = string(rune(0xFEFF))
)

const (
	MaxRateCZK      = 50 // §3d
	AdultAge        = 18 // §3b(1)(b)
	ReasonMax       = 120
	ThresholdNights = 60
	czechCode       = "CZE"
)

var (
	Cadences         = []string{"monthly", "quarterly"}
	Decisions        = []string{"exempt", "charge"}
	ExemptCategories = []string{"disability", "diplomat", "local_rule", "other_statutory"}
	ScopeRules       = []string{"calendar_days", "nights"}
	MonthsCS         = []string{"Leden", "Únor", "Březen", "Duben", "Květen", "Červen", "Červenec",
		"Srpen", "Září", "Říjen", "Listopad", "Prosinec"}
	// DocTypes is validation.DOC_TYPES.
	DocTypes = []string{"op", "pas", "prechodny_pobyt", "pobytova_karta_eu", "povoleni_pobyt",
		"povoleni_pobyt_cizinec", "trvaly_pobyt", "zadatel_mezinarodni_ochrana", "zadatel_docasna_ochrana"}
	DocTypeLabelsCS = map[string]string{
		"op":                          "Občanský průkaz",
		"pas":                         "Cestovní pas",
		"prechodny_pobyt":             "Potvrzení o přechodném pobytu",
		"pobytova_karta_eu":           "Pobytová karta rodinného příslušníka občana EU",
		"povoleni_pobyt":              "Průkaz o povolení k pobytu",
		"povoleni_pobyt_cizinec":      "Průkaz o povolení k pobytu pro cizince",
		"trvaly_pobyt":                "Průkaz o povolení k trvalému pobytu",
		"zadatel_mezinarodni_ochrana": "Průkaz žadatele o mezinárodní ochranu",
		"zadatel_docasna_ochrana":     "Průkaz žadatele o dočasnou ochranu",
	}
)

func inList(list []string, v string) bool {
	for _, item := range list {
		if item == v {
			return true
		}
	}
	return false
}

// Apartment holds the apartment columns the stay-fee code reads. An empty
// string stands for SQL NULL, as everywhere in the Go ports.
type Apartment struct {
	ID               int64
	LegalEntityID    int64 // 0 = none
	InternalName     string
	StayFeeRateCZK   int
	StayFeeCadence   string
	StayFeeVS        string
	AuthorityName    string
	AuthorityAddress string
	AuthorityContact string
	Payee            string
	Instruction      string
	CouncilAccount   string
	CouncilIBAN      string
	ScopeRule        string
	ScopeReference   string
	Collect          bool
	GuestRails       string
	GuestDefaultRail string
	RevolutLink      string
	CashNote         string
	AddrObec         string
	CityEN           string
	AddrStreet       string
	AddrHouseNo      string
	AddrOrientNo     string
	AddrZip          string
	ArchivedAt       string
}

// Entity is a legal_entity row (the payer). SignaturePNG is already decrypted.
type Entity struct {
	ID            int64
	Name          string
	Seat          string
	ICO           string
	ContactEmail  string
	IBAN          string
	BankAccount   string
	SignaturePNG  string
	SignatureName string
}

// GuestRow is one guest joined to its reservation, every field already
// decrypted (db.decrypt_field with the plaintext column as the fallback).
type GuestRow struct {
	ID              int64
	ReservationID   int64
	Surname         string
	FirstName       string
	BirthDate       string
	Nationality     string
	DocType         string
	DocNumber       string
	ResStreet       string
	ResCity         string
	ResCountry      string
	StayFrom        string
	StayTo          string
	FeeHostDecision string
	FeeHostReason   string
	SignaturePNG    string
	Restricted      bool
	ResFrom         string // reservation.date_from
	ResTo           string // reservation.date_to
}

// RateRow is a stay_fee_rate row.
type RateRow struct {
	EffectiveFrom string
	RateCZK       int
}

// RateStep is one entry of a rate schedule: the rate from a day on.
type RateStep struct {
	From time.Time
	Rate int
}

// Adjustment is an open stay_fee_adjustment row with its signed delta and
// decrypted reason.
type Adjustment struct {
	ID        int64  `json:"id"`
	Direction string `json:"direction"`
	Mode      string `json:"mode"`
	BedDays   int    `json:"bed_days"`
	Delta     int    `json:"delta"`
	Reason    string `json:"reason"`
}

// Line is one guest's share of one period (guest_period plus the extra keys
// property_period adds). The JSON tags are the Python dict keys, so a sealed
// payload decodes straight into it.
type Line struct {
	GuestID          int64    `json:"guest_id"`
	StayFrom         string   `json:"stay_from"`
	StayTo           string   `json:"stay_to"`
	Nights           int      `json:"nights"`
	LiableNights     int      `json:"liable_nights"`
	ExemptNights     int      `json:"exempt_nights"`
	Status           string   `json:"status"`
	AutoMinor        bool     `json:"auto_minor"`
	Decision         *string  `json:"decision"`
	Reason           string   `json:"reason"`
	ThresholdNights  bool     `json:"threshold_nights"`
	AmountCZK        int      `json:"amount_czk"`
	RateNights       [][2]int `json:"rate_nights"`
	AutoObecResident bool     `json:"auto_obec_resident"`
	ReservationID    int64    `json:"reservation_id"`
	Name             string   `json:"name"`
	Restricted       bool     `json:"restricted"`
	ResCountry       string   `json:"res_country"`
	ResCity          string   `json:"res_city"`
}

// Period is property_period's dict: the figures for one property and period.
// A frozen period (Frozen true) is a sealed filing; the fields that only a
// live period has (GuestLiableNights, AdjustmentBedDays, Adjustments,
// UnsignedGuests) are then zero.
type Period struct {
	Apartment         *Apartment
	Cadence           string
	First, Last       time.Time
	Label             string
	RateCZK           int
	Lines             []Line
	GuestLiableNights int
	LiableNights      int
	ExemptNights      int
	TotalCZK          int
	AdjustmentBedDays int
	Adjustments       []Adjustment
	UnsignedGuests    int
	RateSegments      [][2]int
	PeriodKey         string

	Frozen            bool
	FilingID          int64
	Version           int
	TotalCollectedCZK int
	SentAt            string
	PaidAt            string
	SentMessageID     string
}

// PeriodInput is everything BuildPeriod needs from the database for one
// apartment and period. Guests are in the order of the SQL (stay start, id);
// Adjustments are the open rows for PeriodKey(cadence, month).
type PeriodInput struct {
	RateRows      []RateRow
	ScheduleToday time.Time
	Guests        []GuestRow
	Adjustments   []Adjustment
}

// --- dates -------------------------------------------------------------------

// Day is a calendar day as a UTC midnight time.Time, the only form the package uses.
func Day(y int, m time.Month, d int) time.Time {
	return time.Date(y, m, d, 0, 0, 0, 0, time.UTC)
}

// ISO is date.isoformat().
func ISO(t time.Time) string { return t.Format("2006-01-02") }

func dayStart(t time.Time) time.Time { return Day(t.Year(), t.Month(), t.Day()) }

func daysBetween(a, b time.Time) int { return int(dayStart(b).Sub(dayStart(a)) / (24 * time.Hour)) }

func floorDiv(a, b int) int {
	q := a / b
	if (a%b != 0) && ((a < 0) != (b < 0)) {
		q--
	}
	return q
}

// ShiftMonth is stay_fee.shift_month: the first day of the month delta months away.
func ShiftMonth(month time.Time, delta int) time.Time {
	index := month.Year()*12 + int(month.Month()) - 1 + delta
	return Day(floorDiv(index, 12), time.Month(index-floorDiv(index, 12)*12+1), 1)
}

// PreviousMonth is stay_fee.previous_month.
func PreviousMonth(today time.Time) time.Time {
	return ShiftMonth(Day(today.Year(), today.Month(), 1), -1)
}

// MonthKey is stay_fee.month_key: YYYY-MM.
func MonthKey(day time.Time) string { return fmt.Sprintf("%04d-%02d", day.Year(), int(day.Month())) }

// PeriodBounds is stay_fee.period_bounds: first and last day, inclusive, of the
// monthly or quarterly period containing month.
func PeriodBounds(cadence string, month time.Time) (time.Time, time.Time) {
	var first, after time.Time
	if cadence == "quarterly" {
		first = Day(month.Year(), time.Month((int(month.Month())-1)/3*3+1), 1)
		after = ShiftMonth(first, 3)
	} else {
		first = Day(month.Year(), month.Month(), 1)
		after = ShiftMonth(first, 1)
	}
	return first, after.AddDate(0, 0, -1)
}

// PeriodLabelCS is stay_fee.period_label_cs: "Srpen 2026" or "3. čtvrtletí 2026".
func PeriodLabelCS(cadence string, month time.Time) string {
	if cadence == "quarterly" {
		return fmt.Sprintf("%d. čtvrtletí %d", (int(month.Month())-1)/3+1, month.Year())
	}
	return fmt.Sprintf("%s %d", MonthsCS[int(month.Month())-1], month.Year())
}

// PeriodComplete is stay_fee.period_complete.
func PeriodComplete(cadence string, month, today time.Time) bool {
	_, last := PeriodBounds(cadence, month)
	return last.Before(dayStart(today))
}

// ParseMonth is stay_fee.parse_month: "2026-08" is the first of August 2026;
// anything else, and any year before 2000, is not ok.
func ParseMonth(value string) (time.Time, bool) {
	text := []rune(strings.TrimSpace(value))
	if len(text) != 7 || text[4] != '-' {
		return time.Time{}, false
	}
	for i, r := range text {
		if i != 4 && (r < '0' || r > '9') {
			return time.Time{}, false
		}
	}
	year, _ := strconv.Atoi(string(text[:4]))
	month, _ := strconv.Atoi(string(text[5:]))
	if month < 1 || month > 12 || year < 2000 {
		return time.Time{}, false
	}
	return Day(year, time.Month(month), 1), true
}

// CountedDaysIn is stay_fee.counted_days_in: days in (arrival, departure]
// inside first..last inclusive.
func CountedDaysIn(start, end, first, last time.Time) int {
	firstDay := start.AddDate(0, 0, 1)
	if end.Before(firstDay) {
		return 0
	}
	lo := firstDay
	if first.After(lo) {
		lo = first
	}
	hi := end
	if last.Before(hi) {
		hi = last
	}
	if n := daysBetween(lo, hi) + 1; n > 0 {
		return n
	}
	return 0
}

// FormatCZK is stay_fee.format_czk: "1 234 Kč" with no-break spaces, also before Kč.
func FormatCZK(amount int) string {
	digits := strconv.Itoa(amount)
	sign := ""
	if amount < 0 {
		sign, digits = "-", digits[1:]
	}
	var b strings.Builder
	for i, r := range digits {
		if i > 0 && (len(digits)-i)%3 == 0 {
			b.WriteString(nbsp)
		}
		b.WriteRune(r)
	}
	return sign + b.String() + nbsp + "Kč"
}

// ParseCZKInt is stay_fee.parse_czk_int: a non-negative integer from ASCII
// digits only. A number too large for int64 is returned as MaxInt64.
func ParseCZKInt(raw string) (int, bool) {
	text := strings.TrimSpace(raw)
	if text == "" {
		return 0, false
	}
	for _, r := range text {
		if r < '0' || r > '9' {
			return 0, false
		}
	}
	n, err := strconv.ParseInt(text, 10, 64)
	if err != nil {
		return int(^uint(0) >> 1), true
	}
	return int(n), true
}

// ClampRate is stay_fee.clamp_rate: 0 for unparseable input, at most MaxRateCZK.
func ClampRate(raw string) int {
	n, ok := ParseCZKInt(raw)
	if !ok {
		return 0
	}
	return max(0, min(n, MaxRateCZK))
}

// IsActive is stay_fee.is_active: the property has a stay-fee rate.
func IsActive(ap *Apartment) bool { return ap != nil && ap.StayFeeRateCZK > 0 }

// CadenceOf is stay_fee.cadence_of.
func CadenceOf(ap *Apartment) string {
	if inList(Cadences, ap.StayFeeCadence) {
		return ap.StayFeeCadence
	}
	return "monthly"
}

// VSOf is stay_fee.vs_of: the digits of the variable symbol.
func VSOf(ap *Apartment) string {
	var b strings.Builder
	for _, r := range ap.StayFeeVS {
		if unicode.IsDigit(r) {
			b.WriteRune(r)
		}
	}
	return b.String()
}

// DefaultDocType is stay_fee.default_doc_type.
func DefaultDocType(nationality string) string {
	if strings.ToUpper(nationality) == czechCode {
		return "op"
	}
	return "pas"
}

// DocTypeOf is stay_fee.doc_type_of.
func DocTypeOf(g GuestRow) string {
	if inList(DocTypes, g.DocType) {
		return g.DocType
	}
	return DefaultDocType(g.Nationality)
}

// --- birth dates -------------------------------------------------------------

// AgeOn is validation.age_on: whole years between birth and when.
func AgeOn(birth, when time.Time) int {
	years := when.Year() - birth.Year()
	if when.Month() < birth.Month() || (when.Month() == birth.Month() && when.Day() < birth.Day()) {
		years--
	}
	return years
}

func stripForbidden(v string) string {
	var b strings.Builder
	for _, r := range v {
		switch {
		case r == '\r' || r == '\n' || r == '|':
			b.WriteByte(' ')
		case r <= 0x08 || r == 0x0b || r == 0x0c || (r >= 0x0e && r <= 0x1f) || r == 0x7f:
			b.WriteByte(' ')
		default:
			b.WriteRune(r)
		}
	}
	return b.String()
}

func asciiDecimals(v string, keep string) string {
	var b strings.Builder
	for _, r := range v {
		if strings.ContainsRune(keep, r) || (r >= '0' && r <= '9') {
			b.WriteRune(r)
		}
	}
	return b.String()
}

func expandTwoDigitYear(two string) string {
	n, _ := strconv.Atoi(two)
	current := time.Now().Year()
	lo, hi := 1900+n, 2000+n
	switch {
	case hi <= current:
		return strconv.Itoa(hi)
	case lo <= current:
		return strconv.Itoa(lo)
	}
	return strconv.Itoa(lo)
}

func padInt(s string, width int) string {
	n, err := strconv.Atoi(s)
	if err != nil {
		return s
	}
	return fmt.Sprintf("%0*d", width, n)
}

// NormaliseBirthDate is validation.normalise_birth_date: DDMMYYYY.
func NormaliseBirthDate(value string) string {
	raw := strings.TrimSpace(stripForbidden(value))
	if raw == "" {
		return ""
	}
	separated := strings.ReplaceAll(strings.ReplaceAll(raw, "/", "."), "-", ".")
	dd := asciiDecimals(separated, ".")
	if strings.Contains(dd, ".") {
		var parts []string
		for _, p := range strings.Split(dd, ".") {
			if p != "" {
				parts = append(parts, p)
			}
		}
		if len(parts) == 3 {
			year := parts[2]
			if len(year) == 2 {
				year = expandTwoDigitYear(year)
			}
			return padInt(parts[0], 2) + padInt(parts[1], 2) + strings.Repeat("0", max(0, 4-len(year))) + year
		}
	}
	digits := asciiDecimals(raw, "")
	switch len(digits) {
	case 8:
		return digits
	case 6:
		return digits[:4] + expandTwoDigitYear(digits[4:])
	}
	return digits
}

// ConservativeBirth is stay_fee.conservative_birth: the earliest possible
// birthday, so an unknown day or month never makes an adult look like a minor.
func ConservativeBirth(raw string) (time.Time, bool) {
	digits := NormaliseBirthDate(raw)
	if len(digits) != 8 {
		return time.Time{}, false
	}
	day, _ := strconv.Atoi(digits[:2])
	month, _ := strconv.Atoi(digits[2:4])
	year, _ := strconv.Atoi(digits[4:])
	if year == 0 {
		return time.Time{}, false
	}
	if month == 0 {
		month = 1
	}
	if day == 0 {
		day = 1
	}
	t := Day(year, time.Month(month), day)
	if t.Year() != year || int(t.Month()) != month || t.Day() != day {
		return time.Time{}, false
	}
	return t, true
}

func certainlyUnderAge(raw string, when *time.Time, years int) bool {
	if when == nil {
		return false
	}
	birth, ok := ConservativeBirth(raw)
	return ok && AgeOn(birth, *when) < years
}

// guestSignatureSettled is reporting.guest_signature_settled: signed, or under
// 15 on arrival and so not asked to sign (brief 1089).
func guestSignatureSettled(g GuestRow) bool {
	sig := strings.TrimSpace(g.SignaturePNG)
	if sig == "imported" || strings.HasPrefix(sig, "data:image/") {
		return true
	}
	var start *time.Time
	if t, ok := validation.ParseISODate(g.StayFrom); ok {
		start = &t
	} else if t, ok := validation.ParseISODate(g.ResFrom); ok {
		start = &t
	}
	return certainlyUnderAge(g.BirthDate, start, 15)
}

// --- same-obec residence (0898) ---------------------------------------------

var (
	statutoryDistrictBases = []string{"PRAHA", "BRNO", "CESKE BUDEJOVICE", "DECIN", "FRYDEK-MISTEK", "HAVIROV",
		"HRADEC KRALOVE", "CHOMUTOV", "JABLONEC NAD NISOU", "JIHLAVA", "KARLOVY VARY",
		"KARVINA", "KLADNO", "LIBEREC", "MLADA BOLESLAV", "MOST", "OLOMOUC", "OPAVA",
		"OSTRAVA", "PARDUBICE", "PLZEN", "PROSTEJOV", "PREROV", "TEPLICE", "TRINEC",
		"USTI NAD LABEM", "ZLIN"}
	obecAliases = map[string]string{
		"PRAGUE": "PRAHA", "PRAG": "PRAHA",
		"BRUNN": "BRNO", "PILSEN": "PLZEN", "BUDWEIS": "CESKE BUDEJOVICE",
		"OSTRAU": "OSTRAVA", "MAHRISCH OSTRAU": "OSTRAVA", "MAHRISCH-OSTRAU": "OSTRAVA",
		"MORAVIAN OSTRAVA": "OSTRAVA", "MORAVSKA OSTRAVA": "OSTRAVA",
		"KARLSBAD": "KARLOVY VARY", "CARLSBAD": "KARLOVY VARY",
		"MARIENBAD": "MARIANSKE LAZNE", "FRANZENSBAD": "FRANTISKOVY LAZNE",
		"OLMUTZ": "OLOMOUC", "REICHENBERG": "LIBEREC", "AUSSIG": "USTI NAD LABEM",
		"KONIGGRATZ": "HRADEC KRALOVE", "PARDUBITZ": "PARDUBICE", "IGLAU": "JIHLAVA",
		"TROPPAU": "OPAVA", "TEPLITZ": "TEPLICE", "KOMOTAU": "CHOMUTOV", "TETSCHEN": "DECIN",
		"JUNGBUNZLAU": "MLADA BOLESLAV", "GABLONZ": "JABLONEC NAD NISOU",
		"PROSSNITZ": "PROSTEJOV", "PRERAU": "PREROV", "BRUX": "MOST",
		"KRUMAU": "CESKY KRUMLOV", "KUTTENBERG": "KUTNA HORA", "ZNAIM": "ZNOJMO",
	}
	officialPrefixes = []string{"HLAVNI MESTO ", "HL. M. ", "HL.M. ", "HL M ", "STATUTARNI MESTO "}
	okresNotObec     = []string{"PRAHA-VYCHOD", "PRAHA-ZAPAD", "BRNO-VENKOV", "PLZEN-JIH", "PLZEN-SEVER"}
	obecSuffixBases  = buildSuffixBases()
	dashRE           = regexp.MustCompile(`\s*[-\x{2010}-\x{2015}\x{2212}]\s*`)
)

func buildSuffixBases() []string {
	set := map[string]bool{}
	for _, b := range statutoryDistrictBases {
		set[b] = true
	}
	for name, target := range obecAliases {
		if inList(statutoryDistrictBases, target) {
			set[name] = true
		}
	}
	out := make([]string, 0, len(set))
	for b := range set {
		out = append(out, b)
	}
	sort.Slice(out, func(i, j int) bool {
		if len(out[i]) != len(out[j]) {
			return len(out[i]) > len(out[j])
		}
		return out[i] < out[j]
	})
	return out
}

// pyUpper is Python str.upper() for the cases that matter here (sharp s).
func pyUpper(s string) string {
	var b strings.Builder
	for _, r := range s {
		if r == 'ß' {
			b.WriteString("SS")
			continue
		}
		b.WriteRune(unicode.ToUpper(r))
	}
	return b.String()
}

// FoldText is stay_fee.fold_text: diacritics, case and spacing folded.
func FoldText(value string) string {
	var b strings.Builder
	for _, r := range norm.NFKD.String(value) {
		if norm.NFC.PropertiesString(string(r)).CCC() != 0 {
			continue
		}
		b.WriteRune(r)
	}
	return strings.Join(strings.Fields(pyUpper(b.String())), " ")
}

// afterBase is _AFTER_BASE.match(text, len(base)): what may follow a city name
// in a city-part form (signature.js uses the same rule).
func afterBase(rest string) bool {
	if rest == "" || strings.HasPrefix(rest, "-") {
		return true
	}
	trimmed := strings.TrimLeft(rest, " \t\n\r\f\v")
	if trimmed != "" {
		first := []rune(trimmed)[0]
		if unicode.IsDigit(first) || first == ',' || first == '(' {
			return true
		}
	}
	if strings.HasPrefix(rest, " ") {
		s2 := rest[1:]
		for _, w := range []string{"NAD", "POD", "U", "NA", "PRI"} {
			if strings.HasPrefix(s2, w) && (len(s2) == len(w) || s2[len(w)] == ' ') {
				return false
			}
		}
		return s2 != "" && s2[0] >= 'A' && s2[0] <= 'Z'
	}
	return false
}

func suffixBase(text string) (string, bool) {
	for _, base := range obecSuffixBases {
		if strings.HasPrefix(text, base) && afterBase(text[len(base):]) {
			return base, true
		}
	}
	return "", false
}

// ObecKey is stay_fee._obec_key: the town a typed name means, folded (1031 rules).
func ObecKey(value string) string {
	text := dashRE.ReplaceAllString(FoldText(value), "-")
	for _, prefix := range officialPrefixes {
		if strings.HasPrefix(text, prefix) {
			rest := strings.TrimSpace(text[len(prefix):])
			if _, ok := suffixBase(rest); ok {
				text = rest
				break
			}
		}
	}
	for _, name := range okresNotObec {
		if strings.HasPrefix(text, name) {
			next := text[len(name):]
			if next == "" || next[0] < 'A' || next[0] > 'Z' {
				return text
			}
		}
	}
	if base, ok := suffixBase(text); ok {
		text = base
	}
	if alias, ok := obecAliases[text]; ok {
		return alias
	}
	return text
}

// PropertyObec is stay_fee.property_obec: addr_obec, else the town in city_en.
func PropertyObec(ap *Apartment) string {
	for _, v := range []string{ap.AddrObec, ap.CityEN} {
		if strings.TrimSpace(v) != "" {
			return v
		}
	}
	return ""
}

// SameObecResident is stay_fee.same_obec_resident: true only for a CZ resident
// whose city is the property's town.
func SameObecResident(g GuestRow, ap *Apartment) bool {
	if g.ResCountry != czechCode {
		return false
	}
	obec := ObecKey(PropertyObec(ap))
	return obec != "" && ObecKey(g.ResCity) == obec
}

// --- dated rates (brief 1027) --------------------------------------------------

// FlatSchedule is stay_fee_rate.flat: one rate for every night.
func FlatSchedule(rate int) []RateStep { return []RateStep{{From: time.Time{}, Rate: rate}} }

// ScheduleFor is stay_fee_rate.schedule_for over loaded rows. today is Python's
// date.today() default, used only when the column moved without a history row.
func ScheduleFor(column int, rows []RateRow, today time.Time) ([]RateStep, error) {
	if len(rows) == 0 {
		return FlatSchedule(column), nil
	}
	schedule := make([]RateStep, 0, len(rows)+1)
	for _, row := range rows {
		from, err := time.Parse("2006-01-02", row.EffectiveFrom)
		if err != nil {
			return nil, fmt.Errorf("stay_fee_rate.effective_from %q: %w", row.EffectiveFrom, err)
		}
		schedule = append(schedule, RateStep{From: from, Rate: row.RateCZK})
	}
	if schedule[len(schedule)-1].Rate != column {
		schedule = append(schedule, RateStep{From: dayStart(today), Rate: column})
		sort.SliceStable(schedule, func(i, j int) bool { return schedule[i].From.Before(schedule[j].From) })
	}
	return schedule, nil
}

// RateOn is stay_fee_rate.rate_on: the last entry dated on or before day.
func RateOn(schedule []RateStep, day time.Time) int {
	rate := schedule[0].Rate
	for _, step := range schedule {
		if !step.From.After(day) {
			rate = step.Rate
		} else {
			break
		}
	}
	return rate
}

// IsUniform is stay_fee_rate.is_uniform: one rate for every night first..last.
func IsUniform(schedule []RateStep, first, last time.Time) bool {
	rates := map[int]bool{RateOn(schedule, first): true, RateOn(schedule, last): true}
	for _, step := range schedule {
		if first.Before(step.From) && !step.From.After(last) {
			rates[RateOn(schedule, step.From)] = true
		}
	}
	return len(rates) == 1
}

// --- per guest and per property ------------------------------------------------

// GuestPeriod is stay_fee.guest_period with the apartment and schedule given:
// one guest's share of one period, or ok false when no counted day falls in it.
func GuestPeriod(g GuestRow, first, last time.Time, ap *Apartment, schedule []RateStep) (Line, bool) {
	fromText, toText := g.StayFrom, g.StayTo
	if fromText == "" {
		fromText = g.ResFrom
	}
	if toText == "" {
		toText = g.ResTo
	}
	start, okStart := validation.ParseISODate(fromText)
	end, okEnd := validation.ParseISODate(toText)
	if !okStart || !okEnd || !end.After(start) {
		return Line{}, false
	}
	stayNights := daysBetween(start, end)
	var decision *string
	if inList(Decisions, g.FeeHostDecision) {
		d := g.FeeHostDecision
		decision = &d
	}
	status := "liable"
	if stayNights > ThresholdNights {
		status = "not_subject"
	}
	liable, exempt, amount := 0, 0, 0
	byRate := map[int]int{}
	autoMinor := false
	var birth time.Time
	haveBirth := false
	if decision == nil {
		birth, haveBirth = ConservativeBirth(g.BirthDate)
	}
	obecAuto := decision == nil && SameObecResident(g, ap)
	d := start.AddDate(0, 0, 1)
	if first.After(d) {
		d = first
	}
	endInPeriod := end
	if last.Before(endInPeriod) {
		endInPeriod = last
	}
	for ; !d.After(endInPeriod); d = d.AddDate(0, 0, 1) {
		if status == "not_subject" {
			continue
		}
		dayStatus := "exempt"
		if !obecAuto {
			switch {
			case decision != nil && *decision == "exempt":
				dayStatus = "exempt"
			default:
				if !haveBirth {
					birth, haveBirth = ConservativeBirth(g.BirthDate)
				}
				if haveBirth && AgeOn(birth, d) < AdultAge {
					dayStatus = "exempt"
				} else {
					dayStatus = "liable"
				}
			}
		}
		if dayStatus == "liable" {
			liable++
			rate := RateOn(schedule, d)
			amount += rate
			byRate[rate]++
		} else {
			exempt++
			if decision == nil && haveBirth && AgeOn(birth, d) < AdultAge {
				autoMinor = true
			}
		}
	}
	days := liable + exempt
	if days <= 0 && status != "not_subject" {
		return Line{}, false
	}
	switch {
	case status == "not_subject":
		days = CountedDaysIn(start, end, first, last)
		liable, exempt = 0, 0
	case exempt > 0 && liable == 0:
		status = "exempt"
	case liable > 0:
		status = "liable"
	}
	rateNights := [][2]int{}
	for r, n := range byRate {
		rateNights = append(rateNights, [2]int{r, n})
	}
	sort.Slice(rateNights, func(i, j int) bool {
		if rateNights[i][0] != rateNights[j][0] {
			return rateNights[i][0] < rateNights[j][0]
		}
		return rateNights[i][1] < rateNights[j][1]
	})
	return Line{
		GuestID:          g.ID,
		StayFrom:         ISO(start),
		StayTo:           ISO(end),
		Nights:           days,
		LiableNights:     liable,
		ExemptNights:     exempt,
		Status:           status,
		AutoMinor:        autoMinor && status == "exempt",
		Decision:         decision,
		Reason:           g.FeeHostReason,
		ThresholdNights:  stayNights == ThresholdNights,
		AmountCZK:        amount,
		RateNights:       rateNights,
		AutoObecResident: obecAuto && status == "exempt",
	}, true
}

// applyScopeBoundary is stay_fee._apply_scope_boundary: a recorded 60-night
// ruling. Exactly 60 nights is 61 calendar days.
func applyScopeBoundary(line *Line, ap *Apartment) {
	if !line.ThresholdNights || strings.TrimSpace(ap.ScopeRule) != "calendar_days" {
		return
	}
	line.Status = "not_subject"
	line.LiableNights = 0
	line.ExemptNights = 0
	line.AutoMinor = false
	line.AmountCZK = 0
	line.RateNights = [][2]int{}
	line.AutoObecResident = false
}

// ChooseCadence is the first line of property_period: cadence if valid, else the apartment's.
func ChooseCadence(ap *Apartment, cadence string) string {
	if inList(Cadences, cadence) {
		return cadence
	}
	return CadenceOf(ap)
}

// BuildPeriod is stay_fee.property_period for a live period (live_only=True):
// the figures for ap and the period of cadence containing month. rate, when
// not nil, overrides the dated schedule with one flat rate. It returns nil when
// the property has no stay fee. The guests, rates and adjustments come in as in.
func BuildPeriod(ap *Apartment, month time.Time, cadence string, rate *int, in PeriodInput) (*Period, error) {
	chosen := ChooseCadence(ap, cadence)
	if !IsActive(ap) {
		return nil, nil
	}
	first, last := PeriodBounds(chosen, month)
	var schedule []RateStep
	if rate != nil {
		schedule = FlatSchedule(*rate)
	} else {
		var err error
		if schedule, err = ScheduleFor(ap.StayFeeRateCZK, in.RateRows, in.ScheduleToday); err != nil {
			return nil, err
		}
	}
	lastRate := RateOn(schedule, last)
	lines := []Line{}
	unsigned := 0
	for _, g := range in.Guests {
		if !guestSignatureSettled(g) {
			unsigned++
		}
		line, ok := GuestPeriod(g, first, last, ap, schedule)
		if !ok {
			continue
		}
		applyScopeBoundary(&line, ap)
		line.ReservationID = g.ReservationID
		line.Name = strings.TrimSpace(g.FirstName + " " + g.Surname)
		line.Restricted = g.Restricted
		line.ResCountry = g.ResCountry
		line.ResCity = g.ResCity
		lines = append(lines, line)
	}
	liable, exempt := 0, 0
	for _, l := range lines {
		liable += l.LiableNights
		exempt += l.ExemptNights
	}
	period := &Period{
		Apartment:         ap,
		Cadence:           chosen,
		First:             first,
		Last:              last,
		Label:             PeriodLabelCS(chosen, first),
		RateCZK:           lastRate,
		Lines:             lines,
		GuestLiableNights: liable,
		LiableNights:      liable,
		ExemptNights:      exempt,
		TotalCZK:          liable * lastRate,
		Adjustments:       []Adjustment{},
		UnsignedGuests:    unsigned,
	}
	applyAdjustments(period, month, in.Adjustments)
	return period, nil
}

// rateSegments is stay_fee._rate_segments: nights per rate, guest nights plus
// bed-days at the last-day rate, as [rate, nights] pairs.
func rateSegments(p *Period) [][2]int {
	nights := map[int]int{}
	for _, line := range p.Lines {
		for _, rn := range line.RateNights {
			nights[rn[0]] += rn[1]
		}
	}
	base := p.RateCZK
	nights[base] += p.AdjustmentBedDays
	deficit := 0
	if nights[base] < 0 {
		deficit = -nights[base]
	}
	if deficit > 0 {
		nights[base] = 0
		rates := make([]int, 0, len(nights))
		for r := range nights {
			rates = append(rates, r)
		}
		sort.Sort(sort.Reverse(sort.IntSlice(rates)))
		for _, r := range rates {
			take := min(deficit, nights[r])
			nights[r] -= take
			deficit -= take
		}
	}
	out := [][2]int{}
	for r, n := range nights {
		if n > 0 {
			out = append(out, [2]int{r, n})
		}
	}
	sort.Slice(out, func(i, j int) bool { return out[i][0] < out[j][0] })
	if len(out) == 0 {
		return [][2]int{{base, 0}}
	}
	return out
}

// applyAdjustments is stay_fee._apply_adjustments: fold open aggregate
// corrections into the live liable total.
func applyAdjustments(p *Period, month time.Time, rows []Adjustment) {
	delta := 0
	for _, r := range rows {
		delta += r.Delta
	}
	guestNights := p.GuestLiableNights
	liable := max(guestNights+delta, 0)
	p.AdjustmentBedDays = liable - guestNights
	p.Adjustments = rows
	if p.Adjustments == nil {
		p.Adjustments = []Adjustment{}
	}
	p.LiableNights = liable
	p.RateSegments = rateSegments(p)
	total := 0
	for _, seg := range p.RateSegments {
		total += seg[0] * seg[1]
	}
	p.TotalCZK = total
	p.PeriodKey = PeriodKey(p.Cadence, month)
}
````

### Block 3: `go/internal/stayfee/report.go` sha256 `1b73fac0fe4c76966ca17c3205bc1cc2e2c2e64fb3b4494918ce148be6a65307`

````go
package stayfee

import (
	"fmt"
	"regexp"
	"strconv"
	"strings"
	"time"
	"unicode"

	"golang.org/x/text/unicode/norm"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/countries"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

const (
	inpassDoc = "INPASS"
	// maxResidence is validation.MAX_RESIDENCE.
	maxResidence = 255
)

// Group is stay_fee.report_group: one hlášení and register per facility.
type Group struct {
	Anchor       *Apartment
	VS           string
	Cadence      string
	First, Last  time.Time
	Label        string
	Periods      []*Period
	LiableNights int
	ExemptNights int
	TotalCZK     int
}

// ReportGroup is stay_fee.report_group with the period given (nil for an
// inactive property). cadence is only read when period is nil.
func ReportGroup(ap *Apartment, month time.Time, period *Period, cadence string) *Group {
	g := &Group{Anchor: ap, VS: VSOf(ap), Periods: []*Period{}}
	if period != nil {
		g.Periods = append(g.Periods, period)
		g.Cadence, g.First, g.Last = period.Cadence, period.First, period.Last
		g.Label = period.Label
		if g.Label == "" {
			g.Label = PeriodLabelCS(g.Cadence, g.First)
		}
	} else {
		g.Cadence = ChooseCadence(ap, cadence)
		g.First, g.Last = PeriodBounds(g.Cadence, month)
		g.Label = PeriodLabelCS(g.Cadence, month)
	}
	for _, p := range g.Periods {
		g.LiableNights += p.LiableNights
		g.ExemptNights += p.ExemptNights
		g.TotalCZK += p.TotalCZK
	}
	return g
}

// IssueContext is what report_issues reads from the database: the payer row
// (nil when the apartment has none) and whether a sealed filing that is not
// this period intersects it (stay_fee_filing.foreign_overlap).
type IssueContext struct {
	Entity         *Entity
	ForeignOverlap bool
}

// ReportIssues is stay_fee.report_issues: the host-UI keys that block
// finalization, in Python's order, without duplicates. Empty means ready.
func ReportIssues(g *Group, today time.Time, ic IssueContext) []string {
	anchor := g.Anchor
	issues := []string{}
	if !PeriodComplete(g.Cadence, g.First, today) {
		issues = append(issues, "stay_fees.issue.period_running")
	}
	if g.VS == "" {
		issues = append(issues, "stay_fees.issue.no_vs")
	}
	if strings.TrimSpace(anchor.AuthorityName) == "" {
		issues = append(issues, "stay_fees.issue.no_authority")
	}
	if ic.Entity == nil || strings.TrimSpace(ic.Entity.Name) == "" {
		issues = append(issues, "stay_fees.issue.no_payer")
	}
	for _, p := range g.Periods {
		for _, line := range p.Lines {
			if line.ThresholdNights {
				rule := strings.TrimSpace(anchor.ScopeRule)
				ref := strings.TrimSpace(anchor.ScopeReference)
				if !inList(ScopeRules, rule) || len([]rune(ref)) < 3 {
					issues = append(issues, "stay_fees.issue.scope_ruling")
				}
			}
		}
	}
	if ic.ForeignOverlap {
		issues = append(issues, "stay_fees.issue.overlaps_saved")
	}
	seen := map[string]bool{}
	out := []string{}
	for _, i := range issues {
		if !seen[i] {
			seen[i] = true
			out = append(out, i)
		}
	}
	return out
}

// --- payment ------------------------------------------------------------------

// Payment is stay_fee.payment_details without the QR image.
type Payment struct {
	Account     string `json:"account"`
	IBAN        string `json:"iban"`
	IBANDisplay string `json:"iban_display"`
	VS          string `json:"vs"`
	SPAYD       string `json:"spayd"`
}

// PaymentDetails is stay_fee.payment_details: nil when the council account is
// unset. The QR image (payments.qr_data_uri) is not part of this port: render
// SPAYD with the payments package.
func PaymentDetails(g *Group) *Payment {
	iban := g.Anchor.CouncilIBAN
	if iban == "" {
		return nil
	}
	payload := ""
	if g.VS != "" && g.TotalCZK > 0 {
		payload = SPAYD(iban, g.TotalCZK, g.VS, "POPLATEK Z POBYTU "+g.VS)
	}
	return &Payment{Account: g.Anchor.CouncilAccount, IBAN: iban, IBANDisplay: FormatIBAN(iban),
		VS: g.VS, SPAYD: payload}
}

// FormatIBAN is payments.format_iban: groups of four characters.
func FormatIBAN(iban string) string {
	runes := []rune(iban)
	var parts []string
	for i := 0; i < len(runes); i += 4 {
		parts = append(parts, string(runes[i:min(i+4, len(runes))]))
	}
	return strings.Join(parts, " ")
}

const qrChars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $+-./:"

// ASCIIUpper is payments.ascii_upper: NFKD, drop combining marks, upper, keep
// only the QR character set (others become spaces), collapse spaces, cut to
// limit characters.
func ASCIIUpper(text string, limit int) string {
	var up strings.Builder
	for _, r := range norm.NFKD.String(text) {
		if norm.NFC.PropertiesString(string(r)).CCC() != 0 {
			continue
		}
		up.WriteString(pyUpper(string(r)))
	}
	var b strings.Builder
	lastSpace := false
	for _, r := range up.String() {
		if !strings.ContainsRune(qrChars, r) {
			r = ' '
		}
		if r == ' ' {
			if lastSpace {
				continue
			}
			lastSpace = true
		} else {
			lastSpace = false
		}
		b.WriteRune(r)
	}
	plain := []rune(strings.TrimSpace(b.String()))
	if len(plain) > limit {
		plain = plain[:limit]
	}
	return strings.TrimRight(string(plain), " ")
}

// SPAYD is payments.spayd without a BIC: the QR Platba string for a whole-CZK amount.
func SPAYD(iban string, amountCZK int, vs, message string) string {
	return strings.Join([]string{"SPD", "1.0", "ACC:" + iban, "AM:" + strconv.Itoa(amountCZK) + ".00",
		"CC:CZK", "X-VS:" + vs, "MSG:" + ASCIIUpper(message, 60)}, "*")
}

// --- pay ways (brief 1071) ---------------------------------------------------

var (
	accountRE = regexp.MustCompile(`^(?:([0-9]{1,6})-)?([0-9]{2,10})/([0-9]{4})$`)
	ibanRE    = regexp.MustCompile(`^[A-Z]{2}[0-9]{2}[A-Z0-9]{10,30}$`)
	weights   = [10]int{6, 3, 7, 9, 10, 5, 8, 4, 2, 1}
	railOrder = []string{"iban", "revolut", "cash"}
)

func mod11OK(digits string) bool {
	padded := strings.Repeat("0", max(0, 10-len(digits))) + digits
	sum := 0
	for i, c := range padded {
		sum += int(c-'0') * weights[i]
	}
	return sum%11 == 0
}

func ibanOK(iban string) bool {
	moved := iban[4:] + iban[:4]
	mod := 0
	for _, c := range moved {
		if c >= 'A' && c <= 'Z' {
			mod = (mod*100 + int(c-'A') + 10) % 97
		} else {
			mod = (mod*10 + int(c-'0')) % 97
		}
	}
	return mod == 1
}

// NormaliseAccount is payments.normalise_account: the IBAN of a Czech account
// or IBAN string; ok false where Python raises ValueError.
func NormaliseAccount(raw string) (string, bool) {
	text := strings.ToUpper(strings.Map(func(r rune) rune {
		if unicode.IsSpace(r) {
			return -1
		}
		return r
	}, raw))
	if ibanRE.MatchString(text) {
		return text, ibanOK(text)
	}
	m := accountRE.FindStringSubmatch(text)
	if m == nil {
		return "", false
	}
	prefix, number, bank := m[1], m[2], m[3]
	if (prefix != "" && !mod11OK(prefix)) || !mod11OK(number) {
		return "", false
	}
	bban := bank + strings.Repeat("0", 6-len(prefix)) + prefix + strings.Repeat("0", 10-len(number)) + number
	mod := 0
	for _, c := range bban + "123500" {
		mod = (mod*10 + int(c-'0')) % 97
	}
	return fmt.Sprintf("CZ%02d%s", 98-mod, bban), true
}

// PayoutAccount is stay_fee.payout_account: (account, payee) of the operator
// guests pay, or empty strings. entity is the apartment's legal entity or nil.
func PayoutAccount(entity *Entity) (string, string) {
	if entity == nil {
		return "", ""
	}
	payee := strings.TrimSpace(entity.Name)
	account := ""
	if entity.IBAN != "" {
		account = entity.IBAN
	} else if entity.BankAccount != "" {
		if iban, ok := NormaliseAccount(entity.BankAccount); ok {
			account = iban
		}
	}
	return account, payee
}

// UsableRailKeys is stay_fee.usable_rail_keys: the guest pay ways that work for
// the property, in the order the guest sees them.
func UsableRailKeys(ap *Apartment, entity *Entity) []string {
	enabled := map[string]bool{}
	for _, part := range strings.Split(ap.GuestRails, ",") {
		if part != "" {
			enabled[part] = true
		}
	}
	if enabled["qr"] {
		enabled["iban"] = true
	}
	first := ap.GuestDefaultRail
	if first == "qr" {
		first = "iban"
	}
	order := []string{}
	if inList(railOrder, first) {
		order = append(order, first)
	}
	for _, k := range railOrder {
		if k != first {
			order = append(order, k)
		}
	}
	account, _ := PayoutAccount(entity)
	usable := []string{}
	for _, key := range order {
		if !enabled[key] || (key == "iban" && account == "") || (key == "revolut" && ap.RevolutLink == "") {
			continue
		}
		usable = append(usable, key)
	}
	return usable
}

// NoPayWay is stay_fee.no_pay_way. guestPay is config.STAY_FEE_GUEST_PAY
// (UBYHOST_STAY_FEE_GUEST_PAY=on).
func NoPayWay(ap *Apartment, entity *Entity, guestPay bool) bool {
	return ap.Collect && IsActive(ap) && guestPay && ap.ArchivedAt == "" && len(UsableRailKeys(ap, entity)) == 0
}

// --- hlášení (the PDF input) --------------------------------------------------

// Rate-row of the hlášení: one per facility and rate.
type HlaseniRow struct {
	PropertyName    string `json:"property_name"`
	PropertyAddress string `json:"property_address"`
	LiableNights    int    `json:"liable_nights"`
	RateCZK         int    `json:"rate_czk"`
	AmountCZK       int    `json:"amount_czk"`
}

// NotCharged is a "not charged" bucket of the hlášení.
type NotCharged struct {
	Reason string `json:"reason"`
	Count  int    `json:"count"`
	Nights int    `json:"nights"`
}

// Hlaseni is stay_fee.hlaseni: the report object the remittance PDF draws.
type Hlaseni struct {
	PayerName        string       `json:"payer_name"`
	PayerSeat        string       `json:"payer_seat"`
	PayerICO         string       `json:"payer_ico"`
	PayerContact     string       `json:"payer_contact"`
	VS               string       `json:"vs"`
	RecipientName    string       `json:"recipient_name"`
	RecipientAddress string       `json:"recipient_address"`
	RecipientContact string       `json:"recipient_contact"`
	Payee            string       `json:"payee"`
	Instruction      string       `json:"instruction"`
	Cadence          string       `json:"cadence"`
	PeriodStart      string       `json:"period_start"`
	PeriodEnd        string       `json:"period_end"`
	IssuedOn         string       `json:"issued_on"`
	Rows             []HlaseniRow `json:"rows"`
	LiableNights     int          `json:"liable_nights"`
	ExemptNights     int          `json:"exempt_nights"`
	TotalCZK         int          `json:"total_czk"`
	NotCharged       []NotCharged `json:"not_charged"`
	SignaturePNG     string       `json:"signature_png"`
	SignatureName    string       `json:"signature_name"`
}

const (
	exemptLabelMinor = "Mladší 18 let"
	exemptLabelHost  = "Osvobozeno ubytovatelem (důvod v evidenční knize)"
	// RegisterHostLine is the register line for bed-days the host entered without guest records.
	RegisterHostLine = "přenocování bez záznamu hosta (doplněno ubytovatelem)"
	// RestrictedNote is appended to the exemption reason of a restricted guest.
	RestrictedNote = "zpracování omezeno (čl. 18 GDPR)"
)

func joinNonEmpty(sep string, parts ...string) string {
	var out []string
	for _, p := range parts {
		if p != "" {
			out = append(out, p)
		}
	}
	return strings.Join(out, sep)
}

// PropertyAddress is stay_fee.property_address.
func PropertyAddress(ap *Apartment) string {
	number := joinNonEmpty("/", ap.AddrHouseNo, ap.AddrOrientNo)
	street := joinNonEmpty(" ", ap.AddrStreet, number)
	town := joinNonEmpty(" ", ap.AddrZip, ap.AddrObec)
	return joinNonEmpty(", ", street, town)
}

// MakeHlaseni is stay_fee.hlaseni(group, issued_on). entity is the payer
// (SignaturePNG decrypted); nil is an error, as the Python call raises.
func MakeHlaseni(g *Group, issuedOn time.Time, entity *Entity) (*Hlaseni, error) {
	if entity == nil {
		return nil, fmt.Errorf("stayfee: apartment %d has no legal entity", g.Anchor.ID)
	}
	anchor := g.Anchor
	rows := []HlaseniRow{}
	minors, hosts := NotCharged{Reason: exemptLabelMinor}, NotCharged{Reason: exemptLabelHost}
	for _, p := range g.Periods {
		segments := p.RateSegments
		if len(segments) == 0 {
			segments = [][2]int{{p.RateCZK, p.LiableNights}}
		}
		for _, seg := range segments {
			rows = append(rows, HlaseniRow{PropertyName: p.Apartment.InternalName,
				PropertyAddress: PropertyAddress(p.Apartment), LiableNights: seg[1], RateCZK: seg[0],
				AmountCZK: seg[1] * seg[0]})
		}
		for _, line := range p.Lines {
			if line.ExemptNights > 0 {
				bucket := &hosts
				if line.AutoMinor || line.Status == "liable" {
					bucket = &minors
				}
				bucket.Count++
				bucket.Nights += line.ExemptNights
			}
		}
	}
	notCharged := []NotCharged{}
	for _, b := range []NotCharged{minors, hosts} {
		if b.Count > 0 {
			notCharged = append(notCharged, b)
		}
	}
	return &Hlaseni{
		PayerName: entity.Name, PayerSeat: entity.Seat, PayerICO: entity.ICO, PayerContact: entity.ContactEmail,
		VS: g.VS, RecipientName: anchor.AuthorityName, RecipientAddress: anchor.AuthorityAddress,
		RecipientContact: anchor.AuthorityContact, Payee: strings.TrimSpace(anchor.Payee),
		Instruction: anchor.Instruction, Cadence: g.Cadence, PeriodStart: ISO(g.First), PeriodEnd: ISO(g.Last),
		IssuedOn: ISO(issuedOn), Rows: rows, LiableNights: g.LiableNights, ExemptNights: g.ExemptNights,
		TotalCZK: g.TotalCZK, NotCharged: notCharged, SignaturePNG: entity.SignaturePNG,
		SignatureName: entity.SignatureName,
	}, nil
}

// --- the register (evidenční kniha, §3g) ---------------------------------------

// RegisterRow is one register line; the JSON tags are the Python dict keys.
type RegisterRow struct {
	Property       string `json:"property"`
	Period         string `json:"period"`
	StayFrom       string `json:"stay_from"`
	StayTo         string `json:"stay_to"`
	Surname        string `json:"surname"`
	FirstName      string `json:"first_name"`
	HomeAddress    string `json:"home_address"`
	BirthDate      string `json:"birth_date"`
	DocType        string `json:"doc_type"`
	DocNumber      string `json:"doc_number"`
	Nights         int    `json:"nights"`
	RateCZK        int    `json:"rate_czk"`
	AmountCZK      int    `json:"amount_czk"`
	ExemptReason   string `json:"exempt_reason"`
	VS             string `json:"vs"`
	CouncilAccount string `json:"council_account"`
}

// RegisterColumns is stay_fee.REGISTER_COLUMNS: the CSV header labels in order.
var RegisterColumns = []string{"Zařízení", "Období", "Den počátku pobytu", "Den konce pobytu", "Příjmení",
	"Jméno", "Adresa místa přihlášení / v zahraničí", "Datum narození", "Druh průkazu", "Číslo průkazu",
	"Nocí v období", "Sazba (Kč)", "Poplatek (Kč)", "Důvod osvobození", "Variabilní symbol", "Účet obce"}

// fmtDate is validation.fmt_date: DD.MM.YYYY, an unparseable value unchanged.
func fmtDate(value string) string {
	if t, ok := validation.ParseISODate(value); ok {
		return t.Format("02.01.2006")
	}
	return value
}

// composeResidence is validation.compose_residence in Czech.
func composeResidence(street, city, country string) string {
	var parts []string
	if street != "" {
		parts = append(parts, street)
	}
	if city != "" {
		parts = append(parts, city)
	}
	if country != "" {
		parts = append(parts, country+"-"+countries.Name(country, "cs"))
	}
	out := []rune(strings.Join(parts, ", "))
	if len(out) > maxResidence {
		out = out[:maxResidence]
	}
	return string(out)
}

// formatBirthDate is validation.format_birth_date.
func formatBirthDate(v string) string {
	if len(v) != 8 {
		return v
	}
	return v[:2] + "." + v[2:4] + "." + v[4:]
}

// RegisterRows is stay_fee.register_rows. guests maps every line's guest id to
// its full row (archived guests included, as Python reads them by id).
func RegisterRows(p *Period, guests map[int64]GuestRow) ([]RegisterRow, error) {
	ap := p.Apartment
	vs := VSOf(ap)
	rows := []RegisterRow{}
	for _, line := range p.Lines {
		g, ok := guests[line.GuestID]
		if !ok {
			return nil, fmt.Errorf("stayfee: guest %d not loaded", line.GuestID)
		}
		reason := ""
		switch line.Status {
		case "exempt":
			reason = line.Reason
			if reason == "" && line.AutoMinor {
				reason = "mladší 18 let"
			}
		case "not_subject":
			reason = "pobyt delší než 60 dnů (není předmětem poplatku)"
		}
		docNumber := g.DocNumber
		if docNumber == inpassDoc {
			docNumber = "zapsán v dokladu rodiče"
		}
		row := RegisterRow{
			Property: ap.InternalName, Period: p.Label,
			StayFrom: fmtDate(line.StayFrom), StayTo: fmtDate(line.StayTo),
			Surname: g.Surname, FirstName: g.FirstName,
			HomeAddress: composeResidence(g.ResStreet, g.ResCity, strings.ToUpper(g.ResCountry)),
			BirthDate:   formatBirthDate(g.BirthDate), DocType: DocTypeLabelsCS[DocTypeOf(g)],
			DocNumber: docNumber, Nights: line.Nights, RateCZK: p.RateCZK, AmountCZK: line.AmountCZK,
			ExemptReason: reason, VS: vs, CouncilAccount: ap.CouncilAccount,
		}
		if line.Restricted {
			row.ExemptReason = strings.Trim(row.ExemptReason+"; "+RestrictedNote, "; ")
		}
		rows = append(rows, row)
	}
	if delta := p.AdjustmentBedDays; delta != 0 {
		rows = append(rows, RegisterRow{Property: ap.InternalName, Period: p.Label, Nights: delta,
			RateCZK: p.RateCZK, AmountCZK: delta * p.RateCZK, ExemptReason: RegisterHostLine, VS: vs,
			CouncilAccount: ap.CouncilAccount})
	}
	return rows, nil
}

// csvSafe is csv_safety.csv_safe: a text cell Excel would evaluate gets an apostrophe.
func csvSafe(v string) string {
	trimmed := strings.TrimLeft(v, " ")
	for _, prefix := range []string{"=", "+", "-", "@", "\t", "\r", "\n", nbsp} {
		if strings.HasPrefix(trimmed, prefix) {
			return "'" + v
		}
	}
	return v
}

// csvField is csv.writer's QUOTE_MINIMAL for ";" and \r\n.
func csvField(v string) string {
	if strings.ContainsAny(v, ";\"\r\n") {
		return "\"" + strings.ReplaceAll(v, "\"", "\"\"") + "\""
	}
	return v
}

// RegisterCSV is stay_fee.register_csv: ";"-separated, \r\n line ends, UTF-8
// with a byte order mark.
func RegisterCSV(rows []RegisterRow) []byte {
	var b strings.Builder
	b.WriteString(bom)
	writeRow := func(cells []string) {
		for i, c := range cells {
			if i > 0 {
				b.WriteByte(';')
			}
			b.WriteString(csvField(c))
		}
		b.WriteString("\r\n")
	}
	writeRow(RegisterColumns)
	for _, r := range rows {
		writeRow([]string{csvSafe(r.Property), csvSafe(r.Period), csvSafe(r.StayFrom), csvSafe(r.StayTo),
			csvSafe(r.Surname), csvSafe(r.FirstName), csvSafe(r.HomeAddress), csvSafe(r.BirthDate),
			csvSafe(r.DocType), csvSafe(r.DocNumber), strconv.Itoa(r.Nights), strconv.Itoa(r.RateCZK),
			strconv.Itoa(r.AmountCZK), csvSafe(r.ExemptReason), csvSafe(r.VS), csvSafe(r.CouncilAccount)})
	}
	return []byte(b.String())
}
````

### Block 4: `go/internal/stayfee/filing.go` sha256 `c53b840ba649d14ea9b6592361673269b82d0fe6dfba4a7e1087c78be122381f`

````go
package stayfee

import (
	"context"
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"time"
)

// PeriodKey is stay_fee_filing.period_key: "2026-Q3" or "2026-08".
func PeriodKey(cadence string, month time.Time) string {
	if cadence == "quarterly" {
		return fmt.Sprintf("%04d-Q%d", month.Year(), (int(month.Month())-1)/3+1)
	}
	return MonthKey(month)
}

// OverlapKeys is stay_fee_filing.overlap_keys: the period keys whose dates
// intersect the period of cadence containing month.
func OverlapKeys(cadence string, month time.Time) []string {
	if cadence == "quarterly" {
		first, _ := PeriodBounds("quarterly", month)
		keys := []string{PeriodKey("quarterly", first)}
		for offset := 0; offset < 3; offset++ {
			keys = append(keys, MonthKey(ShiftMonth(first, offset)))
		}
		return keys
	}
	return []string{PeriodKey("monthly", month), PeriodKey("quarterly", month)}
}

// PeriodAnchor is stay_fee_filing.period_anchor: the first day of the period a
// filing row was sealed for. A malformed key is an error (Python ValueError).
func PeriodAnchor(key string) (time.Time, error) {
	if strings.Contains(key, "-Q") {
		parts := strings.Split(key, "-Q")
		if len(parts) != 2 {
			return time.Time{}, fmt.Errorf("bad period key %s", key)
		}
		year, err1 := strconv.Atoi(parts[0])
		quarter, err2 := strconv.Atoi(parts[1])
		if err1 != nil || err2 != nil || year < 1 || quarter < 1 || quarter > 4 {
			return time.Time{}, fmt.Errorf("bad period key %s", key)
		}
		return Day(year, time.Month((quarter-1)*3+1), 1), nil
	}
	parsed, ok := ParseMonth(key)
	if !ok {
		return time.Time{}, fmt.Errorf("bad period key %s", key)
	}
	return parsed, nil
}

// FilingRow is a stay_fee_filing row without the encrypted PDF and CSV blobs.
// PayloadEnc is the Fernet token of the sealed payload. Empty string is NULL.
type FilingRow struct {
	ID                int64
	ApartmentID       int64
	PeriodKey         string
	Version           int
	Cadence           string
	RateCZK           int
	LiableDays        int
	ExemptDays        int
	TotalDueCZK       int
	TotalCollectedCZK int
	PayloadEnc        string
	CreatedAt         string
	SupersededAt      string
	SentAt            string
	SentMessageID     string
	PaidAt            string
}

const filingColumns = `id, apartment_id, period_key, version, cadence, rate_czk, liable_days, exempt_days,
	total_due_czk, total_collected_czk, COALESCE(payload_enc, ''), created_at, COALESCE(superseded_at, ''),
	COALESCE(sent_at, ''), COALESCE(sent_message_id, ''), COALESCE(paid_at, '')`

func queryFiling(ctx context.Context, q Querier, sql string, args ...any) (*FilingRow, error) {
	rows, err := q.Query(ctx, sql, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	if !rows.Next() {
		return nil, rows.Err()
	}
	var f FilingRow
	if err := rows.Scan(&f.ID, &f.ApartmentID, &f.PeriodKey, &f.Version, &f.Cadence, &f.RateCZK, &f.LiableDays,
		&f.ExemptDays, &f.TotalDueCZK, &f.TotalCollectedCZK, &f.PayloadEnc, &f.CreatedAt, &f.SupersededAt,
		&f.SentAt, &f.SentMessageID, &f.PaidAt); err != nil {
		return nil, err
	}
	return &f, nil
}

// activeFiling is stay_fee_filing._active: the newest live filing among keys.
func activeFiling(ctx context.Context, q Querier, apartmentID int64, keys []string) (*FilingRow, error) {
	if len(keys) == 0 {
		return nil, nil
	}
	return queryFiling(ctx, q, `SELECT `+filingColumns+` FROM stay_fee_filing
		WHERE apartment_id = $1 AND superseded_at IS NULL AND period_key = ANY($2)
		ORDER BY created_at DESC, id DESC LIMIT 1`, apartmentID, keys)
}

// Covering is stay_fee_filing.covering: the newest sealed filing whose period
// contains month, either cadence. nil, nil when there is none.
func Covering(ctx context.Context, q Querier, apartmentID int64, month time.Time) (*FilingRow, error) {
	return activeFiling(ctx, q, apartmentID, OverlapKeys("monthly", month))
}

// ForeignOverlap is stay_fee_filing.foreign_overlap: a sealed filing that
// intersects this period but is not this period itself.
func ForeignOverlap(ctx context.Context, q Querier, apartmentID int64, cadence string, month time.Time) (*FilingRow, error) {
	own := PeriodKey(cadence, month)
	var keys []string
	for _, k := range OverlapKeys(cadence, month) {
		if k != own {
			keys = append(keys, k)
		}
	}
	return activeFiling(ctx, q, apartmentID, keys)
}

// Latest is stay_fee_filing.latest: the live filing of one period key, newest version.
func Latest(ctx context.Context, q Querier, apartmentID int64, key string) (*FilingRow, error) {
	return queryFiling(ctx, q, `SELECT `+filingColumns+` FROM stay_fee_filing
		WHERE apartment_id = $1 AND period_key = $2 AND superseded_at IS NULL
		ORDER BY version DESC LIMIT 1`, apartmentID, key)
}

// CorrectionRateFor is stay_fee_filing.correction_rate over a loaded schedule:
// the sealed flat rate when every night of the sealed period had one rate, nil
// (priced per night again) when the period spans a rate change.
func CorrectionRateFor(schedule []RateStep, row *FilingRow) (*int, error) {
	anchor, err := PeriodAnchor(row.PeriodKey)
	if err != nil {
		return nil, err
	}
	first, last := PeriodBounds(row.Cadence, anchor)
	if !IsUniform(schedule, first, last) {
		return nil, nil
	}
	rate := row.RateCZK
	return &rate, nil
}

// CorrectionRate loads the apartment's schedule and calls CorrectionRateFor.
// scheduleToday is Python's date.today() default of schedule_for.
func CorrectionRate(ctx context.Context, q Querier, ap *Apartment, row *FilingRow, scheduleToday time.Time) (*int, error) {
	schedule, err := LoadSchedule(ctx, q, ap, scheduleToday)
	if err != nil {
		return nil, err
	}
	return CorrectionRateFor(schedule, row)
}

type sealedPayload struct {
	Lines        []Line   `json:"lines"`
	RateSegments [][2]int `json:"rate_segments"`
}

// FrozenSummary is stay_fee_filing.frozen_summary: the Period shape for a
// sealed row. dec decrypts the sealed payload; the lines and rate segments come
// from it, the totals from the row.
func FrozenSummary(row *FilingRow, ap *Apartment, dec Decrypter) (*Period, error) {
	anchor, err := PeriodAnchor(row.PeriodKey)
	if err != nil {
		return nil, err
	}
	first, last := PeriodBounds(row.Cadence, anchor)
	var sealed sealedPayload
	if row.PayloadEnc != "" {
		plain, err := dec(row.PayloadEnc)
		if err != nil {
			return nil, err
		}
		if plain != "" {
			if err := json.Unmarshal([]byte(plain), &sealed); err != nil {
				return nil, fmt.Errorf("stayfee: filing %d payload: %w", row.ID, err)
			}
		}
	}
	if sealed.Lines == nil {
		sealed.Lines = []Line{}
	}
	if len(sealed.RateSegments) == 0 {
		sealed.RateSegments = [][2]int{{row.RateCZK, row.LiableDays}}
	}
	return &Period{
		Apartment: ap, Cadence: row.Cadence, First: first, Last: last,
		Label: PeriodLabelCS(row.Cadence, anchor), PeriodKey: row.PeriodKey, RateCZK: row.RateCZK,
		Lines: sealed.Lines, RateSegments: sealed.RateSegments, LiableNights: row.LiableDays,
		ExemptNights: row.ExemptDays, TotalCZK: row.TotalDueCZK, Frozen: true, FilingID: row.ID,
		Version: row.Version, TotalCollectedCZK: row.TotalCollectedCZK, SentAt: row.SentAt, PaidAt: row.PaidAt,
		SentMessageID: row.SentMessageID,
	}, nil
}
````

### Block 5: `go/internal/stayfee/loader.go` sha256 `e99c4f136bb83d3feacf509bc8dc83d2ec25e8075284eade372d7a66e260d6c6`

````go
package stayfee

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// Querier is the part of *pgxpool.Pool and pgx.Tx the loader uses. A job that
// reads and writes in one transaction passes its pgx.Tx.
type Querier interface {
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
}

// Decrypter opens one stored token (secure.MultiFernet.Decrypt as a string
// function). A token that will not decrypt is an error, like db.decrypt_field.
type Decrypter func(token string) (string, error)

// FernetDecrypter is the Decrypter of the data keys (secure.LoadDataKeys): no
// age limit, like db.decrypt_field.
func FernetDecrypter(keys *secure.MultiFernet) Decrypter {
	return func(token string) (string, error) {
		plain, err := keys.Decrypt(token, 0, time.Now())
		if err != nil {
			return "", err
		}
		return string(plain), nil
	}
}

// ErrNotFound is returned by the Load functions for a missing row.
var ErrNotFound = errors.New("stayfee: not found")

// pick is db.decrypt_field(token, fallback): the decrypted token when there is
// one, else the plaintext column.
func pick(dec Decrypter, token, plain string) (string, error) {
	if token == "" {
		return plain, nil
	}
	return dec(token)
}

const apartmentSelect = `SELECT id, COALESCE(legal_entity_id, 0), internal_name, stay_fee_rate_czk,
	COALESCE(stay_fee_cadence, ''), COALESCE(stay_fee_vs, ''), COALESCE(stay_fee_authority_name, ''),
	COALESCE(stay_fee_authority_address, ''), COALESCE(stay_fee_authority_contact, ''),
	COALESCE(stay_fee_payee, ''), COALESCE(stay_fee_instruction, ''), COALESCE(stay_fee_council_account, ''),
	COALESCE(stay_fee_council_iban, ''), COALESCE(stay_fee_scope_rule, ''), COALESCE(stay_fee_scope_reference, ''),
	stay_fee_collect <> 0, COALESCE(stay_fee_guest_rails, ''), COALESCE(stay_fee_guest_default_rail, ''),
	COALESCE(stay_fee_guest_revolut_link, ''), COALESCE(stay_fee_guest_cash_note, ''),
	COALESCE(addr_obec, ''), COALESCE(city_en, ''), COALESCE(addr_street, ''), COALESCE(addr_house_no, ''),
	COALESCE(addr_orient_no, ''), COALESCE(addr_zip, ''), COALESCE(archived_at, '')
	FROM apartment`

// ApartmentSelect is the column list LoadApartment reads, ending in FROM
// apartment, so a job that lists apartments (stay_fee_auto.run) can append its
// own WHERE and scan with ScanApartment.
const ApartmentSelect = apartmentSelect

// ScanApartment scans one row of ApartmentSelect.
func ScanApartment(rows pgx.Rows) (*Apartment, error) {
	var a Apartment
	if err := rows.Scan(&a.ID, &a.LegalEntityID, &a.InternalName, &a.StayFeeRateCZK, &a.StayFeeCadence,
		&a.StayFeeVS, &a.AuthorityName, &a.AuthorityAddress, &a.AuthorityContact, &a.Payee, &a.Instruction,
		&a.CouncilAccount, &a.CouncilIBAN, &a.ScopeRule, &a.ScopeReference, &a.Collect, &a.GuestRails,
		&a.GuestDefaultRail, &a.RevolutLink, &a.CashNote, &a.AddrObec, &a.CityEN, &a.AddrStreet,
		&a.AddrHouseNo, &a.AddrOrientNo, &a.AddrZip, &a.ArchivedAt); err != nil {
		return nil, err
	}
	return &a, nil
}

// LoadApartment reads one apartment; ErrNotFound when there is none.
func LoadApartment(ctx context.Context, q Querier, id int64) (*Apartment, error) {
	rows, err := q.Query(ctx, apartmentSelect+` WHERE id = $1`, id)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	if !rows.Next() {
		if err := rows.Err(); err != nil {
			return nil, err
		}
		return nil, ErrNotFound
	}
	return ScanApartment(rows)
}

// LoadEntity reads the payer of an apartment (nil, nil when the apartment has
// none or the row is gone). withSignature decrypts the drawn signature, which
// only MakeHlaseni needs.
func LoadEntity(ctx context.Context, q Querier, dec Decrypter, id int64, withSignature bool) (*Entity, error) {
	if id == 0 {
		return nil, nil
	}
	rows, err := q.Query(ctx, `SELECT id, COALESCE(name, ''), COALESCE(seat, ''), COALESCE(ico, ''),
		COALESCE(contact_email, ''), COALESCE(iban, ''), COALESCE(bank_account, ''),
		COALESCE(signature_png_enc, ''), COALESCE(signature_name, '') FROM legal_entity WHERE id = $1`, id)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	if !rows.Next() {
		return nil, rows.Err()
	}
	var e Entity
	var sigToken string
	if err := rows.Scan(&e.ID, &e.Name, &e.Seat, &e.ICO, &e.ContactEmail, &e.IBAN, &e.BankAccount,
		&sigToken, &e.SignatureName); err != nil {
		return nil, err
	}
	if withSignature && sigToken != "" {
		if e.SignaturePNG, err = dec(sigToken); err != nil {
			return nil, err
		}
	}
	return &e, nil
}

// LoadSchedule is stay_fee_rate.schedule_for: the apartment's dated rates.
func LoadSchedule(ctx context.Context, q Querier, ap *Apartment, scheduleToday time.Time) ([]RateStep, error) {
	rows, err := loadRateRows(ctx, q, ap.ID)
	if err != nil {
		return nil, err
	}
	return ScheduleFor(ap.StayFeeRateCZK, rows, scheduleToday)
}

func loadRateRows(ctx context.Context, q Querier, apartmentID int64) ([]RateRow, error) {
	rows, err := q.Query(ctx, `SELECT effective_from, rate_czk FROM stay_fee_rate
		WHERE apartment_id = $1 ORDER BY effective_from`, apartmentID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []RateRow
	for rows.Next() {
		var r RateRow
		if err := rows.Scan(&r.EffectiveFrom, &r.RateCZK); err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

// guestSelect lists the guest columns of the stay-fee reads. With docs false
// the document number is not selected (and so not decrypted).
func guestSelect(docs bool) string {
	doc := `'', ''`
	if docs {
		doc = `COALESCE(g.doc_number, ''), COALESCE(g.doc_number_enc, '')`
	}
	return `SELECT g.id, g.reservation_id, COALESCE(g.surname, ''), COALESCE(g.first_name, ''),
		COALESCE(g.birth_date, ''), COALESCE(g.birth_date_enc, ''), COALESCE(g.nationality, ''),
		COALESCE(g.doc_type, ''), ` + doc + `,
		COALESCE(g.res_street, ''), COALESCE(g.res_street_enc, ''), COALESCE(g.res_city, ''),
		COALESCE(g.res_city_enc, ''), COALESCE(g.res_country, ''), COALESCE(g.stay_from, ''),
		COALESCE(g.stay_to, ''), COALESCE(g.fee_host_decision, ''), COALESCE(g.fee_host_reason, ''),
		COALESCE(g.fee_host_reason_enc, ''), COALESCE(g.signature_png, ''), COALESCE(g.signature_png_enc, ''),
		COALESCE(g.restricted_at, '') <> '', r.date_from, r.date_to
		FROM guest g JOIN reservation r ON r.id = g.reservation_id `
}

func loadGuests(ctx context.Context, q Querier, dec Decrypter, sql string, args ...any) ([]GuestRow, error) {
	rows, err := q.Query(ctx, sql, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []GuestRow
	for rows.Next() {
		var g GuestRow
		var birthEnc, docEnc, streetEnc, cityEN, reasonEnc, sigEnc string
		var docPlain, streetPlain, cityPlain, reasonPlain, birthPlain, sigPlain string
		if err := rows.Scan(&g.ID, &g.ReservationID, &g.Surname, &g.FirstName, &birthPlain, &birthEnc,
			&g.Nationality, &g.DocType, &docPlain, &docEnc, &streetPlain, &streetEnc, &cityPlain, &cityEN,
			&g.ResCountry, &g.StayFrom, &g.StayTo, &g.FeeHostDecision, &reasonPlain, &reasonEnc, &sigPlain,
			&sigEnc, &g.Restricted, &g.ResFrom, &g.ResTo); err != nil {
			return nil, err
		}
		for _, f := range []struct {
			dst          *string
			token, plain string
		}{{&g.BirthDate, birthEnc, birthPlain}, {&g.DocNumber, docEnc, docPlain},
			{&g.ResStreet, streetEnc, streetPlain}, {&g.ResCity, cityEN, cityPlain},
			{&g.FeeHostReason, reasonEnc, reasonPlain}, {&g.SignaturePNG, sigEnc, sigPlain}} {
			v, err := pick(dec, f.token, f.plain)
			if err != nil {
				return nil, fmt.Errorf("stayfee: guest %d: %w", g.ID, err)
			}
			*f.dst = v
		}
		out = append(out, g)
	}
	return out, rows.Err()
}

// periodGuestsWhere is stay_fee._GUESTS_SQL: live guests of the apartment whose
// stay touches first..last (the demo stay owes no fee).
const periodGuestsWhere = `WHERE r.apartment_id = $1 AND r.status = 'active' AND g.archived_at IS NULL
	AND COALESCE(r.source, '') != 'demo'
	AND COALESCE(g.stay_from, r.date_from) <= $2 AND COALESCE(g.stay_to, r.date_to) >= $3`

// LoadPeriodGuests is the guest read of property_period, in its order.
func LoadPeriodGuests(ctx context.Context, q Querier, dec Decrypter, apartmentID int64, first, last time.Time) ([]GuestRow, error) {
	return loadGuests(ctx, q, dec, guestSelect(false)+periodGuestsWhere+
		` ORDER BY COALESCE(g.stay_from, r.date_from), g.id`, apartmentID, ISO(last), ISO(first))
}

// ActiveAdjustments is stay_fee_adjustment.active: the open corrections of one
// period key with their signed bed-days (remove is negative) and the net total.
func ActiveAdjustments(ctx context.Context, q Querier, dec Decrypter, apartmentID int64, key string) (int, []Adjustment, error) {
	rows, err := q.Query(ctx, `SELECT id, direction, mode, bed_days, COALESCE(reason_enc, '')
		FROM stay_fee_adjustment WHERE apartment_id = $1 AND period_key = $2 AND reversed_at IS NULL
		ORDER BY id`, apartmentID, key)
	if err != nil {
		return 0, nil, err
	}
	defer rows.Close()
	out := []Adjustment{}
	total := 0
	for rows.Next() {
		var a Adjustment
		var token string
		if err := rows.Scan(&a.ID, &a.Direction, &a.Mode, &a.BedDays, &token); err != nil {
			return 0, nil, err
		}
		a.Delta = a.BedDays
		if a.Direction == "remove" {
			a.Delta = -a.Delta
		}
		total += a.Delta
		if token != "" {
			if a.Reason, err = dec(token); err != nil {
				return 0, nil, err
			}
		}
		out = append(out, a)
	}
	return total, out, rows.Err()
}

// NetBedDays is stay_fee_adjustment.net_bed_days.
func NetBedDays(ctx context.Context, q Querier, dec Decrypter, apartmentID int64, key string) (int, error) {
	total, _, err := ActiveAdjustments(ctx, q, dec, apartmentID, key)
	return total, err
}

// Opts are the optional arguments of property_period and check.
type Opts struct {
	// LiveOnly false looks for a sealed filing that covers month first and
	// returns its frozen summary (the list page); true always calculates.
	LiveOnly bool
	// Cadence overrides the apartment's cadence when it is a valid one.
	Cadence string
	// Rate, when not nil, replaces the dated schedule by one flat rate.
	Rate *int
	// ScheduleToday is Python's date.today() in schedule_for (see ScheduleFor).
	ScheduleToday time.Time
}

// PropertyPeriod is stay_fee.property_period: nil when the property has no
// stay fee (and no sealed filing, unless LiveOnly).
func PropertyPeriod(ctx context.Context, q Querier, dec Decrypter, ap *Apartment, month time.Time, o Opts) (*Period, error) {
	if !o.LiveOnly {
		row, err := Covering(ctx, q, ap.ID, month)
		if err != nil {
			return nil, err
		}
		if row != nil {
			return FrozenSummary(row, ap, dec)
		}
	}
	if !IsActive(ap) {
		return nil, nil
	}
	chosen := ChooseCadence(ap, o.Cadence)
	first, last := PeriodBounds(chosen, month)
	in := PeriodInput{ScheduleToday: o.ScheduleToday}
	var err error
	if o.Rate == nil {
		if in.RateRows, err = loadRateRows(ctx, q, ap.ID); err != nil {
			return nil, err
		}
	}
	if in.Guests, err = LoadPeriodGuests(ctx, q, dec, ap.ID, first, last); err != nil {
		return nil, err
	}
	if _, in.Adjustments, err = ActiveAdjustments(ctx, q, dec, ap.ID, PeriodKey(chosen, month)); err != nil {
		return nil, err
	}
	return BuildPeriod(ap, month, chosen, o.Rate, in)
}

// UnsignedStays is stay_fee.unsigned_stays: guests in first..last with no
// signature yet. With the live period of the same property and dates its count
// is returned without a second read.
func UnsignedStays(ctx context.Context, q Querier, dec Decrypter, apartmentID int64, first, last time.Time, period *Period) (int, error) {
	if period != nil && !period.Frozen && period.First.Equal(first) && period.Last.Equal(last) &&
		period.Apartment != nil && period.Apartment.ID == apartmentID {
		return period.UnsignedGuests, nil
	}
	guests, err := LoadPeriodGuests(ctx, q, dec, apartmentID, first, last)
	if err != nil {
		return 0, err
	}
	n := 0
	for _, g := range guests {
		if !guestSignatureSettled(g) {
			n++
		}
	}
	return n, nil
}

// LoadIssueContext reads what ReportIssues needs: the payer and the foreign overlap.
func LoadIssueContext(ctx context.Context, q Querier, dec Decrypter, g *Group) (IssueContext, error) {
	var ic IssueContext
	var err error
	if ic.Entity, err = LoadEntity(ctx, q, dec, g.Anchor.LegalEntityID, false); err != nil {
		return ic, err
	}
	if !g.First.IsZero() {
		row, err := ForeignOverlap(ctx, q, g.Anchor.ID, g.Cadence, g.First)
		if err != nil {
			return ic, err
		}
		ic.ForeignOverlap = row != nil
	}
	return ic, nil
}

// Checked is stay_fee_auto.check's result: everything that blocks sealing a period.
type Checked struct {
	Period *Period
	Group  *Group
	Issues []string
	Key    string
}

// Check is stay_fee_auto.check: the live period, its group, the issues that
// block sealing (the unsigned-stays key last) and the filing period key.
func Check(ctx context.Context, q Querier, dec Decrypter, ap *Apartment, month, today time.Time, o Opts) (*Checked, error) {
	o.LiveOnly = true
	period, err := PropertyPeriod(ctx, q, dec, ap, month, o)
	if err != nil {
		return nil, err
	}
	group := ReportGroup(ap, month, period, o.Cadence)
	ic, err := LoadIssueContext(ctx, q, dec, group)
	if err != nil {
		return nil, err
	}
	issues := ReportIssues(group, today, ic)
	unsigned, err := UnsignedStays(ctx, q, dec, ap.ID, group.First, group.Last, period)
	if err != nil {
		return nil, err
	}
	if unsigned > 0 {
		issues = append(issues, "stay_fees.issue.unsigned")
	}
	return &Checked{Period: period, Group: group, Issues: issues, Key: PeriodKey(group.Cadence, group.First)}, nil
}

// RegisterFor is stay_fee.register_rows with the guests read from the database.
func RegisterFor(ctx context.Context, q Querier, dec Decrypter, p *Period) ([]RegisterRow, error) {
	ids := make([]int64, 0, len(p.Lines))
	for _, l := range p.Lines {
		ids = append(ids, l.GuestID)
	}
	byID := map[int64]GuestRow{}
	if len(ids) > 0 {
		guests, err := loadGuests(ctx, q, dec, guestSelect(true)+`WHERE g.id = ANY($1)`, ids)
		if err != nil {
			return nil, err
		}
		for _, g := range guests {
			byID[g.ID] = g
		}
	}
	return RegisterRows(p, byID)
}

// HlaseniFor is stay_fee.hlaseni(group, issued_on) with the payer read from the database.
func HlaseniFor(ctx context.Context, q Querier, dec Decrypter, g *Group, issuedOn time.Time) (*Hlaseni, error) {
	entity, err := LoadEntity(ctx, q, dec, g.Anchor.LegalEntityID, true)
	if err != nil {
		return nil, err
	}
	return MakeHlaseni(g, issuedOn, entity)
}
````

### Block 6: `go/internal/stayfee/golden_test.go` sha256 `14be605ce193cb33c8bcf9ed642bafbe75037e20eaceaaccab256e8d1e7b1821`

````go
package stayfee

// golden_test.go replays testdata/stay_fee_golden.json, written by
// App/scripts/stay_fee_golden.py from the real Python. TestGoldenHelpers pins
// the pure helpers. TestGoldenPure feeds the seed rows to the pure layer through
// an in-memory backend that does what the loader's SQL does. TestGoldenLoader
// loads the same seed into PostgreSQL and runs the real loader; it skips
// without UBYHOST_TEST_DATABASE_URL (CI sets it).

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// scheduleToday stands in for Python's date.today() in schedule_for: any day
// after the seeded periods gives the same figures.
var scheduleToday = Day(2026, 11, 13)

type golden struct {
	Seed            map[string][]map[string]any `json:"seed"`
	Cases           []goldenCase                `json:"cases"`
	ApartmentChecks []map[string]any            `json:"apartment_checks"`
	Helpers         map[string]any              `json:"helpers"`
}

type goldenCase struct {
	Name        string         `json:"name"`
	ApartmentID int64          `json:"apartment_id"`
	Month       string         `json:"month"`
	Today       string         `json:"today"`
	Cadence     *string        `json:"cadence"`
	Rate        *int           `json:"rate"`
	LiveOnly    bool           `json:"live_only"`
	Out         map[string]any `json:"out"`
}

func loadGolden(t *testing.T) *golden {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("testdata", "stay_fee_golden.json"))
	if err != nil {
		t.Fatal(err)
	}
	var g golden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return &g
}

// same compares got, through a JSON round trip, with the Python value.
func same(t *testing.T, name string, got, want any) {
	t.Helper()
	raw, err := json.Marshal(got)
	if err != nil {
		t.Fatalf("%s: marshal: %v", name, err)
	}
	var norm any
	if err := json.Unmarshal(raw, &norm); err != nil {
		t.Fatalf("%s: unmarshal: %v", name, err)
	}
	if !reflect.DeepEqual(norm, want) {
		w, _ := json.Marshal(want)
		t.Errorf("%s:\n got %s\nwant %s", name, raw, w)
	}
}

func day(t *testing.T, s string) time.Time {
	t.Helper()
	d, err := time.Parse("2006-01-02", s)
	if err != nil {
		t.Fatalf("date %q: %v", s, err)
	}
	return d
}

func isoOrNil(d time.Time, ok bool) any {
	if !ok {
		return nil
	}
	return ISO(d)
}

func nilIfEmpty(s string) any {
	if s == "" {
		return nil
	}
	return s
}

// --- seed rows ----------------------------------------------------------------

func sv(m map[string]any, k string) string {
	switch v := m[k].(type) {
	case nil:
		return ""
	case string:
		return v
	case float64:
		return strconv.FormatInt(int64(v), 10)
	case bool:
		return strconv.FormatBool(v)
	}
	return fmt.Sprint(m[k])
}

func iv(m map[string]any, k string) int64 {
	if v, ok := m[k].(float64); ok {
		return int64(v)
	}
	return 0
}

func seedApartment(m map[string]any) *Apartment {
	return &Apartment{
		ID: iv(m, "id"), LegalEntityID: iv(m, "legal_entity_id"), InternalName: sv(m, "internal_name"),
		StayFeeRateCZK: int(iv(m, "stay_fee_rate_czk")), StayFeeCadence: sv(m, "stay_fee_cadence"),
		StayFeeVS: sv(m, "stay_fee_vs"), AuthorityName: sv(m, "stay_fee_authority_name"),
		AuthorityAddress: sv(m, "stay_fee_authority_address"), AuthorityContact: sv(m, "stay_fee_authority_contact"),
		Payee: sv(m, "stay_fee_payee"), Instruction: sv(m, "stay_fee_instruction"),
		CouncilAccount: sv(m, "stay_fee_council_account"), CouncilIBAN: sv(m, "stay_fee_council_iban"),
		ScopeRule: sv(m, "stay_fee_scope_rule"), ScopeReference: sv(m, "stay_fee_scope_reference"),
		Collect: iv(m, "stay_fee_collect") != 0, GuestRails: sv(m, "stay_fee_guest_rails"),
		GuestDefaultRail: sv(m, "stay_fee_guest_default_rail"), RevolutLink: sv(m, "stay_fee_guest_revolut_link"),
		CashNote: sv(m, "stay_fee_guest_cash_note"), AddrObec: sv(m, "addr_obec"), CityEN: sv(m, "city_en"),
		AddrStreet: sv(m, "addr_street"), AddrHouseNo: sv(m, "addr_house_no"),
		AddrOrientNo: sv(m, "addr_orient_no"), AddrZip: sv(m, "addr_zip"), ArchivedAt: sv(m, "archived_at"),
	}
}

func seedFiling(m map[string]any) *FilingRow {
	return &FilingRow{
		ID: iv(m, "id"), ApartmentID: iv(m, "apartment_id"), PeriodKey: sv(m, "period_key"),
		Version: int(iv(m, "version")), Cadence: sv(m, "cadence"), RateCZK: int(iv(m, "rate_czk")),
		LiableDays: int(iv(m, "liable_days")), ExemptDays: int(iv(m, "exempt_days")),
		TotalDueCZK: int(iv(m, "total_due_czk")), TotalCollectedCZK: int(iv(m, "total_collected_czk")),
		PayloadEnc: sv(m, "payload"), CreatedAt: sv(m, "created_at"), SupersededAt: sv(m, "superseded_at"),
		SentAt: sv(m, "sent_at"), SentMessageID: sv(m, "sent_message_id"), PaidAt: sv(m, "paid_at"),
	}
}

func plain(token string) (string, error) { return token, nil }

// --- the two backends -----------------------------------------------------------

type backend interface {
	apartment(id int64) (*Apartment, error)
	entity(id int64, withSignature bool) (*Entity, error)
	propertyPeriod(ap *Apartment, month time.Time, o Opts) (*Period, error)
	check(ap *Apartment, month, today time.Time, o Opts) (*Checked, error)
	unsigned(apartmentID int64, first, last time.Time, p *Period) (int, error)
	register(p *Period) ([]RegisterRow, error)
	hlaseni(g *Group, issuedOn time.Time) (*Hlaseni, error)
	netBedDays(apartmentID int64, key string) (int, error)
	schedule(ap *Apartment) ([]RateStep, error)
	filingByID(id int64) (*FilingRow, error)
	latest(apartmentID int64, key string) (*FilingRow, error)
	covering(apartmentID int64, month time.Time) (*FilingRow, error)
	foreignOverlap(apartmentID int64, cadence string, month time.Time) (*FilingRow, error)
}

// memBackend answers from the seed with the pure layer, doing in Go what the
// loader's SQL does.
type memBackend struct {
	seed map[string][]map[string]any
}

func (m memBackend) apartment(id int64) (*Apartment, error) {
	for _, row := range m.seed["apartments"] {
		if iv(row, "id") == id {
			return seedApartment(row), nil
		}
	}
	return nil, ErrNotFound
}

func (m memBackend) entity(id int64, withSignature bool) (*Entity, error) {
	for _, row := range m.seed["legal_entities"] {
		if id != 0 && iv(row, "id") == id {
			e := &Entity{ID: id, Name: sv(row, "name"), Seat: sv(row, "seat"), ICO: sv(row, "ico"),
				ContactEmail: sv(row, "contact_email"), IBAN: sv(row, "iban"), BankAccount: sv(row, "bank_account"),
				SignatureName: sv(row, "signature_name")}
			if withSignature {
				e.SignaturePNG = sv(row, "signature_png")
			}
			return e, nil
		}
	}
	return nil, nil
}

func (m memBackend) guests(match func(g GuestRow, res map[string]any) bool) []GuestRow {
	res := map[int64]map[string]any{}
	for _, r := range m.seed["reservations"] {
		res[iv(r, "id")] = r
	}
	var out []GuestRow
	for _, row := range m.seed["guests"] {
		r := res[iv(row, "reservation_id")]
		g := GuestRow{ID: iv(row, "id"), ReservationID: iv(row, "reservation_id"), Surname: sv(row, "surname"),
			FirstName: sv(row, "first_name"), BirthDate: sv(row, "birth_date"), Nationality: sv(row, "nationality"),
			DocType: sv(row, "doc_type"), DocNumber: sv(row, "doc_number"), ResStreet: sv(row, "res_street"),
			ResCity: sv(row, "res_city"), ResCountry: sv(row, "res_country"), StayFrom: sv(row, "stay_from"),
			StayTo: sv(row, "stay_to"), FeeHostDecision: sv(row, "fee_host_decision"),
			FeeHostReason: sv(row, "fee_host_reason"), SignaturePNG: sv(row, "signature_png"),
			Restricted: sv(row, "restricted_at") != "", ResFrom: sv(r, "date_from"), ResTo: sv(r, "date_to")}
		if sv(row, "archived_at") != "" && match != nil {
			continue
		}
		if match == nil || match(g, r) {
			out = append(out, g)
		}
	}
	return out
}

// periodGuests is periodGuestsWhere plus its ORDER BY.
func (m memBackend) periodGuests(apartmentID int64, first, last time.Time) []GuestRow {
	out := m.guests(func(g GuestRow, r map[string]any) bool {
		from, to := g.StayFrom, g.StayTo
		if from == "" {
			from = g.ResFrom
		}
		if to == "" {
			to = g.ResTo
		}
		return iv(r, "apartment_id") == apartmentID && sv(r, "status") == "active" && sv(r, "source") != "demo" &&
			from <= ISO(last) && to >= ISO(first)
	})
	start := func(g GuestRow) string {
		if g.StayFrom != "" {
			return g.StayFrom
		}
		return g.ResFrom
	}
	sort.SliceStable(out, func(i, j int) bool {
		if a, b := start(out[i]), start(out[j]); a != b {
			return a < b
		}
		return out[i].ID < out[j].ID
	})
	return out
}

func (m memBackend) adjustments(apartmentID int64, key string) (int, []Adjustment) {
	out := []Adjustment{}
	total := 0
	for _, row := range m.seed["adjustments"] {
		if iv(row, "apartment_id") != apartmentID || sv(row, "period_key") != key || sv(row, "reversed_at") != "" {
			continue
		}
		a := Adjustment{ID: iv(row, "id"), Direction: sv(row, "direction"), Mode: sv(row, "mode"),
			BedDays: int(iv(row, "bed_days")), Reason: sv(row, "reason")}
		a.Delta = a.BedDays
		if a.Direction == "remove" {
			a.Delta = -a.Delta
		}
		total += a.Delta
		out = append(out, a)
	}
	sort.SliceStable(out, func(i, j int) bool { return out[i].ID < out[j].ID })
	return total, out
}

func (m memBackend) rateRows(apartmentID int64) []RateRow {
	var out []RateRow
	for _, row := range m.seed["rates"] {
		if iv(row, "apartment_id") == apartmentID {
			out = append(out, RateRow{EffectiveFrom: sv(row, "effective_from"), RateCZK: int(iv(row, "rate_czk"))})
		}
	}
	sort.SliceStable(out, func(i, j int) bool { return out[i].EffectiveFrom < out[j].EffectiveFrom })
	return out
}

func (m memBackend) propertyPeriod(ap *Apartment, month time.Time, o Opts) (*Period, error) {
	if !o.LiveOnly {
		row, err := m.covering(ap.ID, month)
		if err != nil {
			return nil, err
		}
		if row != nil {
			return FrozenSummary(row, ap, plain)
		}
	}
	chosen := ChooseCadence(ap, o.Cadence)
	first, last := PeriodBounds(chosen, month)
	in := PeriodInput{ScheduleToday: o.ScheduleToday, Guests: m.periodGuests(ap.ID, first, last)}
	if o.Rate == nil {
		in.RateRows = m.rateRows(ap.ID)
	}
	_, in.Adjustments = m.adjustments(ap.ID, PeriodKey(chosen, month))
	return BuildPeriod(ap, month, chosen, o.Rate, in)
}

func (m memBackend) check(ap *Apartment, month, today time.Time, o Opts) (*Checked, error) {
	o.LiveOnly = true
	period, err := m.propertyPeriod(ap, month, o)
	if err != nil {
		return nil, err
	}
	group := ReportGroup(ap, month, period, o.Cadence)
	var ic IssueContext
	if ic.Entity, err = m.entity(ap.LegalEntityID, false); err != nil {
		return nil, err
	}
	row, err := m.foreignOverlap(ap.ID, group.Cadence, group.First)
	if err != nil {
		return nil, err
	}
	ic.ForeignOverlap = row != nil
	issues := ReportIssues(group, today, ic)
	unsigned, err := m.unsigned(ap.ID, group.First, group.Last, period)
	if err != nil {
		return nil, err
	}
	if unsigned > 0 {
		issues = append(issues, "stay_fees.issue.unsigned")
	}
	return &Checked{Period: period, Group: group, Issues: issues, Key: PeriodKey(group.Cadence, group.First)}, nil
}

func (m memBackend) unsigned(apartmentID int64, first, last time.Time, p *Period) (int, error) {
	if p != nil && !p.Frozen && p.First.Equal(first) && p.Last.Equal(last) && p.Apartment.ID == apartmentID {
		return p.UnsignedGuests, nil
	}
	n := 0
	for _, g := range m.periodGuests(apartmentID, first, last) {
		if !guestSignatureSettled(g) {
			n++
		}
	}
	return n, nil
}

func (m memBackend) register(p *Period) ([]RegisterRow, error) {
	byID := map[int64]GuestRow{}
	for _, g := range m.guests(nil) {
		byID[g.ID] = g
	}
	return RegisterRows(p, byID)
}

func (m memBackend) hlaseni(g *Group, issuedOn time.Time) (*Hlaseni, error) {
	e, err := m.entity(g.Anchor.LegalEntityID, true)
	if err != nil {
		return nil, err
	}
	return MakeHlaseni(g, issuedOn, e)
}

func (m memBackend) netBedDays(apartmentID int64, key string) (int, error) {
	total, _ := m.adjustments(apartmentID, key)
	return total, nil
}

func (m memBackend) schedule(ap *Apartment) ([]RateStep, error) {
	return ScheduleFor(ap.StayFeeRateCZK, m.rateRows(ap.ID), scheduleToday)
}

func (m memBackend) filings() []*FilingRow {
	var out []*FilingRow
	for _, row := range m.seed["filings"] {
		out = append(out, seedFiling(row))
	}
	return out
}

func (m memBackend) filingByID(id int64) (*FilingRow, error) {
	for _, f := range m.filings() {
		if f.ID == id {
			return f, nil
		}
	}
	return nil, ErrNotFound
}

func (m memBackend) active(apartmentID int64, keys []string) *FilingRow {
	var best *FilingRow
	for _, f := range m.filings() {
		if f.ApartmentID != apartmentID || f.SupersededAt != "" || !inList(keys, f.PeriodKey) {
			continue
		}
		if best == nil || f.CreatedAt > best.CreatedAt || (f.CreatedAt == best.CreatedAt && f.ID > best.ID) {
			best = f
		}
	}
	return best
}

func (m memBackend) latest(apartmentID int64, key string) (*FilingRow, error) {
	var best *FilingRow
	for _, f := range m.filings() {
		if f.ApartmentID == apartmentID && f.PeriodKey == key && f.SupersededAt == "" &&
			(best == nil || f.Version > best.Version) {
			best = f
		}
	}
	return best, nil
}

func (m memBackend) covering(apartmentID int64, month time.Time) (*FilingRow, error) {
	return m.active(apartmentID, OverlapKeys("monthly", month)), nil
}

func (m memBackend) foreignOverlap(apartmentID int64, cadence string, month time.Time) (*FilingRow, error) {
	own := PeriodKey(cadence, month)
	var keys []string
	for _, k := range OverlapKeys(cadence, month) {
		if k != own {
			keys = append(keys, k)
		}
	}
	return m.active(apartmentID, keys), nil
}

// pgBackend runs the real loader.
type pgBackend struct {
	ctx context.Context
	q   Querier
}

func (p pgBackend) apartment(id int64) (*Apartment, error) { return LoadApartment(p.ctx, p.q, id) }
func (p pgBackend) entity(id int64, withSignature bool) (*Entity, error) {
	return LoadEntity(p.ctx, p.q, plain, id, withSignature)
}
func (p pgBackend) propertyPeriod(ap *Apartment, month time.Time, o Opts) (*Period, error) {
	return PropertyPeriod(p.ctx, p.q, plain, ap, month, o)
}
func (p pgBackend) check(ap *Apartment, month, today time.Time, o Opts) (*Checked, error) {
	return Check(p.ctx, p.q, plain, ap, month, today, o)
}
func (p pgBackend) unsigned(apartmentID int64, first, last time.Time, period *Period) (int, error) {
	return UnsignedStays(p.ctx, p.q, plain, apartmentID, first, last, period)
}
func (p pgBackend) register(period *Period) ([]RegisterRow, error) {
	return RegisterFor(p.ctx, p.q, plain, period)
}
func (p pgBackend) hlaseni(g *Group, issuedOn time.Time) (*Hlaseni, error) {
	return HlaseniFor(p.ctx, p.q, plain, g, issuedOn)
}
func (p pgBackend) netBedDays(apartmentID int64, key string) (int, error) {
	return NetBedDays(p.ctx, p.q, plain, apartmentID, key)
}
func (p pgBackend) schedule(ap *Apartment) ([]RateStep, error) {
	return LoadSchedule(p.ctx, p.q, ap, scheduleToday)
}
func (p pgBackend) filingByID(id int64) (*FilingRow, error) {
	return queryFiling(p.ctx, p.q, `SELECT `+filingColumns+` FROM stay_fee_filing WHERE id = $1`, id)
}
func (p pgBackend) latest(apartmentID int64, key string) (*FilingRow, error) {
	return Latest(p.ctx, p.q, apartmentID, key)
}
func (p pgBackend) covering(apartmentID int64, month time.Time) (*FilingRow, error) {
	return Covering(p.ctx, p.q, apartmentID, month)
}
func (p pgBackend) foreignOverlap(apartmentID int64, cadence string, month time.Time) (*FilingRow, error) {
	return ForeignOverlap(p.ctx, p.q, apartmentID, cadence, month)
}

// --- views: the Python dict shapes of the golden ---------------------------------

func lineView(lines []Line) []Line {
	out := make([]Line, len(lines))
	for i, l := range lines {
		if l.RateNights == nil {
			l.RateNights = [][2]int{}
		}
		out[i] = l
	}
	return out
}

func periodView(p *Period) any {
	if p == nil {
		return nil
	}
	v := map[string]any{"cadence": p.Cadence, "first": ISO(p.First), "last": ISO(p.Last), "label": p.Label,
		"rate_czk": p.RateCZK, "lines": lineView(p.Lines), "liable_nights": p.LiableNights,
		"exempt_nights": p.ExemptNights, "total_czk": p.TotalCZK, "rate_segments": p.RateSegments,
		"period_key": p.PeriodKey, "adjustments": []Adjustment{}}
	if p.Frozen {
		v["frozen"] = true
		v["filing_id"] = p.FilingID
		v["version"] = p.Version
		v["total_collected_czk"] = p.TotalCollectedCZK
		v["sent_at"] = nilIfEmpty(p.SentAt)
		v["paid_at"] = nilIfEmpty(p.PaidAt)
		v["sent_message_id"] = nilIfEmpty(p.SentMessageID)
		return v
	}
	v["guest_liable_nights"] = p.GuestLiableNights
	v["adjustment_bed_days"] = p.AdjustmentBedDays
	v["adjustments"] = p.Adjustments
	v["unsigned_guests"] = p.UnsignedGuests
	return v
}

func groupView(g *Group) any {
	periods := []any{}
	for _, p := range g.Periods {
		periods = append(periods, periodView(p))
	}
	return map[string]any{"cadence": g.Cadence, "first": ISO(g.First), "last": ISO(g.Last), "label": g.Label,
		"vs": g.VS, "liable_nights": g.LiableNights, "exempt_nights": g.ExemptNights, "total_czk": g.TotalCZK,
		"periods": periods}
}

func filingID(f *FilingRow) any {
	if f == nil {
		return nil
	}
	return f.ID
}

// --- the replay -------------------------------------------------------------------

func runCases(t *testing.T, g *golden, b backend) {
	for _, c := range g.Cases {
		t.Run(c.Name, func(t *testing.T) {
			ap, err := b.apartment(c.ApartmentID)
			if err != nil {
				t.Fatal(err)
			}
			month, today := day(t, c.Month), day(t, c.Today)
			o := Opts{LiveOnly: c.LiveOnly, Rate: c.Rate, ScheduleToday: scheduleToday}
			if c.Cadence != nil {
				o.Cadence = *c.Cadence
			}
			period, err := b.propertyPeriod(ap, month, o)
			if err != nil {
				t.Fatal(err)
			}
			same(t, "period", periodView(period), c.Out["period"])
			if !c.LiveOnly {
				return
			}
			checked, err := b.check(ap, month, today, o)
			if err != nil {
				t.Fatal(err)
			}
			grp := checked.Group
			same(t, "group", groupView(grp), c.Out["group"])
			same(t, "issues", checked.Issues, c.Out["issues"])
			same(t, "key", checked.Key, c.Out["key"])
			n, err := b.unsigned(ap.ID, grp.First, grp.Last, nil)
			if err != nil {
				t.Fatal(err)
			}
			same(t, "unsigned_query", n, c.Out["unsigned_query"])
			if n, err = b.unsigned(ap.ID, grp.First, grp.Last, checked.Period); err != nil {
				t.Fatal(err)
			}
			same(t, "unsigned_shortcut", n, c.Out["unsigned_shortcut"])
			same(t, "payment", PaymentDetails(grp), c.Out["payment"])
			rows, csv := []RegisterRow{}, ""
			if checked.Period != nil {
				if rows, err = b.register(checked.Period); err != nil {
					t.Fatal(err)
				}
				csv = base64.StdEncoding.EncodeToString(RegisterCSV(rows))
			}
			same(t, "register_rows", rows, c.Out["register_rows"])
			same(t, "register_csv_b64", csv, c.Out["register_csv_b64"])
			h, err := b.hlaseni(grp, today)
			if err != nil && ap.LegalEntityID != 0 {
				t.Fatal(err)
			}
			if h == nil {
				same(t, "hlaseni", nil, c.Out["hlaseni"])
			} else {
				same(t, "hlaseni", h, c.Out["hlaseni"])
			}
		})
	}
}

func runApartmentChecks(t *testing.T, g *golden, b backend) {
	for _, want := range g.ApartmentChecks {
		id := iv(want, "apartment_id")
		ap, err := b.apartment(id)
		if err != nil {
			t.Fatal(err)
		}
		e, err := b.entity(ap.LegalEntityID, false)
		if err != nil {
			t.Fatal(err)
		}
		account, payee := PayoutAccount(e)
		got := map[string]any{"apartment_id": id, "is_active": IsActive(ap), "cadence_of": CadenceOf(ap),
			"vs_of": VSOf(ap), "usable_rail_keys": UsableRailKeys(ap, e), "payout_account": []string{account, payee},
			"no_pay_way_on": NoPayWay(ap, e, true), "no_pay_way_off": NoPayWay(ap, e, false)}
		same(t, fmt.Sprintf("apartment_checks %d", id), got, want)
	}
}

func list(t *testing.T, h map[string]any, key string) [][]any {
	t.Helper()
	raw, ok := h[key].([]any)
	if !ok {
		t.Fatalf("helpers.%s missing", key)
	}
	out := make([][]any, 0, len(raw))
	for _, r := range raw {
		if row, ok := r.([]any); ok {
			out = append(out, row)
		} else {
			out = append(out, []any{r})
		}
	}
	return out
}

func str(v any) string {
	s, _ := v.(string)
	return s
}

func num(v any) int {
	f, _ := v.(float64)
	return int(f)
}

// runDBHelpers replays the helpers that read rows: adjustments, filings, schedules.
func runDBHelpers(t *testing.T, g *golden, b backend) {
	h := g.Helpers
	for _, r := range list(t, h, "net_bed_days") {
		n, err := b.netBedDays(int64(num(r[0])), str(r[1]))
		if err != nil {
			t.Fatal(err)
		}
		same(t, fmt.Sprint("net_bed_days ", r[:2]), n, r[2])
	}
	for _, raw := range h["filing_reads"].([]any) {
		r := raw.(map[string]any)
		apt := iv(r, "apartment_id")
		var f *FilingRow
		var err error
		switch call := str(r["call"]); call {
		case "latest":
			f, err = b.latest(apt, str(r["key"]))
		case "covering":
			f, err = b.covering(apt, day(t, str(r["key"])))
		default:
			f, err = b.foreignOverlap(apt, strings.TrimPrefix(call, "foreign_overlap:"), day(t, str(r["key"])))
		}
		if err != nil {
			t.Fatal(err)
		}
		same(t, fmt.Sprint("filing_reads ", r), filingID(f), r["id"])
	}
	for _, raw := range h["correction_rate"].([]any) {
		r := raw.(map[string]any)
		f, err := b.filingByID(iv(r, "filing_id"))
		if err != nil {
			t.Fatal(err)
		}
		ap, err := b.apartment(f.ApartmentID)
		if err != nil {
			t.Fatal(err)
		}
		schedule, err := b.schedule(ap)
		if err != nil {
			t.Fatal(err)
		}
		rate, err := CorrectionRateFor(schedule, f)
		if err != nil {
			t.Fatal(err)
		}
		same(t, fmt.Sprint("correction_rate ", r["filing_id"]), rate, r["rate"])
	}
	for _, raw := range h["schedule_uniform"].([]any) {
		r := raw.(map[string]any)
		ap, err := b.apartment(iv(r, "apartment_id"))
		if err != nil {
			t.Fatal(err)
		}
		schedule, err := b.schedule(ap)
		if err != nil {
			t.Fatal(err)
		}
		first, last := day(t, str(r["first"])), day(t, str(r["last"]))
		got := map[string]any{"apartment_id": ap.ID, "first": r["first"], "last": r["last"],
			"uniform": IsUniform(schedule, first, last), "rate_last": RateOn(schedule, last)}
		same(t, fmt.Sprint("schedule_uniform ", r), got, r)
	}
}

func TestGoldenPure(t *testing.T) {
	g := loadGolden(t)
	b := memBackend{seed: g.Seed}
	runCases(t, g, b)
	runApartmentChecks(t, g, b)
	runDBHelpers(t, g, b)
}

func TestGoldenHelpers(t *testing.T) {
	g := loadGolden(t)
	h := g.Helpers
	for _, r := range list(t, h, "shift_month") {
		same(t, fmt.Sprint("shift_month ", r), ISO(ShiftMonth(day(t, str(r[0])), num(r[1]))), r[2])
	}
	for _, r := range list(t, h, "previous_month") {
		same(t, fmt.Sprint("previous_month ", r), ISO(PreviousMonth(day(t, str(r[0])))), r[1])
	}
	for _, r := range list(t, h, "period_bounds") {
		a, b := PeriodBounds(str(r[0]), day(t, str(r[1])))
		same(t, fmt.Sprint("period_bounds ", r), []string{ISO(a), ISO(b)}, r[2])
	}
	for _, r := range list(t, h, "month_key") {
		same(t, fmt.Sprint("month_key ", r), MonthKey(day(t, str(r[0]))), r[1])
	}
	for _, r := range list(t, h, "period_label_cs") {
		same(t, fmt.Sprint("period_label_cs ", r), PeriodLabelCS(str(r[0]), day(t, str(r[1]))), r[2])
	}
	for _, r := range list(t, h, "period_complete") {
		got := PeriodComplete(str(r[0]), day(t, str(r[1])), day(t, str(r[2])))
		same(t, fmt.Sprint("period_complete ", r), got, r[3])
	}
	for _, r := range list(t, h, "parse_month") {
		same(t, fmt.Sprintf("parse_month %q", r[0]), isoOrNil(ParseMonth(str(r[0]))), r[1])
	}
	for _, r := range list(t, h, "parse_czk_int") {
		n, ok := ParseCZKInt(str(r[0]))
		var got any
		if ok {
			got = n
		}
		same(t, fmt.Sprintf("parse_czk_int %q", r[0]), got, r[1])
	}
	for _, r := range list(t, h, "clamp_rate") {
		same(t, fmt.Sprintf("clamp_rate %q", r[0]), ClampRate(str(r[0])), r[1])
	}
	for _, r := range list(t, h, "format_czk") {
		same(t, fmt.Sprint("format_czk ", r[0]), FormatCZK(num(r[0])), r[1])
	}
	for _, r := range list(t, h, "counted_days_in") {
		got := CountedDaysIn(day(t, str(r[0])), day(t, str(r[1])), day(t, str(r[2])), day(t, str(r[3])))
		same(t, fmt.Sprint("counted_days_in ", r), got, r[4])
	}
	for _, r := range list(t, h, "obec_key") {
		same(t, fmt.Sprintf("obec_key %q", r[0]), ObecKey(str(r[0])), r[1])
	}
	for _, r := range list(t, h, "fold_text") {
		same(t, fmt.Sprintf("fold_text %q", r[0]), FoldText(str(r[0])), r[1])
	}
	for _, r := range list(t, h, "conservative_birth") {
		same(t, fmt.Sprintf("conservative_birth %q", r[0]), isoOrNil(ConservativeBirth(str(r[0]))), r[1])
	}
	for _, r := range list(t, h, "default_doc_type") {
		same(t, fmt.Sprintf("default_doc_type %q", r[0]), DefaultDocType(str(r[0])), r[1])
	}
	for _, r := range list(t, h, "period_key") {
		same(t, fmt.Sprint("period_key ", r), PeriodKey(str(r[0]), day(t, str(r[1]))), r[2])
	}
	for _, r := range list(t, h, "overlap_keys") {
		same(t, fmt.Sprint("overlap_keys ", r), OverlapKeys(str(r[0]), day(t, str(r[1]))), r[2])
	}
	for _, r := range list(t, h, "period_anchor") {
		var got any = "error"
		if a, err := PeriodAnchor(str(r[0])); err == nil {
			got = ISO(a)
		}
		same(t, fmt.Sprint("period_anchor ", r[0]), got, r[1])
	}
	for _, r := range list(t, h, "spayd") {
		same(t, fmt.Sprint("spayd ", r[:4]), SPAYD(str(r[0]), num(r[1]), str(r[2]), str(r[3])), r[4])
	}
}

// TestPackageConstants pins the exported constants against stay_fee.py.
func TestPackageConstants(t *testing.T) {
	same(t, "decisions", Decisions, []any{"exempt", "charge"})
	same(t, "exempt_categories", ExemptCategories, []any{"disability", "diplomat", "local_rule", "other_statutory"})
	same(t, "scope_rules", ScopeRules, []any{"calendar_days", "nights"})
	if ReasonMax != 120 || MaxRateCZK != 50 || ThresholdNights != 60 {
		t.Errorf("constants: %d %d %d", ReasonMax, MaxRateCZK, ThresholdNights)
	}
}

// --- PostgreSQL --------------------------------------------------------------------

// testPool is a copy of ical's testPool: a fresh database with the PostgreSQL
// migrations applied. It skips without UBYHOST_TEST_DATABASE_URL.
func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_stayfee_%d", time.Now().UnixNano())
	admin, err := pgx.Connect(ctx, base)
	if err != nil {
		t.Fatal(err)
	}
	_, err = admin.Exec(ctx, "CREATE DATABASE "+name)
	_ = admin.Close(ctx)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		c, err := pgx.Connect(context.Background(), base)
		if err != nil {
			t.Errorf("admin connect for cleanup failed")
			return
		}
		defer c.Close(context.Background())
		if _, err := c.Exec(context.Background(), "DROP DATABASE IF EXISTS "+name+" WITH (FORCE)"); err != nil {
			t.Errorf("drop test database: %v", err)
		}
	})
	cfg, err := pgxpool.ParseConfig(base)
	if err != nil {
		t.Fatal(err)
	}
	cfg.ConnConfig.Database = name
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(pool.Close)
	files, err := filepath.Glob("../../../App/migrations_pg/*.sql")
	if err != nil || len(files) == 0 {
		t.Fatalf("no migrations found: %v", err)
	}
	sort.Strings(files)
	for _, f := range files {
		raw, err := os.ReadFile(f)
		if err != nil {
			t.Fatal(err)
		}
		up := string(raw)
		if i := strings.Index(up, "-- +goose Up"); i >= 0 {
			up = up[i+len("-- +goose Up"):]
		}
		if i := strings.Index(up, "-- +goose Down"); i >= 0 {
			up = up[:i]
		}
		if _, err := pool.Exec(ctx, up); err != nil {
			t.Fatalf("%s: %v", filepath.Base(f), err)
		}
	}
	return pool
}

// insert writes one seed row; renames maps a seed key to its column ("" drops
// it) and extra adds columns. Encrypted columns get the plain text, which the
// plain Decrypter returns as is (the golden script encrypts them in SQLite).
func insert(t *testing.T, pool *pgxpool.Pool, table string, row map[string]any, renames map[string]string,
	extra map[string]any) {
	t.Helper()
	cols, args, marks := []string{}, []any{}, []string{}
	add := func(col string, v any) {
		if f, ok := v.(float64); ok {
			v = int64(f)
		}
		cols = append(cols, col)
		args = append(args, v)
		marks = append(marks, "$"+strconv.Itoa(len(args)))
	}
	keys := make([]string, 0, len(row))
	for k := range row {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		col := k
		if r, ok := renames[k]; ok {
			col = r
		}
		if col != "" {
			add(col, row[k])
		}
	}
	for k, v := range extra {
		add(k, v)
	}
	sql := "INSERT INTO " + table + " (" + strings.Join(cols, ", ") + ") VALUES (" + strings.Join(marks, ", ") + ")"
	if _, err := pool.Exec(context.Background(), sql, args...); err != nil {
		t.Fatalf("%s: %v", table, err)
	}
}

func TestGoldenLoader(t *testing.T) {
	pool := testPool(t)
	g := loadGolden(t)
	stamp := "2026-09-01T00:00:00+00:00"
	for _, r := range g.Seed["legal_entities"] {
		insert(t, pool, "legal_entity", r, map[string]string{"signature_png": "signature_png_enc"},
			map[string]any{"created_at": stamp})
	}
	for _, r := range g.Seed["apartments"] {
		insert(t, pool, "apartment", r, nil, map[string]any{"created_at": stamp})
	}
	for _, r := range g.Seed["rates"] {
		insert(t, pool, "stay_fee_rate", r, nil, map[string]any{"created_at": stamp})
	}
	for _, r := range g.Seed["reservations"] {
		insert(t, pool, "reservation", r, nil, map[string]any{"uid": fmt.Sprintf("uid-%d", iv(r, "id")),
			"created_at": stamp, "updated_at": stamp})
	}
	for _, r := range g.Seed["guests"] {
		insert(t, pool, "guest", r, nil, map[string]any{"created_at": stamp, "updated_at": stamp})
	}
	for _, r := range g.Seed["adjustments"] {
		insert(t, pool, "stay_fee_adjustment", r, map[string]string{"reason": "reason_enc"},
			map[string]any{"created_at": stamp})
	}
	for _, r := range g.Seed["filings"] {
		insert(t, pool, "stay_fee_filing", r, map[string]string{"payload": "payload_enc"}, nil)
	}
	b := pgBackend{ctx: context.Background(), q: pool}
	runCases(t, g, b)
	runApartmentChecks(t, g, b)
	runDBHelpers(t, g, b)
}

func TestFernetDecrypter(t *testing.T) {
	keys, err := secure.LoadDataKeys(func(k string) string {
		if k == "UBYHOST_SECRET_KEY" {
			return "golden-secret-key-not-for-real-use"
		}
		return ""
	})
	if err != nil {
		t.Skipf("data keys: %v", err)
	}
	token, err := keys.EncryptString("Host not recorded")
	if err != nil {
		t.Fatal(err)
	}
	dec := FernetDecrypter(keys)
	if got, err := dec(token); err != nil || got != "Host not recorded" {
		t.Errorf("decrypt: %q %v", got, err)
	}
	if _, err := dec("not-a-token"); err == nil {
		t.Error("a bad token must be an error")
	}
}
````
