"""UX-66 (finding B-12): the auth chrome shows coded notices, never free text."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app import db, host_i18n
from app.main import app
from app.security import _csrf_recovery_location


@pytest.fixture(autouse=True)
def _database():
    db.init_db()


def _login_page(lang: str, query: str = "") -> str:
    return TestClient(app).get(f"/login?lang={lang}{query}").text


def _notice(html: str) -> str | None:
    match = re.search(r'<p class="auth-notice" role="alert">(.*?)</p>', html, re.S)
    return match.group(1) if match else None


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace("'", "&#39;").replace('"', "&#34;")
    )


@pytest.mark.parametrize("lang", ["en", "cs"])
@pytest.mark.parametrize("code", ["form_expired", "2fa_expired", "logged_out"])
def test_each_coded_notice_renders_its_translated_sentence(lang, code):
    expected = host_i18n.STRINGS[lang][f"auth.notice.{code}"]
    assert _notice(_login_page(lang, f"&notice={code}")) == _escape(expected)


def test_the_notice_keys_exist_in_both_languages():
    for code in ("form_expired", "2fa_expired", "logged_out"):
        for lang in ("en", "cs"):
            assert f"auth.notice.{code}" in host_i18n.STRINGS[lang]


def test_an_unknown_notice_renders_nothing_and_is_not_echoed():
    html = _login_page("en", "&notice=<script>alert(1)</script>")
    assert _notice(html) is None
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" not in html


def test_a_notice_code_that_only_looks_like_a_key_is_still_ignored():
    html = _login_page("en", "&notice=form_expired_extra")
    assert _notice(html) is None
    assert "too long" not in html


def test_no_notice_query_renders_no_notice():
    assert _notice(_login_page("en")) is None


def test_logout_sends_the_host_to_the_logged_out_notice():
    client = TestClient(app)
    response = client.post("/logout", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login?notice=logged_out"


def test_the_2fa_timeout_uses_the_coded_notice():
    client = TestClient(app)
    response = client.get("/login/2fa", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login?notice=2fa_expired"


def test_the_csrf_expiry_fallback_uses_the_coded_notice():
    assert _csrf_recovery_location(_request_without_referer()) == "/login?notice=form_expired"


def test_a_stale_login_form_returns_to_the_coded_notice():
    location = _csrf_recovery_location(_request_with_referer("http://testserver/login?lang=en"))
    assert location == "/login?notice=form_expired"


def test_a_stale_form_elsewhere_still_flashes_on_its_own_page():
    location = _csrf_recovery_location(
        _request_with_referer("http://testserver/reservations/123")
    )
    assert location.startswith("/reservations/123?err=")


class _Request:
    def __init__(self, headers):
        self.headers = headers


def _request(headers: dict | None = None):
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "http",
            "server": ("testserver", 80),
            "path": "/login",
            "query_string": b"",
            "headers": raw,
        }
    )


def _request_without_referer():
    return _request()


def _request_with_referer(referer: str):
    return _request({"referer": referer})
