"""Contracts for guest-enhancements.js on the Arrival lane shell."""
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
JS = (APP / "static" / "guest-enhancements.js").read_text(encoding="utf-8")
BASE = (APP / "templates" / "guest" / "base.html").read_text(encoding="utf-8")
FORM = (APP / "templates" / "guest" / "form.html").read_text(encoding="utf-8")
CLAIM = (APP / "templates" / "guest" / "claim.html").read_text(encoding="utf-8")


def test_the_live_shell_loads_guest_enhancements():
    assert "guest-enhancements.js?v=20261003a" in BASE
    assert "ticket.js" not in BASE


def test_party_fields_use_the_stepper_hook():
    assert CLAIM.count("data-guest-stepper") >= 1
    assert 'className = "g-stepper"' in JS
    assert 'className = "g-step-btn"' in JS


def test_pin_cells_paint_six_boxes():
    assert 'className = "g-pin-cells"' in JS
    assert "data-guest-pin-cells" in JS


def test_country_search_keeps_the_real_select_as_the_control():
    assert 'input.id = id + "_search"' in JS
    assert 'input.setAttribute("aria-labelledby", label.id)' in JS
    assert FORM.count("data-guest-required=") == 2
    assert 'select.classList.add("g-vh")' in JS
    assert "[^a-z0-9]+" in JS


def test_invalid_country_marks_the_visible_search_input():
    assert 'input.setAttribute("aria-invalid", "true")' in JS
    assert 'error.setAttribute("role", "alert")' in JS


def test_arrow_up_on_a_closed_list_selects_the_last_option():
    assert "k < 0 ? items.length - 1 : k % items.length" in JS
