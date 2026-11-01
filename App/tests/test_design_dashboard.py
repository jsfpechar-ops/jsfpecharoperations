"""Dashboard on host_page.html (docs/design/pages/dashboard.md)."""

from tests.test_signed_in_chrome import empty_host, host_with_property  # noqa: F401


def test_dashboard_with_a_property_has_the_v2_header_one_primary_and_refresh_hooks(host_with_property):
    page = host_with_property.get("/?lang=en").text
    assert page.count("<h1") == 1 and 'data-body-kind="detail"' in page
    assert page.count('class="btn" href="/reservations?new=1"') == 1  # 0706: the v2 header button
    assert "ui-ph-menu" not in page
    assert "dashboard-more" not in page
    # 0714: the calendar refreshes these in place
    assert 'data-dashboard-refresh="stats"' in page and 'data-dashboard-refresh="work"' in page
    # 0241: the count tiles gave way to the "What needs you" card.
    assert 'data-needs-you-card' in page and 'class="ui-stats' not in page
    assert "page-toolbar" not in page


def test_the_zero_state_keeps_the_welcome_card_and_one_h1(empty_host):
    page = empty_host.get("/?lang=en").text
    assert page.count("<h1") == 1
    assert 'class="onboarding-welcome"' in page
    assert 'class="ui-ph"' not in page


def test_no_raw_style_or_pill_in_the_dashboard_template():
    text = open("app/templates/dashboard.html", encoding="utf-8").read()
    assert 'style="' not in text and 'class="pill' not in text and "<svg" not in text
