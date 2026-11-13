"""Write go/internal/stayfeemail/testdata/stay_fee_job_golden.json from the real Python.

Dev tool, never run in production. Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/stay_fee_job_golden.py

It seeds a throwaway SQLite database with the rows in seed(), then runs the daily
stay_fee_mail job (stay_fee_auto.run, then stay_fee.reconcile_all_no_pay_way) three
times with a fixed clock and a fake PDF (stay_fee_remittance_pdf.render returns
FAKE_PDF and records its input), then the direct writes of WRITES (adjustment add
and reverse, a correction, and the three refusals of stay_fee_filing.save). After
each step it records the counts and the stay_fee_filing (decrypted), adjustment,
email_outbox, alert and audit rows. go/internal/stayfeemail/job_test.go replays the
same seed and steps on PostgreSQL and compares. Invented data only (example.test).
"""

from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "stayfeemail" / "testdata" / "stay_fee_job_golden.json"

OLD = "2026-09-01T00:00:00+00:00"
SIG = "data:image/png;base64,AAAA"
IBAN = "CZ6508000000192000145399"
FAKE_PDF = b"%PDF-1.4\n% stay fee job golden fake\n"

# One step per job run: the Prague date the job sees, the UTC clock, and the
# SQL applied to the database just before it (portable to SQLite and Postgres).
RUNS = [
    {"name": "first", "today": "2026-10-05", "now": "2026-10-05T05:00:00+00:00", "before": []},
    {"name": "again", "today": "2026-10-05", "now": "2026-10-05T05:30:00+00:00", "before": []},
    {"name": "late", "today": "2026-10-20", "now": "2026-10-20T05:00:00+00:00",
     "before": ["UPDATE apartment SET stay_fee_guest_rails = 'cash' WHERE id = 8"]},
]
WRITES_NOW = "2026-10-20T06:00:00+00:00"
WRITES_TODAY = "2026-10-20"


def user(uid, name, role="host", **kw):
    row = {"id": uid, "username": name, "password_hash": "x", "role": role,
           "stay_fee_emails_opt_out": 0, "deletion_due_at": None}
    row.update(kw)
    return row


def entity(eid, name, contact, **kw):
    row = {"id": eid, "name": name, "seat": "Praha", "ico": "12345678", "contact_email": contact,
           "iban": "", "bank_account": ""}
    row.update(kw)
    return row


def apartment(aid, owner, ent, name, rate, vs, **kw):
    row = {"id": aid, "owner_user_id": owner, "legal_entity_id": ent, "internal_name": name,
           "stay_fee_rate_czk": rate, "stay_fee_cadence": "monthly", "stay_fee_vs": vs,
           "stay_fee_authority_name": "Obec %d" % aid, "stay_fee_authority_databox": "",
           "stay_fee_council_account": "", "stay_fee_council_iban": "",
           "stay_fee_collect": 0, "stay_fee_guest_rails": "", "addr_obec": "Praha 1",
           "addr_street": "Nová", "addr_house_no": str(aid), "addr_zip": "11000", "archived_at": None}
    row.update(kw)
    return row


def reservation(rid, aid, start, end):
    return {"id": rid, "apartment_id": aid, "date_from": start, "date_to": end,
            "status": "active", "source": "ical"}


def guest(gid, rid, surname, first, **kw):
    row = {"id": gid, "reservation_id": rid, "surname": surname, "first_name": first,
           "birth_date": "10101980", "nationality": "DEU", "doc_number": "X%07d" % gid,
           "res_street": "Hauptstraße 1", "res_city": "Berlin", "res_country": "DEU",
           "signature_png": SIG}
    row.update(kw)
    return row


