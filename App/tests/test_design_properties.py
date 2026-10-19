"""0140: properties pages render on host_page; the property page keeps its local tabs."""
from __future__ import annotations

import re

from tests.test_signed_in_chrome import empty_host, host_with_property  # noqa: F401


def test_properties_list_header_tabs_and_icon(host_with_property):
    page = host_with_property.get("/apartments?lang=en").text
    assert page.count("<h1") == 1 and 'data-body-kind="list"' in page
    assert 'class="ui-tabs" data-sub-tabs' in page and 'data-icon="house"' in page
    assert page.count('class="ui-btn ui-btn-primary"') == 1


def test_property_page_keeps_local_tabs_without_section_tabs(host_with_property):
    page = host_with_property.get("/apartments?lang=en").text
    match = re.search(r'data-href="(/apartments/\d+)"', page)
    assert match
    detail = host_with_property.get(match.group(1) + "?lang=en").text
    assert '<nav class="ui-tabs property-tabs"' in detail and "data-sub-tabs" not in detail
    assert detail.count('data-property-tab="') == 3 and 'class="ui-ph-back"' in detail
    assert 'data-body-kind="detail"' in detail and "nav_icon" not in detail


def test_add_property_and_businesses_are_v2_pages(empty_host):
    assert 'data-body-kind="form"' in empty_host.get("/apartments/new?lang=en").text
    businesses = empty_host.get("/entities?lang=en").text
    assert 'data-body-kind="list"' in businesses and 'class="ui-tabs" data-sub-tabs' in businesses
