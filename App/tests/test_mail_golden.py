"""0552, 0642: the submission_problem and cancelled_with_guests mail bytes are pinned before the Go port.

The golden files in tests/golden/mail are the subject, text and HTML that
Python composes today for the invented cases in cases.json (submission_problem)
and cancelled_cases.json (cancelled_with_guests). The Go port must
produce the same bytes from the same inputs. Regenerate with
scripts/mail_golden.py only after a deliberate, reviewed change to the wording
or the markup.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
GOLDEN = APP_DIR / "tests" / "golden" / "mail"
GENERATOR = APP_DIR / "scripts" / "mail_golden.py"


def test_regenerated_mail_matches_committed_files_byte_for_byte(tmp_path):
    subprocess.run(
        [sys.executable, str(GENERATOR), "--out", str(tmp_path)],
        check=True,
        capture_output=True,
    )
    cases = json.loads((GOLDEN / "cases.json").read_text(encoding="utf-8"))
    cancelled = json.loads((GOLDEN / "cancelled_cases.json").read_text(encoding="utf-8"))
    inputs = {"cases.json", "cancelled_cases.json"}
    committed = sorted(p.name for p in GOLDEN.iterdir() if p.name not in inputs)
    regenerated = sorted(p.name for p in tmp_path.iterdir())
    assert regenerated == committed
    assert len(committed) == 3 * (len(cases) + len(cancelled))
    for name in committed:
        assert (tmp_path / name).read_bytes() == (GOLDEN / name).read_bytes(), name
