"""go/internal/calendar/dsr_due_test.go reads go/internal/calendar/testdata/dsr_due_golden.json."""

import importlib.util
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "dsr_due_golden", APP_DIR / "scripts" / "dsr_due_golden.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dsr_due_golden_matches_python_raise_due_alerts(monkeypatch, tmp_path):
    from app import config

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "dsr-due-golden.sqlite3")
    generator = _load_generator()
    committed = generator.OUT.read_bytes()
    assert generator.render().encode("utf-8") == committed
    assert committed.count(b'"dedupe_key"') >= 15
