"""PostgreSQL row of the document-number backfill (0473).

Skipped unless UBYHOST_TEST_DATABASE_URL names a disposable database whose name
contains 'test' (the same target rule as tests/test_db_postgres.py).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parent.parent
URL = os.environ.get("UBYHOST_TEST_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not URL,
    reason="needs UBYHOST_TEST_DATABASE_URL (a disposable PostgreSQL database whose name contains 'test')",
)


def _run(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["UBYHOST_DATABASE_URL"] = URL
    env["UBYHOST_SECRET_KEY"] = "pg-test-only-key-0473-not-a-real-secret-0123456789"
    env.pop("UBYHOST_DB", None)
    return subprocess.run(
        [sys.executable, *args],
        cwd=APP,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_document_backfill_check_and_dry_run_work_on_postgresql():
    database = URL.rsplit("/", 1)[-1].split("?", 1)[0]
    schema = _run("scripts/pg_schema.py", "apply", "--expect-database", database)
    assert schema.returncode == 0, schema.stderr[-2000:]
    for flag in ("--check", "--dry-run"):
        result = _run("scripts/migrate_encrypt_doc_fields.py", flag)
        assert result.returncode == 0, result.stderr[-2000:]
        assert "Traceback" not in result.stderr
