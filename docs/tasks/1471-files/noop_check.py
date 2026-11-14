"""Brief 1471: prove goose 00017_goose_parity.sql writes nothing on a database built the way production was.

Run from App/ with a disposable PostgreSQL only (never production):
    .venv/bin/python ../docs/tasks/1471-files/noop_check.py "$UBYHOST_TEST_DATABASE_URL"
It makes ubyhost_test_1471_noop, builds it with scripts/pg_schema.py apply (the
translated SQLite migrations, then the goose files), forgets goose version 17,
records xmin of the 6 foreign keys and of every column of the 8 tables, applies
again (only 00017 runs), and compares. Same xmin = no catalog row was written.
Prints "NOOP OK" and exits 0, or prints the changed rows and exits 1.
"""
import os
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit, urlunsplit

import psycopg

ADMIN = sys.argv[1]
DB = "ubyhost_test_1471_noop"
parts = urlsplit(ADMIN)
URL = urlunsplit((parts.scheme, parts.netloc, "/" + DB, parts.query, ""))
SNAPSHOT = """
SELECT 'fk', conrelid::regclass::text, conname, xmin::text, condeferrable::text, condeferred::text
FROM pg_constraint WHERE contype = 'f'
  AND conrelid::regclass::text IN ('site_booking', 'stay_fee_rate', 'guest_form_draft')
UNION ALL
SELECT 'col', attrelid::regclass::text, attname, xmin::text, attcollation::regcollation::text, ''
FROM pg_attribute WHERE attnum > 0 AND NOT attisdropped
  AND attrelid::regclass::text IN ('apartment', 'guest', 'guest_form_draft', 'property_page',
                                    'reservation', 'reservation_claim', 'site_booking', 'stay_fee_rate')
ORDER BY 1, 2, 3
"""


def apply() -> None:
    env = {k: v for k, v in os.environ.items() if k not in {"UBYHOST_DB", "UBYHOST_TEST_DATABASE_URL"}}
    env.update(UBYHOST_DATABASE_URL=URL, UBYHOST_DATA_DIR=tempfile.mkdtemp())
    out = subprocess.run([sys.executable, "scripts/pg_schema.py", "apply", "--expect-database", DB],
                         env=env, capture_output=True, text=True, check=False)
    print((out.stdout + out.stderr).strip()[-300:])
    if out.returncode:
        sys.exit(1)


def snapshot() -> list:
    with psycopg.connect(URL, autocommit=True) as conn:
        return conn.execute(SNAPSHOT).fetchall()


with psycopg.connect(ADMIN, autocommit=True) as admin:
    admin.execute(f'DROP DATABASE IF EXISTS "{DB}"')
    admin.execute(f'CREATE DATABASE "{DB}"')
try:
    apply()
    with psycopg.connect(URL, autocommit=True) as conn:
        conn.execute("DELETE FROM goose_db_version WHERE version_id = 17")
    before = snapshot()
    apply()
    after = snapshot()
    fks = [row for row in before if row[0] == "fk"]
    assert len(fks) == 6 and all(row[4] == "true" and row[5] == "false" for row in fks), fks
    changed = sorted(set(before) ^ set(after))
    print(f"rows compared: {len(before)}; changed: {len(changed)}")
    for row in changed:
        print("changed:", row)
    print("NOOP OK" if not changed and len(before) == len(after) else "NOOP FAILED")
    status = 0 if not changed and len(before) == len(after) else 1
finally:
    with psycopg.connect(ADMIN, autocommit=True) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{DB}" WITH (FORCE)')
sys.exit(status)
