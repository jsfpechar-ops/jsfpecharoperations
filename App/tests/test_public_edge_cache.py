"""0992: only the public marketing pages may be cached at the Cloudflare edge."""
from __future__ import annotations

from starlette.testclient import TestClient

from app import db
from app.main import app
from app.public_guides import GUIDE_TRANSLATIONS
from tests.test_accounts import _account, _clean_accounts, _login

PUBLIC = "public, max-age=0, s-maxage=300"
PRIVATE = "no-store, private"
CACHEABLE = ("/", "/legal", "/terms", "/privacy", "/dpa", "/subprocessors",
             "/cenik", "/jak-to-funguje", "/robots.txt", "/sitemap.xml")


def _client() -> TestClient:
    db.init_db()
    return TestClient(app)


def test_public_pages_get_the_edge_header_and_no_cookie():
    for path in CACHEABLE:
        r = _client().get(path)          # fresh client: no cookies
        assert r.status_code == 200, path
        assert r.headers["cache-control"] == PUBLIC, path
        assert "set-cookie" not in r.headers, path


def test_a_public_guide_is_cacheable():
    slug = next(iter(GUIDE_TRANSLATIONS["cs"]))
    r = _client().get(f"/pruvodce/{slug}")
    assert r.status_code == 200
    assert r.headers["cache-control"] == PUBLIC and "set-cookie" not in r.headers


def test_query_string_language_cookie_and_session_stay_private():
    assert _client().get("/?lang=en").headers["cache-control"] == PRIVATE
    assert _client().get("/?utm_source=x&gclid=abc").headers["cache-control"] == PRIVATE
    c = _client()
    c.cookies.set("ubyhost_lang", "en")
    assert c.get("/").headers["cache-control"] == PRIVATE
    c = _client()
    c.cookies.set("ubyhost_session", "anything")
    assert c.get("/").headers["cache-control"] == PRIVATE


def test_signed_in_root_is_the_private_dashboard():
    _clean_accounts()
    _account("edge-dashboard")
    r = _login("edge-dashboard").get("/")
    assert r.headers["cache-control"] == PRIVATE


def test_private_areas_never_get_the_public_header():
    for path in ("/login", "/signup", "/l/not-a-real-token", "/settings",
                 "/reservations", "/healthz", "/api/not-a-route"):
        r = _client().get(path, follow_redirects=False)
        assert r.headers.get("cache-control") != PUBLIC, path
        assert "s-maxage" not in r.headers.get("cache-control", ""), path


def test_unknown_guide_404_is_private():
    r = _client().get("/pruvodce/no-such-guide")
    assert r.status_code == 404 and r.headers["cache-control"] == PRIVATE
