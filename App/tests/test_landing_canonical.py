"""The landing page's canonical must point at the page you are actually on.

The landing hard-coded `<link rel="canonical" href="{base}/">`, so `/?lang=cs`
and `/?lang=en` both claimed the bare URL as canonical and Google dropped the
hreflang pair. It now reads seo.head_links like every other public page (D-29 /
UX-160).
"""
from __future__ import annotations

from starlette.testclient import TestClient

from app import config, db
from app.main import app


def _client() -> TestClient:
    db.init_db()
    return TestClient(app)


def test_the_landing_canonical_is_self_referencing_per_language():
    base = config.PUBLIC_BASE_URL

    assert f'<link rel="canonical" href="{base}/">' in _client().get("/").text
    assert (
        f'<link rel="canonical" href="{base}/?lang=cs">' in _client().get("/?lang=cs").text
    )
    assert (
        f'<link rel="canonical" href="{base}/?lang=en">' in _client().get("/?lang=en").text
    )
