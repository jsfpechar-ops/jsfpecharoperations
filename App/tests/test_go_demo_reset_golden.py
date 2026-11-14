"""go/internal/web/onboarding/demo_reset_test.go reads go/internal/web/onboarding/testdata/demo_reset_golden.json.

The generator runs in a child process with no UBYHOST_* variables, so it uses
its own throwaway SQLite database and data directory, never the test
session's. Brief 1596.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
GOLDEN = APP_DIR.parent / "go" / "internal" / "web" / "onboarding" / "testdata" / "demo_reset_golden.json"


def test_go_demo_reset_golden_matches_python():
    env = {k: v for k, v in os.environ.items() if not k.startswith("UBYHOST_")}
    result = subprocess.run(
        [sys.executable, str(APP_DIR / "scripts" / "go_demo_reset_golden.py"), "--check"],
        cwd=APP_DIR, env=env, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-1500:]
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert len(golden["cases"]) >= 7
    # The demo of hosts 2 and 3 is gone; their real properties and every other host's stay.
    assert golden["final"]["apartment"] == [203, 302, 501]
    assert "20311.jpg.enc" in golden["photos_left"] and "20111.jpg.enc" not in golden["photos_left"]
