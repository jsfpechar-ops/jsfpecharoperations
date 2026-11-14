"""Brief 1507: the Go sign-up pages' catalog and golden pages are current.

go/internal/web/auth/signup_catalog.json and testdata/signup/ are written by
scripts/signup_pages_golden.py; this fails when the Python pages, the sign-up
route or their copy changed and the script was not re-run (then run it and
commit, and run the Go test of go/internal/web/auth).
"""
import os
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]


def test_signup_pages_golden_is_current():
    # The script sets its own config; the test session's UBYHOST_* values must not leak in.
    env = {k: v for k, v in os.environ.items() if not k.startswith(("UBYHOST_", "POSTHOG_", "TURNSTILE_"))}
    result = subprocess.run(
        [sys.executable, "scripts/signup_pages_golden.py", "--check"],
        cwd=APP_DIR, env=env, capture_output=True, text=True, timeout=900,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-3000:]
