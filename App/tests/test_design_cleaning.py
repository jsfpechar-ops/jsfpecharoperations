"""0143: host cleaning pages render on host_page; cleaning.css loads once from base."""
from __future__ import annotations

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
        assert page.count("<h1") == 1, path
        assert page.count("/static/cleaning.css") == 1, path
        assert page.index("/static/cleaning.css") < page.index("/static/host2.css"), path
        header = page[page.index('<header class="ui-ph"'):]
        header = header[: header.index("</header>")]
        assert 'class="btn' not in header and "cleaning-page-heading" not in page, path
        lane = page[page.index('<div class="ui-page"'): page.index("</main>")]
        assert lane.count("ui-btn-primary") == primaries, path


def test_host_cleaning_templates_use_only_v2_buttons_and_no_own_stylesheet():
    for name in HOST_TEMPLATES:
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        assert 'class="btn' not in text and 'class="field"' not in text and "<link" not in text, name


def test_other_host_pages_do_not_load_cleaning_css(host_with_property):
    assert "/static/cleaning.css" not in host_with_property.get("/reservations?lang=en").text


def test_shared_cleaner_page_template_keeps_its_own_stylesheet():
    text = (TEMPLATES / "cleaning_shared.html").read_text(encoding="utf-8")
    assert 'href="/static/cleaning.css?v=20261016-0123b-0106b"' in text
    assert 'class="cleaning-page-heading"' in text
