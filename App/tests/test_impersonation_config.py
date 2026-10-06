"""Impersonation limits come from UBYHOST_IMPERSONATION_MAX_HOURS (WP04 / #280)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]


def _max_age(env: dict[str, str]) -> int:
    result = subprocess.run(
        [sys.executable, "-c", "from app import auth; print(auth.IMPERSONATION_MAX_AGE)"],
        cwd=APP_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    return int(result.stdout.strip())


def test_the_default_preview_limit_is_twenty_four_hours():
    env = os.environ.copy()
    env.pop("UBYHOST_IMPERSONATION_MAX_HOURS", None)
    assert _max_age(env) == 24 * 3600


def test_zero_means_no_time_limit():
    env = {**os.environ, "UBYHOST_IMPERSONATION_MAX_HOURS": "0"}
    assert _max_age(env) == 0


def test_a_non_numeric_value_falls_back_to_twenty_four_hours():
    env = {**os.environ, "UBYHOST_IMPERSONATION_MAX_HOURS": "soon"}
    assert _max_age(env) == 24 * 3600
