"""0508: the signed-in shell loads Turbo for page swaps; the speculation rules are gone."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from tests.test_signed_in_chrome import host_with_property  # noqa: F401  (fixture reuse)

TURBO_SRC = '/static/vendor/turbo-8.0.13.js'


def test_signed_in_shell_loads_turbo_and_no_speculation_rules(host_with_property):
    page = host_with_property.get("/?lang=en").text
    assert "speculationrules" not in page
    assert TURBO_SRC in page
    assert 'name="turbo-prefetch" content="true"' in page


def test_login_page_has_no_turbo_and_no_prefetch_rules():
    page = TestClient(app).get("/login?lang=en").text
    assert "speculationrules" not in page
    assert TURBO_SRC not in page
