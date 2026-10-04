"""Ticket Wallet v2 (docs/plans/PLAN_TICKET_WALLET_V2.md): the skin's
contract with the templates, the enhancement script and the dictionary."""
import re
from pathlib import Path

from app import i18n

APP = Path(__file__).resolve().parents[1] / "app"
ARCHIVE = APP / "static" / "archive" / "ticket-wallet"
TW_TEMPLATES = APP / "templates" / "guest" / "archive" / "ticket-wallet"
CSS = (ARCHIVE / "guest-ticket.css").read_text(encoding="utf-8")
JS = (ARCHIVE / "ticket.js").read_text(encoding="utf-8")
FORM = (TW_TEMPLATES / "form.html").read_text(encoding="utf-8")
CLAIM = (TW_TEMPLATES / "claim.html").read_text(encoding="utf-8")
BASE = (TW_TEMPLATES / "base.html").read_text(encoding="utf-8")
ACTIVE_BASE = (APP / "templates" / "guest" / "base.html").read_text(encoding="utf-8")

NEW_KEYS = [
    "tw_email_short", "tw_email_more", "tw_step_details", "tw_step_document",
    "tw_step_home", "tw_step_photo", "tw_step_sign", "tw_step_check",
    "tw_dob_day", "tw_dob_month", "tw_dob_year", "tw_country_search",
    "tw_country_none", "tw_purpose_other", "tw_sign_here", "tw_signed",
]
# WP17 (review 3.E item 14) cut "Keep this page" from the done screen: it
# contradicted "You can close this page" a few lines above it.
CUT_KEYS = ["tw_done_keep"]


def test_every_new_key_exists_in_both_languages():
    for key in NEW_KEYS:
        assert i18n.STRINGS["en"].get(key), f"en.{key}"
        assert i18n.STRINGS["cs"].get(key), f"cs.{key}"


def test_cut_keys_are_gone_from_both_languages_and_the_templates():
    stay = (APP / "templates" / "guest" / "stay.html").read_text(encoding="utf-8")
    for key in CUT_KEYS:
        assert key not in i18n.STRINGS["en"], key
        assert key not in i18n.STRINGS["cs"], key
        assert key not in stay, key


def test_every_enhancement_is_registered_in_start():
    start = JS[JS.index("function start()"):]
    for name in ("initPinCells", "initDobCells", "initCountryCombos",
                 "initPurposeChips", "initTrackerLabels", "initSignState"):
        assert f"function {name}(" in JS, name
        assert f"{name}();" in start, f"{name} is defined but never called"


def test_the_rail_is_no_longer_hidden():
    assert ".tw .g-checkin-rail { display: none !important; }" not in CSS


def test_v2_sections_come_before_the_motion_section():
    """Section 17's reduced-motion rule must be last so it covers v2."""
    assert CSS.index("/* 18. App bar v2") < CSS.index("/* 17. Motion")


def test_every_form_step_has_a_short_label():
    # "data-guest-step-skip-when" must not count as a step of its own.
    steps = re.findall(r"data-guest-step(?=[\s>])", FORM)
    assert steps and len(steps) == FORM.count("data-tw-short=")


def test_the_real_controls_keep_their_names():
    for name in ('name="birth_date"', 'name="nationality"', 'name="res_country"',
                 'name="purpose"', 'name="signature"', 'id="sig-canvas"'):
        assert name in FORM, name


def test_the_full_email_text_is_still_on_the_claim_page():
    assert "t('claim_email_help')" in CLAIM
    assert "t('claim_cookie_help')" in CLAIM
    assert 'class="tw-more"' in CLAIM


def test_assets_are_cache_busted_past_v1():
    assert "guest-ticket.css?v=20260929a" not in BASE
    assert "ticket.js?v=20260929a" not in BASE


def test_the_live_guest_shell_does_not_load_ticket_wallet():
    """Arrival lane is active; TW assets stay in static/archive/ticket-wallet/."""
    assert "guest-ticket.css" not in ACTIVE_BASE
    assert "ticket.js" not in ACTIVE_BASE
    assert 'class="tw"' not in ACTIVE_BASE


def test_no_dark_mode_sneaks_in():
    assert "prefers-color-scheme" not in CSS
