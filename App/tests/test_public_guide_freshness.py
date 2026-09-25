"""Each public guide shows when it was last checked, and names itself in the crumb.

The guides' whole value is that the rules are current, but the "last checked"
date lived only in a hard-coded JSON-LD field and the breadcrumb's last crumb
was the dead word "Guides". D-28 / UX-159.
"""
from __future__ import annotations

import json
import re

from starlette.testclient import TestClient

from app import db
from app.landing_i18n import LANDING_STRINGS
from app.main import app
from app.public_guides import GUIDE_TRANSLATIONS

DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _client() -> TestClient:
    db.init_db()
    return TestClient(app)


def _article_json_ld(html: str) -> dict:
    for block in re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.S
    ):
        data = json.loads(block)
        if data.get("@type") == "Article":
            return data
    raise AssertionError("no Article JSON-LD on the page")


def test_every_guide_carries_an_updated_date():
    for lang, guides in GUIDE_TRANSLATIONS.items():
        for slug, guide in guides.items():
            assert DATE_RE.fullmatch(guide["updated"]), (lang, slug)


def test_the_updated_date_is_visible_and_in_the_json_ld():
    for lang in ("cs", "en"):
        for slug, guide in GUIDE_TRANSLATIONS[lang].items():
            page = _client().get(f"/pruvodce/{slug}?lang={lang}").text
            rendered = LANDING_STRINGS[lang]["guide.updated"] % {"date": guide["updated"]}
            assert rendered in page, (lang, slug)

            data = _article_json_ld(page)
            assert data["datePublished"] == guide["updated"], (lang, slug)
            assert data["dateModified"] == guide["updated"], (lang, slug)


def test_the_breadcrumb_last_crumb_is_the_guide_title():
    for lang in ("cs", "en"):
        for slug, guide in GUIDE_TRANSLATIONS[lang].items():
            page = _client().get(f"/pruvodce/{slug}?lang={lang}").text
            crumb = re.search(
                r'<nav class="guide-breadcrumbs".*?</nav>', page, re.S
            ).group(0)

            assert 'aria-current="page"' in crumb, (lang, slug)
            assert guide["title"] in crumb, (lang, slug)
            assert LANDING_STRINGS[lang]["guide.breadcrumb"] not in crumb, (lang, slug)
