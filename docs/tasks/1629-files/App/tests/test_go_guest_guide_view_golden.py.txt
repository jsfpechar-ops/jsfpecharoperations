"""Freshness test for guest_guide_view golden (brief 1629)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_guest_guide_view_golden_fresh():
    script = ROOT / "scripts" / "go_guest_guide_view_golden.py"
    r = subprocess.run([sys.executable, str(script), "--check"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr or r.stdout
