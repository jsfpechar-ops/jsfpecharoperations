"""Build the installable-app icons from static/ubyhost-mark.png (brief 0203).

Run from App/: .venv/bin/python tools/make_pwa_icons.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"
OUT = STATIC / "icons"
CANVAS = (247, 247, 245, 255)  # tokens.css --canvas, the same light square as apple-touch-icon.png


def _mark() -> Image.Image:
    mark = Image.open(STATIC / "ubyhost-mark.png").convert("RGBA")
    return mark.crop(mark.getchannel("A").getbbox())


def _on_canvas(size: int, mark_share: float) -> Image.Image:
    """The mark centred on the light canvas, its width ``mark_share`` of the side."""
    mark = _mark()
    width = round(size * mark_share)
    height = round(mark.height * width / mark.width)
    mark = mark.resize((width, height), Image.LANCZOS)
    icon = Image.new("RGBA", (size, size), CANVAS)
    icon.alpha_composite(mark, ((size - width) // 2, (size - height) // 2))
    # Opaque: iOS and Android paint transparent corners black.
    return icon.convert("RGB")


def _badge(size: int) -> Image.Image:
    """Android's status-bar badge: the mark's shape in white, the rest transparent."""
    mark = _mark()
    width = round(size * 0.84)
    height = round(mark.height * width / mark.width)
    alpha = mark.getchannel("A").resize((width, height), Image.LANCZOS)
    badge = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    white = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    white.putalpha(alpha)
    badge.alpha_composite(white, ((size - width) // 2, (size - height) // 2))
    return badge


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    # "any": the proportions of apple-touch-icon.png (mark about 72% wide).
    _on_canvas(192, 0.72).save(OUT / "icon-192.png", optimize=True)
    _on_canvas(512, 0.72).save(OUT / "icon-512.png", optimize=True)
    # "maskable": Android crops to a circle of 80% diameter; 56% keeps the mark inside.
    _on_canvas(512, 0.56).save(OUT / "icon-maskable-512.png", optimize=True)
    _badge(96).save(OUT / "badge-96.png", optimize=True)
    for path in sorted(OUT.glob("*.png")):
        print(path.name, Image.open(path).size)


if __name__ == "__main__":
    main()
