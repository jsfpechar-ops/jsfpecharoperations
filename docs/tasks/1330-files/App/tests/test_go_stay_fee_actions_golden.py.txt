"""go/internal/web/stayfees/actions_test.go reads testdata/actions_golden.json and i18n.json.

Both are written by scripts/stay_fee_actions_golden.py from the real Python
routes; this test fails when either committed file is stale.
"""

import importlib.util
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1]


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "stay_fee_actions_golden", APP_DIR / "scripts" / "stay_fee_actions_golden.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The golden file is defined by a fresh SQLite database; the Go test replays it on PostgreSQL.
@pytest.mark.sqlite_only
def test_go_stay_fee_actions_golden_is_current(monkeypatch, tmp_path):
    from app import config

    generator = _load_generator()
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "stay-fee-actions-golden.sqlite3")
    # The seeded csv_enc is a Fernet token of the script's own secret.
    monkeypatch.setenv("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    monkeypatch.delenv("UBYHOST_DATA_KEYS", raising=False)
    monkeypatch.delenv("UBYHOST_DATA_KEY_LEGACY", raising=False)
    golden, catalog = generator.render()
    assert golden.encode("utf-8") == generator.OUT.read_bytes()
    assert catalog.encode("utf-8") == generator.OUT_I18N.read_bytes()
    assert golden.count('"name": ') >= 85