def seed():
    users = [
        user(1, "host1"),
        user(2, "optout", stay_fee_emails_opt_out=1),
        user(3, "leaving", deletion_due_at="2026-11-01T00:00:00+00:00"),
        user(4, "host4"),
        user(5, "admin", role="admin"),
    ]
    entities = [
        entity(1, "Host Alpha s.r.o.", "Alpha <ALPHA@Example.test>", iban=IBAN),
        entity(2, "Beta NoMail", ""),
        entity(3, "Gamma NoAccount", "gamma@example.test"),
        entity(4, "Josef Novák (demo)", "demo@example.test", iban=IBAN),
    ]
    paid = {"stay_fee_council_iban": IBAN, "stay_fee_council_account": "123456789/0800"}
    apts = [
        apartment(1, 1, 1, "Clean Monthly", 20, "101", stay_fee_authority_databox="abc1234",
                  stay_fee_collect=1, stay_fee_guest_rails="cash", **paid),
        apartment(2, 1, 1, "Blocked Monthly", 20, ""),
        apartment(3, 1, 1, "Already Sealed", 20, "103", **paid),
        apartment(4, 1, 1, "Quarterly Řeka & <Co>", 15, "104", stay_fee_cadence="quarterly"),
        apartment(5, 1, 1, "Archived", 20, "105", stay_fee_collect=1, archived_at=OLD),
        apartment(6, 1, 1, "Vinohrady Studio (demo)", 20, "106", **paid),
        apartment(7, 1, 1, "Resend Zero", 20, "107", **paid),
        apartment(8, 1, 3, "No Pay Way", 20, "108", stay_fee_collect=1, stay_fee_guest_rails="iban"),
        apartment(9, 1, 1, "Inactive", 0, "109", stay_fee_collect=1, stay_fee_guest_rails="iban"),
        apartment(10, 2, 1, "Opt Out", 20, "110", **paid),
        apartment(11, 3, 1, "Deleting", 20, "111", **paid),
        apartment(12, 4, 2, "No Contact", 20, "112"),
        apartment(13, 1, 4, "Demo Entity Flat", 20, "113", **paid),
    ]
    res = [
        reservation(101, 1, "2026-09-10", "2026-09-13"),
        reservation(102, 1, "2026-09-28", "2026-10-02"),
        reservation(201, 2, "2026-09-05", "2026-09-07"),
        reservation(301, 3, "2026-09-05", "2026-09-07"),
        reservation(401, 4, "2026-08-01", "2026-08-05"),
        reservation(402, 4, "2026-09-20", "2026-09-22"),
        reservation(601, 6, "2026-09-05", "2026-09-07"),
        reservation(1001, 10, "2026-09-05", "2026-09-07"),
        reservation(1101, 11, "2026-09-05", "2026-09-07"),
        reservation(1201, 12, "2026-09-05", "2026-09-07"),
        reservation(1301, 13, "2026-09-05", "2026-09-07"),
    ]
    guests = [
        guest(101, 101, "Novák", "Jan", res_city="Brno"),
        guest(102, 101, "Kid", "Eva", birth_date="01012020", signature_png=None),
        guest(103, 102, "Late", "Ola", nationality="POL", res_country="POL", res_city="Kraków"),
        guest(201, 201, "Unsigned", "Una", signature_png=None),
        guest(301, 301, "Sealed", "Sam"),
        guest(401, 401, "Quarter", "Quinn"),
        guest(402, 402, "Quarter", "Two"),
        guest(601, 601, "Demo", "Dan"),
        guest(1001, 1001, "Opt", "Out"),
        guest(1101, 1101, "Leav", "Ing"),
        guest(1201, 1201, "No", "Mail"),
        guest(1301, 1301, "Demo", "Entity"),
    ]
    adjs = [
        {"id": 1, "apartment_id": 1, "period_key": "2026-09", "direction": "add", "mode": "bed_days",
         "people_count": None, "nights": None, "bed_days": 2, "reason": "Late guest Ž",
         "created_by": 1, "created_at": OLD},
        {"id": 2, "apartment_id": 1, "period_key": "2026-08", "direction": "add", "mode": "bed_days",
         "people_count": None, "nights": None, "bed_days": 4, "reason": "Other period",
         "created_by": 1, "created_at": OLD},
    ]
    filings = [
        {"id": 1, "apartment_id": 3, "period_key": "2026-09", "version": 1, "cadence": "monthly",
         "rate_czk": 20, "liable_days": 2, "exempt_days": 0, "total_due_czk": 40,
         "total_collected_czk": 40, "created_at": OLD, "superseded_at": None},
        {"id": 2, "apartment_id": 7, "period_key": "2026-08", "version": 1, "cadence": "monthly",
         "rate_czk": 20, "liable_days": 1, "exempt_days": 0, "total_due_czk": 20,
         "total_collected_czk": 20, "created_at": "2026-10-03T00:00:00+00:00",
         "superseded_at": "2026-10-04T00:00:00+00:00"},
        {"id": 3, "apartment_id": 7, "period_key": "2026-08", "version": 2, "cadence": "monthly",
         "rate_czk": 20, "liable_days": 2, "exempt_days": 0, "total_due_czk": 40,
         "total_collected_czk": 40, "created_at": "2026-10-04T00:00:00+00:00", "superseded_at": None},
    ]
    outbox = [
        {"id": 1, "idempotency_key": "stay_fee_report:7:2026-08:v1", "kind": "stay_fee_report",
         "apartment_id": 7, "owner_user_id": 1, "to_email": "alpha@example.test",
         "subject": "old", "payload": "{}", "state": "sent", "attempts": 1,
         "next_attempt_at": OLD, "created_at": OLD, "updated_at": OLD},
    ]
    alerts = [
        {"id": 1, "level": "warning", "kind": "stay_fee_no_pay_way", "apartment_id": 5,
         "owner_user_id": 1, "dedupe_key": "stay_fee_no_pay_way:5",
         "message": "Guests cannot pay the stay fee: add a bank account", "detail": "",
         "params": "{\"property\": \"Archived\"}", "created_at": OLD},
    ]
    return {"users": users, "legal_entities": entities, "apartments": apts, "reservations": res,
            "guests": guests, "adjustments": adjs, "filings": filings, "outbox": outbox,
            "alerts": alerts}


