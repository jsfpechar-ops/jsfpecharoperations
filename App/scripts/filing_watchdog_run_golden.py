"""Write go/internal/calendar/testdata/filing_watchdog_run_golden.json from the real Python.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/filing_watchdog_run_golden.py

It seeds a throwaway SQLite database with SEED from filing_watchdog_golden.py
(brief 1159) and calls filing_watchdog.run once per entry in RUNS, in order, so
each run sees what the one before wrote. Before a run it may change the digest
setting, the mail backend and the operator address. After each run it records
the result, the heartbeat URL, the email_outbox and push_outbox rows the run
added, every stay's at_risk_mailed_at and the digest setting. BUILDERS renders
the digest for inputs no run reaches (more than 50 rows, unknown only), and
CONTACTS records normalise_email for each address form.
go/internal/calendar/filing_watchdog_run_test.go replays the same and compares.
App/tests/test_filing_watchdog_run_golden.py fails when this file is stale.
Timestamps the outbox writes (created_at, next_attempt_at) are not recorded;
a payload and a builder's HTML are recorded as their sha256 (UTF-8).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import date, datetime
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "calendar" / "testdata" / "filing_watchdog_run_golden.json"


def _base():
    spec = importlib.util.spec_from_file_location(
        "filing_watchdog_golden", Path(__file__).resolve().parent / "filing_watchdog_golden.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = _base()
SEED = BASE.SEED
ENV = dict(BASE.GOLDEN_ENV, UBYHOST_HEARTBEAT_FILING_URL="https://hc.example.test/ping/abc/")
UNSET = "-"  # "setting": UNSET deletes the digest setting before the run

# (instant, before). "before" keys: setting (value, or UNSET), mail_backend,
# operator_email: the environment values, applied as config reads them.
RUNS = [
    # Mail off: pushes only, no stamp, no digest, no setting.
    ("2026-09-17T10:00:00+00:00", {"mail_backend": "disabled"}),
    # Mail on: host mails and stamps; the first digest.
    ("2026-09-17T10:05:00+00:00", {"mail_backend": "console"}),
    # 204 and 227 are past the resend grace now; digest within 72 h: none.
    ("2026-09-17T11:00:00+00:00", {}),
    # Sunday: 203 overdue now; 73 h after the last digest: a new one.
    ("2026-09-20T11:05:00+00:00", {}),
    # A stamp in the future does not block the digest.
    ("2026-09-20T11:10:00+00:00", {"setting": "2026-12-01T00:00:00+00:00"}),
    # A stamp without an offset: Python raises, run() logs it, digest 0.
    ("2026-09-20T11:15:00+00:00", {"setting": "2026-09-20T11:10:00"}),
    # An unreadable stamp counts as none.
    ("2026-09-20T11:20:00+00:00", {"setting": "garbage"}),
    # No usable operator address: no digest.
    ("2026-09-20T11:25:00+00:00", {"setting": UNSET, "operator_email": "no-at-sign"}),
    # Exactly 72 h after the last digest: due again.
    ("2026-09-20T11:30:00+00:00", {"setting": "2026-09-17T11:30:00+00:00",
                                   "operator_email": "ops@example.test"}),
    # Empty variable: config falls back to support@ubyhost.com.
    ("2026-09-20T11:35:00+00:00", {"setting": UNSET, "operator_email": ""}),
]


def _builder_stay(i, *, unknown=False):
    stay = {
        "workspace": f"ws{i}@example.test",
        "property": f"Byt {i} <&>",
        "arrival": date(2026, 9, 1 + i % 20),
        "deadline": datetime(2026, 9, 3 + i % 20, 23, 59, 59),
        "unfiled": i % 4 + 1,
    }
    if unknown:
        stay["unfiled"] = 0
        stay["no_guests"] = True
    return stay


# Digest inputs no run reaches: 51 at-risk and 52 unknown rows (both "and N
# more" lines), and an unknown-only digest.
BUILDERS = [
    {"name": "digest_overflow", "stays": 51, "unknown": 52},
    {"name": "digest_unknown_only", "stays": 0, "unknown": 2},
]


# Contact addresses as legal_entity.contact_email may hold them, each with what
# mail.normalise_email (the parseaddr rule) makes of it; every result here is
# the same on Python 3.11, 3.12 and 3.13. Go must give the same address, or
# none and flag the value (logged at error level, the stay left unmailed).
CONTACTS = [
    "host@example.test", "  Host@Example.TEST  ", "Host One <host@example.test>",
    "<host@example.test>", "Jiří Novák <host@example.test>", "o'neil+tag@mail.example-host.test",
    "'host@example.test'", "x" * 241 + "@example.test", "x" * 242 + "@example.test",
    '"Host, One" <host@example.test>', "host@example.test (Host One)", "J. Doe <host@example.test>",
    "mailto:host@example.test", "host@ex ample.test", "<host@example.test",
    "Host <host@example.test", "hé@example.test", "Host One host@example.test",
    "a@b.test, c@d.test", "host@example", "no-at-sign", "Name <host@example.test> trailing",
    "host@example.test>", "Host <a@b.test> <c@d.test>", "host@[127.0.0.1]",
    "Host (x <host@example.test>", '"Host <host@example.test>', "", "   ",
]


def _apply(config, db, before) -> None:
    if "setting" in before:
        if before["setting"] == UNSET:
            db.execute("DELETE FROM settings WHERE key = ?", ("filing_watchdog_digest_sent_at",))
        else:
            db.set_setting("filing_watchdog_digest_sent_at", before["setting"])
    if "mail_backend" in before:
        config.MAIL_BACKEND = before["mail_backend"].strip().lower()
    if "operator_email" in before:
        config.OPERATOR_EMAIL = before["operator_email"].strip() or "support@ubyhost.com"


EMAIL_COLUMNS = ["idempotency_key", "kind", "reservation_id", "apartment_id", "owner_user_id",
                 "to_email", "cc_email", "subject", "payload", "state", "attempts"]
PUSH_COLUMNS = ["idempotency_key", "subscription_id", "user_account_id", "kind", "params", "url",
                "state", "attempts"]


def _emails(db, seen) -> list:
    out = []
    for row in db.query(
        f"SELECT {', '.join(EMAIL_COLUMNS)} FROM email_outbox ORDER BY idempotency_key"
    ):
        if row["idempotency_key"] in seen:
            continue
        seen.add(row["idempotency_key"])
        record = {key: row[key] for key in EMAIL_COLUMNS}
        # The payload carries the HTML part: keep its hash and the readable text.
        payload = row["payload"]
        record["payload"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        record["text"] = json.loads(payload)["text"]
        out.append(record)
    return out


def _pushes(db, seen) -> list:
    out = []
    for row in db.query(
        f"SELECT {', '.join(PUSH_COLUMNS)} FROM push_outbox ORDER BY idempotency_key"
    ):
        if row["idempotency_key"] in seen:
            continue
        seen.add(row["idempotency_key"])
        record = {key: row[key] for key in PUSH_COLUMNS}
        # Go writes the params keys sorted, Python in insertion order: compare values.
        record["params"] = json.loads(row["params"])
        out.append(record)
    return out


def render() -> str:
    """Seed a fresh database, run the watchdog per RUNS, return the golden JSON text."""
    from app import config, db, filing_watchdog, mail, mail_notify

    saved = {name: getattr(config, name) for name in (
        "APP_BASE_URL", "PUBLIC_BASE_URL", "MAIL_BACKEND", "OPERATOR_EMAIL", "WEB_PUSH",
        "HEARTBEAT_FILING_URL")}
    try:
        config.APP_BASE_URL = ENV["UBYHOST_APP_BASE_URL"]
        config.PUBLIC_BASE_URL = ENV["UBYHOST_PUBLIC_BASE_URL"]
        config.MAIL_BACKEND = ENV["UBYHOST_MAIL_BACKEND"]
        config.OPERATOR_EMAIL = ENV["UBYHOST_OPERATOR_EMAIL"]
        config.WEB_PUSH = True
        config.HEARTBEAT_FILING_URL = ENV["UBYHOST_HEARTBEAT_FILING_URL"]
        db.init_db()
        BASE._seed(db)
        seen_mail, seen_push = set(), set()
        runs = []
        for at, before in RUNS:
            _apply(config, db, before)
            result = filing_watchdog.run(datetime.fromisoformat(at))
            stamps = db.query("SELECT id, at_risk_mailed_at FROM reservation ORDER BY id")
            runs.append({
                "at": at,
                "before": before,
                "result": result,
                "heartbeat": filing_watchdog.heartbeat_url(result["at_risk"] > 0),
                "emails": _emails(db, seen_mail),
                "pushes": _pushes(db, seen_push),
                "mailed": {str(r["id"]): r["at_risk_mailed_at"] for r in stamps},
                "setting": db.get_setting("filing_watchdog_digest_sent_at"),
            })
        builders = []
        for case in BUILDERS:
            stays = [_builder_stay(i) for i in range(case["stays"])]
            unknown = [_builder_stay(i, unknown=True) for i in range(case["unknown"])]
            content = mail_notify.build_deadline_digest(stays, lang="en", unknown=unknown)
            builders.append({
                "name": case["name"],
                "stays": [_builder_record(s) for s in stays],
                "unknown": [_builder_record(s) for s in unknown],
                "subject": content["subject"],
                "text": content["text"],
                "html_sha256": hashlib.sha256(content["html"].encode("utf-8")).hexdigest(),
            })
    finally:
        for name, value in saved.items():
            setattr(config, name, value)
    contacts = [{"raw": raw, "python": mail.normalise_email(raw)} for raw in CONTACTS]
    golden = {"env": ENV, "unset": UNSET, "seed": SEED, "runs": runs, "builders": builders,
              "contacts": contacts}
    return json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def _builder_record(stay) -> dict:
    return {
        "workspace": stay["workspace"],
        "property": stay["property"],
        "arrival": stay["arrival"].strftime("%d.%m.%Y"),
        "deadline": stay["deadline"].strftime("%d.%m.%Y %H:%M"),
        "unfiled": stay["unfiled"],
    }


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    BASE.prepare_env()
    main()
