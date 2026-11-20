"""Freshness for go_go_guest_shell_pick_golden.py (brief 1720c)."""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "App"


def test_shell_pick_golden_fresh():
    proc = subprocess.run(
        [str(APP / ".venv/bin/python"), "scripts/go_go_guest_shell_pick_golden.py", "--check"],
        cwd=APP,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout