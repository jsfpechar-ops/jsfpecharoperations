"""The Go retention job (go/internal/retention) replays golden.json, which
scripts/retention_golden.py writes from the real Python retention.run().

On PostgreSQL (UBYHOST_TEST_DATABASE_URL or UBYHOST_DATABASE_URL set, as in
the test-postgres-full CI row) this regenerates the golden in a throwaway
database and fails if the committed file is out of date: a change to
App/app/retention.py or a helper it calls must come with a new golden (and a
matching Go change). If this fails, rerun from App/:

    UBYHOST_TEST_DATABASE_URL=<disposable server> .venv/bin/python scripts/retention_golden.py
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1]
GOLDEN = APP_DIR.parent / "go" / "internal" / "retention" / "testdata" / "golden.json"
SCRIPT = APP_DIR / "scripts" / "retention_golden.py"
PG_URL = os.environ.get("UBYHOST_TEST_DATABASE_URL") or os.environ.get("UBYHOST_DATABASE_URL")


def test_golden_lists_four_scenarios_and_the_script_queries():
    doc = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert [s["name"] for s in doc["scenarios"]] == ["global_dry", "owner1_dry", "owner1_apply", "global_apply"]
    assert '"queries": ' in GOLDEN.read_text(encoding="utf-8")
    assert all(s["error"] in (None, "workspaces") for s in doc["scenarios"])


@pytest.mark.skipif(not PG_URL, reason="needs PostgreSQL (UBYHOST_TEST_DATABASE_URL or UBYHOST_DATABASE_URL)")
def test_golden_is_up_to_date_with_python_retention():
    env = {k: v for k, v in os.environ.items() if k not in ("UBYHOST_DB",)}
    env["UBYHOST_TEST_DATABASE_URL"] = PG_URL
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        cwd=str(APP_DIR),
        env=env,
        capture_output=True,
        check=False,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-2000:]
    assert "golden up to date" in result.stdout
