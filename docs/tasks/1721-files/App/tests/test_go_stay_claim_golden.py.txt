"""Freshness check for go_stay_claim_golden.py output (brief 1721)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]


def test_go_stay_claim_golden_is_current():
    script = APP / "scripts" / "go_stay_claim_golden.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--check"],
        cwd=APP,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout