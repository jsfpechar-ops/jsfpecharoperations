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
from app.landing_i18n import LANDING_STRINGS
from app.main import app

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"
LANDING_CSS = Path(__file__).resolve().parents[1] / "app" / "static" / "landing.css"

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


def _desktop_nav(chunk: str) -> str:
    return _between(chunk, '<nav class="landing-nav"', "</nav>")


def _menu_nav(chunk: str) -> str:
    menu = _between(chunk, '<details class="landing-menu">', "</details>")
    return _between(menu, "<nav ", "</nav>")


def _nav_labels(chunk: str) -> list[str]:
    nav = _desktop_nav(chunk)
    return [text.strip() for text in re.findall(r">([^<]+)</a>", nav)]


def _render(url: str, lang: str = "en") -> str:
    joiner = "&" if "?" in url else "?"
    response = _client().get(f"{url}{joiner}lang={lang}")
    assert response.status_code == 200, f"{url} answered {response.status_code}"
    return response.text


def _media_blocks(css: str, max_width: int) -> list[str]:
    """The bodies of every `@media (max-width: Npx)` block in the stylesheet."""
    blocks = []
    marker = f"@media (max-width: {max_width}px)"
    start = css.find(marker)
    while start != -1:
        depth = 0
        for index in range(css.index("{", start), len(css)):
            if css[index] == "{":
                depth += 1
            elif css[index] == "}":
                depth -= 1
                if depth == 0:
                    blocks.append(css[start : index + 1])
                    break
        start = css.find(marker, index)
    return blocks


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


def test_the_nav_is_the_same_three_destinations_on_every_page():
    seen = {}
    for url in PUBLIC_URLS:
        labels = _nav_labels(_header(_render(url)))
        assert len(labels) == 3, url
        seen[url] = labels
    assert len(set(tuple(labels) for labels in seen.values())) == 1
    assert list(seen.values())[0] == ["How it works", "Pricing", "Guides"]


def test_each_page_marks_its_own_nav_item_and_only_its_own():
    expected = {
        "/": None,
        "/cenik": "Pricing",
        "/jak-to-funguje": "How it works",
        "/pruvodce/hlaseni-cizincu-ubyport": "Guides",
        "/pruvodce/online-ubytovaci-kniha": None,
    }
    for url, label in expected.items():
        for nav in (_desktop_nav(_header(_render(url))), _menu_nav(_header(_render(url)))):
            current = re.findall(r'<a href="[^"]*" aria-current="page">([^<]+)</a>', nav)
            assert current == ([] if label is None else [label]), url


def test_every_nav_label_is_a_destination_not_an_anchor():
    for url in PUBLIC_URLS:
        header = _header(_render(url))
        for nav in (_desktop_nav(header), _menu_nav(header)):
            hrefs = _hrefs(nav)
            assert len(hrefs) == 3, url
            assert not any("#" in href for href in hrefs), url


def test_no_nav_label_is_named_after_someone_elses_system():
    header = _header(_render("/"))
    for nav in (_desktop_nav(header), _menu_nav(header)):
        assert ">UbyPort<" not in nav
    # The guide the third item opens is still reachable, just named for what it is.
    assert 'href="/pruvodce/hlaseni-cizincu-ubyport?lang=en">Guides</a>' in _desktop_nav(header)


def test_the_product_page_has_one_name_across_the_site():
    # "How it works" in the nav, "See how it works" on the hero, "Product details
    # and common questions" at the foot of the body: three names for one page.
    for lang in ("en", "cs"):
        name = LANDING_STRINGS[lang]["landing.nav.how"]
        assert LANDING_STRINGS[lang]["landing.contact"] == name, lang
        assert LANDING_STRINGS[lang]["landing.details.link"] == name, lang


def test_the_phone_menu_offers_the_same_destinations_as_the_desktop_nav():
    for url in PUBLIC_URLS:
        header = _header(_render(url))
        desktop = re.findall(r'href="([^"]+)"', _desktop_nav(header))
        menu = re.findall(r'href="([^"]+)"', _menu_nav(header))
        assert menu == desktop, url


