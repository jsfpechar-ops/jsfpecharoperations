"""The house-book PDF font renders Czech letters (invoice step 3b).

Bitstream Vera silently dropped ě, ř, ů, ň, ť. The vendored DejaVu Sans must carry
them, or every Czech name and the registration-form title lose glyphs.
"""
from __future__ import annotations

from reportlab.pdfbase import pdfmetrics

from app import housebook


def test_housebook_font_is_the_vendored_dejavu():
    assert housebook.FONT_REGULAR == "DejaVu"
    assert housebook.FONT_BOLD == "DejaVu-Bold"


def test_housebook_font_has_czech_glyphs():
    glyphs = pdfmetrics.getFont(housebook.FONT_REGULAR).face.charToGlyph
    for ch in "Přihlašovací ěřůňť":
        assert ord(ch) in glyphs, f"missing glyph for {ch!r}"