def load(db, data):
    for row in data["users"]:
        db.insert("user_account", {**row, "created_at": OLD})
    for row in data["legal_entities"]:
        db.insert("legal_entity", {**row, "created_at": OLD})
    for row in data["apartments"]:
        db.insert("apartment", {**row, "created_at": OLD})
    for row in data["reservations"]:
        db.insert("reservation", {**row, "uid": f"uid-{row['id']}", "created_at": OLD, "updated_at": OLD})
    for row in data["guests"]:
        db.insert("guest", {**row, "created_at": OLD, "updated_at": OLD})
    for row in data["adjustments"]:
        plain = dict(row)
        reason = plain.pop("reason")
        db.insert("stay_fee_adjustment", {**plain, "reason_enc": db.encrypt_field(reason)})
    for row in data["filings"]:
        db.insert("stay_fee_filing", row)
    for row in data["outbox"]:
        db.insert("email_outbox", row)
    for row in data["alerts"]:
        db.insert("alert", row)


def ser(obj):
    if isinstance(obj, dict):
        return {key: ser(val) for key, val in obj.items() if key not in ("apartment", "anchor")}
    if isinstance(obj, (list, tuple)):
        return [ser(item) for item in obj]
    if isinstance(obj, date):
        return obj.isoformat()
    return obj


def b64(data):
    return base64.b64encode(data).decode("ascii") if data is not None else None


def snapshot(db):
    filings = []
    for row in db.query("SELECT * FROM stay_fee_filing ORDER BY id"):
        filings.append({
            **{k: row[k] for k in ("id", "apartment_id", "period_key", "version", "cadence", "rate_czk",
                                   "liable_days", "exempt_days", "total_due_czk", "total_collected_czk",
                                   "created_at", "superseded_at")},
            "pdf": b64(db.decrypt_blob(row["pdf_enc"])) if row["pdf_enc"] else None,
            "csv": b64(db.decrypt_blob(row["csv_enc"])) if row["csv_enc"] else None,
            "payload": db.decrypt_field(row["payload_enc"]) if row["payload_enc"] else None,
        })
    adjustments = []
    for row in db.query("SELECT * FROM stay_fee_adjustment ORDER BY id"):
        item = {k: row[k] for k in ("id", "apartment_id", "period_key", "direction", "mode", "people_count",
                                    "nights", "bed_days", "created_by", "created_at", "reversed_at",
                                    "reversed_by", "filing_id")}
        item["reason"] = db.decrypt_field(row["reason_enc"])
        adjustments.append(item)
    outbox = [{k: row[k] for k in ("idempotency_key", "kind", "reservation_id", "apartment_id",
                                   "owner_user_id", "to_email", "cc_email", "subject", "payload",
                                   "state", "attempts")}
              for row in db.query("SELECT * FROM email_outbox ORDER BY idempotency_key")]
    alerts = [{**{k: row[k] for k in ("level", "kind", "apartment_id", "reservation_id", "owner_user_id",
                                      "dedupe_key", "message", "detail", "params")},
               "resolved": row["resolved_at"] is not None}
              for row in db.query("SELECT * FROM alert ORDER BY dedupe_key, id")]
    audit = [{k: row[k] for k in ("at", "actor", "action", "detail", "owner_user_id", "actor_user_id")}
             for row in db.query("SELECT * FROM audit WHERE action LIKE 'stay_fee%' ORDER BY id")]
    return {"filings": filings, "adjustments": adjustments, "outbox": outbox, "alerts": alerts,
            "audit": audit}


