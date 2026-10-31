#!/usr/bin/env python3
"""Inspect or explicitly apply the PostgreSQL schema; never migrate at app startup."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, db  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "check", "apply", "seal-authority"))
    parser.add_argument("--expect-database", required=True)
    args = parser.parse_args(argv)
    try:
        if config.DB_BACKEND != "postgresql":
            raise RuntimeError("Set UBYHOST_DATABASE_URL to select PostgreSQL.")
        actual = db.current_database_name()
        marker_path = config.DATABASE_AUTHORITY_FILE
        if marker_path.exists():
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            if marker.get("database") != actual or marker.get("schema") != "public":
                raise RuntimeError("Connected PostgreSQL target does not match the durable authority marker.")
        if actual != args.expect_database:
            raise RuntimeError("Connected database does not match --expect-database.")
        if args.action == "plan":
            print(f"PostgreSQL {actual}: schema version {db.expected_schema_version()} is planned; no changes made.")
            return 0
        if args.action == "seal-authority":
            marker = config.seal_database_authority(args.expect_database)
            print(f"PostgreSQL authority sealed for database={actual}; marker_format={marker['format_version']}.")
            return 0
        if args.action == "apply":
            status = db.apply_postgresql_schema()
        else:
            status = db.postgres_schema_status()
            if not status["current"]:
                raise RuntimeError("PostgreSQL schema is not current; run the explicit apply command.")
        print(
            f"PostgreSQL schema {args.action} OK: database={actual}, "
            f"version={status['actual_version']}, tables={status['actual_tables']}."
        )
        return 0
    except Exception as exc:
        print(f"PostgreSQL schema {args.action} failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
