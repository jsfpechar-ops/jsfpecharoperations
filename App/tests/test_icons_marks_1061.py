from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
TEMPLATES = [
    "_property_editor.html", "setup_wizard/done.html", "leon_setup/done.html", "setup_wizard/try_it.html",
    "setup_wizard/_layout.html", "_components.html", "_workflow.html", "stay_fees.html",
    "_smart_locks_panel.html", "auth_base.html", "_dashboard_calendar.html",
]


def test_no_check_cross_times_glyphs_in_templates():
    for name in TEMPLATES:
        text = (APP / "templates" / name).read_text(encoding="utf-8")
        assert not [g for g in "✓✗×" if g in text] and "&times;" not in text, name


def test_app_js_builds_svg_icons_not_glyph_text():
    js = (APP / "static" / "app.js").read_text(encoding="utf-8")
    assert 'textContent = "×"' not in js and '"✓"' not in js
