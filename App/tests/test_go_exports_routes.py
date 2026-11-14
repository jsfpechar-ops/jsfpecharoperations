"""go/internal/web/exports reads testdata/exports_routes_golden.json (briefs 1606-1609).

The golden is the Python answers of the house-book PDF zip, the workspace
export, the archive page and the purge button, written by
scripts/exports_routes_golden.py against PostgreSQL, so the freshness check runs
only where a PostgreSQL URL is set (the test-postgres-full CI job).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1]
SCRIPT = APP_DIR / "scripts" / "exports_routes_golden.py"
GOLDEN = APP_DIR.parent / "go" / "internal" / "web" / "exports" / "testdata" / "exports_routes_golden.json"


def test_exports_routes_golden_names_the_covered_routes():
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    paths = {case["path"].split("?")[0] for case in golden["cases"]}
    for path in ("/guests/11/form.pdf", "/housebook/pdfs.zip", "/settings/workspace-export",
                 "/settings/archived", "/settings/purge-expired"):
        assert path in paths


def test_exports_routes_golden_is_current():
    base = os.environ.get("UBYHOST_TEST_DATABASE_URL") or os.environ.get("UBYHOST_DATABASE_URL")
    if not base:
        pytest.skip("the exports routes golden is written on PostgreSQL only")
    env = {k: v for k, v in os.environ.items() if not k.startswith("UBYHOST_")}
    env["UBYHOST_TEST_DATABASE_URL"] = base
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"], cwd=APP_DIR, env=env,
        capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-2000:]
