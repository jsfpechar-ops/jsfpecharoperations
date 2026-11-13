"""go/internal/web/billing/*_test.go read go/internal/web/billing/testdata/billing_admin_golden.json."""

import importlib.util
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "billing_admin_golden", APP_DIR / "scripts" / "billing_admin_golden.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_billing_admin_golden_matches_python_read_side(monkeypatch, tmp_path):
    from app import billing_admin, billing_analytics, config

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "billing-admin-golden.sqlite3")
    # render() freezes `date` in these two modules; monkeypatch puts the real one back.
    monkeypatch.setattr(billing_admin, "date", billing_admin.date)
    monkeypatch.setattr(billing_analytics, "date", billing_analytics.date)
    generator = _load_generator()
    committed = generator.OUT.read_bytes()
    assert generator.render().encode("utf-8") == committed
    assert committed.count(b'"fn"') >= 30
    assert committed.count(b'"input_b64"') >= 16
