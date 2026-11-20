"""Freshness check for go_smart_locks_golden.py (brief 1707)."""

from pathlib import Path

from scripts.go_smart_locks_golden import build_golden

OUT = Path(__file__).resolve().parents[2] / "go" / "internal" / "web" / "properties" / "testdata" / "smart_locks_golden.json"


def test_smart_locks_golden_is_fresh():
    assert OUT.exists(), "run App/scripts/go_smart_locks_golden.py first"
    assert OUT.read_text(encoding="utf-8") == build_golden()