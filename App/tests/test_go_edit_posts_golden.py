"""go_edit_posts_golden.py output must match Python POST behaviour."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]


def test_go_edit_posts_golden_is_current():
    env = {k: v for k, v in __import__("os").environ.items() if not k.startswith("UBYHOST_")}
    proc = subprocess.run(
        [sys.executable, "scripts/go_edit_posts_golden.py", "--check"],
        cwd=APP,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, (proc.stdout + proc.stderr)[-1500:]