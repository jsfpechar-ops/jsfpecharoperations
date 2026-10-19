"""0155: no "!" prefix on any badge template; one empty state on an empty dashboard."""
from pathlib import Path

T = Path(__file__).resolve().parents[1] / "app" / "templates"


def test_no_bang_prefix_in_badge_macros():
    for name in ("_ui.html", "_components.html"):
        assert "! {% endif %}" not in (T / name).read_text(encoding="utf-8"), name


def test_needs_action_section_is_guarded_by_rows():
    text = (T / "dashboard.html").read_text(encoding="utf-8")
    assert "{% if rows %}\n  {% call ui_section(t('dashboard.section.needs_action'" in text
