"""The feed digest ignores request-time DTSTAMP lines and line-ending differences."""

from app import icalsync

BASE = (
    "BEGIN:VCALENDAR\n"
    "BEGIN:VEVENT\n"
    "UID:abc-1\n"
    "DTSTAMP:20260101T000000Z\n"
    "DTSTART:20260110\n"
    "SUMMARY:Booking\n"
    "END:VEVENT\n"
    "END:VCALENDAR\n"
)


def test_dtstamp_only_difference_gives_same_digest():
    restamped = BASE.replace("20260101T000000Z", "20260202T120000Z")
    assert icalsync.body_digest(BASE) == icalsync.body_digest(restamped)


def test_dtstamp_with_parameters_is_ignored():
    a = BASE.replace("DTSTAMP:", "DTSTAMP;TZID=UTC:")
    b = a.replace("20260101T000000Z", "20260909T000000Z")
    assert icalsync.body_digest(a) == icalsync.body_digest(b)


def test_dtstart_change_gives_different_digest():
    changed = BASE.replace("DTSTART:20260110", "DTSTART:20260111")
    assert icalsync.body_digest(BASE) != icalsync.body_digest(changed)


def test_summary_change_gives_different_digest():
    changed = BASE.replace("SUMMARY:Booking", "SUMMARY:Cancelled")
    assert icalsync.body_digest(BASE) != icalsync.body_digest(changed)


def test_crlf_and_lf_give_same_digest():
    crlf = BASE.replace("\n", "\r\n")
    assert icalsync.body_digest(BASE) == icalsync.body_digest(crlf)
