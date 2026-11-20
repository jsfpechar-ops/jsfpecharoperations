"""Freshness of go/internal/mail/testdata/invoice_issued_golden.json."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_invoice_issued_golden_is_fresh():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "App" / "scripts" / "go_invoice_issued_golden.py"), "--check"],
        cwd=ROOT / "App",
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout