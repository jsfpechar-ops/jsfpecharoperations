"""Brief 1620: the Go marketing pages' catalog and golden pages are current.

go/internal/web/public/catalog_pages.json and testdata/pages/ are written by
scripts/public_pages_golden.py; this fails when the Python pages or their
copy changed and the script was not re-run (then run it and commit).
"""
import os
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]


def test_public_pages_golden_is_current():
    # The script sets its own config; the test session's UBYHOST_* values must not leak in.
    env = {k: v for k, v in os.environ.items() if not k.startswith(("UBYHOST_", "POSTHOG_"))}
    result = subprocess.run(
        [sys.executable, "scripts/public_pages_golden.py", "--check"],
        cwd=APP_DIR, env=env, capture_output=True, text=True, timeout=900,
    )
    assert result.returncode == 0, (result.stdout + result.stderr)[-3000:]
