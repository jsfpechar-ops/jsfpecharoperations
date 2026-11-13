"""go/internal/web/exports reads testdata/exports_golden.json and i18n.json (briefs 1320, 1321).

The golden is written by scripts/exports_golden.py against PostgreSQL, so the
freshness check runs only where a PostgreSQL URL is set (the test-postgres-full
CI job); the catalog check runs everywhere.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1]
SCRIPT = APP_DIR / "scripts" / "exports_golden.py"
PKG = APP_DIR.parent / "go" / "internal" / "web" / "exports"


def test_exports_catalog_matches_host_strings():
    sys.path.insert(0, str(APP_DIR / "scripts"))
    from go_host_i18n import read_keys, render

    keys = read_keys(PKG / "i18n_keys.txt")
    assert "flash.error.no_receipts" in keys
    assert (PKG / "i18n.json").read_text(encoding="utf-8") == render(keys)


def test_exports_golden_names_the_covered_routes():
    golden = json.loads((PKG / "testdata" / "exports_golden.json").read_text(encoding="utf-8"))
    paths = {case["path"].split("?")[0] for case in golden["cases"]}
    for path in ("/reservations.csv", "/submissions/receipts.zip", "/submissions/1/receipt.pdf",
                 "/submissions/2/errors.pdf", "/submissions/1/request.xml",
                 "/reservations/1/dorucenka.zip", "/housebook.csv", "/guests/11/export.json"):
        assert path in paths


def test_exports_golden_is_current():
    base = os.environ.get("UBYHOST_TEST_DATABASE_URL") or os.environ.get("UBYHOST_DATABASE_URL")
    if not base:
        pytest.skip("the exports golden is written on PostgreSQL only")
    env = {k: v for k, v in os.environ.items() if not k.startswith("UBYHOST_")}
    env["UBYHOST_TEST_DATABASE_URL"] = base
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"], cwd=APP_DIR, env=env,
        capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-2000:]
