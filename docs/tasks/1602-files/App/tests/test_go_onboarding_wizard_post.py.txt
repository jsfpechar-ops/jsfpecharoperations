"""go/internal/web/onboarding reads testdata/wizard_golden_post.json (brief 1602); it must match the Python routes."""

import pytest

from test_go_onboarding_wizard import load_wizard_golden


@pytest.mark.sqlite_only
def test_wizard_post_golden_matches_python_routes(monkeypatch, tmp_path):
    from app import config

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "wizard-golden-post.sqlite3")
    generator = load_wizard_golden("onboarding_wizard_golden_post")
    committed = generator.OUT.read_bytes()
    assert generator.render(generator.CASES).encode("utf-8") == committed
    assert committed.count(b'"status": 303') >= 20
    assert committed.count(b'"status": 400') == 2
