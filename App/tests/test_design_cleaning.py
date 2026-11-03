"""0143: host cleaning pages render on host_page; cleaning.css loads once from base."""
from __future__ import annotations

import re
from pathlib import Path

from tests.test_signed_in_chrome import host_with_property  # noqa: F401

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"
# path -> ui-btn-primary count inside the page (properties is a plain link list)
PAGES = {"/cleaning": 1, "/cleaning/new": 1, "/cleaning/properties": 0, "/cleaning/shares": 1}
HOST_TEMPLATES = ("cleaning.html", "cleaning_edit.html", "cleaning_properties.html", "cleaning_settings.html",
                  "cleaning_shares.html", "_cleaning_list.html", "_cleaning_screen.html")


def test_cleaning_pages_have_the_v2_shell_and_one_stylesheet(host_with_property):
    for path, primaries in PAGES.items():
        response = host_with_property.get(f"{path}?lang=en")
        assert response.status_code == 200, path
        page = response.text
        # 0732: /cleaning has the phone headline (ph-top h1) plus the desktop head h1; the other pages have one.
        # The phone calendar view hides the list headline, so a screen-reader-only phone h1 keeps one h1 on screen.
        assert page.count("<h1") == (3 if path == "/cleaning" else 1), path
        if path == "/cleaning":
            # 0542: the host cleaning page is on the v2 shell (tokens.css + app2.css only)
            assert page.count("/static/cleaning.css") == 0 and "/static/host2.css" not in page, path
            # 0732: the phone actbar is gone; the phone share card is a .promo
            assert page.count('class="head cleaning-head"') == 1 and page.count('<a class="btn" href="/cleaning/shares"') == 1 and page.count('class="promo" href="/cleaning/shares"') == 1 and page.count('class="actbar cleaning-phone"') == 0, path
            continue
        # 0804: the sub-pages are on the v2 shell too (tokens.css + app2.css only, no cleaning.css, no host2.css)
        assert page.count("/static/cleaning.css") == 0 and "/static/host2.css" not in page, path
        # 0804: the sub-pages draw their own v2 .head (h1 + sub), so there is no ui-ph header
        assert "cleaning-page-heading" not in page and 'class="head' in page, path
        lane = page[page.index('<div class="ui-page"'): page.index("</main>")]
        assert lane.count("ui-btn-primary") == primaries, path


def test_host_cleaning_templates_use_only_v2_buttons_and_no_own_stylesheet():
    for name in HOST_TEMPLATES:
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        # 0542: cleaning.html is the v2 page, its header button is the v2 .btn
        assert (name == "cleaning.html" or 'class="btn' not in text) and 'class="field"' not in text and "<link" not in text, name


def test_other_host_pages_do_not_load_cleaning_css(host_with_property):
    assert "/static/cleaning.css" not in host_with_property.get("/reservations?lang=en").text


def test_shared_cleaner_page_template_keeps_its_own_stylesheet():
    text = (TEMPLATES / "cleaning_shared.html").read_text(encoding="utf-8")
    assert re.search(r'href="/static/cleaning\.css\?v=[^"]+"', text)
    assert 'class="cleaning-page-heading"' in text
