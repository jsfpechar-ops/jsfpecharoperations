from pathlib import Path

from tests.test_signed_in_chrome import empty_host, host_with_property  # noqa: F401

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"


def test_apartments_copy_buttons_use_the_one_copy_button_component(host_with_property):
    page = host_with_property.get("/apartments?lang=en").text
    assert page.count('class="btn-icon" type="button" data-copy=') == 0
    assert "copy-btn" in page


def test_copy_button_macro_has_no_quiet_badge_variant():
    text = (TEMPLATES / "_components.html").read_text(encoding="utf-8")
    assert 'ui-btn-quiet ui-btn-icon ui-btn-compact" type="button" data-copy' not in text
