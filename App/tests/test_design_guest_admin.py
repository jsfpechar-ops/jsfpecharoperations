"""0139: the host's guest add/edit page renders on host_page as a form page."""
from __future__ import annotations

from pathlib import Path

from tests.test_host_guest_form import _cleanup, _host_client, _host_guest, _host_stay

TEMPLATE = Path(__file__).resolve().parents[1] / "app" / "templates" / "guest_form_admin.html"


def _assert_v2_form_shell(page: str, stay_id: int) -> None:
    assert page.count("<h1") == 1 and 'data-body-kind="form"' in page
    assert f'class="ui-ph-back" href="/reservations/{stay_id}"' in page
    assert 'class="ui-ph-meta"' in page
    assert page.count('class="ui-btn ui-btn-primary"') == 1
    assert '<div class="ui-form-actions">\n    <a class="ui-btn ui-btn-quiet" href="/reservations/' in page
    assert 'class="ui-btn ui-btn-primary" type="submit"' in page
    assert "page-header" not in page and "breadcrumbs" not in page
    assert '/static/signature.js?v=' in page


def test_add_guest_page_has_the_v2_form_shell():
    owner_id, stay_id = _host_stay()
    try:
        page = _host_client(owner_id).get(f"/reservations/{stay_id}/guests/new?lang=en").text
        _assert_v2_form_shell(page, stay_id)
    finally:
        _cleanup()


def test_edit_guest_page_keeps_save_as_the_first_submit_button():
    owner_id, stay_id = _host_stay()
    try:
        guest_id = _host_guest(stay_id)
        page = _host_client(owner_id).get(f"/guests/{guest_id}?lang=en").text
        _assert_v2_form_shell(page, stay_id)
        main = page[page.index(f'<form method="post" action="/guests/{guest_id}"'):]
        main = main[: main.index("</form>")]
        # Enter in a field submits with the first submit button: that must be Save, not Restrict.
        assert main.index('class="ui-btn ui-btn-primary" type="submit"') < main.index("formaction=")
    finally:
        _cleanup()


def test_no_raw_style_or_legacy_control_in_the_template():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert 'style="' not in text and 'class="btn' not in text and "<script src" not in text
