"""go/internal/web/ai reads the Leon setup-wizard files written from this Python (brief 1435).

No database is needed. A stale file means guest_guide.py, leon.py or host_i18n.py changed: run scripts/leon_golden.py and commit the result with the Go side.
"""

import os
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]


def test_leon_setup_files_are_current():
    env = {k: v for k, v in os.environ.items() if not k.startswith("UBYHOST_")}
    result = subprocess.run(
        [sys.executable, str(APP_DIR / "scripts" / "leon_golden.py"), "--check"], cwd=APP_DIR, env=env,
        capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-2000:]
