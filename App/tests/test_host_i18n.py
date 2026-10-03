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


def test_release_help_describes_optional_passports_and_cookie_lifetimes():
    for lang in ("en", "cs"):
        passport = host_i18n.translate(lang, "guide.guests.photo")
        cookies = host_i18n.translate(lang, "guide.guests.cookies")
        assert "UbyPort" in passport
        assert ("off by default" in passport) or ("výchozím stavu vypnuté" in passport)
        assert ("7 days" in cookies and "60 days" in cookies) or (
            "7 dní" in cookies and "60 dní" in cookies
        )


def test_the_guest_engine_delegates_to_the_single_lookup():
    """One interpolation guard for both engines - the guest form must not raise."""
    from app import i18n

    assert not hasattr(i18n, "normalise_language"), (
        "normalise_language belongs to host_i18n only"
    )
    assert i18n.translator("cs")("arrival_question") == host_i18n.lookup(
        i18n.STRINGS["cs"], i18n.STRINGS[i18n.DEFAULT_LANGUAGE], "arrival_question"
    )


def test_a_malformed_key_returns_raw_text_instead_of_raising():
    from app import i18n

    cases = (
        (host_i18n.STRINGS, host_i18n.DEFAULT_LANGUAGE, "dashboard.minutes_saved"),
        (i18n.STRINGS, i18n.DEFAULT_LANGUAGE, "arrival_welcome"),
    )
    for table, fallback, key in cases:
        for lang in ("en", "cs"):
            catalog = table[lang]
            # A missing key renders itself rather than raising.
            assert host_i18n.lookup(catalog, table[fallback], "missing.key") == (
                "missing.key"
            )
            # A real key called with the wrong values renders its raw text.
            raw = host_i18n.lookup(catalog, table[fallback], key)
            assert "%(" in raw
            assert host_i18n.lookup(
                catalog, table[fallback], key, wrong="x"
            ) == raw


def test_the_page_default_follows_the_guests_own_phone():
    """A guest who has chosen nothing gets the language their phone asks for.

    This used to be the Czech public default, which put "Zadejte přístupový PIN"
    in front of every foreigner. The product owner changed it, so a Czech or
    Slovak phone gets Czech and any other phone gets English. The host UI and
    the public site keep their own defaults.
    """
    from app import i18n
    from app.routes.guest import LANG_COOKIE as GUEST_LANG_COOKIE
    from app.routes.guest import _language

    assert host_i18n.PUBLIC_DEFAULT_LANGUAGE == "cs"
    assert i18n.DEFAULT_LANGUAGE == "en"
    # The host UI keeps its own default; only the guest page moved.
    assert host_i18n.resolve_language(None) == host_i18n.DEFAULT_LANGUAGE
    assert host_i18n.supported_language("de") is None

    class _Guest:
        def __init__(self, lang=None, cookie=None, accept=None):
            self.query_params = {"lang": lang} if lang else {}
            self.cookies = {GUEST_LANG_COOKIE: cookie} if cookie else {}
            self.headers = {"accept-language": accept} if accept else {}

    # Nothing at all: the phone is the only signal left, and a client that never
    # told us anything is not a foreign guest, so the documented guest-link
    # default stands. A real browser always sends this header.
    assert _language(_Guest()) == "cs"
    # A header that names no language is the same silent client.
    assert _language(_Guest(accept="*")) == "cs"
    assert _language(_Guest(accept=",,")) == "cs"
    # A Czech or Slovak phone gets Czech, whatever it lists second.
    assert _language(_Guest(accept="cs-CZ,cs;q=0.9,en;q=0.8")) == "cs"
    assert _language(_Guest(accept="sk-SK,sk;q=0.9,cs;q=0.8")) == "cs"
    # A language we do not speak still falls back to the public default, and a
    # guest's own explicit choice beats the phone.
    assert _language(_Guest(lang="de")) == "cs"
    assert _language(_Guest(cookie="de")) == "cs"
    assert _language(_Guest(lang="en", accept="cs-CZ")) == "en"
    assert _language(_Guest(cookie="en", accept="cs-CZ")) == "en"
