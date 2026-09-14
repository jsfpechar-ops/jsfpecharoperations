"""Host UI language selection and translation."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import host_i18n
from app.main import app


def test_normalise_language_accepts_supported_codes_and_falls_back():
    assert host_i18n.normalise_language("en") == "en"
    assert host_i18n.normalise_language("CS") == "cs"
    assert host_i18n.normalise_language("cs-CZ") == "cs"
    assert host_i18n.normalise_language("") == host_i18n.DEFAULT_LANGUAGE
    assert host_i18n.normalise_language("de") == host_i18n.DEFAULT_LANGUAGE


def test_translate_interpolates_kwargs_and_falls_back_to_english():
    assert host_i18n.translate("en", "dashboard.minutes_saved", minutes=24) == (
        "~24 min saved vs manual UbyPort entry"
    )
    assert host_i18n.translate("cs", "dashboard.minutes_saved", minutes=24) == (
        "~24 min ušetřeno oproti ručnímu UbyPortu"
    )
    assert host_i18n.translate("cs", "missing.key") == "missing.key"
    assert host_i18n.translate("en", "send.guests_count", count=2) == (
        "Send 2 guest(s) on this stay"
    )


def test_language_endpoint_sets_cookie_and_rejects_open_redirects():
    client = TestClient(app)

    response = client.post(
        "/language",
        data={"lang": "cs", "next": "/stays"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/stays"
    assert client.cookies.get(host_i18n.LANG_COOKIE) == "cs"

    unsafe = client.post(
        "/language",
        data={"lang": "en", "next": "//evil.example/phish"},
        follow_redirects=False,
    )
    assert unsafe.headers["location"] == "/"


def test_english_and_czech_carry_the_same_keys():
    """A missing key silently renders the key itself in the other language."""
    english = set(host_i18n.STRINGS["en"])
    czech = set(host_i18n.STRINGS["cs"])
    assert english - czech == set(), f"missing Czech: {sorted(english - czech)}"
    assert czech - english == set(), f"missing English: {sorted(czech - english)}"
