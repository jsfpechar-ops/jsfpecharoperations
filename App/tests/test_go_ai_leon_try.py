"""go/internal/web/ai reads the Leon test-message files written from this Python (brief 1436).

No database is needed. A stale file means leon.py, guide_facts.py, guest_guide.py or i18n.py changed: run scripts/leon_try_golden.py and commit the result with the Go side.
"""

import os
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]


def test_leon_try_files_are_current():
    env = {k: v for k, v in os.environ.items() if not k.startswith("UBYHOST_")}
    result = subprocess.run(
        [sys.executable, str(APP_DIR / "scripts" / "leon_try_golden.py"), "--check"], cwd=APP_DIR, env=env,
        capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-2000:]
