"""What Google gets to see, and in which language.

The search result for ubyhost.com was headlined "Continue" — the login
button's label, because the page title was wired to it. The signed-out pages
are the only ones a crawler can read, so they have to name themselves, explain
themselves, and answer in Czech to the hosts the product is built for.
"""
from __future__ import annotations

import re

from starlette.testclient import TestClient

from app import config, db, host_i18n
from app.main import app
from tests.test_accounts import _account, _clean_accounts, _login

PUBLIC_PAGES = ("/login", "/legal", "/terms", "/privacy", "/dpa")


def _client() -> TestClient:
    db.init_db()
    return TestClient(app)


def _title(html: str) -> str:
    found = re.search(r"<title>(.*?)</title>", html, re.S)
    assert found, "the page has no title at all"
    return " ".join(found.group(1).split())


def _meta_description(html: str) -> str:
    found = re.search(r'<meta name="description" content="(.*?)">', html, re.S)
    return found.group(1) if found else ""


def test_the_login_page_is_not_titled_after_its_button():
    page = _client().get("/login?lang=en")

    assert page.status_code == 200
    title = _title(page.text)
    assert title != host_i18n.translate("en", "login.submit"), (
        "Google headlines the result with the title; 'Continue' says nothing"
    )
    assert "UbyHost" in title, "the brand is missing from the search result headline"


def test_the_public_homepage_targets_the_service_people_search_for():
    page = _client().get("/")

    assert page.status_code == 200
    assert 'lang="cs"' in page.text
    assert _title(page.text) == host_i18n.translate("cs", "landing.page_title")
    assert "Online ubytovací kniha" in page.text
    assert "UbyPort" in page.text
    assert "Airbnb" in page.text
    assert "<h1>" in page.text
    assert '<link rel="canonical" href="' + config.PUBLIC_BASE_URL + '/">' in page.text


def test_the_homepage_has_honest_machine_readable_product_information():
    page = _client().get("/?lang=en")

    assert 'lang="en"' in page.text
    assert '"@type": "SoftwareApplication"' in page.text
    assert '"applicationCategory": "BusinessApplication"' in page.text
    assert '"aggregateRating"' not in page.text, "never invent testimonials for a rich result"
    assert '"offers"' not in page.text, "the public page makes no price claim"


def test_the_login_page_describes_itself_for_the_search_snippet():
    page = _client().get("/login?lang=en")

    description = _meta_description(page.text)
    assert description, "no meta description, so Google invents the snippet"
    assert "UbyHost" in description
    assert len(description) <= 160, "longer than a search snippet; it gets cut"


def test_a_visitor_with_no_stated_preference_gets_czech():
    """The canonical URL is stable Czech regardless of crawler headers."""
    page = _client().get("/login")

    assert 'lang="cs"' in page.text
    assert _title(page.text) == host_i18n.translate("cs", "login.page_title")
    assert _meta_description(page.text) == host_i18n.translate("cs", "login.meta_description")


def test_a_browser_header_cannot_change_the_canonical_pages_language():
    page = _client().get("/login", headers={"Accept-Language": "en-GB,en;q=0.9"})

    assert 'lang="cs"' in page.text
    assert _title(page.text) == host_i18n.translate("cs", "login.page_title")


def test_the_explicit_english_alternate_is_english():
    page = _client().get("/login?lang=en", headers={"Accept-Language": "cs"})

    assert 'lang="en"' in page.text


def test_a_language_link_is_remembered_like_the_switcher():
    client = _client()

    page = client.get("/login?lang=en")

    assert 'lang="en"' in page.text
    assert client.cookies.get(host_i18n.LANG_COOKIE) == "en"
    assert 'lang="en"' in client.get("/login").text, "the choice lasted one page"


def test_a_saved_choice_beats_the_browser_header():
    client = _client()
    client.cookies.set(host_i18n.LANG_COOKIE, "en")

    page = client.get("/login", headers={"Accept-Language": "cs"})

    assert 'lang="en"' in page.text


