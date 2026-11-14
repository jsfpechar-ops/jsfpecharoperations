"""go/internal/web/ai reads Havel's data files and golden cases written from this Python (brief 1430; brief 1432 adds the cards script).

No database is needed: scripts/havel_golden.py calls pure functions.
A stale file means havel.py, havel_topics.py, guide_i18n.py or host_i18n.py changed: run the script and commit the result with the Go side.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1]
PKG = APP_DIR.parent / "go" / "internal" / "web" / "ai"


@pytest.mark.parametrize("script", ["havel_golden.py"])
def test_havel_go_files_are_current(script):
    env = {k: v for k, v in os.environ.items() if not k.startswith("UBYHOST_")}
    result = subprocess.run(
        [sys.executable, str(APP_DIR / "scripts" / script), "--check"], cwd=APP_DIR, env=env,
        capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-2000:]


def test_havel_prompt_file_is_the_python_prompt():
    sys.path.insert(0, str(APP_DIR))
    from app.havel_prompt import HAVEL_SYSTEM_PROMPT

    assert (PKG / "havel_prompt.txt").read_text(encoding="utf-8") == HAVEL_SYSTEM_PROMPT
