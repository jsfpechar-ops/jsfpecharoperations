from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"


def test_no_glyph_icons_in_guest_and_marketing_files():
    for rel in ("static/guest.css", "static/landing.css"):
        css = (APP / rel).read_text(encoding="utf-8")
        for bad in ('content: "▾"', 'content: "▴"', 'content: "−"', 'content: "+"', "\\25B8", "\\25BE", "\\2192", "\\2193"):
            assert bad not in css, (rel, bad)
    for rel in ("landing.html", "pricing.html", "product.html", "public_guide.html", "guest/stay.html"):
        text = (APP / "templates" / rel).read_text(encoding="utf-8")
        assert not [g for g in "✓↗‹›▾▴▸−" if g in text], rel
    js = (APP / "static/guest-enhancements.js").read_text(encoding="utf-8")
    assert '"−"' not in js


def test_summary_fold_saved_has_no_check_glyph_in_translations():
    for rel in ("i18n.py", "guest_uk_i18n.py"):
        for line in (APP / rel).read_text(encoding="utf-8").splitlines():
            if '"summary_fold_saved"' in line:
                assert "✓" not in line, (rel, line)
