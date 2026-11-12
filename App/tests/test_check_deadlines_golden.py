"""go/internal/calendar/watch_test.go reads go/internal/calendar/testdata/check_deadlines_golden.json."""

import importlib.util
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "check_deadlines_golden", APP_DIR / "scripts" / "check_deadlines_golden.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_check_deadlines_golden_matches_python_check_deadlines(monkeypatch, tmp_path):
    from app import config

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "check-deadlines-golden.sqlite3")
    generator = _load_generator()
    committed = generator.OUT.read_bytes()
    assert generator.render().encode("utf-8") == committed
    assert committed.count(b'"dedupe_key"') >= 80
