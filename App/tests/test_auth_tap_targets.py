"""UX-123 (audit B-19): the auth chrome's controls must clear the 44px bar.

The language switch is the first control a non-Czech host needs on a phone,
and it was ~22px tall; "Remember me" was ~20px.
"""
import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
APP_CSS = APP_DIR / "static" / "app.css"
TOKENS_CSS = APP_DIR / "static" / "tokens.css"
AUTH_BASE = APP_DIR / "templates" / "auth_base.html"


def _css() -> str:
    return APP_CSS.read_text(encoding="utf-8")


def _declarations(selector: str) -> str:
    """Every declaration for one selector, in source order (later wins)."""
    body = _css()
    found = []
    for match in re.finditer(
        r"(?:^|\})\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", body, re.M
    ):
        found.append(match.group(1))
    assert found, f"{selector} disappeared from app.css"
    return " ".join(" ".join(chunk.split()) for chunk in found)


def test_the_language_switch_buttons_are_at_least_44px():
    rules = _declarations(".auth-lang-switch button")
    assert "min-height: 44px" in rules
    assert "min-width: 44px" in rules
    assert "font-size: var(--text-sm)" in rules


def test_the_language_switch_keeps_its_pill_and_weight():
    rules = _declarations(".auth-lang-switch button")
    assert "border-radius: var(--radius-pill)" in rules
    assert "font-weight: 760" in rules


def test_remember_me_is_at_least_44px_tall():
    rules = _declarations(".auth-remember")
    assert "min-height: 44px" in rules
    # The label is a flex row, so the taller box keeps the checkbox centred.
    assert "align-items: center" in rules


def test_the_font_size_token_is_real():
    assert "--text-sm:" in TOKENS_CSS.read_text(encoding="utf-8")


def test_the_switch_labels_are_unchanged():
    """B-19 is a tap-target fix; the labels stay the product-wide "EN"/"CZ"."""
    html = AUTH_BASE.read_text(encoding="utf-8")
    assert 'class="lang-switch auth-lang-switch"' in html
    assert "flag" not in html.lower()
