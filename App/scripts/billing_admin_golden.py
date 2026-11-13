"""Write go/internal/web/billing/testdata/billing_admin_golden.json from the real Python.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt):

    .venv/bin/python scripts/billing_admin_golden.py

It seeds a throwaway SQLite database with the fixed, synthetic rows in SEED
(no real data), then records, with a fixed "today", what the read side of the
operator billing page /admin/fakturace returns: billing_admin (invoices,
unpaid, accounts_by_status, export_csv), bank_import.unmatched,
billing_analytics (portfolio, revenue_totals, watchlists, operator_queue,
aging, forecast, movement, funnel, trend, discount_overview, the CSV files of
export_all_zip) and the context assembly of routes/admin_billing.py
billing_admin_page. It also records pure helpers (month_or_current and the
three money formatters) and bank_import.parse on synthetic GPC and CSV
statements. The ZIP is compared by the CSV files inside it, not by its bytes.

go/internal/web/billing/*_test.go seeds PostgreSQL from the same file and
compares every scenario. App/tests/test_billing_admin_golden.py fails when
this file is stale.

date.today() inside billing_admin and billing_analytics is frozen to the
scenario's day, so no value depends on the clock. Ordering ties are avoided in
the seed (equal dates in an ORDER BY), because SQL leaves their order open.
"""

from __future__ import annotations

import base64
import io
import json
import os
import sys
import tempfile
import zipfile
from datetime import date, timedelta
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "billing" / "testdata" / "billing_admin_golden.json"

STAMP = "2026-09-01T00:00:00+00:00"
D1 = date(2026, 11, 13)
D2 = date(2026, 12, 30)


def _user(uid, name, email, *, role="host", active=1, verified=None, signup=None, created=STAMP):
    return [uid, f"user{uid}", name, "x", role, active, created, email, verified, signup]


def _account(owner, status, plan, interval, apts, *, ttlock=0, wl=0, carry=0, cancel=0, disc=0,
             reason=None, started=None, ends=None, p_start=None, p_end=None):
    return [owner, status, plan, interval, apts, ttlock, wl, carry, cancel, disc, reason,
            started, ends, p_start, p_end, STAMP]


USERS = [
    _user(1, "Admin", "admin@example.test", role="admin"),
    _user(2, "Alfa s.r.o.", "alfa@example.test", verified=STAMP),
    _user(3, 'Firma "Beta"; spol. s r.o.', "beta@example.test", verified=STAMP),
    _user(4, "Čeněk Žluťoučký", "cenek@example.test", verified=STAMP),
    _user(5, None, "gamma@example.test", verified=STAMP),
    _user(6, "Delta", "delta@example.test", verified=STAMP),
    _user(7, "Epsilon", "epsilon@example.test", verified=STAMP),
    _user(8, "Zeta", "zeta@example.test", verified=STAMP),
    _user(9, "Eta", "eta@example.test", verified=STAMP),
    _user(10, "Theta", "theta@example.test", verified=STAMP),
    _user(11, "Iota", "iota@example.test", verified=STAMP),
    _user(12, "Kappa", "kappa@example.test", verified=STAMP),
    _user(13, "Lambda", "lambda@example.test"),
    _user(14, "My", "my@example.test"),
    _user(15, "Ny", "ny@example.test", verified=STAMP),
]
# 62 signups that never confirmed their email: they fill the queue past its LIMIT 25.
for n in range(62):
    USERS.append(_user(100 + n, f"Signup {n}", f"signup{n}@example.test", active=0,
                       signup=STAMP, created=f"2026-11-01T00:{n // 60:02d}:{n % 60:02d}+00:00"))