def test_the_phone_menu_is_rendered_in_the_language_of_the_page():
    menu = _between(_header(_render("/cenik", lang="en")), '<details class="landing-menu">', "</details>")
    assert ">Menu<" in menu
    czech = _between(_header(_render("/cenik", lang="cs")), '<details class="landing-menu">', "</details>")
    assert ">Menu<" in czech
    assert ">Jak to funguje<" in czech
    assert ">Ceník<" in czech
    assert "landing." not in czech


def test_the_phone_menu_is_a_javascript_free_disclosure():
    header = _header(_render("/"))
    menu = _between(header, '<details class="landing-menu">', "</details>")
    assert "<summary>" in menu
    # A `<summary>` is the disclosure control; a button would need script.
    assert "<button" not in menu


def test_log_in_is_never_hidden_by_a_media_query():
    css = (Path(__file__).resolve().parents[1] / "app" / "static" / "landing.css").read_text(
        encoding="utf-8"
    )
    assert re.search(r"\.landing-login\s*\{[^}]*display:\s*none", css) is None


def test_log_in_is_a_quiet_text_link_not_a_second_primary():
    css = LANDING_CSS.read_text(encoding="utf-8")
    rule = re.search(r"^\.landing-login\s*\{([^}]*)\}", css, re.M)
    assert rule, "no .landing-login rule in landing.css"
    body = rule.group(1)
    # The coral fill belongs to the page's one primary CTA, so the header link
    # must not carry it back.
    for declaration in ("brand-action", "brand-pressed", "on-brand", "border-radius"):
        assert declaration not in body, declaration
    # Quiet, but still a full-size tap target on a phone.
    assert re.search(r"min-height:\s*44px", body)
    # And no hover rule may re-fill it.
    assert re.search(r"\.landing-login:hover\s*\{[^}]*background", css) is None


def test_the_phone_menu_only_appears_where_the_nav_is_hidden():
    css = (Path(__file__).resolve().parents[1] / "app" / "static" / "landing.css").read_text(
        encoding="utf-8"
    )
    # Hidden by default, so on a wide screen the desktop nav is the only nav.
    assert re.search(r"^\.landing-menu\s*\{\s*display:\s*none;\s*\}", css, re.M)
    # Revealed only where the nav goes away, so there is never no nav and never
    # two of them.
    for block in _media_blocks(css, 900):
        if ".landing-menu" in block and "display: block" in block:
            break
    else:
        raise AssertionError("no max-width: 900px block reveals the phone menu")
    assert any(".landing-nav { display: none; }" in block for block in _media_blocks(css, 900))


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


# --- UX-153 / D-22: the language switch is a labelled nav with a current mark --


def test_the_language_switch_is_a_labelled_nav():
    for url in PUBLIC_URLS:
        header = _header(_render(url))
        assert (
            re.search(r'<nav class="landing-languages" aria-label="[^"]+">', header)
            is not None
        ), url
        assert "</nav>" in header


def test_the_language_switch_announces_the_current_language():
    english = _header(_render("/cenik", "en"))
    czech = _header(_render("/cenik", "cs"))

    assert re.search(r'hreflang="en"[^>]*aria-current="true"', english)
    assert not re.search(r'hreflang="cs"[^>]*aria-current', english)
    assert re.search(r'hreflang="cs"[^>]*aria-current="true"', czech)
    assert not re.search(r'hreflang="en"[^>]*aria-current', czech)


def test_the_language_switch_has_a_44px_tap_height_on_mobile():
    css = LANDING_CSS.read_text(encoding="utf-8")
    blocks = _media_blocks(css, 600)
    assert any(
        ".landing-languages a" in block and "min-height: 44px" in block
        for block in blocks
    ), "the phone language switch is under the 44px tap bar"
