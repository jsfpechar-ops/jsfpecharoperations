"""0250: facility name example on the property page (the overview Open-pill cards were removed by the one-scroll property page, #659)."""

from tests.property_host_fixture import host  # noqa: F401


def test_facility_name_help_shows_highlighted_example_unescaped(host):
    html = host["client"].get(
        f"/apartments/{host['apartment']}?view=settings&section=reporting&lang=en"
    ).text
    assert "<mark>BYT Č. [2] FIKTVNÍ 1234/56 (PRAHA,</mark>" in html
    assert "Example from a police letter:" in html
    assert "&lt;mark&gt;" not in html