ACCOUNTS = [
    # standard yearly, 3 flats: 3570 Kc, monthly 297.5 -> 298 (half to even, up)
    _account(2, "active", "standard", "year", 3, started=STAMP, p_start="2026-10-01", p_end="2027-09-30"),
    # max yearly, 12 flats, whitelabel, carry 100, 15 % off
    _account(3, "active", "max", "year", 12, wl=1, carry=100, disc=15, reason="Launch", started=STAMP,
             p_start="2026-10-01T00:00:00+00:00", p_end="2027-09-30T00:00:00+00:00"),
    _account(4, "canceling", "standard", "month", 5, ttlock=1, cancel=1, started=STAMP,
             p_start="2026-11-01", p_end="2026-11-30"),
    # 149 Kc at 50 % = 74.5 -> 74 (half to even)
    _account(5, "overdue", "standard", "month", 1, disc=50, reason="Partner", started=STAMP,
             p_start="2026-10-12", p_end="2026-11-11"),
    _account(6, "trialing", "standard", "month", 2, started="2026-11-01T00:00:00+00:00",
             ends="2026-11-15T10:00:00+00:00"),
    # a trial ending exactly on the 7th day: listed as a plain date, not with a time
    _account(7, "trialing", "standard", "month", 1, started="2026-11-06T00:00:00+00:00", ends="2026-11-20"),
    _account(8, "trialing", "max", "month", 4, started="2026-11-06T00:00:00+00:00",
             ends="2026-11-20T09:00:00+00:00"),
    _account(9, "trialing", "standard", "month", 1, started="2026-10-30T00:00:00+00:00",
             ends="2026-11-13T08:00:00+00:00"),
    _account(10, "trialing", "standard", "month", 3, started="2026-10-29T00:00:00+00:00",
             ends="2026-11-12T08:00:00+00:00"),
    _account(11, "paused", "standard", "month", 2),
    # 3558 Kc a year: monthly 296.5 -> 296 (half to even, down); ends at period end
    _account(12, "active", "standard", "year", 3, carry=-12, cancel=1, p_start="2026-01-01",
             p_end="2026-12-31"),
    _account(13, "trial_pending", "standard", "month", 1),
    _account(14, "trial_pending", None, None, 0),
    _account(15, "trialing", "standard", "month", 1, started="2026-12-28T00:00:00+00:00",
             ends="2027-01-03T10:00:00+00:00"),
]
for n in range(62):
    ACCOUNTS.append(_account(100 + n, "trial_pending", None, None, 0, started=STAMP))

INVOICES: list = []
_seq: dict = {}


def _snap(name, ico, dic):
    return json.dumps({"invoice": {"buyer_name": name, "buyer_ico": ico, "buyer_dic": dic}},
                      ensure_ascii=False)


BUYERS = {
    2: _snap("Alfa s.r.o.", "12345678", "CZ12345678"),
    3: _snap('Firma "Beta"; spol. s r.o.', "87654321", ""),
    4: _snap("Čeněk Žluťoučký", "", ""),
}


def add(owner, kind, issue, due, p_from, p_to, total, *, voided=0, paid_on=None, via=None,
        corrects=None, snap=None):
    year = int(issue[:4])
    _seq[year] = _seq.get(year, 0) + 1
    n = _seq[year]
    row = [len(INVOICES) + 1, owner, kind, corrects, year, n, f"UBY-{year}-{n:04d}", f"{year}{n:04d}",
           issue, due, p_from, p_to, total, voided, paid_on, via,
           snap if snap is not None else BUYERS.get(owner, _snap(f"Buyer {owner}", "", "")), STAMP]
    INVOICES.append(row)
    return row[0]


def _plus(day, days):
    return (date.fromisoformat(day) + timedelta(days=days)).isoformat()


# Twelve paid months before the page's months: the trend strip keeps the last twelve of sixteen.
for k in range(12):
    y, m = divmod(2025 * 12 + 8 + k, 12)
    issue = f"{y}-{m + 1:02d}-01"
    paid = f"{y}-{m + 1:02d}-06" if k % 2 == 0 else _plus(issue, 35)
    add(2, "invoice", issue, _plus(issue, 14), issue, _plus(issue, 29), 14900 + k * 7,
        paid_on=paid, via="bank_auto")
