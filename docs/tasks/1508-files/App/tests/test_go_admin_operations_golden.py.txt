"""go/internal/web/auth/opspage/page_test.go reads go/internal/web/auth/opspage/testdata/admin_operations_golden.json.

Brief 1508 (port plumbing). The generator runs in a child process with no
UBYHOST_* variables, so it uses its own throwaway SQLite database and never the
test session's database.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
GOLDEN = APP_DIR.parent / "go" / "internal" / "web" / "auth" / "opspage" / "testdata" / "admin_operations_golden.json"


def test_go_admin_operations_golden_matches_python():
    env = {k: v for k, v in os.environ.items() if not k.startswith("UBYHOST_")}
    result = subprocess.run(
        [sys.executable, str(APP_DIR / "scripts" / "admin_operations_golden.py"), "--check"],
        cwd=APP_DIR, env=env, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-1500:]
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert len(golden["cases"]) == 5
    assert all(case["status"] == 200 and len(case["lines"]) > 250 for case in golden["cases"])
