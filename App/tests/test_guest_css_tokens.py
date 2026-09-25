"""UX-120 (audit A-33): guest.css tokens, dead rules and kicker casing."""
import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
CSS_PATH = APP_DIR / "static" / "guest.css"
TEMPLATES = APP_DIR / "templates"

# Selectors the audit found unused by any guest template or script. ``.g-fold``
# is deliberately absent: the audit listed it as dead, but claim.html and
# form.html both render it, so deleting it would have broken the explainer.
DEAD_SELECTORS = (".g-host-info", ".g-badge", ".g-stay .arrow")

# The one guest token that is set from a template's style attribute rather than
# declared in the stylesheet.
INLINE_TOKENS = ("--lane-index",)


def _css() -> str:
    return CSS_PATH.read_text(encoding="utf-8")


def _rule(selector: str, css: str | None = None) -> str:
    """The declaration block for an exact selector, whitespace-normalised."""
    body = css if css is not None else _css()
    match = re.search(
        r"(?:^|\})\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", body, re.S
    )
    assert match, f"no rule for {selector}"
    return " ".join(match.group(1).split())


def _templates() -> str:
    """Every guest template: guest.css is only loaded by the guest flow."""
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((TEMPLATES / "guest").glob("*.html"))
    )


def test_every_guest_token_is_actually_defined():
    css = _css()
    declared = set(re.findall(r"(--g-[a-z0-9-]+)\s*:", css))
    used = set(re.findall(r"var\(\s*(--g-[a-z0-9-]+)", css))
    assert used - declared == set(), sorted(used - declared)


def test_the_legal_ack_separator_uses_real_tokens():
    css = _css()
    heading = _rule(".g-legal-notice h3", css)
    assert "var(--g-ink)" in heading
    assert "var(--g-text)" not in css
    ack = _rule(".g-legal-notice .legal-ack", css)
    assert "1px solid var(--g-line)" in ack
    assert "var(--g-border)" not in css


def test_the_kickers_render_the_copy_as_written():
    css = _css()
    for selector in (".g-question-kicker", ".g-details h3"):
        rule = _rule(selector, css)
        assert "text-transform: none" in rule, selector
        assert "uppercase" not in rule, selector
    # weight and colour stay, per the audit
    assert "font-weight: 750" in _rule(".g-question-kicker", css)
    assert "var(--g-accent)" in _rule(".g-question-kicker", css)
    assert "font-weight: 700" in _rule(".g-details h3", css)
    assert "var(--g-muted)" in _rule(".g-details h3", css)


def test_the_dead_selectors_are_gone_and_nothing_still_asks_for_them():
    css = _css()
    templates = _templates()
    for selector in DEAD_SELECTORS:
        assert selector not in css, selector
        # the class a template would have to carry for the rule to matter
        class_name = selector.split()[-1].lstrip(".")
        assert class_name not in templates, selector


def test_the_still_used_fold_was_not_swept_up_with_them():
    css = _css()
    templates = _templates()
    assert ".g-fold > summary" in css
    assert "g-fold" in templates
