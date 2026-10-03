"""The UbyHost mark, sized for print.

The web mark is a 512 px RGBA PNG. Embedded as is, it made up about 140 KB of
every invoice and stay-fee PDF, while printing at 3.6-4.5 mm. 192 px is still
over 1,000 dpi at that size, so the printed mark looks identical.
"""
from __future__ import annotations

import io
import os
from functools import lru_cache

from PIL import Image
from reportlab.lib.utils import ImageReader

SOURCE = os.path.join(os.path.dirname(__file__), "static", "ubyhost-mark.png")
PRINT_PX = 192


@lru_cache(maxsize=1)
def _png() -> bytes:
    with Image.open(SOURCE) as image:
        mark = image.convert("RGBA")
        mark.thumbnail((PRINT_PX, PRINT_PX), Image.LANCZOS)
        out = io.BytesIO()
        mark.save(out, "PNG", optimize=True)
    return out.getvalue()


def reader() -> ImageReader:
    """A fresh reader per document; the resized bytes are computed once."""
    return ImageReader(io.BytesIO(_png()))
