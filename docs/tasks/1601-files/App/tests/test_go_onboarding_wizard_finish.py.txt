"""go/internal/web/onboarding reads testdata/wizard_golden_finish.json (brief 1601); it must match the Python routes."""

import pytest

from test_go_onboarding_wizard import load_wizard_golden


@pytest.mark.sqlite_only
def test_wizard_finish_golden_matches_python_routes(monkeypatch, tmp_path):
    from app import config

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "wizard-golden-finish.sqlite3")
    generator = load_wizard_golden("onboarding_wizard_golden_finish")
    committed = generator.OUT.read_bytes()
    assert generator.render(generator.CASES).encode("utf-8") == committed
    assert committed.count(b'"status": 200') >= 13