# October 2026
add(2, "invoice", "2026-10-01", "2026-10-15", "2026-10-01", "2027-09-30", 357000,
    paid_on="2026-10-10", via="bank_auto")
add(3, "invoice", "2026-10-01", "2026-10-15", "2026-10-01", "2027-09-30", 262350,
    paid_on="2026-10-20T08:00:00+00:00", via="bank_manual")
voided_id = add(4, "invoice", "2026-10-05", "2026-10-19", "2026-10-05", "2026-11-04", 44700, voided=1)
add(4, "storno", "2026-10-06", "2026-10-06", "2026-10-05", "2026-11-04", -44700, corrects=voided_id)
add(2, "supplementary", "2026-10-31", "2026-11-14", "2026-10-01", "2026-10-31", 12345)
add(None, "supplementary", "2026-10-15", "2026-10-29", "2026-10-01", "2026-10-31", 500)
# Unpaid and overdue, one per aging edge at D1: 3, 7, 8, 30, 31, 90 and 91 days late.
for i, (due, total, owner) in enumerate([
    ("2026-11-10", 14999, 5), ("2026-11-06", 29901, 6), ("2026-11-05", 4950, 7),
    ("2026-10-14", 100050, 8), ("2026-10-13", 1, 9), ("2026-08-15", 99, 10), ("2026-08-14", 300001, 11),
]):
    issue = _plus(due, -14)
    add(owner, "invoice", issue, due, issue, _plus(issue, 29), total,
        snap="" if i == 0 else '{"invoice": {}}' if i == 1 else None)
# Due today, in 30 days (listed in the forecast) and in 31 days (not).
add(11, "supplementary", "2026-11-01", "2026-11-13", "2026-11-01", "2026-11-30", 2599)
add(12, "supplementary", "2026-11-01", "2026-12-13", "2026-11-01", "2026-11-30", 1999)
add(13, "supplementary", "2026-11-01", "2026-12-14", "2026-11-01", "2026-11-30", 777)
# 26 small overdue documents: the watchlist and the queue show 25.
for d in range(1, 27):
    add(2, "supplementary", "2026-08-01", f"2026-09-{d:02d}", "2026-08-01", "2026-08-31", 100 + d)
# November 2026, December (a storno alone: the month's billed sum is negative), January 2027
add(6, "invoice", "2026-11-02", "2026-11-16", "2026-11-02", "2026-12-01", 14900)
add(7, "invoice", "2026-11-03", "2026-11-17", "2026-11-03", "2026-12-02", 9900,
    paid_on="2026-11-08", via="bank_manual")
add(2, "storno", "2026-12-02", "2026-12-02", "2026-10-01", "2027-09-30", -14901, corrects=13)
add(2, "invoice", "2027-01-02", "2027-01-16", "2027-01-02", "2027-01-31", 14900)

PAYMENTS = [
    ["csv-1", "2026-11-11", 14900, "20260006", "123456789/0300", "Platba", None, "matched"],
    ["csv-2", "2026-11-09", 5000, "20260007", "987654/0100", "Částečná platba", None, "partial"],
    ["csv-3", "2026-11-05", 99900, None, None, None, None, "unmatched"],
    ["gpc-77", "2026-10-30", 20000, "20260008", "555/0300", "Přeplatek", None, "overpaid"],
    ["csv-4", "2026-10-25", 14900, "20260009", "123/0800", "OK", None, "matched"],
]
# 205 older unmatched payments: only the 200 newest of the 209 are listed.
for n in range(205):
    PAYMENTS.append([f"seed-{n:03d}", (date(2026, 1, 1) + timedelta(days=n)).isoformat(),
                     100 + n, None, None, None, None, "unmatched"])


def _snapshot(owner, month, status, monthly):
    return [owner, month, status, "standard", "month", 1, 0, 0, 0, monthly, monthly, monthly, STAMP]


