"""Tests for scripts/hooks/read_guard.py (PreToolUse Read guard)."""

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "hooks" / "read_guard.py"


def _run(file_path, limit=None, env=None):
    tool_input = {"file_path": str(file_path)}
    if limit is not None:
        tool_input["limit"] = limit
    payload = json.dumps({"tool_name": "Read", "tool_input": tool_input})
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
    )


def _make(tmp_path, lines, name="f.txt"):
    path = tmp_path / name
    path.write_text("".join(f"line {i}\n" for i in range(lines)), encoding="utf-8")
    return path


def test_short_file_without_limit_is_allowed(tmp_path):
    result = _run(_make(tmp_path, 100))
    assert result.returncode == 0


def test_long_file_without_limit_is_blocked(tmp_path):
    result = _run(_make(tmp_path, 500))
    assert result.returncode == 2
    assert "500 lines" in result.stderr


def test_long_file_with_small_limit_is_allowed(tmp_path):
    result = _run(_make(tmp_path, 500), limit=150)
    assert result.returncode == 0


def test_long_file_with_limit_above_max_is_blocked(tmp_path):
    result = _run(_make(tmp_path, 500), limit=900)
    assert result.returncode == 2


def test_allow_full_read_env_overrides(tmp_path):
    env = {**os.environ, "ALLOW_FULL_READ": "1"}
    result = _run(_make(tmp_path, 500), env=env)
    assert result.returncode == 0


def test_missing_file_is_allowed(tmp_path):
    result = _run(tmp_path / "does-not-exist.txt")
    assert result.returncode == 0
