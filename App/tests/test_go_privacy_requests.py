"""go/internal/web/privacy reads two generated files; both must match the Python."""

import importlib.util
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
PRIVACY_DIR = APP_DIR.parent / "go" / "internal" / "web" / "privacy"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, APP_DIR / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_privacy_requests_golden_matches_python_routes(tmp_path, monkeypatch):
    from app import config

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "privacy-requests-golden.sqlite3")
    generator = _load("privacy_requests_golden")
    committed = generator.OUT.read_bytes()
    assert generator.render().encode("utf-8") == committed
    assert committed.count(b'"name"') >= 19


def test_privacy_catalog_matches_host_i18n():
    # go_host_i18n.py only globs go/internal/*/, so this package is checked here.
    generator = _load("go_host_i18n")
    keys = PRIVACY_DIR / "i18n_keys.txt"
    current = (PRIVACY_DIR / "i18n.json").read_text(encoding="utf-8")
    assert generator.render(generator.read_keys(keys)) == current
