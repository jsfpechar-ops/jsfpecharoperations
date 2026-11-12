"""go/internal/calendar/filing_watchdog_test.go reads go/internal/calendar/testdata/filing_watchdog_golden.json."""

import importlib.util
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "filing_watchdog_golden", APP_DIR / "scripts" / "filing_watchdog_golden.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_filing_watchdog_golden_matches_python_watchdog(monkeypatch, tmp_path):
    from app import config

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "filing-watchdog-golden.sqlite3")
    generator = _load_generator()
    committed = generator.OUT.read_bytes()
    assert generator.render().encode("utf-8") == committed
    assert committed.count(b'"reservation_id"') >= 60
