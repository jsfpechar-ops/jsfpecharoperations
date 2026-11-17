"""go/internal/web/properties/apartment_update_test.go reads go/internal/web/properties/testdata/apartment_update_golden.json.

The generator runs in a child process with no UBYHOST_* variables, so it uses
its own throwaway SQLite database, never the test session's. Brief 1702c1.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
GOLDEN = APP_DIR.parent / "go" / "internal" / "web" / "properties" / "testdata" / "apartment_update_golden.json"


def test_go_apartment_update_golden_matches_python():
    env = {k: v for k, v in os.environ.items() if not k.startswith("UBYHOST_")}
    result = subprocess.run(
        [sys.executable, str(APP_DIR / "scripts" / "go_apartment_update_golden.py"), "--check"],
        cwd=APP_DIR, env=env, capture_output=True, text=True, timeout=300, check=False,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-1500:]
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    cases = {case["name"]: case for case in golden["cases"]}
    assert len(cases) >= 25
    # A refused save writes nothing (no partial write), whether Python draws the page or redirects.
    for case in golden["cases"]:
        if case["page"] or (case["location"] or "").find("err=") >= 0:
            assert not case["changed"] and not case["audit"], case["name"]
    full = cases["full save: rename, new login and password, controller, later rate, PIN, times"]["after"]
    assert full["password"] == "golden-ws-pass" and full["alerts"] == []
    assert full["row"]["uby_mark"] == "MLJNO" and full["slug"] == "loft-karlin-ii-abc234"
    assert full["rates"] == [[50, "2000-01-01"], [40, "2026-12-01"]]
    kept = cases["IBAN-only account kept, no times, rate stays 0"]["after"]["row"]
    assert kept["stay_fee_council_account"] == "CZ6508000000192000145399" and kept["checkin_hour"] is None
