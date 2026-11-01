"""The Go response port must match this committed oracle.

The oracle is written by scripts/ubyport_golden_responses.py; see that file.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
SCRIPT = APP_DIR / "scripts" / "ubyport_golden_responses.py"
GOLDEN = APP_DIR / "tests" / "golden" / "ubyport" / "responses"


def test_expected_json_is_current(tmp_path):
    subprocess.run(
        [sys.executable, str(SCRIPT), "--out", str(tmp_path)],
        check=True,
        cwd=APP_DIR,
        capture_output=True,
    )
    assert (tmp_path / "expected.json").read_bytes() == (GOLDEN / "expected.json").read_bytes()


def test_every_input_has_an_entry():
    expected = json.loads((GOLDEN / "expected.json").read_text(encoding="utf-8"))
    inputs = sorted(p.name for p in GOLDEN.glob("*.xml"))
    assert inputs
    assert sorted(expected["responses"]) == inputs
    cases = json.loads((GOLDEN / "classify_cases.json").read_text(encoding="utf-8"))
    assert sorted(expected["classify"]) == sorted(c["name"] for c in cases)
