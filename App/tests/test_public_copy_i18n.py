"""Public copy lives in landing_i18n.py, not in the templates.

The footer's guest-book link, the two guide cards on the product page and the
demo calendar's weekday row were hard-coded in the templates, so the EN/CS
parity test could not see them and the CS page rendered the English weekdays.
UX-150 moves them all into landing_i18n.py.
"""
from __future__ import annotations

import re
from pathlib import Path

from starlette.testclient import TestClient

from app import db
from app.landing_i18n import LANDING_STRINGS
from app.main import app

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"
CALENDAR_DAYS_RE = re.compile(
    r'<div class="calendar-days" aria-hidden="true">(.*?)</div>', re.DOTALL
)


def _client() -> TestClient:
    db.init_db()
    return TestClient(app)


def _get(url: str, lang: str) -> str:
    joiner = "&" if "?" in url else "?"
    response = _client().get(f"{url}{joiner}lang={lang}")
    assert response.status_code == 200, f"{url} answered {response.status_code}"
    return response.text


def _read(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def test_the_footer_guest_book_link_comes_from_i18n():
    assert LANDING_STRINGS["en"]["landing.footer.guestbook"] == "Guest book"
    assert LANDING_STRINGS["cs"]["landing.footer.guestbook"] == "Ubytovací kniha"
    assert "Guest book" in _get("/", "en")
    assert "Ubytovací kniha" in _get("/", "cs")


def test_the_product_guide_cards_come_from_i18n():
    for lang in ("en", "cs"):
        page = _get("/jak-to-funguje", lang)
        for name in ("ubyport", "book"):
            for field in ("kicker", "title", "meta"):
                value = LANDING_STRINGS[lang][f"landing.guide.{name}.{field}"]
                assert value in page, (lang, name, field, value)
        other = "cs" if lang == "en" else "en"
        assert LANDING_STRINGS[other]["landing.guide.ubyport.title"] not in page


def test_the_demo_weekday_row_is_localized():
    english = CALENDAR_DAYS_RE.search(_get("/", "en")).group(1)
    czech = CALENDAR_DAYS_RE.search(_get("/", "cs")).group(1)

    assert "<b>M</b><b>T</b><b>W</b>" in english
    assert "<b>Po</b><b>Út</b><b>St</b>" in czech
    assert "<b>M</b><b>T</b>" not in czech


def test_the_templates_no_longer_carry_this_copy():
    assert "'Guest book' if lang" not in _read("_public_footer.html")
    assert "Reporting foreign guests through UbyPort" not in _read("product.html")
    assert "Online guest book without paperwork" not in _read("product.html")
    assert "('M','T','W','T','F','S','S')" not in _read("landing.html")
