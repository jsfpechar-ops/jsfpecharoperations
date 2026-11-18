"""go/internal/web/properties/apartment_create_test.go reads go/internal/web/properties/testdata/apartment_create_golden.json.

The generator runs in a child process with no UBYHOST_* variables, so it uses
its own throwaway SQLite database, never the test session's. Brief 1700b2.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
GOLDEN = APP_DIR.parent / "go" / "internal" / "web" / "properties" / "testdata" / "apartment_create_golden.json"


def test_go_apartment_create_golden_matches_python():
    env = {k: v for k, v in os.environ.items() if not k.startswith("UBYHOST_")}
    result = subprocess.run(
        [sys.executable, str(APP_DIR / "scripts" / "go_apartment_create_golden.py"), "--check"],
        cwd=APP_DIR, env=env, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-1500:]
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    created = [case for case in golden["cases"] if "created" in case]
    assert len(golden["cases"]) >= 20 and len(created) == 5
    # Quirk kept on create: a copied council account is not saved.
    copied = next(case for case in created if case["form"].get("stay_fee_council_account"))
    assert copied["created"]["row"]["stay_fee_council_account"] is None
    assert copied["created"]["rates"] == [[50, "2000-01-01"]]
