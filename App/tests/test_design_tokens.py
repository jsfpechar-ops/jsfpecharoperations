"""Design v2 tokens (docs/design/MASTER.md section 2) exist in tokens.css.

The three layers are the only place a raw colour may live. Later briefs
build the host stylesheet from these names; this test keeps them stable.
"""
import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
TOKENS = (APP_DIR / "static" / "tokens.css").read_text(encoding="utf-8")
# The reduced-motion block redefines the motion tokens on purpose; count
# definitions only in the main :root block.
ROOT_BLOCK = TOKENS.split("@media (prefers-reduced-motion", 1)[0]

V2_NAMES = [
    "--coral-600", "--sand-100", "--ink-900", "--amber-700", "--green-700", "--red-700",
    "--size-16", "--radius-2", "--shadow-2", "--motion-2",
    "--surface-2", "--ink-2", "--ink-3", "--line-strong", "--accent", "--accent-soft", "--accent-ink",
    "--focus-ring-2", "--st-action-bg", "--st-attention-bg", "--st-done-bg", "--st-neutral-bg", "--danger",
    "--property-1", "--control-h", "--control-h-phone", "--control-h-compact", "--row-h", "--badge-h",
    "--nav-w", "--tabbar-h", "--topbar-h", "--lane", "--lane-narrow", "--body-size",
    "--skeleton-delay", "--skeleton-min",
]


def test_every_v2_token_is_defined_once():
    for name in V2_NAMES:
        assert len(re.findall(rf"{re.escape(name)}\s*:", ROOT_BLOCK)) == 1, name


def test_primitive_values_are_what_master_says():
    assert "--coral-600: #ad4942" in TOKENS
    assert "--coral-500: #c85a52" in TOKENS
    assert "--ink-900: #20201e" in TOKENS
    assert "--body-size: var(--size-16)" in TOKENS


def test_reduced_motion_zeroes_the_v2_motion_tokens():
    assert "--motion-1: 0.01ms; --motion-2: 0.01ms; --motion-3: 0.01ms;" in TOKENS
