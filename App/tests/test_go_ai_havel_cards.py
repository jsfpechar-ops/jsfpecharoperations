"""go/internal/web/ai reads the cards and support-mail golden written from this Python (brief 1432).

No database is needed: scripts/havel_cards_golden.py calls pure functions. A stale file means
havel_actions.py or mail_notify.build_havel_support (or host_i18n.py) changed: run the script
and commit the result with the Go side.
"""

import os
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]


def test_havel_cards_golden_is_current():
    env = {k: v for k, v in os.environ.items() if not k.startswith("UBYHOST_")}
    result = subprocess.run(
        [sys.executable, str(APP_DIR / "scripts" / "havel_cards_golden.py"), "--check"], cwd=APP_DIR, env=env,
        capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-2000:]
