"""The pre-2026 landing rules and their copy are gone, not merely overridden.

`landing.css` kept a whole earlier landing (product window, feature grid, proof
strip, how-it-works) whose classes no template has used since the 2026 layer,
plus landing.mock.* / landing.proof.* / landing.how.* keys nothing rendered.
D-31 / UX-162 deletes them.
"""
from __future__ import annotations

from pathlib import Path

from app.landing_i18n import LANDING_STRINGS

CSS = (Path(__file__).resolve().parents[1] / "app" / "static" / "landing.css").read_text(
    encoding="utf-8"
)

DEAD_SELECTORS = (
    ".product-window",
    ".product-window-bar",
    ".product-shell",
    ".product-queue",
    ".product-queue-head",
    ".product-stay",
    ".product-receipt",
    ".landing-product-stage",
    ".landing-proof",
    ".landing-how",
    ".landing-steps",
    ".landing-feature-grid",
    ".feature-icon",
    ".feature-calendar",
    ".feature-form",
    ".feature-book",
    ".feature-report",
    ".stage-note",
    ".stay-avatar",
    ".stay-state",
)

DEAD_MOCK_KEYS = (
    "landing.mock.label",
    "landing.mock.action",
    "landing.mock.arrival",
    "landing.mock.complete",
    "landing.mock.missing",
    "landing.mock.report",
    "landing.mock.receipt",
    "landing.mock.note.forms",
    "landing.mock.note.receipts",
)


def test_the_dead_pre_2026_selectors_are_gone():
    for selector in DEAD_SELECTORS:
        assert selector not in CSS, selector


def test_the_unused_landing_key_families_are_gone():
    for lang in ("en", "cs"):
        keys = LANDING_STRINGS[lang]
        assert not [key for key in keys if key.startswith("landing.proof.")]
        assert not [key for key in keys if key.startswith("landing.how.")]
        for key in DEAD_MOCK_KEYS:
            assert key not in keys, (lang, key)


def test_the_mock_keys_the_demo_still_uses_survive():
    for lang in ("en", "cs"):
        assert "landing.mock.today" in LANDING_STRINGS[lang]
        assert "landing.mock.guest_form" in LANDING_STRINGS[lang]
