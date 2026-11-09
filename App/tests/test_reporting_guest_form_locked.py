"""Unit tests for reporting.guest_form_locked (owner decision 2026-11-09, PR #835).

Integration flows live in test_guest_edit_until_filed.py; these pin the narrow
rule so a complete signed form does not lock again by accident.
"""
from __future__ import annotations

from app import reporting

SIG = "data:image/png;base64,AAAA"


def test_filed_with_ubport_is_locked():
    guest = {"submit_state": reporting.SENT, "signature_png": SIG}
    assert reporting.guest_form_locked(guest, {})


def test_restricted_record_is_locked():
    guest = {"submit_state": "ready", "restricted_at": "2026-11-09T12:00:00+00:00"}
    assert reporting.guest_form_locked(guest, {})


def test_complete_signed_but_not_filed_stays_editable():
    """Regression: signature + complete used to lock; only SENT and restricted do now."""
    guest = {"submit_state": "ready", "signature_png": SIG, "restricted_at": None}
    assert not reporting.guest_form_locked(guest, {})


def test_empty_draft_is_not_locked():
    guest = {"submit_state": None, "signature_png": "", "restricted_at": None}
    assert not reporting.guest_form_locked(guest, {})
