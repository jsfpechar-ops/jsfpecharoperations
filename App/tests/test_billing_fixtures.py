"""Drift guard for the Go billing port: the committed fixtures must match the Python oracle."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
SCRIPT = APP / "scripts" / "billing_fixtures.py"
COMMITTED = APP.parent / "go" / "internal" / "billing" / "testdata" / "quote_fixtures.json"


def test_fixtures_match_generator(tmp_path):
    out = tmp_path / "quote_fixtures.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--out", str(out)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip().startswith("fixtures written: ")
    assert out.read_bytes() == COMMITTED.read_bytes()