SNAPSHOTS = [
    _snapshot(2, "2026-10", "active", 298), _snapshot(2, "2026-11", "active", 298),
    _snapshot(3, "2026-10", "active", 2000), _snapshot(3, "2026-11", "active", 2500),
    _snapshot(4, "2026-10", "active", 500), _snapshot(4, "2026-11", "canceling", 400),
    _snapshot(5, "2026-10", "active", 200), _snapshot(5, "2026-11", "paused", 0),
    _snapshot(6, "2026-10", "trialing", 0), _snapshot(6, "2026-11", "active", 149),
    _snapshot(7, "2026-11", "active", 99),
    _snapshot(8, "2026-10", "overdue", 300), _snapshot(8, "2026-11", "overdue", 300),
    _snapshot(9, "2026-10", "paused", 0), _snapshot(9, "2026-11", "active", 120),
    _snapshot(10, "2026-10", "active", 50),
    _snapshot(11, "2026-11", "trialing", 0),
    _snapshot(2, "2025-12", "active", 100), _snapshot(2, "2026-01", "active", 150),
    _snapshot(3, "2026-01", "active", 200),
]

SEED = [
    {"table": "user_account",
     "columns": ["id", "username", "display_name", "password_hash", "role", "active", "created_at",
                 "email", "email_verified_at", "signup_at"],
     "rows": USERS},
    {"table": "billing_account",
     "columns": ["owner_user_id", "status", "plan", "billing_interval", "apartments_billed",
                 "addon_ttlock", "addon_whitelabel", "carry_czk", "cancel_at_period_end",
                 "discount_percent", "discount_reason", "trial_started_at", "trial_ends_at",
                 "period_start", "period_end", "updated_at"],
     "rows": ACCOUNTS},
    {"table": "platform_invoice",
     "columns": ["id", "owner_user_id", "kind", "corrects_id", "seq_year", "seq_no", "number", "vs",
                 "issue_date", "due_date", "period_from", "period_to", "total_haler", "voided",
                 "paid_on", "paid_via", "snapshot_json", "created_at"],
     "rows": INVOICES},
    {"table": "bank_payment",
     "columns": ["bank_tx_id", "received_on", "amount_haler", "vs", "counter_account", "message",
                 "matched_invoice_id", "status"],
     "rows": PAYMENTS},
    {"table": "billing_month_snapshot",
     "columns": ["owner_user_id", "month", "status", "plan", "billing_interval", "apartments",
                 "addon_ttlock", "addon_whitelabel", "discount_percent", "list_czk", "net_czk",
                 "monthly_czk", "created_at"],
     "rows": SNAPSHOTS},
]


# --- synthetic bank statements ------------------------------------------------

CP1250_ALL = bytes(b for b in range(0x80, 0x100) if b not in (0x81, 0x83, 0x88, 0x90, 0x98))


def gpc(tx, amount, code, vs, account, d91, message, d122=""):
    """One 128-character 075 line: columns as bank_import.parse_gpc reads them."""
    line = "075" + "0000001234567890"
    line += account.rjust(16, "0")[:16]
    line += tx.rjust(13, "0")[:13]
    line += (amount if isinstance(amount, str) else str(amount)).rjust(12, "0")[:12]
    line += code + vs.rjust(10, "0")[:10] + "0" * 20 + d91 + message.ljust(20)[:20] + "00203" + d122.ljust(6)
    assert len(line) == 128, len(line)
    return line


def _enc(text, encoding="cp1250", crlf=True):
    return text.replace("\n", "\r\n" if crlf else "\n").encode(encoding)


