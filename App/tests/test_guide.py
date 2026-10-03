"""The Help & guide renders every section in both languages, with no raw keys."""
from __future__ import annotations

from tests.test_submission_retry_cap import host as host  # noqa: F401


def test_the_guide_renders_every_section_without_raw_keys(host):
    for lang in ("en", "cs"):
        page = host.get(f"/guide?lang={lang}").text
        for section in ("overview", "statuses", "setup", "stays", "guests", "reporting",
                        "filters", "housebook", "stay_fee", "invoices", "settings",
                        "faster", "faq", "legal"):
            assert f'id="{section}"' in page, (lang, section)
        assert "guide." not in page.replace("/guide", "")
        assert '<span class="pill red">' in page


def test_the_guide_has_the_same_keys_in_english_and_czech():
    from app.guide_i18n import GUIDE_STRINGS

    english, czech = set(GUIDE_STRINGS["en"]), set(GUIDE_STRINGS["cs"])
    assert english - czech == set(), "keys missing in Czech"
    assert czech - english == set(), "keys missing in English"
    for lang, strings in GUIDE_STRINGS.items():
        assert all(value.strip() for value in strings.values()), lang


def test_the_guide_describes_the_owner_decisions(host):
    """Second pass: one automatic retry, deletion and the ZIP, date changes, filing time."""
    from app import host_i18n

    for lang in ("en", "cs"):
        page = host.get(f"/guide?lang={lang}").text
        for key in ("guide.reporting.failure", "guide.reporting.filed",
                    "guide.stays.dates_changed", "guide.settings.deletion"):
            text = host_i18n.translate(lang, key)
            assert text and text != key, (lang, key)
            # Jinja escapes apostrophes, so compare on a stretch without one.
            assert text[:40].replace("'", "&#39;") in page, (lang, key)

    english = host_i18n.STRINGS["en"]
    assert "once more" in english["guide.reporting.failure"]
    assert "stay-fee filings" in english["guide.settings.deletion"]
    assert "do not sign again" in english["guide.stays.dates_changed"]
    # The button the deletion text names is the one the banner shows.
    for lang in ("en", "cs"):
        assert host_i18n.STRINGS[lang]["workspace.deletion.download_zip"] in (
            host_i18n.STRINGS[lang]["guide.settings.deletion"]
        )
