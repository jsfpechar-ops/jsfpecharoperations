"""0154: form actions stay visible on phone; the alert stack is one quiet card."""
from __future__ import annotations

import re
from pathlib import Path

CSS = (Path(__file__).resolve().parents[1] / "app" / "static" / "host2.css").read_text(encoding="utf-8")


def test_form_actions_are_never_hidden_on_phone():
    assert not re.search(r"\.ui-form-actions\s*\{\s*display:\s*none", CSS)


def test_alert_stack_is_one_card_without_shadows():
    block = CSS.split("/* 0154:", 1)[1]
    assert ".notification-stack { gap: 0;" in block
    assert "box-shadow: none" in block
