"""Freshness for go_go_guest_shell_pin_golden.py (brief 1720b)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]


def test_shell_pin_golden_fresh():
    script = APP / "scripts" / "go_go_guest_shell_pin_golden.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--check"],
        cwd=APP,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout