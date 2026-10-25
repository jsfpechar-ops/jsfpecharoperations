"""Guide coverage (plan 16b): Havel's guide pages, the guide's anchors and its three
languages stay in step. A failure here means: update guide_i18n.py, host_vi_i18n.py,
guide.html or havel.GUIDE_ANCHORS in the same PR."""
import re

from app import guide_i18n, havel, havel_topics, host_vi_i18n
from tests.test_submission_retry_cap import host  # noqa: F401

EN = guide_i18n.GUIDE_STRINGS["en"]
LEGAL_TERMS = "guide.door_codes.terms"


def test_every_guide_key_has_czech_and_vietnamese():
    no_cs = [k for k in EN if k not in guide_i18n.GUIDE_STRINGS["cs"]]
    no_vi = [k for k in EN if k not in host_vi_i18n.STRINGS and not k.startswith(LEGAL_TERMS)]
    assert no_cs == [], f"Czech missing: {no_cs[:10]}"
    assert no_vi == [], f"Vietnamese missing (host_vi_i18n.py): {no_vi[:10]}"


def test_every_havel_guide_page_and_menu_link_has_an_anchor(host):
    html = host.get("/guide").text
    ids = set(re.findall(r'\sid="([^"]+)"', html))
    pages = {page: entry[0] for page, entry in havel.PAGES.items() if page.startswith("guide_")}
    assert [p for p, url in pages.items() if url.split("#", 1)[1] not in ids] == []
    menu = re.findall(r'<a href="#([^"]+)" class="guide-nav-link"', html)
    assert len(menu) >= 20 and [a for a in menu if a not in ids] == []


def test_every_guide_section_is_known_to_havel(host):
    html = host.get("/guide").text
    sections = re.findall(r'<section class="guide-section[^"]*" id="([^"]+)"', html)
    assert len(sections) >= 20
    assert [s for s in sections if s != "demo" and s not in havel.GUIDE_ANCHORS] == []


def test_quick_help_answers_read_real_guide_text_in_every_language():
    for lang in ("en", "cs", "vi"):
        for topic in havel_topics.TOPICS:
            for q in topic["questions"]:
                for p in havel_topics.answer(lang, topic["id"], q["id"])["paragraphs"]:
                    assert len(p) > 25 and not p.startswith(("guide.", "havel.")), (lang, topic["id"], q["id"], p)
