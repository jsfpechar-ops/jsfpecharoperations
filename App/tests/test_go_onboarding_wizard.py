"""go/internal/web/onboarding reads testdata/wizard_golden_entry.json (brief 1599); it must match the Python routes."""

import importlib.util
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1]
SCRIPTS = APP_DIR / "scripts"


def load_wizard_golden(name: str):
    """Import scripts/<name>.py (the part scripts import onboarding_wizard_golden)."""
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.sqlite_only
def test_wizard_entry_golden_matches_python_routes(monkeypatch, tmp_path):
    from app import config

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "wizard-golden-entry.sqlite3")
    generator = load_wizard_golden("onboarding_wizard_golden")
    committed = generator.OUT.read_bytes()
    assert generator.render(generator.CASES).encode("utf-8") == committed
    assert committed.count(b'"status": 200') >= 7
    assert committed.count(b'"status": 303') >= 20
