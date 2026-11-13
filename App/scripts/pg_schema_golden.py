"""Write the fixtures that pin the Go schema command to Python (brief 1260).

go/internal/schema/expected_schema.json is the schema postgres_schema_status
expects; Go embeds it, because Go has no SQLite to build it from. The testdata
files pin the Go goose parser and the target fingerprint to Python's output.
No database is needed. Run from App/ after adding a goose or migrations file:

    .venv/bin/python scripts/pg_schema_golden.py

With --check it writes nothing and exits 1 when a file is stale.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

from app import config, db  # noqa: E402

SCHEMA_DIR = APP_DIR.parent / "go" / "internal" / "schema"
EXPECTED = SCHEMA_DIR / "expected_schema.json"
GOOSE_GOLDEN = SCHEMA_DIR / "testdata" / "goose_statements_golden.json"
FINGERPRINT_GOLDEN = SCHEMA_DIR / "testdata" / "fingerprint_golden.json"

# Copied from db.postgres_schema_status; test_go_schema_golden.py proves the
# snapshot satisfies that function, so a drift here fails the test.
PG_TYPES = {"INTEGER": "bigint", "REAL": "double precision", "BLOB": "bytea", "TEXT": "text"}
TRIGGERS = [
    "invoice_issued_guard", "invoice_note_guard", "invoice_delete_guard",
    "invoice_item_insert_guard", "invoice_item_update_guard", "invoice_item_delete_guard",
]
INDEX_RE = r"\bCREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z_0-9]*)"

COMPLETE_CASES = [
    "", ";", " ;  ", "SELECT 1;", "SELECT 1", "SELECT ';';", "SELECT ';'", "SELECT 'it''s';",
    "SELECT 1; -- c", "SELECT 1; -- c\n", "-- only", "-- only\n", "SELECT 1;\n-- trailing",
    "/* x; */", "/* x; */ SELECT 1;", "/* open", "SELECT 1; /* open", "a-b;", "a/b;", "a - - b;",
    'SELECT "a;b";', 'SELECT "a;b', "SELECT [a;b];", "SELECT [a;b", "SELECT `a;b`;",
    "SELECT $$a;b$$;", "DO $$ BEGIN END $$;", "SELECT 'é;';", "SELECT é;",
    "CREATE TRIGGER t AFTER INSERT ON x BEGIN SELECT 1; END;",
    "CREATE TRIGGER t AFTER INSERT ON x BEGIN SELECT 1;",
    "CREATE TRIGGER t AFTER INSERT ON x BEGIN SELECT 1; END",
    "CREATE TEMP TRIGGER t BEGIN SELECT 1; END;",
    "create temporary trigger t begin select 1; end ;",
    "CREATE TRIGGER x BEGIN SELECT 1; END; SELECT 2;",
    "CREATE TRIGGER x BEGIN SELECT 1; END; SELECT 2",
    "EXPLAIN SELECT 1;", "EXPLAIN CREATE TRIGGER x BEGIN SELECT 1; END;",
    "EXPLAIN CREATE TRIGGER x BEGIN SELECT 1;",
    "CREATE TABLE trigger_log (a);", "CREATE INDEX end_idx ON t(end);",
    "CREATE OR REPLACE TRIGGER x BEGIN SELECT 1;", "CREATE\tTRIGGER\nx BEGIN SELECT 1; END\f;",
    "CREATE TEMPORARY TABLE t (a);", "create_trigger;", "CREATE TRIGGERS x;",
]

SPLIT_CASES = [
    "", "\n\n", "SELECT 1;", "SELECT 1; SELECT 2;\nSELECT 3;\n", "SELECT 1;\r\nSELECT 2;\r\n",
    "SELECT 1;\rSELECT 2;\r", "SELECT\n  1;\n-- tail comment\n", "-- head\nSELECT 1;\n",
    "SELECT 1;\n-- a\n\n-- b", "SELECT 1;\nSELECT 2", "SELECT 1;\n  -- ok\n  x", "SELECT 1;\fSELECT 2;\f",
    "SELECT 1;\x0bSELECT 2;", "SELECT 1;\x1cSELECT 2;\x1c", "SELECT 1; SELECT 2; ",
    "SELECT 1;\x85", "  SELECT 1;  \n\t\n", "SELECT 'a\nb;\nc';\n", "/* a\nb; */ SELECT 1;\n",
    "SELECT 1; -- x\nSELECT 2;", "SELECT 1;\x1f\n",
]

GOOSE_CASES = [
    "SELECT 1;",
    "-- +goose Up\nSELECT 1;\n",
    "-- +goose Up\n-- only a comment;\nSELECT 1;\n-- +goose Down\nSELECT 2;\n",
    "-- +goose Up\n-- +goose StatementBegin\nCREATE FUNCTION f() AS $$ BEGIN; END $$;\n-- +goose StatementEnd\n",
    "-- +goose Up\nSELECT 1;\n-- +goose StatementBegin\nA;\nB;\n-- +goose StatementEnd\nSELECT 2;\n",
    "-- +goose Up\n-- +goose StatementBegin\nA;\n",
    "-- +goose Up\nSELECT 1\n",
    "  -- +goose Up  \r\nSELECT 1;\r\n  -- +goose Down\r\nSELECT 2;\r\n",
    "SELECT 0;\n-- +goose Up\nSELECT 1;\n",
    "-- +goose Down\nSELECT 2;\n-- +goose Up\nSELECT 1;\n",
    "-- +goose Up\n-- +goose StatementBegin\n\n-- +goose StatementEnd\nSELECT 1;\n",
    "-- +goose Up\n-- comment\n\n-- other comment\n",
    "-- +goose Up\nSELECT 1; -- trailing\n",
]

FINGERPRINT_URLS = [
    "postgresql:///ubyhost?host=/var/run/postgresql",
    "postgresql://ubyhost@/ubyhost?host=%2Fvar%2Frun%2Fpostgresql&port=5432",
    "postgresql://postgres:ubyhost@localhost:5432/ubyhost_test",
    "postgresql://postgres:ubyhost@127.0.0.1:5432/ubyhost_test",
    "postgresql://postgres@127.0.0.1:55460/postgres",
    "postgres://u:p@DB.Example.COM:6543/app?sslmode=require",
    "postgres://u:p@db.example.com/app?sslmode=verify-full",
    "postgresql://u@db.example.com/app",
    "postgresql://u@db.example.com/app?sslmode=disable",
    "postgresql://u@[::1]:5433/x",
    "postgresql://u@[::1]/x",
    "postgresql://[::1/db",
    "postgresql://[127.0.0.1]/db",
    "postgresql:///db?host=//var/run//pg/",
    "postgresql:///db?host=///var/run/pg",
    "postgresql:///db?host=/var/run/../run/./pg",
    "postgresql:///db?host=/../x",
    "postgresql:///db?host=relative",
    "postgresql:///db?host=/",
    "postgresql:///db?host=",
    "postgresql://h/db?host=/s",
    "postgresql:///db",
    "postgresql:///db?host=/s&port=abc",
    "postgresql:///db?host=/s&port=0",
    "postgresql:///db?host=/s&port=70000",
    "postgresql:///db?host=/s&port=6000",
    "postgresql://localhost:5432/db?port=5433",
    "postgresql://localhost:5433/db?port=5433",
    "postgresql://localhost:0/db",
    "postgresql://localhost:99999/db",
    "postgresql://localhost:5x/db",
    "postgresql://localhost:/db",
    "mysql://localhost/db",
    "postgresql://localhost/db#frag",
    "postgresql://localhost/db#",
    "postgresql://localhost/",
    "postgresql://localhost/a/b",
    "postgresql://localhost//db//",
    "postgresql://localhost/db%20name",
    "postgresql://localhost/caf%C3%A9",
    "postgresql://localhost/a%2Fb",
    "postgresql://localhost/bad%zzpct",
    "postgresql:///db?host=/s&host=/t",
    "postgresql:///db?host=/s&&port=5",
    "postgresql:///db?host=/s+x",
    "POSTGRESQL://LOCALHOST/Db",
    "postgresql://localhost/db?sslmode",
    " postgresql://localhost/db",
    "postgresql://local\thost/db",
    "postgresql://user:p%40ss@localhost/db",
    "postgresql://a@b@localhost/db",
    "localhost/db",
    "",
]


def _dump(obj) -> str:
    return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=True) + "\n"


def expected_schema() -> dict:
    columns = db._expected_sqlite_columns()
    columns["schema_migrations"] = [
        ("version", "INTEGER", 1, 1),
        ("name", "TEXT", 1, 0),
        ("applied_at", "TEXT", 1, 0),
    ]
    tables = {
        table: [
            {"name": name, "type": PG_TYPES.get(kind, ""), "not_null": bool(notnull or pk)}
            for name, kind, notnull, pk in cols
        ]
        for table, cols in columns.items()
    }
    indexes = {"ubyhost_user_account_username_sqlite_nocase"}
    for source in [db.SCHEMA, *(p.read_text(encoding="utf-8") for _v, _n, p in db.migration_files())]:
        indexes.update(re.findall(INDEX_RE, db._without_sql_comments(source), re.IGNORECASE))
    return {
        "comment": "Generated by App/scripts/pg_schema_golden.py; never edit.",
        "expected_version": db.expected_schema_version(),
        "tables": tables,
        "indexes": sorted(indexes),
        "triggers": sorted(TRIGGERS),
    }


def _outcome(fn, arg):
    try:
        return {"ok": fn(arg)}
    except RuntimeError as exc:
        return {"error": str(exc)}


def goose_golden() -> dict:
    # Python never parses 00001 (apply records it as the baseline) and its
    # parser refuses that pg_dump file; Go must refuse it the same way.
    def hashed(text):
        return [hashlib.sha256(s.encode("utf-8")).hexdigest() for s in db._goose_up_statements(text)]

    files = {
        path.name: _outcome(hashed, path.read_text(encoding="utf-8"))
        for _version, _name, path in db.goose_files()
    }
    return {
        "comment": "Generated by App/scripts/pg_schema_golden.py; never edit.",
        "files": files,
        "complete": [[text, sqlite3.complete_statement(text)] for text in COMPLETE_CASES],
        "split": [[text, _outcome(db._statements, text)] for text in SPLIT_CASES],
        "goose": [[text, _outcome(db._goose_up_statements, text)] for text in GOOSE_CASES],
    }


def fingerprint_golden() -> dict:
    return {
        "comment": "Generated by App/scripts/pg_schema_golden.py; never edit.",
        "cases": [[url, _outcome(config._database_target_fingerprint, url)] for url in FINGERPRINT_URLS],
    }


def render() -> dict:
    return {
        EXPECTED: _dump(expected_schema()),
        GOOSE_GOLDEN: _dump(goose_golden()),
        FINGERPRINT_GOLDEN: _dump(fingerprint_golden()),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="write nothing; exit 1 when a file is stale")
    args = parser.parse_args(argv)
    stale = []
    for path, text in render().items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == text:
            continue
        stale.append(path)
        if not args.check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    for path in stale:
        print(f"{'stale' if args.check else 'wrote'}: {path.relative_to(APP_DIR.parent)}")
    return 1 if (args.check and stale) else 0


if __name__ == "__main__":
    raise SystemExit(main())