GPC_LINES = "\n".join([
    "0740000001234567890Synthetic statement   ",
    gpc("1", 14900, "2", "20260006", "123456789", "051126", "Platba za fakturu", "061126"),
    gpc("", 5000, "2", "0020260007", "987654", "301026", "Bez ID"),
    gpc("3", 2500, "1", "20260008", "111", "011126", "Debet"),
    gpc("4", 2500, "4", "20260008", "111", "011126", "Storno"),
    gpc("5", 1000, "2", "20260009", "222", "320126", "Spatne datum", "000000"),
    "075" + "0" * 50,
    gpc("6", 30000, "2", "ABC2026009", "333", "290224", "Priliš žluťoučký kůň"),
    gpc("7", 100, "2", "20260010", "444", "290225", "Leap fallback", "290225"),
    gpc("8", 777, "2", "20260011", "555", "151126", "Short")[:100],
    gpc("9", 123456, "2", "0000000000", "", "151126", "Zero vs"),
    "079 trailing line",
])
GPC_BAD_AMOUNT = "\n".join([
    "0740000001234567890Synthetic statement   ",
    gpc("1", "ABC000000123", "2", "20260006", "123456789", "051126", "Bad amount"),
])

CSV_HEAD = "Datum zaúčtování;Částka;Variabilní symbol;Protiúčet;Kód banky protiúčtu;Zpráva pro příjemce;ID pohybu"
CSV_ROWS = [
    "5. 11. 2026;1 234,50;0020260006;1234567890;0800;Platba;1001",
    "06.11.2026;1.234,50;20260007;987654/0100;;Faktura;",
    "2026-11-07;99,5;;;;Bez VS;1003",
    "2026-11-08;-100,00;20260008;;;Odchozí;1004",
    "2026-11-09;0;20260008;;;Nula;1005",
    ";;;;;;",
    "abc;10;;;;Bad date;1006",
    "31.02.2026;10,00;;;;Impossible day;1007",
    "2026-11-10;1e2;2026 0009;;;Exp;1008",
    "2026-11-11;.5;;;;Half;1009",
    "2026-11-12;2,675;;;;Round down;1010",
    "2026-11-13;0,015;;;;Round;1011",
    "2026-11-23;0,005;;;;Half to zero;1020",
    "2026-11-24;0,025;;;;Half to even;1021",
    "2026-11-14;12.;;;;Dot end;1012",
    "2026-11-15;+5;;;;Plus;1013",
    "2026-11-16;1,5",
    "2026-11-17;abc;;;;Not a number;1014",
    "2026-11-18;nan;;;;Nan;1015",
    "2026-11-19;1\u00a0000\u00a0000,00;;;;Nbsp;1016",
    "2026-11-20;1_0;;;;Underscore;1017",
    "2026-11-21;5,00;;;;\"two\nlines\";1018",
    "2026-11-22;7,00;;;;" + "Žluťoučký " * 20 + ";1019",
]
CSV_TEXT = "Výpis z účtu 123456789/0300\n" + CSV_HEAD + "\n" + "\n".join(CSV_ROWS) + "\n"

PARSER_CASES = [
    ("gpc_cp1250", _enc(GPC_LINES)),
    ("gpc_utf8_bom", b"\xef\xbb\xbf" + _enc(GPC_LINES, "utf-8")),
    ("gpc_leading_blank_lf", _enc("\n  \n" + GPC_LINES, crlf=False)),
    ("gpc_bad_amount", _enc(GPC_BAD_AMOUNT)),
    ("csv_cp1250_semicolon", _enc(CSV_TEXT)),
    ("csv_utf8_bom", b"\xef\xbb\xbf" + _enc(CSV_TEXT, "utf-8")),
    ("csv_comma_english", _enc(
        'Date,Amount,VS,Message,Account\n2026-11-05,"1,234.50",20260006,"Hello, world",111/0100\n'
        '2026-11-06,10.25,"0020260007",Plain,\n3.11.2026,7,,Short year,\n', "utf-8")),
    ("csv_mixed_line_breaks", b"Date;Amount;Message\r2026-11-05;1,00;cr\n2026-11-06;2,00;lf\r\n"
                              b"2026-11-07;3,00;crlf\x0c2026-11-08;4,00;ff\x0b2026-11-09;5,00;vt"),
    ("csv_all_cp1250_bytes", b"Datum;Amount;Message\n2026-11-05;1,00;" + CP1250_ALL + b"\n"),
    ("csv_undefined_cp1250_byte", b"Datum;Castka\n2026-11-05;1,00;\x81\n"),
    ("csv_duplicate_date_columns", _enc("Datum;Datum zaúčtování;Částka;VS\n2026-01-01;2026-02-02;3,00;1\n")),
    ("csv_account_with_slash_and_bank", _enc(
        "Datum;Částka;Protiúčet;Kód banky\n2026-02-02;3,00;12-345/0100;0800\n2026-02-03;4,00;999;0300\n")),
    ("csv_header_only", _enc("Datum;Částka\n")),
    ("csv_no_header", _enc("foo;bar\n1;2\n")),
    ("csv_no_columns", _enc("Částka;Popis\n1;2\n")),
    ("csv_empty", b""),
]


