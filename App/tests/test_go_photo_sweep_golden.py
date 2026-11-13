"""go/internal/photosweep/sweep_test.go reads go/internal/photosweep/testdata/photo_sweep_golden.json."""

import importlib.util
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "photo_sweep_golden", APP_DIR / "scripts" / "photo_sweep_golden.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_photo_sweep_golden_matches_python_photo_sweep(monkeypatch, tmp_path):
    from app import config

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "photo-sweep-golden.sqlite3")
    generator = _load_generator()
    committed = generator.OUT.read_bytes()
    assert generator.render().encode("utf-8") == committed
    assert committed.count(b'"retention_delete"') == 2
