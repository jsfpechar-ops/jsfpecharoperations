"""The TTLock app pictures in the door-lock guide exist, are small, and have alt text (task 0031)."""
from pathlib import Path

from app.guide_i18n import GUIDE_STRINGS

APP = Path(__file__).resolve().parent.parent / "app"
SHOTS = ("home", "create-admin", "form")


def test_every_picture_exists_and_stays_small():
    for shot in SHOTS:
        path = APP / "static" / "guide" / f"ttlock-{shot}.png"
        assert path.exists(), path
        assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", path
        assert path.stat().st_size < 300_000, path


def test_every_picture_has_alt_text_in_both_languages():
    for lang in ("en", "cs"):
        for shot in SHOTS:
            assert GUIDE_STRINGS[lang][f"guide.door_codes.shot_{shot}"].strip()


def test_the_guide_shows_the_pictures_under_steps_three_to_five():
    template = (APP / "templates" / "guide.html").read_text(encoding="utf-8")
    assert "{% set door_shots = {3: ['home'], 4: ['create-admin'], 5: ['form']} %}" in template
    assert 'class="guide-shot"' in template
    assert "/static/guide/ttlock-" in template
