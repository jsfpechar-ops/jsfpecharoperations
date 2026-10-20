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


def test_form_actions_wrap_and_mono_breaks():
    assert ".ui-form-actions { display: flex; flex-wrap: wrap;" in CSS
    assert "overflow-wrap: anywhere" in CSS


def test_unroled_stacked_cells_show_labels():
    block = CSS.split("/* 0141-fix-1:", 1)[1]
    assert "td[data-label]:not([data-card])::before { content: attr(data-label);" in block
    # 0189: metric tiles are separate bordered cards with a gap, so there is no
    # shared side line left to remove when they stack; assert that design instead.
    host = (Path(__file__).resolve().parents[1] / "app" / "static" / "host.css").read_text(encoding="utf-8")
    assert ".host-workspace .stay-metrics { background: transparent; border: 0; gap: var(--space-3); }" in host
    assert ".host-workspace .detail-metric { padding: 14px 20px; border: 1px solid var(--line); border-radius: var(--card-radius); }" in host


def test_fee_layout_fixes():
    block = CSS.split("/* 0142-fix-1:", 1)[1]
    assert ".lc-fees td.row-actions { grid-column: 2; grid-row: 1;" in block
    assert ".copyrow textarea { flex: 1 1 14rem;" in block
    assert ".fee-send-marks { flex-direction: column;" in block
    detail = (Path(__file__).resolve().parents[1] / "app" / "templates" / "stay_fee_detail.html").read_text(encoding="utf-8")
    assert '<section class="ui-section" id="payment">' in detail
    assert '<section class="ui-section" id="guests">' in detail
