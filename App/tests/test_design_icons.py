"""_icons.html: vendored Lucide icons (ISC), docs/design/MASTER.md 6.1."""
from pathlib import Path

import jinja2
import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "app"
ENV = jinja2.Environment(loader=jinja2.FileSystemLoader(str(APP_DIR / "templates")), undefined=jinja2.StrictUndefined)

MASTER_ICONS = [
    "layout-dashboard", "calendar-days", "house", "receipt", "brush-cleaning", "coins", "settings",
    "key-round", "book-open", "shield", "ellipsis", "ellipsis-vertical", "search", "plus", "x",
    "arrow-left", "chevron-left", "chevron-right", "chevron-down", "sliders-horizontal", "copy",
    "download", "send", "refresh-cw", "pencil", "trash-2", "circle-help", "triangle-alert", "check",
    "external-link", "info", "menu", "panel-left", "log-out", "languages", "archive", "file-lock", "users",
]


def _render(name, size=20):
    return ENV.from_string('{% from "_icons.html" import icon %}{{ icon(name, size) }}').render(name=name, size=size)


@pytest.mark.parametrize("name", MASTER_ICONS)
def test_every_master_icon_renders_inline_and_hidden(name):
    html = _render(name)
    assert html.startswith("<svg class=\"ui-icon\"")
    assert f'data-icon="{name}"' in html
    assert 'aria-hidden="true"' in html
    assert 'viewBox="0 0 24 24"' in html
    assert "http" not in html


def test_button_size_uses_stroke_two_and_nav_size_uses_one_seventy_five():
    assert 'stroke-width="2"' in _render("plus", 16)
    assert 'stroke-width="1.75"' in _render("plus", 20)


def test_an_unknown_icon_name_fails_instead_of_rendering_nothing():
    with pytest.raises(jinja2.exceptions.UndefinedError):
        _render("broom")


def test_the_license_is_vendored():
    text = (APP_DIR.parent / "LICENSES" / "lucide.txt").read_text(encoding="utf-8")
    assert "ISC License" in text and "lucide-static 0.552.0" in text
    assert "ISC license" in (APP_DIR / "templates" / "_icons.html").read_text(encoding="utf-8")
