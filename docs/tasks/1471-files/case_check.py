"""Brief 1471: what goose 00017 does on a database built the way production was.

Run from App/ with a disposable PostgreSQL only (never production):
    .venv/bin/python ../docs/tasks/1471-files/case_check.py "$UBYHOST_TEST_DATABASE_URL" a
    .venv/bin/python ../docs/tasks/1471-files/case_check.py "$UBYHOST_TEST_DATABASE_URL" b
Both build ubyhost_test_1471_case with scripts/pg_schema.py apply and forget goose
version 17. Case a leaves it as built (production as expected). Case b first undoes
part of 00017 by hand (stay_fee_rate_apartment_id_fkey NOT DEFERRABLE;
stay_fee_rate.effective_from, which is in two indexes, one UNIQUE, and
stay_fee_rate.created_at back to the default collation) and inserts rows.
Then it runs the 00017 Up statements in one transaction, prints every relation
lock they took and the time, rolls back, runs pg_schema.py apply for real
(only 00017 is pending), and checks the schema, the data, table rewrite
(relfilenode) and index rebuilds. Prints "CASE <x> OK" and exits 0, or exits 1.
"""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg

sys.path.insert(0, str(Path.cwd()))
from app import db  # only the goose parser is used; no connection

ADMIN, CASE = sys.argv[1], sys.argv[2]
DB = "ubyhost_test_1471_case"
parts = urlsplit(ADMIN)
URL = urlunsplit((parts.scheme, parts.netloc, "/" + DB, parts.query, ""))
GOOSE = Path("migrations_pg/00017_goose_parity.sql")
FKS = ("site_booking_apartment_id_fkey", "site_booking_invoice_id_fkey", "site_booking_owner_user_id_fkey",
       "site_booking_reservation_id_fkey", "stay_fee_rate_apartment_id_fkey", "guest_form_draft_reservation_id_fkey")
STATE = """
SELECT (SELECT count(*) FROM pg_constraint WHERE contype = 'f' AND condeferrable AND NOT condeferred
          AND conname = ANY(%s)),
       (SELECT count(*) FROM information_schema.columns WHERE table_schema = 'public'
          AND table_name = 'stay_fee_rate' AND column_name IN ('effective_from', 'created_at')
          AND collation_name = 'C')
"""
FILENODES = ("SELECT c.relname, c.relfilenode FROM pg_class c WHERE c.relname IN ('stay_fee_rate', "
             "'stay_fee_rate_pkey', 'stay_fee_rate_apartment_id_effective_from_key', 'idx_stay_fee_rate_apartment') "
             "ORDER BY 1")
LOCKS = ("SELECT c.relname, l.mode FROM pg_locks l JOIN pg_class c ON c.oid = l.relation "
         "WHERE l.pid = pg_backend_pid() AND c.relnamespace = 'public'::regnamespace AND c.relkind = 'r' "
         "ORDER BY 1, 2")


def apply() -> None:
    env = {k: v for k, v in os.environ.items() if k not in {"UBYHOST_DB", "UBYHOST_TEST_DATABASE_URL"}}
    env.update(UBYHOST_DATABASE_URL=URL, UBYHOST_DATA_DIR=tempfile.mkdtemp())
    out = subprocess.run([sys.executable, "scripts/pg_schema.py", "apply", "--expect-database", DB],
                         env=env, capture_output=True, text=True, check=False)
    print((out.stdout + out.stderr).strip()[-200:])
    if out.returncode:
        sys.exit(1)


with psycopg.connect(ADMIN, autocommit=True) as admin:
    admin.execute(f'DROP DATABASE IF EXISTS "{DB}"')
    admin.execute(f'CREATE DATABASE "{DB}"')
status = 1
try:
    apply()
    with psycopg.connect(URL, autocommit=True) as conn:
        conn.execute("DELETE FROM goose_db_version WHERE version_id = 17")
        if CASE == "b":
            conn.execute("ALTER TABLE stay_fee_rate ALTER CONSTRAINT stay_fee_rate_apartment_id_fkey NOT DEFERRABLE")
            conn.execute('ALTER TABLE stay_fee_rate ALTER COLUMN effective_from TYPE text COLLATE "default"')
            conn.execute('ALTER TABLE stay_fee_rate ALTER COLUMN created_at TYPE text COLLATE "default"')
            user = conn.execute("INSERT INTO user_account (username, password_hash, created_at) "
                                "VALUES ('case-b', 'x', '2026-01-01') RETURNING id").fetchone()[0]
            for name in ("A", "B"):
                apt = conn.execute("INSERT INTO apartment (internal_name, created_at, owner_user_id) "
                                   "VALUES (%s, '2026-01-01', %s) RETURNING id", (name, user)).fetchone()[0]
                for day in ("2026-01-01", "2026-07-01", "2027-01-01"):
                    conn.execute("INSERT INTO stay_fee_rate (apartment_id, rate_czk, effective_from, created_at) "
                                 "VALUES (%s, 50, %s, %s)", (apt, day, day + "T00:00:00+00:00"))
        before_state = conn.execute(STATE, (list(FKS),)).fetchone()
        rows = conn.execute("SELECT * FROM stay_fee_rate ORDER BY id").fetchall()
        nodes = dict(conn.execute(FILENODES).fetchall())
    print(f"before: deferrable_fks={before_state[0]} c_columns={before_state[1]} rows={len(rows)}")
    with psycopg.connect(URL) as conn:  # one transaction, like the apply
        conn.execute("SET lock_timeout = '30s'")  # what both apply paths set
        start = time.monotonic()
        for statement in db._goose_up_statements(GOOSE.read_text(encoding="utf-8")):
            conn.execute(statement)
        took = time.monotonic() - start
        for relname, mode in conn.execute(LOCKS).fetchall():
            print(f"lock: {relname} {mode}")
        print(f"00017 Up took {took * 1000:.0f} ms (rolled back)")
        conn.rollback()
    apply()
    with psycopg.connect(URL, autocommit=True) as conn:
        state = conn.execute(STATE, (list(FKS),)).fetchone()
        same_rows = conn.execute("SELECT * FROM stay_fee_rate ORDER BY id").fetchall() == rows
        after = dict(conn.execute(FILENODES).fetchall())
        dup = None
        if CASE == "b":
            try:
                conn.execute("INSERT INTO stay_fee_rate (apartment_id, rate_czk, effective_from, created_at) "
                             "SELECT apartment_id, 1, effective_from, created_at FROM stay_fee_rate LIMIT 1")
                dup = "accepted"
            except psycopg.errors.UniqueViolation:
                dup = "refused"
    print(f"after: deferrable_fks={state[0]} c_columns={state[1]} rows_intact={same_rows}"
          + (f" duplicate_insert={dup}" if dup else ""))
    print("table rewritten:", after["stay_fee_rate"] != nodes["stay_fee_rate"])
    print("indexes rebuilt:", sorted(k for k in after if k != "stay_fee_rate" and after[k] != nodes[k]))
    ok = tuple(state) == (6, 2) and same_rows and dup in (None, "refused")
    print(f"CASE {CASE} OK" if ok else f"CASE {CASE} FAILED")
    status = 0 if ok else 1
finally:
    with psycopg.connect(ADMIN, autocommit=True) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{DB}" WITH (FORCE)')
sys.exit(status)
