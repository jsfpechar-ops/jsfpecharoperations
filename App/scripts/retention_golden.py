"""Write go/internal/retention/testdata/golden.json from the real Python retention job.

Needs a disposable PostgreSQL server (the Go port runs on PostgreSQL only).
Run from App/ with the venv (create it first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    UBYHOST_TEST_DATABASE_URL='postgresql://postgres@/postgres?host=/var/tmp/pg&port=5433' \
        .venv/bin/python scripts/retention_golden.py [--check]

The script creates its own database (ubyhost_retention_golden_<pid>) on that
server and drops it at the end. For each scenario it rebuilds the schema from
App/migrations_pg, loads go/internal/retention/testdata/fixture.sql, creates
the photo files, runs retention.run() at a frozen instant and records the
counts, the first failure and the state of every table the job touches.
--check compares with the committed file instead of writing it (exit 1 on a
difference). The Go test in go/internal/retention/ replays the same scenarios.

Brief 1210 ports the counting half only, so only the dry-run scenarios are
recorded; brief 1211 adds the apply scenarios.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit

APP = Path(__file__).resolve().parents[1]
REPO = APP.parent
PKG = REPO / "go" / "internal" / "retention" / "testdata"
OUT = PKG / "golden.json"
FIXTURE = PKG / "fixture.sql"

TODAY = date(2026, 1, 20)
NOW = datetime(2026, 1, 20, 3, 0, 0, 250000, tzinfo=UTC)
PHOTOS = ["1000.jpg.enc", "1001.png", "1002.jpg", "2000.pdf.enc", "notes.txt"]
SCENARIOS = [
    ("global_dry", None, True),
    ("owner1_dry", 1, True),
]
# One text column per row, so Go and Python compare plain strings.
QUERIES = {
    "guest": "SELECT id::text || '|' || COALESCE(filled_ip, '~') FROM guest ORDER BY id",
    "submission": "SELECT id::text FROM submission ORDER BY id",
    "reservation": (
        "SELECT id::text || '|' || COALESCE(guest_email, '~') || '|' || COALESCE(phone_last4, '~')"
        " || '|' || updated_at FROM reservation ORDER BY id"
    ),
    "reservation_claim": (
        "SELECT reservation_id::text || '|' || COALESCE(email, '~') || '|' || updated_at"
        " FROM reservation_claim ORDER BY reservation_id"
    ),
    "stay_fee_filing": "SELECT id::text FROM stay_fee_filing ORDER BY id",
    "stay_fee_adjustment": "SELECT id::text FROM stay_fee_adjustment ORDER BY id",
    "invoice": "SELECT id::text FROM invoice ORDER BY id",
    "invoice_item": "SELECT id::text FROM invoice_item ORDER BY id",
    "platform_invoice": "SELECT id::text FROM platform_invoice ORDER BY id",
    "bank_payment": "SELECT bank_tx_id FROM bank_payment ORDER BY bank_tx_id",
    "audit": (
        "SELECT id::text || '|' || at || '|' || COALESCE(actor, '~') || '|' || action || '|'"
        " || COALESCE(detail, '~') || '|' || COALESCE(owner_user_id::text, '~')"
        " || '|' || COALESCE(actor_user_id::text, '~') || '|' || COALESCE(impersonator_user_id::text, '~')"
        " FROM audit ORDER BY id"
    ),
    "alert": (
        "SELECT id::text || '|' || level || '|' || kind || '|' || COALESCE(owner_user_id::text, '~') || '|'"
        " || COALESCE(apartment_id::text, '~') || '|' || COALESCE(reservation_id::text, '~') || '|'"
        " || COALESCE(dedupe_key, '~') || '|' || message || '|' || COALESCE(detail, '~') || '|'"
        " || COALESCE(params, '~') || '|' || created_at || '|' || COALESCE(resolved_at, '~')"
        " FROM alert ORDER BY id"
    ),
    "rate_limit_event": "SELECT id::text FROM rate_limit_event ORDER BY id",
    "havel_gap": "SELECT id::text FROM havel_gap ORDER BY id",
    "login_token": "SELECT id::text FROM login_token ORDER BY id",
    "webauthn_challenge": "SELECT id::text FROM webauthn_challenge ORDER BY id",
    "door_code": (
        "SELECT id::text || '|' || COALESCE(pin_enc, '~') || '|' || updated_at FROM door_code ORDER BY id"
    ),
    "cleaning_event": "SELECT id::text || '|' || COALESCE(notes_enc, '~') FROM cleaning_event ORDER BY id",
    "cleaning_share": "SELECT id::text FROM cleaning_share ORDER BY id",
    "push_outbox": "SELECT id::text FROM push_outbox ORDER BY id",
    "push_subscription": "SELECT id::text FROM push_subscription ORDER BY id",
    "guide_import": (
        "SELECT id::text || '|' || status || '|' || COALESCE(raw_json, '~') FROM guide_import ORDER BY id"
    ),
    "guest_chat": "SELECT id::text FROM guest_chat ORDER BY id",
    "guest_chat_message": "SELECT id::text FROM guest_chat_message ORDER BY id",
    "guest_question": "SELECT id::text FROM guest_question ORDER BY id",
    "legal_acceptance": "SELECT id::text FROM legal_acceptance ORDER BY id",
    "user_account": "SELECT id::text FROM user_account ORDER BY id",
    "settings": "SELECT key || '=' || COALESCE(value, '~') FROM settings ORDER BY key",
    "email_outbox": "SELECT COUNT(*)::text FROM email_outbox",
}
RETENTION_ENV = (
    "UBYHOST_RETENTION_AUTOPURGE",
    "UBYHOST_RETENTION_NOTICE_DAYS",
    "UBYHOST_AUDIT_RETENTION_DAYS",
    "UBYHOST_ALERT_RETENTION_DAYS",
    "UBYHOST_RATE_LIMIT_RETENTION_HOURS",
)


def _url_for(base: str, name: str) -> str:
    parts = urlsplit(base)
    return urlunsplit((parts.scheme, parts.netloc, "/" + name, parts.query, parts.fragment))


def _migrations_sql() -> list[str]:
    out = []
    for path in sorted((APP / "migrations_pg").glob("*.sql")):
        text = path.read_text(encoding="utf-8")
        i = text.find("-- +goose Up")
        if i >= 0:
            text = text[i + len("-- +goose Up"):]
        j = text.find("-- +goose Down")
        if j >= 0:
            text = text[:j]
        out.append(text)
    return out


class _Frozen(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz) if tz else NOW.astimezone().replace(tzinfo=None)


def _freeze() -> None:
    from app import db, login_link, passkeys, push, retention

    db.datetime = _Frozen
    retention.datetime = _Frozen
    retention.time = SimpleNamespace(time=lambda: NOW.timestamp(), perf_counter=time.perf_counter)
    for module in (login_link, passkeys, push):
        module._now = lambda: NOW


def _scenario(psycopg, url: str, photos_dir: Path, name: str, owner, dry_run: bool) -> dict:
    from app import db, retention

    db.close_connections()
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        for sql in _migrations_sql():
            conn.execute(sql)
        conn.execute(FIXTURE.read_text(encoding="utf-8"))
    photos_dir.mkdir(parents=True, exist_ok=True)
    for old in photos_dir.iterdir():
        old.unlink()
    for photo in PHOTOS:
        (photos_dir / photo).write_bytes(b"x")
    error = None
    try:
        retention.run(TODAY, dry_run=dry_run, owner_user_id=owner)
    except Exception as exc:  # noqa: BLE001 - recorded; the Go test must fail the same way
        error = type(exc).__name__
    db.close_connections()
    state = {}
    with psycopg.connect(url, autocommit=True) as conn:
        for key, sql in QUERIES.items():
            state[key] = [row[0] for row in conn.execute(sql).fetchall()]
        last = conn.execute("SELECT value FROM settings WHERE key = 'retention_last_run'").fetchone()[0]
    counts = [[k, v] for k, v in json.loads(last)["counts"].items()]
    return {
        "name": name,
        "owner_user_id": owner,
        "dry_run": dry_run,
        "error": error,
        "counts": counts,
        "photos": sorted(p.name for p in photos_dir.iterdir()),
        "state": state,
    }


def render() -> str:
    base = os.environ.get("UBYHOST_TEST_DATABASE_URL") or os.environ.get("UBYHOST_DATABASE_URL")
    if not base:
        raise SystemExit("set UBYHOST_TEST_DATABASE_URL to a disposable PostgreSQL server")
    import psycopg

    name = f"ubyhost_retention_golden_{os.getpid()}"
    with psycopg.connect(base, autocommit=True) as admin:
        admin.execute(f"CREATE DATABASE {name}")
    url = _url_for(base, name)
    data_dir = Path(tempfile.mkdtemp(prefix="ubyhost-retention-golden-"))
    os.environ.pop("UBYHOST_DB", None)
    for key in RETENTION_ENV:
        os.environ.pop(key, None)
    os.environ["UBYHOST_DATABASE_URL"] = url
    os.environ["UBYHOST_DATA_DIR"] = str(data_dir)
    os.environ.setdefault("UBYHOST_SECRET_KEY", "retention-golden-not-a-secret")
    os.environ["UBYHOST_ENABLE_SCHEDULER"] = "0"
    sys.path.insert(0, str(APP))
    try:
        _freeze()
        scenarios = [
            _scenario(psycopg, url, data_dir / "passport_photos", n, owner, dry)
            for n, owner, dry in SCENARIOS
        ]
    finally:
        from app import db

        db.close_connections()
        with psycopg.connect(base, autocommit=True) as admin:
            admin.execute(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")
    doc = {
        "today": TODAY.isoformat(),
        "now": NOW.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "photos": PHOTOS,
        "queries": QUERIES,
        "scenarios": scenarios,
    }
    return json.dumps(doc, indent=1, ensure_ascii=True) + "\n"


if __name__ == "__main__":
    text = render()
    if "--check" in sys.argv[1:]:
        if OUT.read_text(encoding="utf-8") != text:
            print(f"{OUT} is out of date: rerun scripts/retention_golden.py")
            raise SystemExit(1)
        print("golden up to date")
    else:
        OUT.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {OUT}")