class Clock:
    """The fixed UTC clock for db.utcnow and stay_fee_auto's cutoff."""

    value = RUNS[0]["now"]


class FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime.fromisoformat(Clock.value).astimezone(tz or timezone.utc)


def refusal(fn):
    try:
        fn()
    except ValueError as exc:
        return f"ValueError: {exc}"
    return "no error"


def writes(db, rendered):
    from app import stay_fee_adjustment, stay_fee_filing

    Clock.value = WRITES_NOW
    today = date.fromisoformat(WRITES_TODAY)
    apt = {i: db.query_one("SELECT * FROM apartment WHERE id = ?", (i,)) for i in (1, 3, 9)}
    out = {}
    out["added"] = stay_fee_adjustment.add(apartment_id=1, period_key="2026-09", direction="add",
                                           mode="people", people_count=2, nights=3, bed_days=6,
                                           reason="Correction: 2 people × 3 nights", created_by=1)
    stay_fee_adjustment.reverse(1, 1)
    live = stay_fee_filing.latest(1, "2026-09")
    out["replaced"] = live["id"]
    out["corrected"] = stay_fee_filing.save(apt[1], date(2026, 9, 1), rate_czk=None, collected={101: 0},
                                            issued_on=today, replacing_id=live["id"])
    out["changed"] = refusal(lambda: stay_fee_filing.save(apt[1], date(2026, 9, 1), rate_czk=None,
                                                          collected={}, issued_on=today,
                                                          replacing_id=live["id"]))
    out["overlap"] = refusal(lambda: stay_fee_filing.save(apt[3], date(2026, 9, 1), rate_czk=None,
                                                          collected={}, issued_on=today))
    out["inactive"] = refusal(lambda: stay_fee_filing.save(apt[9], date(2026, 9, 1), rate_czk=None,
                                                           collected={}, issued_on=today))
    out["state"] = snapshot(db)
    out["rendered"] = rendered[:]
    rendered.clear()
    return out


def render() -> str:
    from app import config, db, stay_fee, stay_fee_auto, stay_fee_remittance_pdf

    config.STAY_FEE_GUEST_PAY = True
    db.init_db()
    db.utcnow = lambda: Clock.value
    stay_fee_auto.datetime = FixedDatetime
    rendered = []

    def fake_render(data):
        rendered.append(ser(data))
        return FAKE_PDF

    stay_fee_remittance_pdf.render = fake_render
    data = seed()
    load(db, data)
    runs = []
    for step in RUNS:
        for sql in step["before"]:
            db.execute(sql)
        Clock.value = step["now"]
        counts = stay_fee_auto.run(date.fromisoformat(step["today"]))
        reconciled = stay_fee.reconcile_all_no_pay_way()
        runs.append({**step, "counts": counts, "reconciled": reconciled, "state": snapshot(db),
                     "rendered": rendered[:]})
        rendered.clear()
    due = []
    day = date(2026, 1, 1)
    while day.year == 2026:
        for cadence in ("monthly", "quarterly"):
            month = stay_fee_auto.due_month(cadence, day)
            due.append(f"{cadence} {day.isoformat()} {month.isoformat() if month else '-'}")
        day += timedelta(days=1)
    golden = {"seed": data, "fake_pdf": b64(FAKE_PDF), "runs": runs, "writes": writes(db, rendered),
              "due_month": due}
    return json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-job-golden-"))
    os.environ["UBYHOST_DATA_DIR"] = str(tmp)
    os.environ["UBYHOST_DB"] = str(tmp / "stay_fee_job_golden.sqlite3")
    os.environ["UBYHOST_SECRET_KEY"] = "golden-secret-key-not-for-real-use"
    os.environ.pop("UBYHOST_DATA_KEYS", None)
    os.environ["UBYHOST_ENABLE_SCHEDULER"] = "0"
    os.environ["UBYHOST_STAY_FEE_GUEST_PAY"] = "on"
    os.environ["UBYHOST_MAIL_BACKEND"] = "console"
    os.environ["UBYHOST_UBYPORT_ENV"] = "mock"
    os.environ["UBYHOST_APP_BASE_URL"] = "https://app.example.test"
    os.environ["UBYHOST_PUBLIC_BASE_URL"] = "https://www.example.test"
    os.environ.pop("UBYHOST_DATABASE_URL", None)
    sys.path.insert(0, str(APP))
    main()
