"""The search shortcut hint must show the right label from first paint (no JS swap)."""
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"


def test_hint_markup_has_both_labels_and_head_sets_platform():
    base = (APP / "templates/base.html").read_text()
    head = base[: base.index("</head>")]
    assert 'setAttribute("data-mac"' in head, "the data-mac line must be inline in <head>"
    assert "/static/platform.js" not in base
    assert head.index('setAttribute("data-mac"') < head.index("/static/app.js")
    for name in ("_shell_v2.html", "_shell_sidebar.html"):
        html = (APP / "templates" / name).read_text()
        assert 'class="kbd-pc">Ctrl K' in html and 'class="kbd-mac">⌘ K' in html


def test_app_js_no_longer_rewrites_hint():
    assert "hint.textContent" not in (APP / "static/app.js").read_text()
