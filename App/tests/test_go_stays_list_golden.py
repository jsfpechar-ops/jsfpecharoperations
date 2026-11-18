"""go_stays_list_golden.py output must match Python stays list visible text."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]


def test_stays_visible_golden_is_current():
    proc = subprocess.run(
        [sys.executable, "scripts/go_stays_list_golden.py", "--check"],
        cwd=APP,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr