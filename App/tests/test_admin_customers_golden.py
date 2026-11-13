"""go/internal/web/customers/*_test.go read go/internal/web/customers/testdata/admin_customers_golden.json.

The generator runs in a child process with no UBYHOST_* variables, so it uses
its own throwaway SQLite database and never the test session's database.
"""

import os
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
GOLDEN = APP_DIR.parent / "go" / "internal" / "web" / "customers" / "testdata" / "admin_customers_golden.json"


def test_admin_customers_golden_matches_python():
    env = {k: v for k, v in os.environ.items() if not k.startswith("UBYHOST_")}
    result = subprocess.run(
        [sys.executable, str(APP_DIR / "scripts" / "admin_customers_golden.py"), "--check"],
        cwd=APP_DIR, env=env, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-1500:]
    committed = GOLDEN.read_bytes()
    assert committed.count(b'"audit_added"') >= 8
    assert committed.count(b'"older"') >= 40
