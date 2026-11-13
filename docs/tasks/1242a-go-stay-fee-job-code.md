# 1242a: code blocks of brief 1242 (do not read; the brief's step 0 helper copies them)

Payload of [brief 1242](1242-go-stay-fee-job.md). Each block is one file, byte for byte; the heading gives its path and sha256. Do not edit.

### Block 1: `App/scripts/stay_fee_job_golden.py` sha256 `2f4077b7ef2a9dd4976dde075a9537d190e2a1568430078fb7d343d42b2a4da7`

````python
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
````

### Block 2: `go/internal/stayfee/save.go` sha256 `1badab6a857c4c98b9c2357acc67ea5137a4c1ef06e9dd85d2def7c6d0738c19`

````go
package stayfee

// The write side of App/app/stay_fee_filing.py (save) and stay_fee_auto.py
// (confirm), brief 1242. The PDF comes from a PDFRenderer the caller passes
// in; this package draws nothing.

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"sort"
	"strconv"
	"strings"
	"time"
	"unicode/utf16"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// DB is the part of *pgxpool.Pool the write functions use: reads, single
// statements and a transaction for Save.
type DB interface {
	Querier
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	Begin(ctx context.Context) (pgx.Tx, error)
}

// Encrypter seals one value with the primary data key (Fernet), as
// db.encrypt_blob and db.encrypt_secret do. It returns the token text.
type Encrypter func(plain []byte) (string, error)

// FernetEncrypter is the Encrypter of the data keys (secure.LoadDataKeys):
// the first key, like Python's MultiFernet.encrypt, so Python decrypts it.
func FernetEncrypter(keys *secure.MultiFernet) Encrypter {
	return func(plain []byte) (string, error) { return keys.Encrypt(plain) }
}

// PDFRenderer draws the hlášení PDF (stay_fee_remittance_pdf.render).
type PDFRenderer interface {
	Render(h Hlaseni) ([]byte, error)
}

// The errors Save returns where Python raises ValueError, plus the unique
// violation of (apartment_id, period_key, version) that Python lets through as
// an IntegrityError. Confirm treats all four as "not sealed".
var (
	ErrInactive  = errors.New("stayfee: inactive property")
	ErrOverlap   = errors.New("stayfee: overlaps saved period")
	ErrChanged   = errors.New("stayfee: filing changed")
	ErrDuplicate = errors.New("stayfee: filing version already exists")
)

// SaveDeps are the services Save and Confirm need. Now nil is time.Now.
// ScheduleToday is Python's date.today() in schedule_for (see Opts).
type SaveDeps struct {
	Dec           Decrypter
	Enc           Encrypter
	Renderer      PDFRenderer
	Now           func() time.Time
	ScheduleToday time.Time
}

func (d SaveDeps) now() time.Time {
	if d.Now == nil {
		return time.Now()
	}
	return d.Now()
}

// SaveArgs are save()'s keyword arguments. RateCZK nil prices each night at
// the dated rate; ReplacingID nil seals a new period (overlap check), else it
// supersedes that filing (a correction). Cadence "" (or an unknown one) is the
// apartment's.
type SaveArgs struct {
	Month       time.Time
	RateCZK     *int
	Collected   map[int64]int
	IssuedOn    time.Time
	Cadence     string
	ReplacingID *int64
}

// UTCStamp is db.utcnow() for an instant: "2026-10-05T05:00:00+00:00".
func UTCStamp(t time.Time) string {
	return t.UTC().Format("2006-01-02T15:04:05") + "+00:00"
}

type payloadAdjustment struct {
	ID     int64  `json:"id"`
	Delta  int    `json:"delta"`
	Mode   string `json:"mode"`
	Reason string `json:"reason"`
}

type payloadObj struct {
	Collected    map[string]int      `json:"collected"`
	Lines        []Line              `json:"lines"`
	RateSegments [][2]int            `json:"rate_segments"`
	Adjustments  []payloadAdjustment `json:"adjustments"`
}

// sealPayload is json.dumps(payload_obj, sort_keys=True) of save(): sorted
// keys at every level, ASCII-only escapes, ", " and ": " separators.
func sealPayload(period *Period, collected map[int64]int) (string, error) {
	obj := payloadObj{Collected: map[string]int{}, Lines: period.Lines, RateSegments: period.RateSegments,
		Adjustments: []payloadAdjustment{}}
	for gid, amount := range collected {
		obj.Collected[strconv.FormatInt(gid, 10)] = amount
	}
	if obj.Lines == nil {
		obj.Lines = []Line{}
	}
	if obj.RateSegments == nil {
		obj.RateSegments = [][2]int{}
	}
	for _, a := range period.Adjustments {
		obj.Adjustments = append(obj.Adjustments, payloadAdjustment{ID: a.ID, Delta: a.Delta, Mode: a.Mode, Reason: a.Reason})
	}
	return PyJSONSorted(obj)
}

// PyJSONSorted is json.dumps(v, sort_keys=True) (ensure_ascii on, default
// separators) for a value that encoding/json can marshal. Numbers keep the
// text encoding/json wrote; nil slices must already be empty slices.
func PyJSONSorted(v any) (string, error) {
	raw, err := json.Marshal(v)
	if err != nil {
		return "", err
	}
	dec := json.NewDecoder(strings.NewReader(string(raw)))
	dec.UseNumber()
	var generic any
	if err := dec.Decode(&generic); err != nil {
		return "", err
	}
	var b strings.Builder
	if err := writePy(&b, generic); err != nil {
		return "", err
	}
	return b.String(), nil
}

