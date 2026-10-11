"""Platform source badges use only local static logos."""
from __future__ import annotations

from markupsafe import Markup

from app import templating


def test_source_mark_renders_img_for_known_platform():
    html = templating.source_mark("airbnb")
    assert isinstance(html, Markup)
    assert "<img" in html
    assert 'src="/static/platforms/airbnb-icon.svg"' in html
    assert 'alt=""' in html
    assert "http" not in html.lower().replace("/static/", "")


def test_source_mark_empty_for_manual_and_missing():
    assert templating.source_mark("manual") == ""
    assert templating.source_mark("not-a-platform") == ""
    assert templating.source_mark("UPPER") == ""


def test_source_badge_macro_includes_img_when_logo_exists():
    rendered = (
        templating.templates.env.from_string(
            '{% from "_components.html" import source_badge %}{{ source_badge("booking", "Booking.com") }}'
        )
        .render()
    )
    assert "<img" in rendered
    assert "Booking.com" in rendered
    assert 'src="/static/platforms/booking-icon.svg"' in rendered


def test_source_badge_macro_label_only_without_logo():
    rendered = (
        templating.templates.env.from_string(
            '{% from "_components.html" import source_badge %}{{ source_badge("manual", "Direct booking") }}'
        )
        .render()
    )
    assert "<img" not in rendered
    assert "Direct booking" in rendered
    assert 'class="source-badge"' in rendered


def test_source_mark_rejects_invalid_keys():
    assert templating.source_mark("air bnb") == ""
    assert templating.source_mark("airbnb!") == ""


def test_source_mark_supports_vrbo_and_trip_owner_files():
    vrbo = templating.source_mark("vrbo")
    trip = templating.source_mark("trip")
    assert 'src="/static/platforms/Vrbo.svg"' in vrbo
    assert 'src="/static/platforms/Trip.com_logo.svg.webp"' in trip


def test_source_mark_monkeypatched_cache(tmp_path, monkeypatch):
    monkeypatch.setitem(templating._PLATFORM_LOGO_KEYS, "demo", "demo.png")
    html = templating.source_mark("demo")
    assert 'src="/static/platforms/demo.png"' in html
    monkeypatch.delitem(templating._PLATFORM_LOGO_KEYS, "demo", raising=False)
