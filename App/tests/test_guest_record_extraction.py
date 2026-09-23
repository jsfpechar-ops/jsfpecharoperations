"""W5.2: the host form and the guest link read one guest record, not two.

Both entry paths post the same fields to the same table, so a field parsed in
only one of them silently drops data from the other. These tests pin the single
extractor and the deliberate differences that remain between the two callers.
"""
from __future__ import annotations

import asyncio
import base64
import os

import pytest
from starlette.background import BackgroundTasks

from app import alerts, mail_notify, reporting, validation
from app.routes import exports
from app.routes.admin_helpers import (
    guest_form_payload,
    guest_form_raw,
    kept_signature,
    stay_dates_from_form,
)

APARTMENT = {"default_purpose": "03"}

# A real 1x1 PNG: is_valid_signature checks the magic bytes, not just the prefix.
PNG = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()

FORM = {
    "surname": "Nováková",
    "first_name": "Eva",
    "birth_date": "1990-04-02",
    "nationality": "CZ",
    "doc_number": "AB123456",
    "visa_number": "",
    "res_street": "Dlouhá 12",
    "res_city": "Praha",
    "res_country": "CZ",
    "purpose": "03",
    "note": "",
}


def test_host_and_guest_forms_extract_the_same_record():
    host = guest_form_raw(FORM)
    guest = guest_form_raw(FORM, APARTMENT)
    assert host == guest
    assert set(host) == set(validation.GUEST_TEXT_FIELDS)


def test_the_extractor_reads_every_field_the_table_stores():
    raw = guest_form_raw(FORM)
    assert raw["surname"] == "Nováková"
    assert raw["note"] == ""


def test_the_guest_checkbox_becomes_the_inpass_marker_and_the_parent_note():
    guest = guest_form_raw(
        dict(FORM, doc_number="", child_in_passport="1", parent_doc_number="XY987654"),
        APARTMENT,
    )
    assert guest["doc_number"] == validation.INPASS
    assert guest["note"] == validation.INPASS_NOTE_PREFIX + "XY987654"


def test_the_parent_note_keeps_what_the_guest_already_typed():
    guest = guest_form_raw(
        dict(FORM, doc_number="", note="přijel autem", child_in_passport="1",
             parent_doc_number="XY987654"),
        APARTMENT,
    )
    assert guest["note"].endswith("přijel autem")
    assert guest["note"].startswith(validation.INPASS_NOTE_PREFIX)


def test_the_host_form_has_no_checkbox_so_it_is_unaffected():
    host = guest_form_raw(dict(FORM, parent_doc_number="XY987654"))
    assert host["doc_number"] == "AB123456"
    assert host["note"] == ""


def test_the_guest_link_supplies_the_purpose_but_the_host_form_does_not():
    blank = dict(FORM, purpose="")
    assert guest_form_raw(blank, APARTMENT)["purpose"] == "03"
    assert guest_form_raw(blank)["purpose"] == ""


def test_a_guest_with_no_apartment_default_still_gets_a_valid_purpose():
    assert guest_form_raw(dict(FORM, purpose=""), {"default_purpose": ""})[
        "purpose"
    ] == validation.DEFAULT_PURPOSE


def test_the_payload_is_normalised_and_never_clamped():
    payload = guest_form_payload(dict(FORM, surname="  " + "N" * 400), APARTMENT)
    assert payload["surname"] == "N" * 400
    assert payload["doc_number"] == "AB123456"


def test_a_post_with_no_usable_signature_keeps_the_stored_one():
    assert kept_signature("", PNG) == PNG
    assert kept_signature("   ", PNG) == PNG
    assert kept_signature("not-an-image", PNG) == PNG


def test_a_post_with_a_usable_signature_replaces_the_stored_one():
    fresh = PNG[:-4] + "AAAA"
    assert kept_signature(fresh, PNG) == fresh


def test_junk_is_never_filed_when_nothing_valid_is_stored():
    assert kept_signature("not-an-image", "") == "not-an-image"


def test_stay_dates_come_from_the_form_and_fall_back_to_the_booking():
    assert stay_dates_from_form({}, ("2026-01-01", "2026-01-05")) == (
        "2026-01-01",
        "2026-01-05",
    )
    assert stay_dates_from_form(
        {"stay_from": "2026-02-02", "stay_to": "2026-02-09"},
        ("2026-01-01", "2026-01-05"),
    ) == ("2026-02-02", "2026-02-09")
    # The host form passes no fallback: the server fills the dates in.
    assert stay_dates_from_form({}) == (None, None)


# --- item 2: one completeness predicate ----------------------------------


def test_one_signature_predicate_serves_the_host_and_the_guest():
    host = reporting.guest_signature_issue("")
    assert host is not None
    assert host.message == reporting.HOST_SIGNATURE_REQUIRED_MESSAGE

    guest = reporting.guest_signature_issue("", lambda key: f"<{key}>")
    assert guest is not None
    assert guest.message == "<signature_missing>"


def test_the_signature_predicate_accepts_an_imported_record_and_rejects_junk():
    assert reporting.guest_signature_issue(reporting.IMPORTED_SIGNATURE) is None
    assert reporting.guest_signature_issue(PNG) is None
    assert reporting.guest_signature_issue("not-an-image") is not None


def test_the_stored_record_check_appends_the_same_predicate():
    reservation = {"date_from": "2026-01-01", "date_to": "2026-01-05"}
    guest = {
        "stay_from": "",
        "stay_to": "",
        "signature_png": "",
        "surname": "Nováková",
        "first_name": "Eva",
        "birth_date": "1990-04-02",
        "nationality": "CZ",
        "doc_number": "AB123456",
        "visa_number": "",
        "res_street": "Dlouhá 12",
        "res_city": "Praha",
        "res_country": "CZ",
        "purpose": "03",
        "note": "",
    }
    fields = [issue.field for issue in reporting.guest_issues(guest, reservation)]
    assert "signature" in fields
    localised = reporting.guest_issues(guest, reservation, lambda key: f"<{key}>")
    assert any(issue.message == "<signature_missing>" for issue in localised)


# --- item 3: one naive-timestamp convention -------------------------------


def test_a_naive_stored_timestamp_is_read_as_utc():
    assert reporting._as_utc("2026-01-01T10:00:00").isoformat() == "2026-01-01T10:00:00+00:00"
    # An offset-aware value keeps its own offset: the convention only decides
    # how to read a value that has no offset at all.
    assert reporting._as_utc("2026-01-01T10:00:00+02:00").isoformat() == (
        "2026-01-01T10:00:00+02:00"
    )


def test_an_unparseable_timestamp_is_not_guessed_at():
    assert reporting._as_utc("") is None
    assert reporting._as_utc(None) is None


# --- item 4: one _fmt_date ------------------------------------------------


def test_the_date_formatter_is_one_function_everywhere():
    assert alerts._fmt_date is validation.fmt_date
    assert mail_notify._fmt_date is validation.fmt_date
    assert validation.fmt_date("2026-01-05") == "05.01.2026"
    assert validation.fmt_date("not a date") == "not a date"


def test_the_range_formatter_is_one_function_everywhere():
    assert validation.fmt_date_range("2026-01-01", "2026-01-05") == "01.01.2026 \u2013 05.01.2026"
    assert alerts._stay_dates({"date_from": "2026-01-01", "date_to": "2026-01-05"}) == (
        "01.01.2026 \u2013 05.01.2026"
    )


# --- item 7: one bulk-zip helper ------------------------------------------


def test_the_zip_helper_streams_what_the_builder_wrote(tmp_path):
    background = BackgroundTasks()
    seen = {}

    def builder(rows, path):
        seen["path"] = path
        seen["rows"] = rows
        with open(path, "wb") as handle:
            handle.write(b"PK\x05\x06" + b"\x00" * 18)
        return 2

    response = exports._zip_download(background, ["a", "b"], builder, "dorucenky-20260101.zip")
    assert response is not None
    assert response.media_type == "application/zip"
    assert seen["rows"] == ["a", "b"]
    assert os.path.exists(seen["path"])
    # The temp file is deleted after the response is sent, not before.
    asyncio.run(background())
    assert not os.path.exists(seen["path"])


def test_the_zip_helper_reports_an_empty_archive_instead_of_streaming_it():
    def builder(rows, path):
        with open(path, "wb") as handle:
            handle.write(b"PK\x05\x06" + b"\x00" * 18)
        return 0

    assert exports._zip_download(BackgroundTasks(), ["a"], builder, "x.zip") is None


def test_the_zip_helper_cleans_up_when_the_builder_raises():
    caught = {}

    def builder(rows, path):
        caught["path"] = path
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        exports._zip_download(BackgroundTasks(), ["a"], builder, "x.zip")
    assert not os.path.exists(caught["path"])
