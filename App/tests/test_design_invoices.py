"""0141: invoice pages render on host_page with one primary and no inline styles."""
from __future__ import annotations

from pathlib import Path

from tests.test_signed_in_chrome import host_with_property  # noqa: F401

TEMPLATES = ("invoices.html", "invoice_detail.html", "invoice_form.html", "invoice_stay_picker.html")
TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "app" / "templates"


def test_invoice_list_has_the_v2_list_shell(host_with_property):
    page = host_with_property.get("/invoices?lang=en").text
    assert page.count("<h1") == 1 and 'data-body-kind="list"' in page
    assert 'class="ui-toolbar"' in page and "data-filter-summary" in page
    # One coral New invoice in the header; the empty state repeats it as secondary.
    assert page.count('<a class="ui-btn ui-btn-primary" href="/invoices/new">') == 1
    assert "filter-toolbar list-toolbar" not in page and "page-header" not in page


def test_invoice_stay_picker_has_the_v2_form_shell(host_with_property):
    # Without reservation_id, /invoices/new renders the stay picker.
    page = host_with_property.get("/invoices/new?lang=en").text
    assert page.count("<h1") == 1 and 'data-body-kind="form"' in page and "<style>" not in page
    assert 'class="ui-ph-back" href="/invoices"' in page


def test_templates_have_no_raw_style_or_legacy_control():
    for name in TEMPLATES:
        text = (TEMPLATE_DIR / name).read_text(encoding="utf-8")
        assert 'style="' not in text and 'class="btn' not in text and "<style>" not in text, name
