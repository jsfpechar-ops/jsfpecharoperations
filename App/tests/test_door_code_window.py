"""The disclosed hours must match the actual TTLock window, including DST."""
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app import config, host_i18n, ttlock


class _Window(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values = {}
        self.hidden = {}
        self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for key in ("data-window-start", "data-window-end", "data-window-values", "data-window-missing"):
            if key in attrs:
                self.hidden[key] = "hidden" in attrs
                if tag == "dd":
                    self.current = key
                    self.values[key] = ""

    def handle_data(self, data):
        if self.current:
            self.values[self.current] += data

    def handle_endtag(self, tag):
        if tag == "dd":
            self.current = None


def _render(cin, cout, lang, buffer=1):
    env = Environment(
        loader=FileSystemLoader(Path(__file__).resolve().parents[1] / "app" / "templates"),
        autoescape=True, undefined=StrictUndefined,
    )
    html = env.get_template("_door_code_window.html").render(
        apartment={"checkin_hour": cin, "checkout_hour": cout},
        door_code={"buffer": buffer},
        t=lambda key, **kwargs: host_i18n.translate(lang, key, **kwargs),
    )
    parsed = _Window()
    parsed.feed(html)
    return html, parsed


@pytest.mark.parametrize("lang", ["en", "cs", "vi"])
@pytest.mark.parametrize("cin,cout", [(15, 11), (0, 23), (1, 22), (23, 0)])
@pytest.mark.parametrize("arrival,departure", [
    ("2026-01-10", "2026-01-12"),
    ("2026-07-10", "2026-07-12"),
    ("2026-03-28", "2026-03-30"),
    ("2026-10-24", "2026-10-26"),
])
def test_disclosed_times_match_the_window_sent_to_ttlock(lang, cin, cout, arrival, departure):
    _, parsed = _render(cin, cout, lang, config.DOOR_CODE_BUFFER_HOURS)
    start, end = ttlock.stay_window(
        arrival, departure, cin, cout, config.DOOR_CODE_BUFFER_HOURS
    )
    tz = ZoneInfo(config.TIMEZONE)
    for key, epoch, booking_day, normal_day, overflow_day in (
        ("data-window-start", start, arrival, "arrival", "previous"),
        ("data-window-end", end, departure, "departure", "next"),
    ):
        actual = datetime.fromtimestamp(epoch / 1000, tz)
        day_key = normal_day if actual.date().isoformat() == booking_day else overflow_day
        expected = actual.strftime("%H:%M") + " · " + host_i18n.translate(
            lang, "door_code.window." + day_key
        )
        assert parsed.values[key] == expected
    assert not parsed.hidden["data-window-values"]
    assert parsed.hidden["data-window-missing"]


@pytest.mark.parametrize("cin,cout", [(None, None), (15, None), (None, 11)])
@pytest.mark.parametrize("lang", ["en", "cs", "vi"])
def test_incomplete_times_do_not_invent_an_access_window(cin, cout, lang):
    html, parsed = _render(cin, cout, lang)
    assert parsed.hidden["data-window-values"]
    assert not parsed.hidden["data-window-missing"]
    assert not any(parsed.values.values())
    assert host_i18n.translate(lang, "door_code.window.margin", hours=1) in html


def test_preview_uses_the_configured_margin():
    _, parsed = _render(15, 11, "en", buffer=2)
    assert parsed.values["data-window-start"] == "13:00 · arrival day"
    assert parsed.values["data-window-end"] == "13:00 · departure day"


@pytest.mark.parametrize("lang", ["en", "cs", "vi"])
@pytest.mark.parametrize("cin,cout", [("15", "11"), ("0", "23"), ("23", "0")])
def test_posted_hour_strings_render_like_saved_integer_hours(lang, cin, cout):
    _, posted = _render(cin, cout, lang)
    _, saved = _render(int(cin), int(cout), lang)
    assert posted.values == saved.values
    assert posted.hidden == saved.hidden


@pytest.mark.parametrize("lang", ["en", "cs", "vi"])
@pytest.mark.parametrize("cin,cout", [
    ("", ""), ("", "11"), ("15", ""),
    ("99", "10"), ("15", "24"), ("-1", "11"),
    ("invalid", "11"), ("15.5", "11"), ("15", "NaN"),
])
def test_invalid_posted_hours_keep_the_explanation_without_inventing_times(lang, cin, cout):
    _, parsed = _render(cin, cout, lang)
    assert parsed.hidden["data-window-values"]
    assert not parsed.hidden["data-window-missing"]
    assert not any(parsed.values.values())
