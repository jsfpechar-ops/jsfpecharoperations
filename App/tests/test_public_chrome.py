"""One header, one footer, for every page a guest or a stranger can reach.

Each of the four public pages used to carry its own hand-copied header and
footer, so they had already drifted apart: the pricing page offered no way to
log in, the "product" page named the UbyPort guide differently, and only the
landing page marked where you were. They are now two shared partials, and these
tests hold them together.
"""
from __future__ import annotations

import re
from pathlib import Path

from starlette.testclient import TestClient

from app import db
from app.main import app

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"

PUBLIC_URLS = (
    "/",
    "/cenik",
    "/jak-to-funguje",
    "/pruvodce/hlaseni-cizincu-ubyport",
    "/pruvodce/online-ubytovaci-kniha",
)

PAGE_TEMPLATES = (
    "landing.html",
    "pricing.html",
    "product.html",
    "public_guide.html",
)


def _read(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def _client() -> TestClient:
    db.init_db()
    return TestClient(app)


def _between(html: str, start: str, end: str) -> str:
    found = html.index(start)
    return html[found : html.index(end, found) + len(end)]


def _header(html: str) -> str:
    return _between(html, '<header class="landing-header">', "</header>")


def _footer(html: str) -> str:
    return _between(html, '<footer class="landing-footer">', "</footer>")


def _hrefs(chunk: str) -> list[str]:
    return re.findall(r'href="([^"]+)"', chunk)


def _nav_labels(chunk: str) -> list[str]:
    nav = _between(chunk, '<nav class="landing-nav"', "</nav>")
    return [text.strip() for text in re.findall(r">([^<]+)</a>", nav)]


def _render(url: str, lang: str = "en") -> str:
    joiner = "&" if "?" in url else "?"
    response = _client().get(f"{url}{joiner}lang={lang}")
    assert response.status_code == 200, f"{url} answered {response.status_code}"
    return response.text


def test_no_public_page_carries_its_own_copy_of_the_chrome():
    for name in PAGE_TEMPLATES:
        html = _read(name)
        assert '{% include "_public_header.html" %}' in html, name
        assert '{% include "_public_footer.html" %}' in html, name
        # The hand-copied markup is what drifted; it must not come back.
        assert '<header class="landing-header">' not in html, name
        assert '<footer class="landing-footer">' not in html, name
        assert 'class="landing-skip"' not in html, name


def test_the_shared_chrome_lives_in_exactly_two_files():
    assert '<header class="landing-header">' in _read("_public_header.html")
    assert '<footer class="landing-footer">' in _read("_public_footer.html")


def test_the_nav_is_the_same_four_destinations_on_every_page():
    seen = {}
    for url in PUBLIC_URLS:
        labels = _nav_labels(_header(_render(url)))
        assert len(labels) == 4, url
        seen[url] = labels
    assert len(set(tuple(labels) for labels in seen.values())) == 1
    assert list(seen.values())[0] == ["Product", "How it works", "Pricing", "UbyPort"]


def test_each_page_marks_its_own_nav_item_and_only_its_own():
    expected = {
        "/": None,
        "/cenik": "Pricing",
        "/jak-to-funguje": "How it works",
        "/pruvodce/hlaseni-cizincu-ubyport": "UbyPort",
        "/pruvodce/online-ubytovaci-kniha": None,
    }
    for url, label in expected.items():
        header = _header(_render(url))
        current = re.findall(r'<a href="[^"]*" aria-current="page">([^<]+)</a>', header)
        assert current == ([] if label is None else [label]), url


def test_the_product_anchor_stays_an_anchor_on_the_home_page():
    assert _nav_labels(_header(_render("/")))[0] == "Product"
    assert 'href="#product"' in _header(_render("/"))
    # Anywhere else it has to travel back to the home page first.
    assert 'href="/?lang=en#product"' in _header(_render("/cenik"))


def test_the_footer_is_byte_for_byte_the_same_on_every_page():
    footers = {url: _footer(_render(url)) for url in PUBLIC_URLS}
    assert len(set(footers.values())) == 1
    hrefs = _hrefs(list(footers.values())[0])
    for expected in (
        "/jak-to-funguje?lang=en",
        "/cenik?lang=en",
        "/pruvodce/hlaseni-cizincu-ubyport?lang=en",
        "/pruvodce/online-ubytovaci-kniha?lang=en",
        "/legal?lang=en",
        "/terms?lang=en",
        "/privacy?lang=en",
        "/dpa?lang=en",
        "/subprocessors?lang=en",
        "/login?lang=en",
        "mailto:support@ubyhost.com",
    ):
        assert expected in hrefs, expected


def test_the_pricing_page_now_offers_a_way_to_log_in():
    footer = _footer(_render("/cenik"))
    assert "/login?lang=en" in _hrefs(footer)
    assert "Host login" in footer


def test_the_language_switch_keeps_you_on_the_page_you_are_reading():
    for url in PUBLIC_URLS:
        header = _header(_render(url))
        assert f'href="{url}?lang=cs"' in header, url
        assert f'href="{url}?lang=en"' in header, url


def test_the_language_switch_marks_the_language_you_are_reading():
    czech = _header(_render("/cenik", lang="cs"))
    assert 'hreflang="cs" class="active"' in czech
    assert 'hreflang="en" class=""' in czech
    assert 'hreflang="en" class="active"' in _header(_render("/cenik", lang="en"))


def test_the_footer_answers_in_czech_when_the_page_is_czech():
    footer = _footer(_render("/cenik", lang="cs"))
    assert "Průvodce" in footer
    assert "Ubytovací kniha" in footer
    assert "Přihlášení pro ubytovatele" in footer
    assert "Další zpracovatelé" in footer
    assert "landing." not in footer
    assert "footer_short" not in footer


def test_the_footer_still_names_support_once():
    footer = _footer(_render("/"))
    assert footer.count("mailto:support@ubyhost.com") == 1
    assert footer.count("support@ubyhost.com") == 2  # the href and its label
