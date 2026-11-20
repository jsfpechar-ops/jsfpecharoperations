"""Freshness check for go_claim_ops_golden.py output (brief 1732)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]


def test_go_claim_ops_golden_is_current():
    script = APP / "scripts" / "go_claim_ops_golden.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--check"],
        cwd=APP,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout