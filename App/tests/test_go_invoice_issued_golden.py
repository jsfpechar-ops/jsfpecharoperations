"""Freshness of go/internal/mail/testdata/invoice_issued_golden.json."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]


def test_invoice_issued_golden_is_fresh():
    script = APP / "scripts" / "go_invoice_issued_golden.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--check"],
        cwd=APP,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout