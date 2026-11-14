"""go/internal/web/exports reads testdata/registration_form_golden.json (brief 1605).

The golden is the draw operations of housebook.registration_form_pdf for made-up
rows, written by scripts/registration_form_golden.py; this test fails when the
Python form changes and the golden was not rewritten.
"""

import os
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
SCRIPT = APP_DIR / "scripts" / "registration_form_golden.py"


def test_registration_form_golden_is_current():
    env = {k: v for k, v in os.environ.items() if not k.startswith("UBYHOST_")}
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"], cwd=APP_DIR, env=env,
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-2000:]
