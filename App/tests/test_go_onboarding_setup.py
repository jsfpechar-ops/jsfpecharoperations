"""1290: go/internal/web/onboarding reads testdata/setup_golden.json.

The file is what app/property_setup.py and security.safe_local_path give today.
A Python change that would leave the Go port behind fails here: regenerate with
scripts/onboarding_setup_golden.py and make the Go test pass again.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
SCRIPT = APP_DIR / "scripts" / "onboarding_setup_golden.py"
COMMITTED = APP_DIR.parent / "go" / "internal" / "web" / "onboarding" / "testdata" / "setup_golden.json"


def test_onboarding_setup_golden_matches_python(tmp_path):
    out = tmp_path / "setup_golden.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(out)],
        cwd=APP_DIR,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert out.read_bytes() == COMMITTED.read_bytes()


def test_onboarding_setup_golden_covers_the_matrix():
    golden = json.loads(COMMITTED.read_text(encoding="utf-8"))
    assert len(golden["matrix"]) >= 300
    assert {case["lock_available"] for case in golden["matrix"]} == {True, False}
    assert any(case["raises"] for case in golden["safe_paths"])
    assert all(case["ops"] for case in golden["stored"])
