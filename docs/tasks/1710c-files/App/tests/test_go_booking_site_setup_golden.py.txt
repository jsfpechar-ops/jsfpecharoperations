"""Freshness of go_booking_site_setup_golden.py output (brief 1710c)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
SCRIPT = APP / "scripts" / "go_booking_site_setup_golden.py"


def test_go_booking_site_setup_golden_fresh():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        cwd=APP,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout