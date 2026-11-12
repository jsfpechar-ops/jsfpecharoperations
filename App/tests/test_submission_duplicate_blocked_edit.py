"""Brief 1121: an edit that changes nothing reported keeps a duplicate block.

A guest the register refused as a duplicate (submit_state 'blocked' and
last_errors naming the duplicate) cannot be accepted on a second try, so
collect_sendable skips it even on a deliberate resend. Before 1121 any host or
guest edit set 'pending', cleared last_errors and reset submit_attempts, which
removed that skip and let the next sweep send the record again. An edit to a
field reported to the police (reporting.filed_record_changed) still resets, and
a guest blocked for any other reason behaves as before.
"""
from __future__ import annotations

from app import db, reporting
from tests.test_guest_edit_until_filed import _guest_on_device, _resave, stay  # noqa: F401
from tests.test_submission_retry_cap import SIGNATURE, _cleanup, _seed, host  # noqa: F401

DUPLICATE = "150: Duplicate record"
NOT_DUPLICATE = "104: Invalid date of birth"


def _host_form(**overrides):
    # The seeded guest's reported fields as the host form posts them. The seed
    # stores them already normalised, so posting them unchanged changes no
    # field guest_payload() reports.
    data = {
        "surname": "SMITH",
        "first_name": "JOHN",
        "birth_date": "01.01.1990",
        "nationality": "GBR",
        "doc_number": "P1234567",
        "res_street": "Street 1",
        "res_city": "London",
        "res_country": "GBR",
        "purpose": "10",
        "signature": SIGNATURE,
    }
    data.update(overrides)
    return data


def _blocked_host_guest(token, last_errors):
    apartment, _reservation, guest_id = _seed(token, surname="SMITH", auto=True)
    db.update(
        "guest",
        guest_id,
        {
            "first_name": "JOHN",
            "submit_state": reporting.BLOCKED,
            "last_errors": last_errors,
            "submit_attempts": 1,
        },
    )
    return apartment, guest_id


def _blocked_guest_on_device(token, stay_id, last_errors):
    browser, row = _guest_on_device(token, stay_id)
    db.update(
        "guest",
        row["id"],
        {
            "submit_state": reporting.BLOCKED,
            "last_errors": last_errors,
            "submit_attempts": 1,
        },
    )
    return browser, row["id"]


def _row(guest_id):
    return db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))


def _sendable_ids(apartment_id):
    # The widest gate there is: a host resend, past the schedule and the cap.
    pairs = reporting.collect_sendable(
        apartment_id, ignore_automation=True, allow_resend=True
    )
    return [guest["id"] for guest, _reservation in pairs]


def _assert_still_blocked(guest_id):
    after = _row(guest_id)
    assert after["submit_state"] == reporting.BLOCKED
    assert after["last_errors"] == DUPLICATE
    assert after["submit_attempts"] == 1


def _assert_reset(guest_id):
    after = _row(guest_id)
    assert after["submit_state"] == reporting.PENDING
    assert after["last_errors"] is None
    assert after["submit_attempts"] == 0


# (a) host edit of a non-reported field on a duplicate-blocked guest
def test_host_edit_of_an_unreported_field_keeps_the_duplicate_block(host):
    apartment, guest_id = _blocked_host_guest("tok-1121-a", DUPLICATE)
    try:
        saved = host.post(
            f"/guests/{guest_id}", data=_host_form(doc_type="pas"), follow_redirects=False
        )
        assert saved.status_code == 303
        assert "err=" not in saved.headers["location"]
        assert _row(guest_id)["doc_type"] == "pas", "the other columns are still saved"
        _assert_still_blocked(guest_id)
        assert guest_id not in _sendable_ids(apartment["id"])
    finally:
        _cleanup(apartment["id"])


# (c) host edit of a reported field still resets, as today
def test_host_edit_of_a_reported_field_still_resets_a_duplicate_block(host):
    apartment, guest_id = _blocked_host_guest("tok-1121-c", DUPLICATE)
    try:
        saved = host.post(
            f"/guests/{guest_id}",
            data=_host_form(doc_number="P7654321"),
            follow_redirects=False,
        )
        assert saved.status_code == 303
        _assert_reset(guest_id)
        assert guest_id in _sendable_ids(apartment["id"])
    finally:
        _cleanup(apartment["id"])


# (d) host edit of a guest blocked for another reason: unchanged behaviour
def test_host_edit_of_a_guest_blocked_for_another_reason_still_resets(host):
    apartment, guest_id = _blocked_host_guest("tok-1121-d", NOT_DUPLICATE)
    try:
        saved = host.post(
            f"/guests/{guest_id}", data=_host_form(doc_type="pas"), follow_redirects=False
        )
        assert saved.status_code == 303
        _assert_reset(guest_id)
        assert guest_id in _sendable_ids(apartment["id"])
    finally:
        _cleanup(apartment["id"])


# (b) guest form save that changes no reported field
def test_guest_resave_without_a_reported_change_keeps_the_duplicate_block(stay):
    token, stay_id = stay
    browser, guest_id = _blocked_guest_on_device(token, stay_id, DUPLICATE)
    assert _resave(browser, token, stay_id, guest_id).status_code == 303
    _assert_still_blocked(guest_id)
    apartment_id = db.query_one(
        "SELECT apartment_id FROM reservation WHERE id = ?", (stay_id,)
    )["apartment_id"]
    assert guest_id not in _sendable_ids(apartment_id)


# (c) guest form save that changes a reported field still resets
def test_guest_resave_with_a_reported_change_still_resets_a_duplicate_block(stay):
    token, stay_id = stay
    browser, guest_id = _blocked_guest_on_device(token, stay_id, DUPLICATE)
    assert _resave(browser, token, stay_id, guest_id, surname="Jones").status_code == 303
    _assert_reset(guest_id)


# (d) guest form save of a guest blocked for another reason: unchanged
def test_guest_resave_of_a_guest_blocked_for_another_reason_still_resets(stay):
    token, stay_id = stay
    browser, guest_id = _blocked_guest_on_device(token, stay_id, NOT_DUPLICATE)
    assert _resave(browser, token, stay_id, guest_id).status_code == 303
    _assert_reset(guest_id)
