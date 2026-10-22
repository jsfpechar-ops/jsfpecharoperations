"""0250: Open pills on property cards, whole Guest links card, facility name example."""

from tests.test_property_navigation_browser import host  # noqa: F401


def _pill(text):
    return (
        '<span class="host-property-card-open" aria-hidden="true">'
        f'<span class="host-property-card-open-text">{text}</span>'
    )


def _overview(host, lang):
    return host["client"].get(f"/apartments/{host['apartment']}?view=overview&lang={lang}").text


def test_overview_cards_show_open_pill_and_guest_link_is_stretched(host):
    html = _overview(host, "en")
    assert html.count(_pill("Open")) == 7
    assert 'class="host-property-card-link"' in html


def test_overview_open_pill_is_translated_in_cs_and_vi(host):
    assert _overview(host, "cs").count(_pill("Otevřít")) == 7
    assert _overview(host, "vi").count(_pill("Mở")) == 7


def test_facility_name_help_shows_highlighted_example_unescaped(host):
    html = host["client"].get(
        f"/apartments/{host['apartment']}?view=settings&section=reporting&lang=en"
    ).text
    assert "<mark>BYT Č. [2] FIKTVNÍ 1234/56 (PRAHA,</mark>" in html
    assert "Example from a police letter:" in html
    assert "&lt;mark&gt;" not in html
