"""The Python plan_outcome oracle regenerates the committed golden bytes.

Runs scripts/ubyport_golden_outcome.py into a temp dir and compares the file
with tests/golden/ubyport/outcome/expected.json byte for byte. Invented data only.
"""

import json
import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
SCRIPT = APP / "scripts" / "ubyport_golden_outcome.py"
GOLDEN = APP / "tests" / "golden" / "ubyport" / "outcome"


def test_outcome_oracle_regenerates_committed_bytes(tmp_path):
    subprocess.run(
        [sys.executable, str(SCRIPT), "--out", str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert (tmp_path / "expected.json").read_bytes() == (GOLDEN / "expected.json").read_bytes()


def test_every_case_has_an_expected_entry():
    cases = json.loads((GOLDEN / "cases.json").read_text(encoding="utf-8"))
    expected = json.loads((GOLDEN / "expected.json").read_text(encoding="utf-8"))
    assert {case["name"] for case in cases} == set(expected)
