"""Golden freshness for utility routes (brief 1750)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]


def test_go_go_main_utility_routes_golden_matches_python():
    script = APP_DIR / "scripts" / "go_go_main_utility_routes_golden.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--check"],
        cwd=APP_DIR,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr