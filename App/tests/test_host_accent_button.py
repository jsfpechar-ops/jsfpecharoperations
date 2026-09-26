"""The host accent button must not carry a glow, and no stale colour comment.

`tokens.css` reserves shadows for floating UI. The accent button was styled with
a blue glow and a "Blue = send to the police" comment left over from when the
accent was blue rather than coral (C-44 / UX-148).
"""
from __future__ import annotations

import re
from pathlib import Path

APP_CSS = (
    Path(__file__).resolve().parents[1] / "app" / "static" / "app.css"
).read_text(encoding="utf-8")

ACCENT_BLOCK_RE = re.compile(r"\.btn\.accent, \.btn\.send-all \{(.*?)\n\}", re.S)


def test_the_accent_button_has_no_glow():
    block = ACCENT_BLOCK_RE.search(APP_CSS)
    assert block, "no .btn.accent / .btn.send-all rule"
    assert "box-shadow" not in block.group(1)


def test_the_stale_send_to_police_comment_is_gone():
    assert "Blue = send to the police" not in APP_CSS
