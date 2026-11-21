"""Freshness check for go_go_guest_shell_gate_golden.py (brief 1720d)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_guest_shell_gate_golden_check() -> None:
    script = ROOT / "App" / "scripts" / "go_go_guest_shell_gate_golden.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--check"],
        cwd=ROOT / "App",
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout