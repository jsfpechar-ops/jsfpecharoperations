"""0134: the stays list renders on host_page with v2 controls and its hooks."""
from __future__ import annotations

from tests.test_signed_in_chrome import host_with_property, empty_host  # noqa: F401


def test_stays_list_has_the_v2_header_toolbar_and_table(host_with_property):
    page = host_with_property.get("/reservations?range=all&lang=en").text
    assert page.count("<h1") == 1 and 'data-body-kind="list"' in page
    assert 'class="ui-toolbar" data-filter-toolbar data-list-toolbar' in page
    assert 'data-filter-toggle aria-expanded="true" aria-controls="stays-filter-panel" hidden' in page
    assert 'class="ui-table ui-table-stack"' in page or "data-empty-state" in page
    assert 'id="add-stay-panel" class="action-panel hidden"' in page
    assert 'data-toggle-panel="add-stay-panel"' in page
    assert "list-page-header" not in page and 'class="filter-toolbar' not in page


def test_an_empty_workspace_has_no_header_actions(empty_host):
    page = empty_host.get("/reservations?lang=en").text
    assert page.count("<h1") == 1
    assert 'class="ui-ph-acts"' not in page
    assert page.count("data-empty-state") == 1


def test_no_raw_style_or_legacy_control_in_the_template():
    text = open("app/templates/reservations.html", encoding="utf-8").read()
    assert 'style="' not in text and 'class="btn' not in text and 'class="pill' not in text
    assert text.count('ui-btn-primary') == 1
