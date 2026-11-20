"""Freshness for go_go_guest_shell_pin_golden.py (brief 1720b)."""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def test_shell_pin_golden_fresh():
    script = ROOT / "App" / "scripts" / "go_go_guest_shell_pin_golden.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--check"],
        cwd=ROOT / "App",
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout