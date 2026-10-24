"""0291: soft-coral "Open" text buttons on rows and cards, not the arrow pill."""

from pathlib import Path

from tests.test_signed_in_chrome import empty_host, host_with_property  # noqa: F401

APP = Path(__file__).resolve().parents[1]


def test_row_open_cue_has_no_arrow_icon(host_with_property):
    page = host_with_property.get("/apartments?lang=en").text
    assert 'class="row-open"' in page
    for chunk in page.split('class="row-open"')[1:]:
        assert "chevron-right" not in chunk[:200]


def test_cleaning_properties_show_an_open_button_not_an_arrow(host_with_property):
    page = host_with_property.get("/cleaning/properties?lang=en").text
    assert "ui-btn ui-btn-open" in page
    assert "→</span>" not in page


def test_needs_you_dismiss_slot_is_only_reserved_when_present():
    css = (APP / "app" / "static" / "workflow.css").read_text(encoding="utf-8")
    assert ".needs-you-list:has(.needs-you-dismiss)" in css


def test_entities_edit_is_the_primary_and_open_is_never_in_the_name_cell(host_with_property):
    page = host_with_property.get("/entities?lang=en").text
    assert "ui-btn ui-btn-open ui-btn-compact" in page
    for chunk in page.split('class="row-primary-link"')[1:]:
        assert "row-open" not in chunk.split("</td>")[0]


def test_stay_fees_open_is_never_in_the_name_cell(host_with_property):
    page = host_with_property.get("/stay-fees?lang=en").text
    for chunk in page.split('class="row-primary-link"')[1:]:
        assert "row-open" not in chunk.split("</td>")[0]
