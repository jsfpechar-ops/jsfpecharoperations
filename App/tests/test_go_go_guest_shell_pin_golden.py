"""Freshness for go_go_guest_shell_pin_golden.py (brief 1720b)."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_shell_pin_golden_fresh():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "App" / "scripts" / "go_go_guest_shell_pin_golden.py"), "--check"],
        cwd=ROOT / "App",
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout