"""go/internal/web/hostweb/dashboard_test.go reads testdata/dashboard_golden.json."""

import os
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
GOLDEN = APP_DIR.parent / "go" / "internal" / "web" / "hostweb" / "testdata" / "dashboard_golden.json"


def test_go_dashboard_golden_matches_python():
    env = {k: v for k, v in os.environ.items() if not k.startswith("UBYHOST_")}
    result = subprocess.run(
        [sys.executable, str(APP_DIR / "scripts" / "go_dashboard_golden.py"), "--check"],
        cwd=APP_DIR, env=env, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-1500:]
    assert GOLDEN.is_file()