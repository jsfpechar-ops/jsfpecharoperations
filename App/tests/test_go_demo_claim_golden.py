"""Brief 1597a: demo claim golden freshness."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
SCRIPT = APP / "scripts" / "go_demo_claim_golden.py"


def test_go_demo_claim_golden_fresh():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        cwd=APP,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout