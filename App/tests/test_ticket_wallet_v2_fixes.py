"""Regression cover for the fixes made after the Ticket Wallet v2 review.

The behaviours themselves were exercised with node against the shipped
``ticket.js`` source during review, because this environment has no browser.
These tests lock the contracts that a later edit could silently break, in the
same source-reading style as ``test_ticket_wallet_v2.py``.
"""
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
JS = (APP / "static" / "ticket.js").read_text(encoding="utf-8")
SIGNATURE = (APP / "static" / "signature.js").read_text(encoding="utf-8")
BASE = (APP / "templates" / "guest" / "base.html").read_text(encoding="utf-8")
FORM = (APP / "templates" / "guest" / "form.html").read_text(encoding="utf-8")


def test_the_search_input_is_labelled_without_moving_the_original_label():
    """signature.js resolves a review row's label as label[for="<control id>"],
    so the country label must keep pointing at the real <select>. The search
    input is named through aria-labelledby instead."""
    assert 'label[for="' in SIGNATURE, "signature.js label lookup moved"
    assert 'label.setAttribute("for"' not in JS
    assert 'input.setAttribute("aria-labelledby", label.id)' in JS


def test_the_enhancement_never_takes_over_the_control_id():
    """The real select keeps its id and name; the search input gets its own."""
    assert 'input.id = id + "_search"' in JS
    assert "select.setAttribute(\"tabindex\", \"-1\")" in JS


def test_ticket_js_does_not_re_implement_the_wizard_step_filter():
    """One filter, owned by signature.js. A second copy is what desynced the
    tracker labels from the rail for a Czech guest."""
    assert "data-guest-step-skip-when" not in JS
    assert 'form.querySelectorAll("[data-guest-step]")' in JS


def test_the_pasted_date_is_padded_before_signature_js_regroups_it():
    """signature.js strips non-digits and regroups, so the paste handler must
    hand it a padded day and month instead of the raw text."""
    assert "real.value = text;" not in JS
    assert 'padStart(2, "0")' in JS


def test_country_search_folds_punctuation():
    """The list must match "guinea bissau" against "Guinea-Bissau" and a curly
    apostrophe against a straight one."""
    assert "[^a-z0-9]+" in JS
    # The old range was written with the invisible marks themselves.
    assert "\u0300" not in JS


def test_arrow_up_on_a_closed_list_selects_the_last_option():
    assert "k < 0 ? items.length - 1 : k % items.length" in JS


def test_the_signature_state_listens_to_every_event_signature_js_ends_on():
    """The pad must not stay on "Sign here" when the stroke ends off-canvas."""
    ends = re.search(r'\[([^\]]+)\]\.forEach\(function \(e\) \{ canvas\.addEventListener\(e, end\)', SIGNATURE)
    assert ends, "signature.js end-event list moved"
    ended = set(re.findall(r'"(\w+)"', ends.group(1)))
    state = re.search(r'\[([^\]]*)\]\.forEach\(function \(name\) \{\n      canvas\.addEventListener', JS)
    assert state, "ticket.js sign-state event list moved"
    listened = set(re.findall(r'"(\w+)"', state.group(1)))
    assert ended <= listened, f"missing {sorted(ended - listened)}"


def test_an_invalid_country_marks_the_visible_control_and_says_why():
    """The real select is clipped and aria-hidden, so the visible search input
    must carry the invalid state itself, and a text message with it."""
    from app import i18n

    assert i18n.STRINGS["en"].get("tw_country_required"), "en.tw_country_required"
    assert i18n.STRINGS["cs"].get("tw_country_required"), "cs.tw_country_required"
    assert FORM.count("data-tw-required=") == 2, "both country selects need the message"
    assert 'input.setAttribute("aria-invalid", "true")' in JS
    assert 'input.removeAttribute("aria-invalid")' in JS
    assert 'error.setAttribute("role", "alert")' in JS
    assert 'input.setAttribute("aria-describedby", error.id)' in JS


def test_the_asset_version_is_past_the_version_these_fixes_shipped_in():
    assert "ticket.js?v=20260929a" not in BASE
    assert "ticket.js?v=20260929b" not in BASE
