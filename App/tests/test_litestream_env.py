"""Litestream enablement follows empty S3 credentials (preflight auto-disable).

``litestream_env.sh`` is sourced by deploy and preflight; a wrong default would
start the compose profile without credentials and fail production deploy.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LITESTREAM_ENV = REPO_ROOT / "deploy" / "lightsail" / "scripts" / "litestream_env.sh"


def _resolve(env: dict[str, str]) -> tuple[int, int]:
    """Return (litestream_enabled, litestream_auto_disabled) from the script."""
    clean = {
        k: v
        for k, v in os.environ.items()
        if k
        not in (
            "UBYHOST_LITESTREAM_ENABLED",
            "LITESTREAM_S3_BUCKET",
            "LITESTREAM_ACCESS_KEY_ID",
            "LITESTREAM_SECRET_ACCESS_KEY",
        )
    }
    clean.update(env)
    script = f'source "{LITESTREAM_ENV}"; echo "$litestream_enabled $litestream_auto_disabled"'
    result = subprocess.run(
        ["bash", "-c", script],
        env=clean,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    parts = result.stdout.strip().split()
    assert len(parts) == 2
    return int(parts[0]), int(parts[1])


def test_empty_s3_credentials_auto_disable_litestream():
    enabled, auto = _resolve({})
    assert enabled == 0
    assert auto == 1


def test_explicit_litestream_off_wins_over_bucket():
    enabled, auto = _resolve(
        {
            "UBYHOST_LITESTREAM_ENABLED": "0",
            "LITESTREAM_S3_BUCKET": "my-bucket",
        }
    )
    assert enabled == 0
    assert auto == 0


def test_any_s3_credential_keeps_litestream_on_when_flag_unset():
    enabled, auto = _resolve({"LITESTREAM_S3_BUCKET": "my-bucket"})
    assert enabled == 1
    assert auto == 0


def test_invalid_litestream_flag_fails():
    result = subprocess.run(
        ["bash", "-c", f'source "{LITESTREAM_ENV}"'],
        env={**os.environ, "UBYHOST_LITESTREAM_ENABLED": "maybe"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
    assert "UBYHOST_LITESTREAM_ENABLED" in result.stderr
