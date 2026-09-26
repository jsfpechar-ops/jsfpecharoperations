"""Logo slots must match docs/LOGO.md (file per placement)."""
from __future__ import annotations

import re
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"
ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "app" / "static" / "landing.css").read_text(encoding="utf-8")
LOGO = (ROOT.parent / "docs" / "LOGO.md").read_text(encoding="utf-8")


def _read(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def test_auth_uses_horizontal_and_stacked_lockups():
    html = _read("auth_base.html")
    assert 'src="/static/ubyhost-logo.png"' in html
    assert 'src="/static/ubyhost-logo-stacked.png"' in html
    assert "ubyhost-logo-stacked.png" in html.split("auth-hero", 1)[1]
    assert "ubyhost-logo.png" in html.split("auth-brand", 1)[1].split("auth-hero", 1)[0]


def test_host_chrome_uses_mark_only_with_live_wordmark():
    html = _read("base.html")
    assert 'src="/static/ubyhost-mark.png"' in html
    assert "brand-word" in html and "UbyHost" in html
    # Horizontal/stacked lockups must not land in the sidebar.
    sidebar = html.split('id="app-sidebar"', 1)[1].split("</aside>", 1)[0]
    assert "ubyhost-logo.png" not in sidebar
    assert "ubyhost-logo-stacked.png" not in sidebar


PUBLIC_PAGE_TEMPLATES = (
    "landing.html",
    "pricing.html",
    "product.html",
    "public_guide.html",
)


def test_public_surfaces_use_horizontal_lockup_and_mark_accents():
    header = _read("_public_header.html")
    footer = _read("_public_footer.html")
    landing = _read("landing.html")
    # The lockup now lives in the shared chrome every public page includes.
    assert header.count('src="/static/ubyhost-logo.png"') >= 1
    assert footer.count('src="/static/ubyhost-logo.png"') >= 1
    assert 'src="/static/ubyhost-mark.png"' in landing
    for name in PUBLIC_PAGE_TEMPLATES + ("_public_header.html", "_public_footer.html"):
        assert "ubyhost-logo-stacked.png" not in _read(name)


def test_onboarding_uses_mark_only():
    html = _read("_components.html")
    assert 'class="onboarding-logo" src="/static/ubyhost-mark.png"' in html


def test_favicons_point_at_png_not_retired_svg():
    for name in ("base.html", "auth_base.html", "guest/base.html", "landing.html", "public_guide.html"):
        html = _read(name)
        assert 'href="/static/favicon.png"' in html
        assert "favicon.svg" not in html
        assert 'href="/static/apple-touch-icon.png"' in html


# --- UX-152 / D-21: the public display sizes and their doc rows -------------


def _blocks(selector: str) -> list[str]:
    found = []
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", CSS):
        if selector in [part.strip() for part in match.group(1).split(",")]:
            found.append(match.group(2))
    return found


def test_the_reel_side_mark_is_28px():
    blocks = _blocks(".reel-side img")
    assert blocks, "no .reel-side img rule"
    assert "width: 28px" in blocks[-1]


def test_the_final_cta_mark_is_64px_not_56():
    assert "width: 56px" not in CSS, "the old 56px override is back"
    blocks = _blocks(".landing-final img")
    assert blocks, "no .landing-final img rule"
    assert "width: 64px" in blocks[-1]


def test_the_pricing_card_mark_is_documented_at_its_css_size():
    blocks = _blocks(".pricing-card-head img")
    assert blocks, "no .pricing-card-head img rule"
    assert "width: 44px" in blocks[-1]
    assert ".pricing-card-head img" in LOGO


def test_the_doc_no_longer_cites_the_dead_product_shell():
    assert "product-shell" not in LOGO
    assert ".reel-side img" in LOGO
    assert "**64 × 64 px**" in LOGO