def test_every_public_page_offers_both_languages_to_search_engines():
    client = _client()
    for path in PUBLIC_PAGES:
        html = client.get(path).text
        assert f'<link rel="canonical" href="{config.PUBLIC_BASE_URL}{path}">' in html, path
        for lang in host_i18n.LANGUAGES:
            expected = (
                f'<link rel="alternate" hreflang="{lang}" '
                f'href="{config.PUBLIC_BASE_URL}{path}?lang={lang}">'
            )
            assert expected in html, f"{path} has no {lang} alternate"
        assert f'hreflang="x-default" href="{config.PUBLIC_BASE_URL}{path}">' in html, path


def test_a_language_url_points_at_itself():
    """Each hreflang URL must be its own canonical or Google drops the pair."""
    html = _client().get("/login?lang=cs").text

    assert f'<link rel="canonical" href="{config.PUBLIC_BASE_URL}/login?lang=cs">' in html


def test_the_workspace_itself_is_not_offered_to_search_engines():
    _clean_accounts()
    _account("seo-workspace")
    try:
        html = _login("seo-workspace").get("/settings").text

        assert 'rel="canonical"' not in html, "a page full of guest data is not indexable"
    finally:
        _clean_accounts()


def test_a_signed_in_host_still_gets_the_dashboard_at_root():
    _clean_accounts()
    _account("seo-dashboard")
    try:
        html = _login("seo-dashboard").get("/").text

        assert "landing-hero" not in html
        assert 'action="/logout"' in html
    finally:
        _clean_accounts()


def test_robots_keeps_crawlers_out_of_the_workspace():
    response = _client().get("/robots.txt")

    assert response.status_code == 200
    body = response.text
    for private in ("/reservations", "/submissions", "/housebook", "/settings", "/l/"):
        assert f"Disallow: {private}" in body, private
    assert f"Sitemap: {config.PUBLIC_BASE_URL}/sitemap.xml" in body
    assert "Disallow: /login" not in body, "the one page worth indexing is blocked"


def test_the_sitemap_lists_both_languages_of_every_public_page():
    response = _client().get("/sitemap.xml")

    assert response.status_code == 200
    body = response.text
    for lang in host_i18n.LANGUAGES:
        assert f"<loc>{config.PUBLIC_BASE_URL}/?lang={lang}</loc>" in body
    for path in PUBLIC_PAGES:
        for lang in host_i18n.LANGUAGES:
            assert f"<loc>{config.PUBLIC_BASE_URL}{path}?lang={lang}</loc>" in body, path


def test_original_czech_guides_are_public_and_indexable():
    client = _client()
    expected = {
        "/pruvodce/hlaseni-cizincu-ubyport": "Hlášení cizinců přes UbyPort",
        "/pruvodce/online-ubytovaci-kniha": "Online ubytovací kniha",
    }

    for path, phrase in expected.items():
        page = client.get(path)
        assert page.status_code == 200
        assert 'lang="cs"' in page.text
        assert phrase in _title(page.text)
        assert f'<link rel="canonical" href="{config.PUBLIC_BASE_URL}{path}">' in page.text
        assert '"@type": "Article"' in page.text
        assert "Airbo" not in page.text, "competitor wording or brand leaked into our guide"


def test_guides_are_linked_and_listed_for_discovery():
    client = _client()
    homepage = client.get("/").text
    sitemap = client.get("/sitemap.xml").text

    for path in (
        "/pruvodce/hlaseni-cizincu-ubyport",
        "/pruvodce/online-ubytovaci-kniha",
    ):
        assert f'href="{path}"' in homepage
        assert f"<loc>{config.PUBLIC_BASE_URL}{path}</loc>" in sitemap


def test_unknown_guide_is_a_real_404():
    assert _client().get("/pruvodce/neexistuje").status_code == 404
