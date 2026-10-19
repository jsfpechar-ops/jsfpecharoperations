"""0138: reports list, report detail and house book render on host_page."""
from __future__ import annotations

from pathlib import Path

from tests.test_signed_in_chrome import host_with_property  # noqa: F401

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"


def test_reports_and_housebook_have_the_v2_header_and_tabs(host_with_property):
    for path in ("/submissions?lang=en", "/housebook?lang=en"):
        page = host_with_property.get(path).text
        assert page.count("<h1") == 1 and 'data-body-kind="list"' in page, path
        assert 'class="ui-tabs" data-sub-tabs' in page, path
        assert "page-header" not in page, path


def test_the_house_book_keeps_its_filter_and_export_hooks(host_with_property):
    page = host_with_property.get("/housebook?lang=en").text
    assert 'id="housebook-filter-panel"' in page and "data-filter-toggle" in page
    assert 'class="filters ui-section host-filter-panel"' in page
    assert 'id="housebook-pdf-dialog" class="csv-export-dialog"' in page


def test_no_raw_style_or_legacy_control_in_the_three_templates():
    for name in ("submissions.html", "submission_detail.html", "housebook.html"):
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        assert 'style="' not in text and 'class="btn' not in text and 'class="pill' not in text, name
        assert text.count('class="ui-btn ui-btn-primary') <= 1, name
