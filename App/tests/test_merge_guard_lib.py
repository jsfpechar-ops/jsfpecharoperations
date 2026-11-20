"""merge-pr-on-green policy helpers (docs/tasks-only vs go/ App code)."""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_merge_guard_lib_bash_unit():
    subprocess.run(
        ["bash", "scripts/test_merge_guard_lib.sh"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )