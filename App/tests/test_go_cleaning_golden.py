"""go/internal/web/cleaning reads testdata/cleaning_golden.json and i18n.json; both must match the Python."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1]


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "cleaning_golden", APP_DIR / "scripts" / "cleaning_golden.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.sqlite_only
def test_cleaning_golden_matches_python_routes(monkeypatch, tmp_path):
    from app import config

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "cleaning-golden.sqlite3")
    generator = _load_generator()
    committed = generator.OUT.read_bytes()
    assert generator.render().encode("utf-8") == committed
    assert committed.count(b'"status": 200') >= 14
    assert b'"status": 409' in committed and b'"status": 404' in committed


def test_go_cleaning_i18n_is_current():
    result = subprocess.run(
        [sys.executable, str(APP_DIR / "scripts" / "go_cleaning_i18n.py"), "--check"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
