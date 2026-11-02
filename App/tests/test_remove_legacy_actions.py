"""0137: legacy host buttons are gone from the templates; their routes still answer."""
from __future__ import annotations

from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"


def _t(name):
    return (TEMPLATES / name).read_text(encoding="utf-8")


def test_update_calendars_lives_only_in_the_property_calendar_section():
    assert "sync_calendars_button(" not in _t("dashboard.html")
    assert "sync_calendars_button(" not in _t("apartments.html")
    assert _t("_property_calendars.html").count("sync_calendars_button(") == 1


def test_the_stays_list_has_no_row_send_and_send_all_is_manual_only():
    text = _t("reservations.html")
    assert "row_reporting_actions" not in text
    # v2 header: send-all is a ghost button shown only in manual send mode
    assert '{% if manual_send %}<form method="post" action="/reservations/submit-ready"' in text


def test_the_stay_detail_keeps_one_send_and_moves_the_rest_into_the_menu():
    text = _t("reservation_detail.html")
    assert text.count('/submit" class="inline"') == 1
    assert text.count('/submit" class="row-menu-form"') == 1
    assert "remove-empty-slot" not in text
    assert text.count("delete-demo") == 1  # item 7 kept: shows only for the demo stay
    # v2: the header row menu replaced the old "Now" panel menu
    start = text.index("{{ row_menu_begin() }}")
    menu = text[start:text.index("row_menu_end()", start)]
    assert "reopen-guest" in menu and "release-claim" not in menu
    assert text.count("data-release-claim") == 1  # 0380: a visible button in the Guests section
    assert "filed-by-hand" in text  # Keep: the manual-filing fallback
    assert text.count("{{ stay_cta() }}") == 1  # v2: one primary action (send, fix or receipt), placed by CSS


def test_code_list_refresh_is_gone_and_test_connection_and_clear_demo_stay():
    assert "refresh-codelists" not in _t("_property_editor.html")
    assert "test-connection" in _t("_property_editor.html")  # item 10: kept in UbyPort setup
    assert _t("dashboard.html").count("/demo/reset") == 1  # item 7 kept, once
