"""The public landing keeps the brand's atmosphere budget.

`tokens.css` says semantic hues communicate state, never decoration, and that
shadows are reserved for floating UI. The landing page had drifted past both:
two 36%-wide `blur(60px)` colour blobs behind the reel, floating "✓ Guest
form" / "UbyPort ✓" promo chips, a coral glow under the primary button, two
54px coral rings on the final band, and a body wash warmer and more saturated
than the host app's own.

The same two rules were broken again by the card grids — blue/amber/green
benefit tiles, `factor-blue/yellow/green` pricing factors and four
`tone-*` product rows, all on 250–270px white cards with a `0 1px 3px` shadow
around one line of copy. Those three grids are now one hairline "lane" list
each, and the final band is flat rather than gradient-filled.
"""
from __future__ import annotations

import re
from pathlib import Path

from starlette.testclient import TestClient

from app import db
from app.landing_i18n import LANDING_STRINGS
from app.main import app

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"
TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"
CSS = (STATIC / "landing.css").read_text(encoding="utf-8")
APP_CSS = (STATIC / "app.css").read_text(encoding="utf-8")

REMOVED_CLASSES = (
    "benefit-grid",
    "benefit-card",
    "benefit-blue",
    "benefit-yellow",
    "benefit-green",
    "factor-blue",
    "factor-yellow",
    "factor-green",
    "pricing-factor-grid",
)

LANES = (".benefit-list", ".pricing-factor-list", ".product-feature-row")

TINTED_SELECTORS = (
    ".benefit-blue",
    ".benefit-yellow",
    ".benefit-green",
    ".factor-blue",
    ".factor-yellow",
    ".factor-green",
    ".tone-blue",
    ".tone-yellow",
    ".tone-purple",
    ".tone-green",
)


def _client() -> TestClient:
    db.init_db()
    return TestClient(app)


def _render(url: str, lang: str = "en") -> str:
    joiner = "&" if "?" in url else "?"
    response = _client().get(f"{url}{joiner}lang={lang}")
    assert response.status_code == 200, f"{url} answered {response.status_code}"
    return response.text


def _section(page: str, marker: str) -> str:
    start = page.index(marker)
    return page[start : page.index("</section>", start)]


def _rule(selector: str) -> str:
    """The declaration block for `selector`, whatever file it lives in."""
    found = re.search(rf"\n{re.escape(selector)} \{{(.*?)\n\}}", CSS, re.S)
    assert found, f"no rule for {selector}"
    return found.group(1)


def _blocks(selector: str) -> list[str]:
    """The body of every rule whose selector list contains `selector` exactly.

    Unlike `_rule`, this also reaches the rules inside media queries, which is
    where the old card grids re-stated their `min-height`.
    """
    found = []
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", CSS):
        if selector in [part.strip() for part in match.group(1).split(",")]:
            found.append(match.group(2))
    return found


def _lane_blocks(lane: str) -> list[str]:
    """Every rule that styles a lane itself or something inside it."""
    found = []
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", CSS):
        selectors = [part.strip() for part in match.group(1).split(",")]
        if any(part == lane or part.startswith(lane + " ") for part in selectors):
            found.append(match.group(2))
    return found


def _selectors() -> list[str]:
    found: list[str] = []
    for match in re.finditer(r"([^{}]+)\{", CSS):
        found.extend(part.strip() for part in match.group(1).split(","))
    return found


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


def test_no_semantic_hue_tints_a_body_card():
    selectors = _selectors()
    for selector in TINTED_SELECTORS:
        assert selector not in selectors, f"{selector} tints a card with a semantic hue"


def test_the_decorative_card_classes_are_gone_from_every_surface():
    paths = sorted(STATIC.glob("*.css")) + sorted(TEMPLATES.rglob("*.html"))
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for name in REMOVED_CLASSES:
            assert name not in text, f"{path.name} still references .{name}"


def test_every_body_list_is_a_hairline_lane_and_not_a_card():
    for lane in LANES:
        blocks = _lane_blocks(lane)
        assert blocks, f"{lane} has no rule left"
        assert any("border-bottom: 1px solid var(--border)" in b for b in blocks), lane
        # The benefit and pricing lanes carry their number in a mono span. UX-155
        # removed the product lane's number, so that lane has no mono element.
        if lane != ".product-feature-row":
            assert any(
                "font-family: var(--font-mono)" in b and "color: var(--brand-ink)" in b
                for b in blocks
            ), lane
        for block in blocks:
            assert "box-shadow" not in block, lane
            assert "border-radius" not in block, lane


def test_the_final_band_is_flat():
    blocks = _blocks(".landing-final")
    assert blocks
    for block in blocks:
        assert "box-shadow" not in block
        assert "linear-gradient" not in block


def test_the_pricing_card_and_its_button_do_not_float():
    for selector in (".pricing-card", ".pricing-button"):
        blocks = _blocks(selector)
        assert blocks, selector
        for block in blocks:
            assert "box-shadow" not in block, selector


def test_the_landing_benefits_render_as_three_numbered_lanes():
    section = _section(_render("/"), "landing-section benefits")
    assert 'class="benefit-list"' in section
    assert section.count("<li>") == 3
    for number in ("01", "02", "03"):
        assert f"<span>{number}</span>" in section
    for name in ("calendar", "guest", "ubyport"):
        assert LANDING_STRINGS["en"][f"landing.benefit.{name}.title"] in section
    # The OS-dependent dingbats went out with the tinted tiles.
    for dingbat in ("▦", "✎", "✓"):
        assert dingbat not in section


def test_the_pricing_factors_render_as_three_numbered_lanes():
    section = _section(_render("/cenik"), "pricing-factors")
    assert 'class="pricing-factor-list"' in section
    assert section.count("<li>") == 3
    for name in ("properties", "volume", "workflow"):
        assert LANDING_STRINGS["en"][f"pricing.factor.{name}.title"] in section


def test_the_product_features_are_lanes_with_no_tone():
    section = _section(_render("/jak-to-funguje"), "product-feature-list")
    assert section.count('class="product-feature-row"') == 4
    assert "tone-" not in section


# --- UX-154 / D-23: hero type safe for Czech diacritics --------------------


def test_the_product_feature_rows_are_not_double_numbered():
    section = _section(_render("/jak-to-funguje"), "product-feature-list")

    assert "<span>01</span>" not in section, "the number span came back"
    for number, word in ((1, "Sync"), (2, "Collect"), (3, "Keep"), (4, "Report")):
        assert f"0{number} / {word}</p>" in section


def test_the_hero_h1_is_set_loose_enough_for_czech_diacritics():
    blocks = _blocks(".landing-hero h1")
    assert blocks, "no .landing-hero h1 rule"
    for block in blocks:
        assert "line-height: .94" not in block
        assert "line-height: 0.92" not in block
        assert "-.058em" not in block
        assert "-0.065em" not in block
    assert any(
        "line-height: 1.02" in block and "letter-spacing: -.04em" in block
        for block in blocks
    )


def test_the_mobile_hero_eyebrow_is_plain_text_not_a_pill():
    found = re.search(
        r"@media \(max-width: 600px\) \{.*?"
        r"\.landing-hero \.landing-eyebrow \{(.*?)\}",
        CSS,
        re.S,
    )
    assert found, "no mobile eyebrow rule"
    body = found.group(1)
    assert "background: transparent" in body
    assert "border: 0" in body
    assert "border-radius: 0" in body
