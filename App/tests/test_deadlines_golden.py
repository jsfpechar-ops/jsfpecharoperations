"""The Go deadlines package reads go/internal/deadlines/testdata/golden.json."""

import importlib.util
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "deadlines_golden", APP_DIR / "scripts" / "deadlines_golden.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_deadlines_golden_matches_python_deadlines():
    generator = _load_generator()
    committed = generator.OUT.read_bytes()
    assert generator.render().encode("utf-8") == committed
    assert committed.count(b'"check_in"') >= 500