def _parse_case(bank_import, name, data):
    case = {"name": name, "input_b64": base64.b64encode(data).decode("ascii")}
    try:
        case["rows"] = bank_import.parse(data)
    except bank_import.StatementError as exc:
        case["error"] = "StatementError"
        case["reason"] = str(exc)
    except ValueError:
        case["error"] = "ValueError"
    return case


# --- recording ----------------------------------------------------------------


def _json_default(value):
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(type(value))


def _clean(value):
    """Round-trip through JSON, so dates become strings and rows become dicts."""
    return json.loads(json.dumps(value, default=_json_default))


def _seed(db) -> None:
    for table in SEED:
        cols = ", ".join(table["columns"])
        marks = ", ".join("?" for _ in table["columns"])
        for row in table["rows"]:
            db.execute(f"INSERT INTO {table['table']} ({cols}) VALUES ({marks})", row)


def _zip_files(blob: bytes) -> dict:
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        return {name: zf.read(name).decode("utf-8") for name in sorted(zf.namelist())}


def render() -> str:
    """Seed a fresh database, record every scenario, and return the golden JSON text."""
    from app import bank_import, billing_admin, billing_analytics, db

    class Frozen(date):
        current = D1

        @classmethod
        def today(cls):
            return cls.current

    billing_admin.date = Frozen
    billing_analytics.date = Frozen
    db.init_db()
    _seed(db)

    def kc_route(haler):
        return f"{int(haler) // 100:,}".replace(",", " ")

    def admin_page(mesic, q, state, day):
        # The context of routes/admin_billing.py billing_admin_page (lines 33-69).
        month = billing_admin.month_or_current(mesic)
        unpaid = billing_admin.unpaid(day)
        return {
            "month": month,
            "invoices": billing_admin.invoices(month),
            "unpaid": unpaid,
            "unpaid_total": kc_route(sum(int(r["total_haler"]) for r in unpaid)),
            "payments": bank_import.unmatched(),
            "accounts": billing_admin.accounts_by_status(),
            "today": day.isoformat(),
            "q": q.strip()[:120],
            "state": state if state in ("trial_pending", "trialing", "active", "overdue", "canceling",
                                        "paused") else "",
            "cockpit": billing_analytics.portfolio(day),
            "revenue": billing_analytics.revenue_totals(day),
            "watch": billing_analytics.watchlists(day),
            "aging": billing_analytics.aging(day),
            "forecast": billing_analytics.forecast(day),
            "trend_rows": billing_analytics.trend(),
            "movement": billing_analytics.movement(month),
            "funnel_counts": billing_analytics.funnel(),
            "discounts": billing_analytics.discount_overview(),
        }

    calls = {
        "invoices": lambda a, d: billing_admin.invoices(a["month"]),
        "unpaid": lambda a, d: billing_admin.unpaid(d),
        "accounts_by_status": lambda a, d: billing_admin.accounts_by_status(),
        "export_csv": lambda a, d: billing_admin.export_csv(a["month"]).decode("utf-8"),
        "unmatched": lambda a, d: bank_import.unmatched(),
        "portfolio": lambda a, d: billing_analytics.portfolio(d),
        "revenue_totals": lambda a, d: billing_analytics.revenue_totals(d),
        "watchlists": lambda a, d: billing_analytics.watchlists(d),
        "operator_queue": lambda a, d: billing_analytics.operator_queue(d),
        "aging": lambda a, d: billing_analytics.aging(d),
        "forecast": lambda a, d: billing_analytics.forecast(d),
        "movement": lambda a, d: billing_analytics.movement(a["month"]),
        "funnel": lambda a, d: billing_analytics.funnel(),
        "trend": lambda a, d: billing_analytics.trend(),
        "discount_overview": lambda a, d: billing_analytics.discount_overview(),
        "export_all_files": lambda a, d: _zip_files(billing_analytics.export_all_zip()),
        "admin_page": lambda a, d: admin_page(a["mesic"], a["q"], a["state"], d),
    }
    plan = []
    for month in ("2026-10", "2026-11", "2026-12", "2027-01", "2025-02"):
        plan.append(("invoices", {"month": month}, D1))
    for month in ("2026-10", "2026-11", "2026-12"):
        plan.append(("export_csv", {"month": month}, D1))
    for month in ("2026-11", "2026-01"):
        plan.append(("movement", {"month": month}, D1))
    for fn in ("unpaid", "portfolio", "revenue_totals", "watchlists", "aging", "forecast"):
        plan.append((fn, {}, D1))
        plan.append((fn, {}, D2))
    plan.append(("revenue_totals", {}, date(2026, 10, 15)))
    for fn in ("accounts_by_status", "unmatched", "operator_queue", "funnel", "trend",
               "discount_overview", "export_all_files"):
        plan.append((fn, {}, D1))
    plan.append(("discount_overview", {}, D2))
    plan.append(("admin_page", {"mesic": "2026-11", "q": "  Alfa  ", "state": "active"}, D1))
    plan.append(("admin_page", {"mesic": "bad", "q": "x" * 130, "state": "nope"}, D2))

    scenarios = []
    for fn, args, day in plan:
        Frozen.current = day
        scenarios.append({"fn": fn, "args": args, "today": day.isoformat(),
                          "result": _clean(calls[fn](args, day))})
    Frozen.current = D1

    pure = {
        "month_or_current": [
            {"in": value, "out": billing_admin.month_or_current(value, D1)}
            for value in ("2026-10", " 2026-10 ", "2026-13", "2026-00", "", "abc", "2026-1", "2026-10-01",
                          "2026-12\n")
        ],
        "kc_csv": [{"in": h, "out": billing_admin._kc(h)}
                   for h in (0, 5, 99, 100, 12345, 123456789, -1, -250, -123456, 1000000)],
        "cz": [{"in": h, "out": billing_analytics._cz(h)}
               for h in (0, 5, 99, 100, 12345, 123456789, -1, -250, -123456, 1000000)],
        "kc_page": [{"in": h, "out": kc_route(h)}
                    for h in (0, 5, 99, 100, 12345, 123456789, -1, -250, -123456, 1000000, -100000000)],
        "next_month_start": [
            {"in": d.isoformat(), "out": billing_analytics.next_month_start(d)}
            for d in (date(2026, 1, 31), date(2026, 11, 30), date(2026, 12, 1), date(2026, 12, 31))],
    }
    golden = {
        "today": D1.isoformat(),
        "seed": SEED,
        "pure": pure,
        "parser": [_parse_case(bank_import, name, data) for name, data in PARSER_CASES],
        "scenarios": scenarios,
    }
    return json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True, default=_json_default) + "\n"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    if os.environ.get("UBYHOST_DATABASE_URL"):
        sys.exit("refusing to run: UBYHOST_DATABASE_URL is set; this script wipes tables")
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ["UBYHOST_DATA_DIR"] = str(tmp)
    os.environ["UBYHOST_DB"] = str(tmp / "billing_admin_golden.sqlite3")
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    sys.path.insert(0, str(APP))
    main()
