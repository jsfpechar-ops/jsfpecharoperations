"""0375: plain bordered Open on rows, and one look for "What needs you" lines."""

from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"


def test_0291_open_rule_is_plain_not_soft_coral():
    css = (APP / "static" / "host2.css").read_text(encoding="utf-8")
    start = css.index("/* 0291 + 0375")
    end = css.index("/* 0292")
    block = css[start:end]
    assert "accent-soft" not in block
    assert "coral-500" not in block


def test_needs_you_template_uses_icon_and_primary_only_on_first_line():
    html = (APP / "templates" / "dashboard.html").read_text(encoding="utf-8")
    # 0706: the v2 Overview renders each line with overview_card (mockup .todo)
    assert "overview_card(line, loop.first)" in html
    assert 'class="ic {{ ph_tone }}"' in html
    assert "if first else ' ghost line'" in html
    assert "ui_button(line.action, 'open'" not in html
