"""Freshness check for go_booking_site_actions_golden.py (brief 1710d)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]


def test_go_booking_site_actions_golden_is_current():
    script = APP / "scripts" / "go_booking_site_actions_golden.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--check"],
        cwd=APP,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout