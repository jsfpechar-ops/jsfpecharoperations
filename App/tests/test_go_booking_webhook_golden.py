"""go/internal/payments/booking_webhook_test.go reads the files App/scripts/booking_webhook_golden.py writes."""

import importlib.util
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1]


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "booking_webhook_golden", APP_DIR / "scripts" / "booking_webhook_golden.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.sqlite_only
def test_booking_webhook_golden_matches_python_handler(monkeypatch, tmp_path):
    from app import config

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "booking-webhook-golden.sqlite3")
    generator = _load_generator()
    committed = generator.OUT.read_bytes()
    assert generator.render().encode("utf-8") == committed
    assert committed.count(b'"idempotency_key"') >= 10


def test_booking_i18n_matches_host_catalog():
    generator = _load_generator()
    assert generator.render_i18n().encode("utf-8") == generator.I18N_OUT.read_bytes()
