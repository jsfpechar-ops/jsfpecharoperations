"""0234: "No smart lock" is an answer, saved as not_needed, shown as Not needed."""

from __future__ import annotations

from app import property_setup


def _state(**steps):
    return {"steps": steps, "finished": False, "hidden": False}


def test_not_needed_is_a_stored_mark():
    assert "not_needed" in property_setup.MARKS


def test_not_needed_counts_as_answered():
    state = _state(door_lock="not_needed")
    apartment = {"lock_provider": None, "stay_fee_rate_czk": 0}
    facts = {"feeds": 0, "stays": 0, "guests_registered": False, "report_complete": False}
    assert property_setup.step_status("door_lock", state, apartment, facts) == "not_needed"


def test_the_summary_reads_not_needed_in_every_language():
    from app import host_i18n

    assert host_i18n.STRINGS["en"]["wizard.summary.status.not_needed"] == "Not needed"
    assert host_i18n.STRINGS["cs"]["wizard.summary.status.not_needed"] == "Není potřeba"
