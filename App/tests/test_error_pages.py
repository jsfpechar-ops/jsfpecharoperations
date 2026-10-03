"""People get a branded error page; scripts keep the JSON body."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import db
from app.main import app


def test_unknown_page_is_html_for_browsers_and_json_otherwise():
    db.init_db()
    client = TestClient(app)
    page = client.get("/no-such-page?lang=en", headers={"accept": "text/html"})
    assert page.status_code == 404
    assert "text/html" in page.headers["content-type"]
    assert "Page not found" in page.text or "Stránka nenalezena" in page.text
    api = client.get("/no-such-page")
    assert api.status_code == 404
    assert api.headers["content-type"].startswith("application/json")


def test_a_crash_page_keeps_the_security_headers_and_logs_no_token(caplog):
    db.init_db()

    async def boom(token: str):
        raise RuntimeError("boom")

    app.add_api_route("/__test_boom/{token}", boom)
    client = TestClient(app, raise_server_exceptions=False)
    page = client.get("/__test_boom/secret-token-123", headers={"accept": "text/html"})
    assert page.status_code == 500
    assert page.headers["cache-control"] == "no-store, private"
    assert page.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
    assert "secret-token-123" not in caplog.text
    assert "/__test_boom/{token}" in caplog.text


def test_a_405_page_keeps_the_allow_header():
    db.init_db()
    client = TestClient(app)
    page = client.put("/login", headers={"accept": "text/html"})
    assert page.status_code == 405
    assert "allow" in {key.lower() for key in page.headers}
