"""go/internal/web/guest/testdata/form_pages_golden.json from scripts/go_form_pages_golden.py.

Brief 1723. The generator uses its own throwaway SQLite database.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
GOLDEN = APP_DIR.parent / "go" / "internal" / "web" / "guest" / "testdata" / "form_pages_golden.json"


def test_go_form_pages_golden_matches_python():
    env = {k: v for k, v in os.environ.items() if not k.startswith("UBYHOST_")}
    env.setdefault("UBYHOST_MAIL_BACKEND", "off")
    env.setdefault("UBYHOST_GUEST_PIN_REQUIRED", "0")
    result = subprocess.run(
        [sys.executable, str(APP_DIR / "scripts" / "go_form_pages_golden.py"), "--check"],
        cwd=APP_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-1500:]
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert len(golden["cases"]) == 8
    for case in golden["cases"]:
        if case["method"] == "GET" and case["name"].startswith(("new_", "edit_", "remove_confirm")):
            assert case["status"] == 200, case["name"]
            assert len(case["lines"]) > 30, case["name"]