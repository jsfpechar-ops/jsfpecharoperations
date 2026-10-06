"""litestream_env.sh decides whether deploy/preflight start the S3 replica.

A missing S3 config must not make production preflight die when the operator
has not wired Litestream yet; an explicit enable still requires credentials.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LITESTREAM_ENV = REPO_ROOT / "deploy" / "lightsail" / "scripts" / "litestream_env.sh"

_PROBE = """
set -a
source "{script}"
set +a
printf 'enabled=%s auto=%s\\n' "${{litestream_enabled}}" "${{litestream_auto_disabled}}"
"""


def _probe(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    body = _PROBE.format(script=LITESTREAM_ENV)
    clean = {k: v for k, v in os.environ.items() if not k.startswith("LITESTREAM_")}
    clean.pop("UBYHOST_LITESTREAM_ENABLED", None)
    clean.update(env)
    return subprocess.run(
        ["bash", "-c", body],
        capture_output=True,
        text=True,
        env=clean,
        timeout=30,
    )


def _vars(stdout: str) -> tuple[str, str]:
    enabled = auto = ""
    for token in stdout.strip().split():
        if token.startswith("enabled="):
            enabled = token.split("=", 1)[1]
        if token.startswith("auto="):
            auto = token.split("=", 1)[1]
    return enabled, auto


def test_explicit_off_skips_litestream_even_when_s3_is_configured():
    result = _probe(
        {
            "UBYHOST_LITESTREAM_ENABLED": "0",
            "LITESTREAM_S3_BUCKET": "bucket",
            "LITESTREAM_ACCESS_KEY_ID": "key",
            "LITESTREAM_SECRET_ACCESS_KEY": "secret",
        }
    )
    assert result.returncode == 0, result.stderr
    assert _vars(result.stdout) == ("0", "0")


def test_empty_s3_variables_auto_disable_litestream():
    result = _probe({})
    assert result.returncode == 0, result.stderr
    assert _vars(result.stdout) == ("0", "1")


def test_any_s3_variable_keeps_litestream_enabled_by_default():
    result = _probe({"LITESTREAM_S3_BUCKET": "ubyhost-litestream-demo"})
    assert result.returncode == 0, result.stderr
    assert _vars(result.stdout) == ("1", "0")


def test_explicit_on_with_empty_s3_still_enables_litestream():
    """Preflight must catch missing credentials; the profile switch stays on."""
    result = _probe({"UBYHOST_LITESTREAM_ENABLED": "1"})
    assert result.returncode == 0, result.stderr
    assert _vars(result.stdout) == ("1", "0")


def test_an_invalid_switch_fails_fast():
    result = _probe({"UBYHOST_LITESTREAM_ENABLED": "maybe"})
    assert result.returncode != 0
    assert "must be 0 or 1" in result.stderr
