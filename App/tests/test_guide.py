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