func writePy(b *strings.Builder, v any) error {
	switch x := v.(type) {
	case nil:
		b.WriteString("null")
	case bool:
		if x {
			b.WriteString("true")
		} else {
			b.WriteString("false")
		}
	case json.Number:
		b.WriteString(x.String())
	case string:
		writePyStr(b, x)
	case []any:
		b.WriteByte('[')
		for i, item := range x {
			if i > 0 {
				b.WriteString(", ")
			}
			if err := writePy(b, item); err != nil {
				return err
			}
		}
		b.WriteByte(']')
	case map[string]any:
		keys := make([]string, 0, len(x))
		for k := range x {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		b.WriteByte('{')
		for i, k := range keys {
			if i > 0 {
				b.WriteString(", ")
			}
			writePyStr(b, k)
			b.WriteString(": ")
			if err := writePy(b, x[k]); err != nil {
				return err
			}
		}
		b.WriteByte('}')
	default:
		return fmt.Errorf("stayfee: json value of type %T", v)
	}
	return nil
}

var pyEscapes = map[rune]string{'"': `\"`, '\\': `\\`, '\n': `\n`, '\r': `\r`, '\t': `\t`, '\b': `\b`, '\f': `\f`}

// writePyStr writes a Python str as json.dumps with ensure_ascii does (copy
// of ubyport writePyString).
func writePyStr(b *strings.Builder, s string) {
	b.WriteByte('"')
	for _, r := range s {
		if esc, ok := pyEscapes[r]; ok {
			b.WriteString(esc)
		} else if r >= 0x20 && r <= 0x7e {
			b.WriteRune(r)
		} else if r > 0xffff {
			hi, lo := utf16.EncodeRune(r)
			fmt.Fprintf(b, `\u%04x\u%04x`, hi, lo)
		} else {
			fmt.Fprintf(b, `\u%04x`, r)
		}
	}
	b.WriteByte('"')
}

func isUniqueViolation(err error) bool {
	var pgErr *pgconn.PgError
	return errors.As(err, &pgErr) && pgErr.Code == "23505"
}

// isIntegrity is db.integrity_errors(): any SQLSTATE of class 23.
func isIntegrity(err error) bool {
	var pgErr *pgconn.PgError
	return errors.As(err, &pgErr) && strings.HasPrefix(pgErr.Code, "23")
}

// Save is stay_fee_filing.save: seal a period and return the new filing id.
// The figures are read before the transaction, as in Python; the transaction
// takes the advisory lock of db.lock_key("stay_fee_filing", apartment id),
// supersedes ReplacingID or refuses an overlapping live filing, inserts the
// next version with the encrypted PDF, CSV and payload, and links the open
// adjustments of the period. A failure leaves the earlier filing in place.
func Save(ctx context.Context, db DB, deps SaveDeps, ap *Apartment, a SaveArgs) (int64, error) {
	if deps.Renderer == nil || deps.Enc == nil || deps.Dec == nil {
		return 0, errors.New("stayfee: Save needs a renderer, an encrypter and a decrypter")
	}
	chosen := ChooseCadence(ap, a.Cadence)
	period, err := PropertyPeriod(ctx, db, deps.Dec, ap, a.Month,
		Opts{LiveOnly: true, Cadence: chosen, Rate: a.RateCZK, ScheduleToday: deps.ScheduleToday})
	if err != nil {
		return 0, err
	}
	if period == nil {
		return 0, ErrInactive
	}
	group := ReportGroup(ap, a.Month, period, chosen)
	key := PeriodKey(group.Cadence, group.First)
	h, err := HlaseniFor(ctx, db, deps.Dec, group, a.IssuedOn)
	if err != nil {
		return 0, err
	}
	pdf, err := deps.Renderer.Render(*h)
	if err != nil {
		return 0, err
	}
	rows, err := RegisterFor(ctx, db, deps.Dec, period)
	if err != nil {
		return 0, err
	}
	csv := RegisterCSV(rows)
	due := group.TotalCZK
	collectedTotal := 0
	for _, line := range period.Lines {
		if v, ok := a.Collected[line.GuestID]; ok {
			collectedTotal += v
		} else {
			collectedTotal += line.AmountCZK
		}
	}
	payload, err := sealPayload(period, a.Collected)
	if err != nil {
		return 0, err
	}
	now := UTCStamp(deps.now())
	payloadEnc, err := deps.Enc([]byte(payload))
	if err != nil {
		return 0, err
	}
	pdfEnc, err := deps.Enc(pdf)
	if err != nil {
		return 0, err
	}
	csvEnc, err := deps.Enc(csv)
	if err != nil {
		return 0, err
	}
	tx, err := db.Begin(ctx)
	if err != nil {
		return 0, err
	}
	defer func() { _ = tx.Rollback(ctx) }()
	if _, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtext($1), $2)`, "stay_fee_filing", ap.ID); err != nil {
		return 0, err
	}
	if a.ReplacingID != nil {
		tag, err := tx.Exec(ctx, `UPDATE stay_fee_filing SET superseded_at = $1
			WHERE id = $2 AND apartment_id = $3 AND superseded_at IS NULL`, now, *a.ReplacingID, ap.ID)
		if err != nil {
			return 0, err
		}
		if tag.RowsAffected() != 1 {
			return 0, ErrChanged
		}
	} else {
		var one int64
		err := tx.QueryRow(ctx, `SELECT id FROM stay_fee_filing WHERE apartment_id = $1
			AND superseded_at IS NULL AND period_key = ANY($2) LIMIT 1`,
			ap.ID, OverlapKeys(group.Cadence, group.First)).Scan(&one)
		if err == nil {
			return 0, ErrOverlap
		}
		if !errors.Is(err, pgx.ErrNoRows) {
			return 0, err
		}
	}
	var version int64
	if err := tx.QueryRow(ctx, `SELECT COALESCE(MAX(version), 0) FROM stay_fee_filing
		WHERE apartment_id = $1 AND period_key = $2`, ap.ID, key).Scan(&version); err != nil {
		return 0, err
	}
	version++
	var filingID int64
	err = tx.QueryRow(ctx, `INSERT INTO stay_fee_filing (
		apartment_id, period_key, version, cadence, rate_czk, liable_days, exempt_days,
		total_due_czk, total_collected_czk, pdf_enc, csv_enc, payload_enc, created_at,
		superseded_at) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, NULL) RETURNING id`,
		ap.ID, key, version, group.Cadence, period.RateCZK, group.LiableNights, group.ExemptNights, due,
		collectedTotal, []byte(pdfEnc), []byte(csvEnc), payloadEnc, now).Scan(&filingID)
	if err != nil {
		if isUniqueViolation(err) {
			return 0, ErrDuplicate
		}
		return 0, err
	}
	if _, err := tx.Exec(ctx, `UPDATE stay_fee_adjustment SET filing_id = $1
		WHERE apartment_id = $2 AND period_key = $3 AND reversed_at IS NULL
		AND filing_id IS NULL`, filingID, ap.ID, key); err != nil {
		return 0, err
	}
	if err := tx.Commit(ctx); err != nil {
		if isUniqueViolation(err) {
			return 0, ErrDuplicate
		}
		return 0, err
	}
	return filingID, nil
}

// ConfirmOpts are confirm()'s options. AuditEvent "" is
// "stay_fee_auto_finalize". AuditOwner is the audit row's owner_user_id
// (Python's request context; the job leaves it nil). The audit actor is
// "host", as db.audit writes it with no signed-in user.
type ConfirmOpts struct {
	AuditEvent string
	AuditOwner *int64
}

// Confirm is stay_fee_auto.confirm: seal a clean period at the calculated
// fee. It returns 0 with no error when the period is blocked, already sealed,
// or Save refuses it (ErrInactive, ErrOverlap, ErrChanged, ErrDuplicate or
// any other integrity error), as Python returns None.
func Confirm(ctx context.Context, db DB, deps SaveDeps, ap *Apartment, month, today time.Time, o ConfirmOpts) (int64, error) {
	checked, err := Check(ctx, db, deps.Dec, ap, month, today, Opts{ScheduleToday: deps.ScheduleToday})
	if err != nil {
		return 0, err
	}
	if len(checked.Issues) > 0 {
		return 0, nil
	}
	latest, err := Latest(ctx, db, ap.ID, checked.Key)
	if err != nil {
		return 0, err
	}
	if latest != nil {
		return 0, nil
	}
	collected := map[int64]int{}
	if checked.Period != nil {
		for _, line := range checked.Period.Lines {
			collected[line.GuestID] = line.AmountCZK
		}
	}
	id, err := Save(ctx, db, deps, ap, SaveArgs{Month: checked.Group.First, Collected: collected,
		IssuedOn: today, Cadence: checked.Group.Cadence})
	if err != nil {
		if errors.Is(err, ErrInactive) || errors.Is(err, ErrOverlap) || errors.Is(err, ErrChanged) ||
			errors.Is(err, ErrDuplicate) || isIntegrity(err) {
			return 0, nil
		}
		return 0, err
	}
	event := o.AuditEvent
	if event == "" {
		event = "stay_fee_auto_finalize"
	}
	if _, err := db.Exec(ctx, `INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id,
		impersonator_user_id) VALUES ($1, 'host', $2, $3, $4, NULL, NULL)`,
		UTCStamp(deps.now()), event, fmt.Sprintf("apartment_id=%d period=%s", ap.ID, checked.Key),
		o.AuditOwner); err != nil {
		return 0, err
	}
	return id, nil
}

// RecentLive is the job's query of the live filings of one apartment created
// at or after cutoff (a UTCStamp), in id order (Python has no ORDER BY).
func RecentLive(ctx context.Context, q Querier, apartmentID int64, cutoff string) ([]FilingRow, error) {
	rows, err := q.Query(ctx, `SELECT `+filingColumns+` FROM stay_fee_filing
		WHERE apartment_id = $1 AND superseded_at IS NULL AND created_at >= $2 ORDER BY id`, apartmentID, cutoff)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []FilingRow
	for rows.Next() {
		var f FilingRow
		if err := rows.Scan(&f.ID, &f.ApartmentID, &f.PeriodKey, &f.Version, &f.Cadence, &f.RateCZK, &f.LiableDays,
			&f.ExemptDays, &f.TotalDueCZK, &f.TotalCollectedCZK, &f.PayloadEnc, &f.CreatedAt, &f.SupersededAt,
			&f.SentAt, &f.SentMessageID, &f.PaidAt); err != nil {
			return nil, err
		}
		out = append(out, f)
	}
	return out, rows.Err()
}
````

### Block 3: `go/internal/stayfee/adjust.go` sha256 `c53925ad6a21454007d7475e234ec3da00f8edf3342c480d7705880aad3ae0c9`

````go
package stayfee

// The write side of App/app/stay_fee_adjustment.py (brief 1242): add and
// reverse. Python writes no audit row in either; the routes do.

import (
	"context"
	"time"
)

// AdjustmentInput is stay_fee_adjustment.add's keyword arguments. Direction is
// "add" or "remove", Mode "people" or "bed_days" (CHECK constraints in the
// schema). PeopleCount and Nights 0 are stored as NULL, as Python's "or None".
type AdjustmentInput struct {
	ApartmentID int64
	PeriodKey   string
	Direction   string
	Mode        string
	PeopleCount int
	Nights      int
	BedDays     int
	Reason      string
	CreatedBy   int64
}

func zeroNull(v int) any {
	if v == 0 {
		return nil
	}
	return v
}

// AddAdjustment is stay_fee_adjustment.add: insert one correction and return
// its id. The reason is encrypted like db.encrypt_field: an empty reason is
// NULL, which the NOT NULL column refuses, as in Python.
func AddAdjustment(ctx context.Context, db DB, enc Encrypter, in AdjustmentInput, now time.Time) (int64, error) {
	var reason any
	if in.Reason != "" {
		token, err := enc([]byte(in.Reason))
		if err != nil {
			return 0, err
		}
		reason = token
	}
	var id int64
	err := db.QueryRow(ctx, `INSERT INTO stay_fee_adjustment (apartment_id, period_key, direction, mode,
		people_count, nights, bed_days, reason_enc, created_by, created_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) RETURNING id`,
		in.ApartmentID, in.PeriodKey, in.Direction, in.Mode, zeroNull(in.PeopleCount), zeroNull(in.Nights),
		in.BedDays, reason, in.CreatedBy, UTCStamp(now)).Scan(&id)
	return id, err
}

// ReverseAdjustment is stay_fee_adjustment.reverse: mark one correction
// reversed. Like db.update it does not check that a row matched.
func ReverseAdjustment(ctx context.Context, db DB, adjustmentID, actorID int64, now time.Time) error {
	_, err := db.Exec(ctx, `UPDATE stay_fee_adjustment SET reversed_at = $1, reversed_by = $2 WHERE id = $3`,
		UTCStamp(now), actorID, adjustmentID)
	return err
}
````

### Block 4: `go/internal/stayfeemail/job.go` sha256 `9f9d07e3111a357f0c180c780b3ba6266f298f4f5540430b675c508f06d41ac6`

````go
package stayfeemail

// Port of the daily stay_fee_mail job (brief 1242): App/app/stay_fee_auto.py
// due_month, run and _run_apartment, the two queue_stay_fee_* functions of
// App/app/mail_notify.py and stay_fee.reconcile_all_no_pay_way, run in the
// order of scheduler._job_stay_fee_mail. The PDF comes from Deps.Renderer;
// with none the job refuses to start (ErrNoRenderer) before it reads or
// writes anything, so the kind can be switched on before brief 1243 without
// sealing or mailing.

import (
	"context"
	"errors"
	"log/slog"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
)

// ErrNoRenderer is the error of a job built without a PDF renderer.
var ErrNoRenderer = errors.New("stay_fee_mail: no PDF renderer configured (brief 1243); nothing sealed or mailed")

// Deps are what the job reads besides the database. Now nil is time.Now;
// Keys nil loads the data keys from Getenv when the job runs.
type Deps struct {
	Getenv   func(string) string
	Now      func() time.Time
	Renderer stayfee.PDFRenderer
	Keys     *secure.MultiFernet
}

// Counts is run()'s counts dict.
type Counts struct {
	Confirmed int `json:"confirmed"`
	Reports   int `json:"reports"`
	Blocked   int `json:"blocked"`
}

// demo.py names: the seeded demo apartments and legal entities.
const (
	demoApartment  = "Vinohrady Studio (demo)"
	demoLoft       = "Karlín Loft (demo)"
	demoEntity     = "Josef Novák (demo)"
	demoController = "Demo Controller s.r.o."
)

// hostMailLanguage is mail_notify.HOST_MAIL_LANGUAGE.
const hostMailLanguage = "en"

// DueMonth is stay_fee_auto.due_month: the first month of the period that
// ended most recently, when today is from the 2nd to the 15th day after its
// end; ok false otherwise.
func DueMonth(cadence string, today time.Time) (time.Time, bool) {
	var month time.Time
	if cadence == "quarterly" {
		thisQuarter := stayfee.Day(today.Year(), time.Month((int(today.Month())-1)/3*3+1), 1)
		month = stayfee.ShiftMonth(thisQuarter, -3)
	} else {
		month = stayfee.PreviousMonth(today)
	}
	_, last := stayfee.PeriodBounds(cadence, month)
	if !today.Before(last.AddDate(0, 0, 2)) && !today.After(last.AddDate(0, 0, 15)) {
		return month, true
	}
	return time.Time{}, false
}

// pragueToday is claim.prague_today for an instant.
func pragueToday(now time.Time) time.Time {
	l := deadlines.LocalNow(now)
	return stayfee.Day(l.Year(), l.Month(), l.Day())
}

// ubyportEnv is config.UBYPORT_ENV: lower case, "mock" when unset.
func ubyportEnv(getenv func(string) string) string {
	env := strings.ToLower(getenv("UBYHOST_UBYPORT_ENV"))
	if env == "" {
		return "mock"
	}
	return env
}

// isDemoApartment is demo.is_demo_apartment: the seeded names always; the
// legal entity's name only in the mock environment.
func isDemoApartment(ctx context.Context, q stayfee.Querier, getenv func(string) string, ap *stayfee.Apartment) (bool, error) {
	if ap.InternalName == demoApartment || ap.InternalName == demoLoft {
		return true, nil
	}
	if ubyportEnv(getenv) != "mock" || ap.LegalEntityID == 0 {
		return false, nil
	}
	rows, err := q.Query(ctx, `SELECT COALESCE(name, '') FROM legal_entity WHERE id = $1`, ap.LegalEntityID)
	if err != nil {
		return false, err
	}
	defer rows.Close()
	if !rows.Next() {
		return false, rows.Err()
	}
	var name string
	if err := rows.Scan(&name); err != nil {
		return false, err
	}
	return name == demoEntity || name == demoController, nil
}

type runner struct {
	pool          *pgxpool.Pool
	deps          Deps
	save          stayfee.SaveDeps
	today         time.Time
	cutoff        string
	counts        Counts
	appBase       string
	publicBase    string
	mailOn        bool
	scheduleToday time.Time
}

// Run is stay_fee_auto.run: for every host who is not being deleted and has
// not opted out, and each of their apartments that is not archived, seal the
// period that is due, mail a blocked period, and mail the report of each live
// filing created in the last 3 days. An error in one apartment is logged and
// the next apartment runs, as in Python.
func Run(ctx context.Context, pool *pgxpool.Pool, deps Deps) (Counts, error) {
	if deps.Renderer == nil {
		return Counts{}, ErrNoRenderer
	}
	if deps.Now == nil {
		deps.Now = time.Now
	}
	keys := deps.Keys
	if keys == nil {
		var err error
		if keys, err = secure.LoadDataKeys(deps.Getenv); err != nil {
			return Counts{}, err
		}
	}
	now := deps.Now()
	r := &runner{pool: pool, deps: deps, today: pragueToday(now),
		cutoff:     stayfee.UTCStamp(now.Add(-72 * time.Hour)),
		appBase:    appBase(deps.Getenv),
		publicBase: publicBase(deps.Getenv),
		mailOn:     mailEnabled(deps.Getenv),
	}
	u := now.UTC()
	r.scheduleToday = stayfee.Day(u.Year(), u.Month(), u.Day())
	r.save = stayfee.SaveDeps{Dec: stayfee.FernetDecrypter(keys), Enc: stayfee.FernetEncrypter(keys),
		Renderer: deps.Renderer, Now: deps.Now, ScheduleToday: r.scheduleToday}
	hosts, err := queryIDs(ctx, pool, `SELECT id FROM user_account WHERE role = 'host' AND deletion_due_at IS NULL
		AND COALESCE(stay_fee_emails_opt_out, 0) = 0 ORDER BY id`)
	if err != nil {
		return Counts{}, err
	}
	for _, host := range hosts {
		aps, err := loadApartments(ctx, pool, host)
		if err != nil {
			return r.counts, err
		}
		for _, ap := range aps {
			if err := r.apartment(ctx, ap, host); err != nil {
				slog.Error("stay-fee mail failed for apartment", "apartment_id", ap.ID, "error", err)
			}
		}
	}
	return r.counts, nil
}

func queryIDs(ctx context.Context, q stayfee.Querier, sql string, args ...any) ([]int64, error) {
	rows, err := q.Query(ctx, sql, args...)
	if err != nil {
		return nil, err
	}
	ids, err := pgx.CollectRows(rows, pgx.RowTo[int64])
	return ids, err
}

func loadApartments(ctx context.Context, q stayfee.Querier, owner int64) ([]*stayfee.Apartment, error) {
	rows, err := q.Query(ctx, stayfee.ApartmentSelect+` WHERE owner_user_id = $1 AND archived_at IS NULL ORDER BY id`, owner)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*stayfee.Apartment
	for rows.Next() {
		ap, err := stayfee.ScanApartment(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, ap)
	}
	return out, rows.Err()
}

// apartment is _run_apartment.
func (r *runner) apartment(ctx context.Context, ap *stayfee.Apartment, owner int64) error {
	if !stayfee.IsActive(ap) {
		return nil
	}
	demo, err := isDemoApartment(ctx, r.pool, r.deps.Getenv, ap)
	if err != nil || demo {
		return err
	}
	cadence := stayfee.CadenceOf(ap)
	if month, ok := DueMonth(cadence, r.today); ok {
		latest, err := stayfee.Latest(ctx, r.pool, ap.ID, stayfee.PeriodKey(cadence, month))
		if err != nil {
			return err
		}
		if latest == nil {
			id, err := stayfee.Confirm(ctx, r.pool, r.save, ap, month, r.today, stayfee.ConfirmOpts{})
			if err != nil {
				return err
			}
			if id != 0 {
				r.counts.Confirmed++
			} else {
				checked, err := stayfee.Check(ctx, r.pool, r.save.Dec, ap, month, r.today,
					stayfee.Opts{Cadence: cadence, ScheduleToday: r.scheduleToday})
				if err != nil {
					return err
				}
				if len(checked.Issues) > 0 {
					queued, err := r.queueBlocked(ctx, ap, owner, checked.Group, checked.Issues)
					if err != nil {
						return err
					}
					if queued != 0 {
						r.counts.Blocked++
					}
				}
			}
		}
	}
	// Live filings saved or sealed in the last 3 days. The mail key includes
	// the version, so a repeated run sends nothing twice and a correction
	// sends again.
	rows, err := stayfee.RecentLive(ctx, r.pool, ap.ID, r.cutoff)
	if err != nil {
		return err
	}
	for i := range rows {
		queued, err := r.queueReport(ctx, ap, owner, &rows[i])
		if err != nil {
			return err
		}
		if queued != 0 {
			r.counts.Reports++
		}
	}
	return nil
}

// Handler is the stay_fee_mail job (scheduler._job_stay_fee_mail): Run, then
// the no-pay-way sweep, whose failure is logged and does not fail the job.
// It returns confirmed + reports + blocked. Without a renderer it returns
// ErrNoRenderer before touching the pool, so a nil pool is safe in tests.
func Handler(pool *pgxpool.Pool, deps Deps) func(ctx context.Context) (int, error) {
	return func(ctx context.Context) (int, error) {
		if deps.Renderer == nil {
			return 0, ErrNoRenderer
		}
		counts, err := Run(ctx, pool, deps)
		if err != nil {
			return 0, err
		}
		if _, err := ReconcileAllNoPayWay(ctx, pool, deps.Getenv); err != nil {
			slog.Error("stay-fee no-pay-way sweep failed", "error", err)
		}
		slog.Info("stay fee mail", "confirmed", counts.Confirmed, "reports", counts.Reports, "blocked", counts.Blocked)
		return counts.Confirmed + counts.Reports + counts.Blocked, nil
	}
}
````

### Block 5: `go/internal/stayfeemail/queue.go` sha256 `fef367d07ead89587675e6bf9bf7e9631b65704f0af36600f5a58dbcb0ea0dc2`

````go
package stayfeemail

// mail_notify.queue_stay_fee_report / queue_stay_fee_blocked with
// mail.enqueue's gates, and stay_fee.reconcile_no_pay_way_alert /
// reconcile_all_no_pay_way (brief 1242).

import (
	"context"
	"fmt"
	"log/slog"
	"sort"
	"strconv"
	"strings"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// NoPayWayKind is stay_fee.NO_PAY_WAY_KIND.
const NoPayWayKind = "stay_fee_no_pay_way"

const noPayWayMessage = "Guests cannot pay the stay fee: add a bank account"

func appBase(getenv func(string) string) string    { return hostweb.AppBase(getenv) }
func publicBase(getenv func(string) string) string { return hostweb.PublicBase(getenv) }

// mailEnabled is mail.mail_enabled: UBYHOST_MAIL_BACKEND console or ses.
func mailEnabled(getenv func(string) string) bool {
	backend := strings.ToLower(strings.TrimSpace(getenv("UBYHOST_MAIL_BACKEND")))
	return backend == "console" || backend == "ses"
}

// guestPayOn is config.STAY_FEE_GUEST_PAY.
func guestPayOn(getenv func(string) string) bool {
	return strings.ToLower(strings.TrimSpace(getenv("UBYHOST_STAY_FEE_GUEST_PAY"))) == "on"
}

// entityContactEmail is mail_notify._entity_contact_email.
func (r *runner) entityContactEmail(ctx context.Context, legalEntityID int64) (string, error) {
	if legalEntityID == 0 {
		return "", nil
	}
	rows, err := r.pool.Query(ctx, `SELECT COALESCE(contact_email, '') FROM legal_entity WHERE id = $1`, legalEntityID)
	if err != nil {
		return "", err
	}
	defer rows.Close()
	if !rows.Next() {
		return "", rows.Err()
	}
	var raw string
	if err := rows.Scan(&raw); err != nil {
		return "", err
	}
	return ubyport.NormaliseEmail(raw), nil
}

// enqueue is mail.enqueue for a host kind: nothing when mail is off or there
// is no address. Python logs an insert failure and returns the row that is
// there, if any; here that is EnqueueMail's error, logged, and 0.
func (r *runner) enqueue(ctx context.Context, kind, key, to, subject, payload string, apartmentID, owner int64) int64 {
	if !r.mailOn {
		slog.Info("mail disabled; skip enqueue", "kind", kind)
		return 0
	}
	to = ubyport.NormaliseEmail(to)
	if to == "" {
		return 0
	}
	id, err := ubyport.EnqueueMail(ctx, r.pool, ubyport.OutboxMail{Kind: kind, Key: key, ApartmentID: &apartmentID,
		OwnerUserID: &owner, To: to, Subject: subject, Payload: payload})
	if err != nil {
		slog.Error("mail enqueue failed", "kind", kind, "error", err)
		return 0
	}
	return id
}

func propertyName(ap *stayfee.Apartment) string {
	if ap.InternalName == "" {
		return "UbyHost"
	}
	return ap.InternalName
}

func (r *runner) reportURL(apartmentID int64, month string) string {
	return fmt.Sprintf("%s/stay-fees/%d?month=%s", r.appBase, apartmentID, month)
}

// queueReport is mail_notify.queue_stay_fee_report with lang None.
func (r *runner) queueReport(ctx context.Context, ap *stayfee.Apartment, owner int64, row *stayfee.FilingRow) (int64, error) {
	to, err := r.entityContactEmail(ctx, ap.LegalEntityID)
	if err != nil || to == "" {
		return 0, err
	}
	lang := hostMailLanguage
	month, err := stayfee.PeriodAnchor(row.PeriodKey)
	if err != nil {
		return 0, err
	}
	total := row.TotalDueCZK
	group := &stayfee.Group{Anchor: ap, VS: stayfee.VSOf(ap), TotalCZK: total}
	details := stayfee.PaymentDetails(group)
	hasQR := details != nil && details.SPAYD != ""
	var databox string
	if err := r.pool.QueryRow(ctx, `SELECT COALESCE(stay_fee_authority_databox, '') FROM apartment WHERE id = $1`,
		ap.ID).Scan(&databox); err != nil {
		return 0, err
	}
	account, vs := "", group.VS
	if details != nil {
		account = details.Account
		if details.VS != "" {
			vs = details.VS
		}
	}
	built := BuildStayFeeReport(r.appBase, r.publicBase, lang, StayFeeReport{
		PropertyName: propertyName(ap),
		Period:       PeriodLabel(lang, row.Cadence, month.Year(), int(month.Month())),
		Amount:       stayfee.FormatCZK(total),
		TotalCZK:     total,
		Authority:    ap.AuthorityName,
		Databox:      databox,
		Account:      account,
		VS:           vs,
		HasQR:        hasQR,
		ReportURL:    r.reportURL(ap.ID, stayfee.MonthKey(month)),
	})
	var b strings.Builder
	b.WriteString(`{"text": ` + ubyport.PyString(built.Text) + `, "html": ` + ubyport.PyString(built.HTML) +
		`, "lang": ` + ubyport.PyString(lang) + `, "stay_fee_filing_id": ` + strconv.FormatInt(row.ID, 10))
	if hasQR {
		b.WriteString(`, "qr_spayd": ` + ubyport.PyString(details.SPAYD))
	}
	b.WriteString("}")
	key := fmt.Sprintf("stay_fee_report:%d:%s:v%d", ap.ID, row.PeriodKey, row.Version)
	return r.enqueue(ctx, "stay_fee_report", key, to, built.Subject, b.String(), ap.ID, owner), nil
}

// queueBlocked is mail_notify.queue_stay_fee_blocked with lang None.
func (r *runner) queueBlocked(ctx context.Context, ap *stayfee.Apartment, owner int64, g *stayfee.Group, issues []string) (int64, error) {
	to, err := r.entityContactEmail(ctx, ap.LegalEntityID)
	if err != nil || to == "" {
		return 0, err
	}
	lang := hostMailLanguage
	key := stayfee.PeriodKey(g.Cadence, g.First)
	reportURL := r.reportURL(ap.ID, stayfee.MonthKey(g.First))
	built := BuildStayFeeBlocked(r.appBase, r.publicBase, lang, propertyName(ap),
		PeriodLabel(lang, g.Cadence, g.First.Year(), int(g.First.Month())), append([]string(nil), issues...), reportURL)
	payload := `{"text": ` + ubyport.PyString(built.Text) + `, "html": ` + ubyport.PyString(built.HTML) +
		`, "lang": ` + ubyport.PyString(lang) + `}`
	return r.enqueue(ctx, "stay_fee_blocked", fmt.Sprintf("stay_fee_blocked:%d:%s", ap.ID, key), to,
		built.Subject, payload, ap.ID, owner), nil
}

// ReconcileNoPayWay is stay_fee.reconcile_no_pay_way_alert: raise the host
// alert while no pay way works, resolve it once one does or collection is off.
func ReconcileNoPayWay(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, apartmentID int64) error {
	key := fmt.Sprintf("%s:%d", NoPayWayKind, apartmentID)
	ap, err := stayfee.LoadApartment(ctx, pool, apartmentID)
	if err != nil && err != stayfee.ErrNotFound {
		return err
	}
	noPay := false
	if ap != nil {
		entity, err := stayfee.LoadEntity(ctx, pool, nil, ap.LegalEntityID, false)
		if err != nil {
			return err
		}
		noPay = stayfee.NoPayWay(ap, entity, guestPayOn(getenv))
	}
	if !noPay {
		return ubyport.ResolveAlert(ctx, pool, key)
	}
	id := apartmentID
	return ubyport.RaiseAlert(ctx, pool, "warning", NoPayWayKind, noPayWayMessage, "", key, &id, nil, nil,
		ubyport.AlertParams{"property": ap.InternalName})
}

// ReconcileAllNoPayWay is stay_fee.reconcile_all_no_pay_way: every collecting,
// unarchived apartment and every apartment with an open alert of the kind, in
// id order (Python iterates a set). It returns how many it checked and stops
// at the first error, as Python does.
func ReconcileAllNoPayWay(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string) (int, error) {
	collecting, err := queryIDs(ctx, pool, `SELECT id FROM apartment WHERE stay_fee_collect = 1 AND archived_at IS NULL`)
	if err != nil {
		return 0, err
	}
	alerted, err := queryIDs(ctx, pool, `SELECT apartment_id FROM alert WHERE kind = $1 AND resolved_at IS NULL
		AND apartment_id IS NOT NULL`, NoPayWayKind)
	if err != nil {
		return 0, err
	}
	seen := map[int64]bool{}
	var ids []int64
	for _, id := range append(collecting, alerted...) {
		if !seen[id] {
			seen[id] = true
			ids = append(ids, id)
		}
	}
	sort.Slice(ids, func(i, j int) bool { return ids[i] < ids[j] })
	for _, id := range ids {
		if err := ReconcileNoPayWay(ctx, pool, getenv, id); err != nil {
			return 0, err
		}
	}
	return len(ids), nil
}
````

### Block 6: `go/internal/stayfeemail/job_test.go` sha256 `dc26766b5921caa17cef144d263fc24b938a0d765c92bd898b0d30570bd724cf`

````go
package stayfeemail

// Go vs Python for the stay_fee_mail job (brief 1242). The golden
// testdata/stay_fee_job_golden.json is written by
// App/scripts/stay_fee_job_golden.py; the database tests skip without
// UBYHOST_TEST_DATABASE_URL (CI's Go job sets it).

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"
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
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
)

type jobGolden struct {
	Seed     map[string][]map[string]any `json:"seed"`
	FakePDF  string                      `json:"fake_pdf"`
	Runs     []map[string]any            `json:"runs"`
	Writes   map[string]any              `json:"writes"`
	DueMonth []string                    `json:"due_month"`
}

func loadJobGolden(t *testing.T) *jobGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/stay_fee_job_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g jobGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return &g
}

// norm turns a Go value into the generic JSON form the golden decodes to.
func norm(t *testing.T, v any) any {
	t.Helper()
	raw, err := json.Marshal(v)
	if err != nil {
		t.Fatal(err)
	}
	var out any
	if err := json.Unmarshal(raw, &out); err != nil {
		t.Fatal(err)
	}
	return out
}

func sameJSON(t *testing.T, name string, got, want any) {
	t.Helper()
	g := norm(t, got)
	if !reflect.DeepEqual(g, want) {
		a, _ := json.MarshalIndent(g, "", " ")
		b, _ := json.MarshalIndent(want, "", " ")
		t.Errorf("%s:\n got %s\nwant %s", name, a, b)
	}
}

func TestDueMonthGolden(t *testing.T) {
	g := loadJobGolden(t)
	if len(g.DueMonth) != 730 {
		t.Fatalf("%d due_month rows", len(g.DueMonth))
	}
	for _, line := range g.DueMonth {
		parts := strings.Fields(line)
		today, err := time.Parse("2006-01-02", parts[1])
		if err != nil {
			t.Fatal(err)
		}
		got := "-"
		if m, ok := DueMonth(parts[0], today); ok {
			got = m.Format("2006-01-02")
		}
		if got != parts[2] {
			t.Errorf("due_month %s %s: got %s want %s", parts[0], parts[1], got, parts[2])
		}
	}
}

func TestHandlerNeedsRenderer(t *testing.T) {
	n, err := Handler(nil, Deps{Getenv: func(string) string { return "" }})(context.Background())
	if n != 0 || !errors.Is(err, ErrNoRenderer) {
		t.Fatalf("got %d, %v", n, err)
	}
	if _, err := Run(context.Background(), nil, Deps{}); !errors.Is(err, ErrNoRenderer) {
		t.Fatalf("Run: %v", err)
	}
}

func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_stayfeejob_%d", time.Now().UnixNano())
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

func goldenEnv(k string) string {
	switch k {
	case "UBYHOST_SECRET_KEY":
		return "golden-secret-key-not-for-real-use"
	case "UBYHOST_STAY_FEE_GUEST_PAY":
		return "on"
	case "UBYHOST_MAIL_BACKEND":
		return "console"
	case "UBYHOST_UBYPORT_ENV":
		return "mock"
	case "UBYHOST_APP_BASE_URL":
		return "https://app.example.test"
	case "UBYHOST_PUBLIC_BASE_URL":
		return "https://www.example.test"
	}
	return ""
}

func goldenKeys(t *testing.T) *secure.MultiFernet {
	t.Helper()
	keys, err := secure.LoadDataKeys(goldenEnv)
	if err != nil {
		t.Fatal(err)
	}
	return keys
}

// insertRow writes one seed row; extra adds columns, and encrypt maps a seed
// key to the column that gets its Fernet token.
func insertRow(t *testing.T, pool *pgxpool.Pool, table string, row map[string]any, extra map[string]any,
	encrypt map[string]string, keys *secure.MultiFernet) {
	t.Helper()
	cols, args, marks := []string{}, []any{}, []string{}
	merged := map[string]any{}
	for k, v := range row {
		merged[k] = v
	}
	for k, v := range extra {
		merged[k] = v
	}
	names := make([]string, 0, len(merged))
	for k := range merged {
		names = append(names, k)
	}
	sort.Strings(names)
	for _, k := range names {
		v := merged[k]
		col := k
		if enc, ok := encrypt[k]; ok {
			col = enc
			if s, _ := v.(string); s != "" {
				token, err := keys.EncryptString(s)
				if err != nil {
					t.Fatal(err)
				}
				v = token
			} else {
				v = nil
			}
		}
		if f, ok := v.(float64); ok {
			v = int64(f)
		}
		cols = append(cols, col)
		args = append(args, v)
		marks = append(marks, "$"+strconv.Itoa(len(args)))
	}
	sql := fmt.Sprintf("INSERT INTO %s (%s) VALUES (%s)", table, strings.Join(cols, ", "), strings.Join(marks, ", "))
	if _, err := pool.Exec(context.Background(), sql, args...); err != nil {
		t.Fatalf("%s: %v", table, err)
	}
}

func seedJob(t *testing.T, pool *pgxpool.Pool, g *jobGolden, keys *secure.MultiFernet) {
	t.Helper()
	old := "2026-09-01T00:00:00+00:00"
	stamp := map[string]any{"created_at": old}
	both := map[string]any{"created_at": old, "updated_at": old}
	for _, r := range g.Seed["users"] {
		insertRow(t, pool, "user_account", r, stamp, nil, keys)
	}
	for _, r := range g.Seed["legal_entities"] {
		insertRow(t, pool, "legal_entity", r, stamp, nil, keys)
	}
	for _, r := range g.Seed["apartments"] {
		insertRow(t, pool, "apartment", r, stamp, nil, keys)
	}
	for _, r := range g.Seed["reservations"] {
		insertRow(t, pool, "reservation", r, map[string]any{"uid": fmt.Sprintf("uid-%v", r["id"]),
			"created_at": old, "updated_at": old}, nil, keys)
	}
	for _, r := range g.Seed["guests"] {
		insertRow(t, pool, "guest", r, both, nil, keys)
	}
	for _, r := range g.Seed["adjustments"] {
		insertRow(t, pool, "stay_fee_adjustment", r, nil, map[string]string{"reason": "reason_enc"}, keys)
	}
	for _, r := range g.Seed["filings"] {
		insertRow(t, pool, "stay_fee_filing", r, nil, nil, keys)
	}
	for _, r := range g.Seed["outbox"] {
		insertRow(t, pool, "email_outbox", r, nil, nil, keys)
	}
	for _, r := range g.Seed["alerts"] {
		insertRow(t, pool, "alert", r, nil, nil, keys)
	}
	for _, table := range []string{"user_account", "legal_entity", "apartment", "reservation", "guest",
		"stay_fee_adjustment", "stay_fee_filing", "email_outbox", "alert", "audit"} {
		if _, err := pool.Exec(context.Background(), fmt.Sprintf(
			`SELECT setval(pg_get_serial_sequence('%[1]s', 'id'), COALESCE((SELECT MAX(id) FROM %[1]s), 0) + 1, false)`,
			table)); err != nil {
			t.Fatalf("setval %s: %v", table, err)
		}
	}
}

// fakeRenderer returns the golden's fixed bytes and records its input.
type fakeRenderer struct {
	pdf  []byte
	seen []any
	t    *testing.T
}

func (f *fakeRenderer) Render(h stayfee.Hlaseni) ([]byte, error) {
	f.seen = append(f.seen, norm(f.t, h))
	return f.pdf, nil
}

func (f *fakeRenderer) take() []any {
	out := f.seen
	if out == nil {
		out = []any{}
	}
	f.seen = nil
	return out
}

// queryMaps reads rows as column name -> value maps.
func queryMaps(t *testing.T, pool *pgxpool.Pool, sql string) []map[string]any {
	t.Helper()
	rows, err := pool.Query(context.Background(), sql)
	if err != nil {
		t.Fatal(err)
	}
	maps, err := pgx.CollectRows(rows, pgx.RowToMap)
	if err != nil {
		t.Fatal(err)
	}
	return maps
}

func pick(m map[string]any, keys ...string) map[string]any {
	out := map[string]any{}
	for _, k := range keys {
		out[k] = m[k]
	}
	return out
}

func snapshotJob(t *testing.T, pool *pgxpool.Pool, keys *secure.MultiFernet) map[string]any {
	t.Helper()
	open := func(v any) ([]byte, bool) {
		var token string
		switch x := v.(type) {
		case nil:
			return nil, false
		case []byte:
			token = string(x)
		case string:
			token = x
		}
		if token == "" {
			return nil, false
		}
		plain, err := keys.Decrypt(token, 0, time.Now())
		if err != nil {
			t.Fatalf("decrypt: %v", err)
		}
		return plain, true
	}
	b64 := func(v any) any {
		if plain, ok := open(v); ok {
			return base64.StdEncoding.EncodeToString(plain)
		}
		return nil
	}
	text := func(v any) any {
		if plain, ok := open(v); ok {
			return string(plain)
		}
		return nil
	}
	filings := []map[string]any{}
	for _, r := range queryMaps(t, pool, `SELECT * FROM stay_fee_filing ORDER BY id`) {
		f := pick(r, "id", "apartment_id", "period_key", "version", "cadence", "rate_czk", "liable_days",
			"exempt_days", "total_due_czk", "total_collected_czk", "created_at", "superseded_at")
		f["pdf"], f["csv"], f["payload"] = b64(r["pdf_enc"]), b64(r["csv_enc"]), text(r["payload_enc"])
		filings = append(filings, f)
	}
	adjustments := []map[string]any{}
	for _, r := range queryMaps(t, pool, `SELECT * FROM stay_fee_adjustment ORDER BY id`) {
		a := pick(r, "id", "apartment_id", "period_key", "direction", "mode", "people_count", "nights",
			"bed_days", "created_by", "created_at", "reversed_at", "reversed_by", "filing_id")
		a["reason"] = text(r["reason_enc"])
		adjustments = append(adjustments, a)
	}
	outbox := []map[string]any{}
	for _, r := range queryMaps(t, pool, `SELECT * FROM email_outbox ORDER BY idempotency_key`) {
		outbox = append(outbox, pick(r, "idempotency_key", "kind", "reservation_id", "apartment_id",
			"owner_user_id", "to_email", "cc_email", "subject", "payload", "state", "attempts"))
	}
	alerts := []map[string]any{}
	for _, r := range queryMaps(t, pool, `SELECT * FROM alert ORDER BY dedupe_key, id`) {
		a := pick(r, "level", "kind", "apartment_id", "reservation_id", "owner_user_id", "dedupe_key",
			"message", "detail", "params")
		a["resolved"] = r["resolved_at"] != nil
		alerts = append(alerts, a)
	}
	audit := []map[string]any{}
	for _, r := range queryMaps(t, pool, `SELECT * FROM audit WHERE action LIKE 'stay_fee%' ORDER BY id`) {
		audit = append(audit, pick(r, "at", "actor", "action", "detail", "owner_user_id", "actor_user_id"))
	}
	return map[string]any{"filings": filings, "adjustments": adjustments, "outbox": outbox,
		"alerts": alerts, "audit": audit}
}

func fixedNow(t *testing.T, s string) func() time.Time {
	t.Helper()
	at, err := time.Parse(time.RFC3339, s)
	if err != nil {
		t.Fatal(err)
	}
	return func() time.Time { return at }
}

func sameState(t *testing.T, name string, got, want map[string]any) {
	t.Helper()
	for _, part := range []string{"filings", "adjustments", "outbox", "alerts", "audit"} {
		sameJSON(t, name+" "+part, got[part], want[part])
	}
}

func TestJobGolden(t *testing.T) {
	pool := testPool(t)
	g := loadJobGolden(t)
	keys := goldenKeys(t)
	seedJob(t, pool, g, keys)
	pdf, err := base64.StdEncoding.DecodeString(g.FakePDF)
	if err != nil {
		t.Fatal(err)
	}
	fake := &fakeRenderer{pdf: pdf, t: t}
	ctx := context.Background()
	for _, run := range g.Runs {
		name := run["name"].(string)
		for _, sql := range run["before"].([]any) {
			if _, err := pool.Exec(ctx, sql.(string)); err != nil {
				t.Fatal(err)
			}
		}
		now := fixedNow(t, run["now"].(string))
		if got := pragueToday(now()).Format("2006-01-02"); got != run["today"] {
			t.Fatalf("%s: Prague today %s, golden %v", name, got, run["today"])
		}
		counts, err := Run(ctx, pool, Deps{Getenv: goldenEnv, Now: now, Renderer: fake, Keys: keys})
		if err != nil {
			t.Fatalf("%s: %v", name, err)
		}
		reconciled, err := ReconcileAllNoPayWay(ctx, pool, goldenEnv)
		if err != nil {
			t.Fatalf("%s reconcile: %v", name, err)
		}
		sameJSON(t, name+" counts", counts, run["counts"])
		sameJSON(t, name+" reconciled", reconciled, run["reconciled"])
		sameJSON(t, name+" rendered", fake.take(), run["rendered"])
		sameState(t, name, snapshotJob(t, pool, keys), run["state"].(map[string]any))
	}
	runWrites(t, pool, g, keys, fake)
}

func refusal(err error) string {
	switch {
	case err == nil:
		return "no error"
	case errors.Is(err, stayfee.ErrChanged):
		return "ValueError: filing changed"
	case errors.Is(err, stayfee.ErrOverlap):
		return "ValueError: overlaps saved period"
	case errors.Is(err, stayfee.ErrInactive):
		return "ValueError: inactive property"
	}
	return err.Error()
}

func runWrites(t *testing.T, pool *pgxpool.Pool, g *jobGolden, keys *secure.MultiFernet, fake *fakeRenderer) {
	ctx := context.Background()
	want := g.Writes
	now := fixedNow(t, "2026-10-20T06:00:00+00:00")
	today := stayfee.Day(2026, 10, 20)
	deps := stayfee.SaveDeps{Dec: stayfee.FernetDecrypter(keys), Enc: stayfee.FernetEncrypter(keys),
		Renderer: fake, Now: now, ScheduleToday: today}
	ap := map[int64]*stayfee.Apartment{}
	for _, id := range []int64{1, 3, 9} {
		a, err := stayfee.LoadApartment(ctx, pool, id)
		if err != nil {
			t.Fatal(err)
		}
		ap[id] = a
	}
	added, err := stayfee.AddAdjustment(ctx, pool, deps.Enc, stayfee.AdjustmentInput{ApartmentID: 1,
		PeriodKey: "2026-09", Direction: "add", Mode: "people", PeopleCount: 2, Nights: 3, BedDays: 6,
		Reason: "Correction: 2 people × 3 nights", CreatedBy: 1}, now())
	if err != nil {
		t.Fatal(err)
	}
	sameJSON(t, "added", added, want["added"])
	if err := stayfee.ReverseAdjustment(ctx, pool, 1, 1, now()); err != nil {
		t.Fatal(err)
	}
	live, err := stayfee.Latest(ctx, pool, 1, "2026-09")
	if err != nil || live == nil {
		t.Fatalf("latest: %v %v", live, err)
	}
	sameJSON(t, "replaced", live.ID, want["replaced"])
	sept := stayfee.Day(2026, 9, 1)
	corrected, err := stayfee.Save(ctx, pool, deps, ap[1], stayfee.SaveArgs{Month: sept,
		Collected: map[int64]int{101: 0}, IssuedOn: today, ReplacingID: &live.ID})
	if err != nil {
		t.Fatal(err)
	}
	sameJSON(t, "corrected", corrected, want["corrected"])
	_, err = stayfee.Save(ctx, pool, deps, ap[1], stayfee.SaveArgs{Month: sept, Collected: map[int64]int{},
		IssuedOn: today, ReplacingID: &live.ID})
	sameJSON(t, "changed", refusal(err), want["changed"])
	_, err = stayfee.Save(ctx, pool, deps, ap[3], stayfee.SaveArgs{Month: sept, Collected: map[int64]int{}, IssuedOn: today})
	sameJSON(t, "overlap", refusal(err), want["overlap"])
	_, err = stayfee.Save(ctx, pool, deps, ap[9], stayfee.SaveArgs{Month: sept, Collected: map[int64]int{}, IssuedOn: today})
	sameJSON(t, "inactive", refusal(err), want["inactive"])
	sameJSON(t, "writes rendered", fake.take(), want["rendered"])
	sameState(t, "writes", snapshotJob(t, pool, keys), want["state"].(map[string]any))
}

// Without a renderer Run writes nothing, even on a seeded database.
func TestRunNoRendererWritesNothing(t *testing.T) {
	pool := testPool(t)
	g := loadJobGolden(t)
	keys := goldenKeys(t)
	seedJob(t, pool, g, keys)
	before := snapshotJob(t, pool, keys)
	_, err := Run(context.Background(), pool, Deps{Getenv: goldenEnv, Keys: keys,
		Now: fixedNow(t, "2026-10-05T05:00:00+00:00")})
	if !errors.Is(err, ErrNoRenderer) {
		t.Fatalf("Run: %v", err)
	}
	if n, err := Handler(pool, Deps{Getenv: goldenEnv, Keys: keys})(context.Background()); n != 0 || !errors.Is(err, ErrNoRenderer) {
		t.Fatalf("Handler: %d %v", n, err)
	}
	sameJSON(t, "unchanged", snapshotJob(t, pool, keys), norm(t, before))
}
````

### Block 7: `go/cmd/ubyhost-web/register_job_stay_fee_mail.go` sha256 `f9bb9b89b053cb63391f336c6ca173377383fd67d1b0bc50332c0ba6f2dfcae4`

````go
package main

// Thread 1240 (stay-fee mail) owns this file. The stay_fee_mail job seals the
// due stay-fee periods and queues the host reports (stayfeemail.Handler).
// stayFeeRenderer is nil until brief 1243 plugs in the PDF renderer; until
// then the handler returns stayfeemail.ErrNoRenderer before it reads or
// writes anything, so the kind in UBYHOST_GO_JOB_KINDS only fails the job.

import (
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/jobs"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfeemail"
)

// stayFeeRenderer draws the hlášení PDF. Brief 1243 sets it.
var stayFeeRenderer stayfee.PDFRenderer

func init() {
	registerJob("stay_fee_mail", 24*60, stayFeeMailJob)
}

// stayFeeMailJob builds the handler without touching the pool.
func stayFeeMailJob(pool *pgxpool.Pool) jobs.Handler {
	return stayfeemail.Handler(pool, stayfeemail.Deps{Getenv: os.Getenv, Now: time.Now, Renderer: stayFeeRenderer})
}
````

### Block 8: `go/cmd/ubyhost-web/register_job_stay_fee_mail_test.go` sha256 `668dd0ec18741be3d22d1cc88756b9bb9463ee5786474d22e2c7870f57ea90de`

````go
package main

import (
	"context"
	"errors"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfeemail"
)

// Without a renderer the registered handler fails at once. The pool is nil,
// so any read or write would panic: nothing is touched.
func TestStayFeeMailNeedsRenderer(t *testing.T) {
	if goIntervals["stay_fee_mail"] != 24*60 {
		t.Fatalf("interval %d", goIntervals["stay_fee_mail"])
	}
	h, ok := goHandlers(nil)["stay_fee_mail"]
	if !ok {
		t.Fatal("stay_fee_mail is not registered")
	}
	n, err := h(context.Background())
	if n != 0 || !errors.Is(err, stayfeemail.ErrNoRenderer) {
		t.Fatalf("got %d, %v", n, err)
	}
	if _, err := parseGoKinds("stay_fee_mail"); err != nil {
		t.Fatalf("parseGoKinds: %v", err)
	}
}
````
