from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
TEMPLATES = ["_date_range.html", "_list_filter.html", "reservation_detail.html"]


def test_no_text_glyph_controls_left_in_templates():
    for name in TEMPLATES:
        text = (APP / "templates" / name).read_text(encoding="utf-8")
        assert not [g for g in "‹›▾▴▸" if g in text], name
