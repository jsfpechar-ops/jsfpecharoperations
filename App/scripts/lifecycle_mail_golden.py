#!/usr/bin/env python3
"""Write the Python oracle for the Go lifecyclemail package (1235).

Dev tool, never run in production. Invented data only: no .env, no network, a
throwaway SQLite database. Run from App/:

    .venv/bin/python scripts/lifecycle_mail_golden.py [--out DIR]

It writes two files to go/internal/lifecyclemail/testdata/lifecycle_mail/:

* fixture.json: the tables the Go test loads into Postgres;
* expected.json: the environment, the state after each run_daily call
  (summary, outbox rows, lifecycle_mail_sent, settings), build_lifecycle
  output for every kind and some unsubscribe tokens and hashes.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUT = APP_DIR.parent / "go" / "internal" / "lifecyclemail" / "testdata" / "lifecycle_mail"

TMP = Path(tempfile.mkdtemp(prefix="lifecycle-golden-"))
ENV = {
    "UBYHOST_LIFECYCLE_MAIL": "1",
    "UBYHOST_MAIL_BACKEND": "console",
    "UBYHOST_SECRET_KEY": "golden-secret-key-0123456789-abcdefghij-invented",
    "UBYHOST_PUBLIC_BASE_URL": "https://www.example.test",
    "UBYHOST_APP_BASE_URL": "https://app.example.test",
    "UBYHOST_OPERATOR_NAME": "Demo & Sons <s.r.o.>",
    "UBYHOST_OPERATOR_ICO": "12345678",
    "UBYHOST_OPERATOR_ADDRESS": "Demo Street 1, 100 00 Praha č",
    "UBYHOST_OPERATOR_EMAIL": "help@example.test",
}
os.environ.update(ENV)
os.environ["UBYHOST_DB"] = str(TMP / "golden.db")
os.environ["UBYHOST_DATA_DIR"] = str(TMP)
os.environ["UBYHOST_ENABLE_SCHEDULER"] = "0"
os.environ.pop("UBYHOST_DATABASE_URL", None)
sys.path.insert(0, str(APP_DIR))

from app import db, lifecycle_mail, mail, mail_notify  # noqa: E402

REF = datetime(2026, 3, 10, 8, 30, tzinfo=timezone.utc)
# Instants: before 09:00 Prague, after, same day again, next day, and the
# morning DST starts (29 March: 06:30Z is 08:30 local, 07:30Z is 09:30 local).
RUNS = [
    datetime(2026, 3, 10, 7, 30, tzinfo=timezone.utc),
    datetime(2026, 3, 10, 8, 30, tzinfo=timezone.utc),
    datetime(2026, 3, 10, 14, 0, tzinfo=timezone.utc),
    datetime(2026, 3, 11, 8, 30, tzinfo=timezone.utc),
    datetime(2026, 3, 30, 6, 30, tzinfo=timezone.utc),
    datetime(2026, 3, 30, 7, 30, tzinfo=timezone.utc),
]


def ago(days: int = 0, hours: int = 0) -> str:
    return (REF - timedelta(days=days, hours=hours)).replace(microsecond=0).isoformat()


# One line per account: (id, login days ago, contact addresses, user columns).
# Apartments, feeds and reservations follow in APARTMENTS, FEEDS, RESERVATIONS.
HOSTS = [
    (1, 4, ["Alpha@Example.Test", " alpha@example.test ", "Second <second@example.test>"], {}),
    (2, 2, ["two@example.test"], {}),  # not due yet
    (3, 5, ["three@example.test"], {"onboarding_emails_opt_out": 1}),
    (4, 5, ["four@example.test"], {}),  # suppressed
    (5, 5, ["five-a@example.test", "five-b@example.test"], {}),  # one suppressed
    (6, 5, [], {}),  # no contact
    (7, 40, ["seven@example.test"], {}),  # too late
    (8, 20, ["eight@example.test"], {}),  # also a 2FA login 5 days ago
    (9, None, ["nine@example.test"], {"last_login_at": ago(4)}),
    (10, 5, ["ten@example.test"], {"active": 0}),
    (11, 5, ["eleven@example.test"], {"deletion_due_at": ago(-5)}),
    (12, 5, ["twelve@example.test"], {"role": "admin"}),
    (13, 10, ["thirteen@example.test"], {}),
    (14, 10, ["fourteen@example.test"], {}),
    (15, 40, ["fifteen@example.test"], {}),
    (16, 40, ["sixteen@example.test"], {}),
    (17, 40, ["seventeen@example.test"], {}),
    (18, 40, ["eighteen@example.test"], {}),
    (19, 10, ["nineteen@example.test"], {}),
    (20, 4, ["twenty@example.test"], {}),  # marker already there
    (21, 3, ["twentyone@example.test"], {}),  # due on the second morning
    (22, 5, ["not-an-email", "", None], {}),
    (23, 4, ["\u017dlu\u0165ou\u010dk\u00fd@example.test"], {}),
    (24, 4, ["dup@example.test"], {}),  # outbox row with the key exists
]
APARTMENTS = [(1, 13, 4), (2, 14, 4), (3, 15, 40), (4, 16, 40), (5, 17, 40), (6, 18, 40), (7, 19, 4), (8, 19, 1)]
FEEDS = [(1, 2, 4, 0, "error"), (2, 3, 15, 1, "ok"), (3, 4, 15, 1, "ok"), (4, 5, 15, 1, "ok"), (5, 6, 10, 1, "ok")]
RESERVATIONS = [(1, 4, "ical"), (2, 5, "demo")]  # both completed


def build_fixture() -> list:
    users, entities, audits = [], [], []
    for uid, days, emails, extra in HOSTS:
        users.append(
            {"id": uid, "username": f"user{uid}", "password_hash": "x", "role": "host", "active": 1,
             "created_at": ago(100), "onboarding_emails_opt_out": 0, **extra}
        )
        if days is not None:
            hours = -6 if uid == 21 else 0
            audits.append({"id": len(audits) + 1, "at": ago(days, hours), "action": "login", "owner_user_id": uid})
        for email in emails:
            entities.append({"id": len(entities) + 1, "name": f"Entity {len(entities) + 1}",
                             "contact_email": email, "owner_user_id": uid, "created_at": ago(100)})
    audits.append({"id": len(audits) + 1, "at": ago(5), "action": "two_factor_login", "owner_user_id": 8})
    apartments = [{"id": a, "owner_user_id": u, "internal_name": f"Flat {a}", "created_at": ago(d)}
                  for a, u, d in APARTMENTS]
    feeds = [{"id": f, "apartment_id": a, "url": f"https://cal.example.test/{f}.ics", "active": act,
              "last_status": status, "created_at": ago(d)} for f, a, d, act, status in FEEDS]
    reservations = [{"id": r, "apartment_id": a, "source": src, "uid": f"uid-{r}", "date_from": "2026-03-01",
                     "date_to": "2026-03-03", "registration_completed_at": ago(5), "created_at": ago(9),
                     "updated_at": ago(9)} for r, a, src in RESERVATIONS]
    suppression = [{"email_hash": lifecycle_mail.email_hash(a), "scope": "onboarding", "created_at": ago(2)}
                   for a in ("four@example.test", "five-a@example.test")]
    sent = [{"user_account_id": 20, "kind": "lifecycle_no_property", "sent_at": ago(1)}]
    outbox = [{"idempotency_key": "lifecycle:lifecycle_no_property:24:dup@example.test",
               "kind": "lifecycle_no_property", "owner_user_id": 24, "to_email": "dup@example.test",
               "subject": "old", "payload": "{}", "state": "queued", "attempts": 0,
               "created_at": ago(1), "updated_at": ago(1)}]
    return [
        ("user_account", users), ("legal_entity", entities), ("audit", audits), ("apartment", apartments),
        ("ical_feed", feeds), ("reservation", reservations), ("lifecycle_mail_sent", sent),
        ("mail_suppression", suppression), ("email_outbox", outbox),
        ("settings", [{"key": "other_setting", "value": "keep"}]),
    ]


def snapshot(skip: int) -> dict:
    """The state now; ``outbox`` holds only the rows after the first ``skip``."""
    outbox = db.query(
        "SELECT idempotency_key, kind, to_email, cc_email, subject, payload, state, attempts, "
        "owner_user_id, reservation_id, apartment_id FROM email_outbox ORDER BY id"
    )
    sent = db.query("SELECT user_account_id, kind FROM lifecycle_mail_sent ORDER BY user_account_id, kind")
    # init_db seeds its own markers; only the keys this job and the fixture use count.
    settings = db.query(
        "SELECT key, value FROM settings WHERE key IN ('lifecycle_mail_last_day', 'other_setting') ORDER BY key"
    )
    return {
        "outbox_total": len(outbox),
        "outbox": [dict(row) for row in outbox][skip:],
        "sent": [dict(row) for row in sent],
        "settings": [dict(row) for row in settings],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    try:
        db.init_db()
        tables = build_fixture()
        for table, rows in tables:
            for row in rows:
                cols = ", ".join(row)
                marks = ", ".join("?" for _ in row)
                db.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(row.values()))
        runs = []
        seen = 1  # the pre-existing outbox row
        for moment in RUNS:
            summary = lifecycle_mail.run_daily(moment)
            state = snapshot(seen)
            seen = state["outbox_total"]
            runs.append({"now": moment.isoformat(), "summary": summary, **state})
        builds = []
        for kind in lifecycle_mail.mail_notify.LIFECYCLE_ACTIONS:
            for url in (
                "https://www.example.test/mail/unsubscribe/abc?lang=en",
                'https://x.example.test/u?a=1&b="2"&c=<3>',
            ):
                content = mail_notify.build_lifecycle(kind, unsubscribe_url=url, lang="en")
                builds.append({"kind": kind, "unsubscribe_url": url, **content})
        tokens = []
        for user_id, address in (
            (1, "Alpha@Example.Test"),
            (0, ""),
            (123456789, "Second <second@example.test>"),
            (7, "Žluťoučký@example.test"),
            (9, "nope"),
        ):
            tokens.append(
                {
                    "user_id": user_id,
                    "address": address,
                    "hash": lifecycle_mail.email_hash(address),
                    "token": lifecycle_mail.unsubscribe_token(user_id, address),
                    "url": lifecycle_mail.unsubscribe_url(user_id, address, "en"),
                }
            )
        expected = {"env": ENV, "runs": runs, "builds": builds, "tokens": tokens}
        args.out.mkdir(parents=True, exist_ok=True)
        fixture = [{"table": table, "rows": rows} for table, rows in tables]
        (args.out / "fixture.json").write_text(
            json.dumps(fixture, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
        )
        (args.out / "expected.json").write_text(
            json.dumps(expected, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
        )
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
