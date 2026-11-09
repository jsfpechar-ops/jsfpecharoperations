from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app" / "templates"


def test_no_arrow_search_close_glyphs_left():
    for name in ("property_page_review.html", "property_page_book.html", "base.html"):
        text = (APP / name).read_text(encoding="utf-8")
        assert not [g for g in "↑↓→⌕" if g in text] and "&times;" not in text, name
    assert "×" not in (APP / "property_page_review.html").read_text(encoding="utf-8")
