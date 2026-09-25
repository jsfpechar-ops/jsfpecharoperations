"""The public landing keeps the brand's atmosphere budget.

`tokens.css` says semantic hues communicate state, never decoration, and that
shadows are reserved for floating UI. The landing page had drifted past both:
two 36%-wide `blur(60px)` colour blobs behind the reel, floating "✓ Guest
form" / "UbyPort ✓" promo chips, a coral glow under the primary button, two
54px coral rings on the final band, and a body wash warmer and more saturated
than the host app's own.
"""
from __future__ import annotations

import re
from pathlib import Path

from starlette.testclient import TestClient

from app import db
from app.main import app

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"
CSS = (STATIC / "landing.css").read_text(encoding="utf-8")
APP_CSS = (STATIC / "app.css").read_text(encoding="utf-8")


def _client() -> TestClient:
    db.init_db()
    return TestClient(app)


def _rule(selector: str) -> str:
    """The declaration block for `selector`, whatever file it lives in."""
    found = re.search(rf"\n{re.escape(selector)} \{{(.*?)\n\}}", CSS, re.S)
    assert found, f"no rule for {selector}"
    return found.group(1)


def test_the_floating_promo_chips_are_gone():
    for lang in ("en", "cs"):
        html = _client().get(f"/?lang={lang}").text
        assert "demo-float" not in html
    assert ".demo-float" not in CSS, "the chips' rules outlived the chips"


def test_the_blur_blobs_are_gone():
    assert "demo-wrap::before" not in CSS
    assert "demo-wrap::after" not in CSS
    assert "blur(60px)" not in CSS


def test_the_primary_button_carries_no_coral_glow():
    primary = _rule(".landing-button.primary")
    assert "box-shadow" not in primary, "a solid fill already reads as the action"


def test_the_final_band_has_no_rings():
    assert "landing-final::before" not in CSS
    assert "landing-final::after" not in CSS


def test_the_body_wash_matches_the_host_app():
    wash = _rule("body")
    assert "background" in wash
    gradients = re.findall(r"radial-gradient\(", wash)
    assert len(gradients) == 1, "one gradient, as in app.css"
    assert "color-mix(in srgb, var(--brand-soft) 60%, transparent)" in wash
    assert "rgba(200, 90, 82" not in wash, "coral at 9% is warmer than the app's wash"
    reference = re.search(r"\nbody \{(.*?)\n\}", APP_CSS, re.S)
    assert reference, "app.css is the reference wash"
    assert "color-mix(in srgb, var(--" in reference.group(1), "pale token tints, not raw colour"
