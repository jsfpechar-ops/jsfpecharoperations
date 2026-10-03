"""WP22: retention periods match the owner's legal decision (legal positions, section 4).

Every test freezes the date it runs on by passing ``today`` or ``now``, so the
outcome does not depend on the day the suite runs.

- passport/ID photos: gone on verification, else 7 days after check-in, and
  never later than 30 days after upload;
- guest records and stay-fee evidence: six years from the end of the stay,
  deleted on 31 January of the year after the six years end;
- raw UbyPort XML: 90 days, the receipt row without personal data stays;
- invoices: 10 years from the end of the calendar year of issue;
- every deletion run writes an audit line with class, count and cutoff.
"""
from __future__ import annotations

import base64
import json
from datetime import date, datetime, timedelta, timezone

import pytest

from app import config, db, housebook, invoices, passport_photos, reporting, retention

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGMAAQAABQAB"
    "DQottAAAAABJRU5ErkJggg=="
)
PREFIX = "wp22-"


@pytest.fixture(autouse=True)
def _cleanup():
    db.init_db()
    _purge()
    yield
    _purge()


def _purge():
    db.init_db()
    owners = [r["id"] for r in db.query(
        "SELECT id FROM user_account WHERE username LIKE ?", (PREFIX + "%",)
    )]
    for owner in owners:
        for row in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (owner,)):
            for g in db.query(
                "SELECT g.id AS id FROM guest g JOIN reservation r ON r.id = g.reservation_id "
                "WHERE r.apartment_id = ?",
                (row["id"],),
            ):
                passport_photos.delete_photo(int(g["id"]))
            db.execute(
                "DELETE FROM guest WHERE reservation_id IN"
                " (SELECT id FROM reservation WHERE apartment_id = ?)",
                (row["id"],),
            )
            db.execute("DELETE FROM submission WHERE apartment_id = ?", (row["id"],))
            db.execute("DELETE FROM reservation WHERE apartment_id = ?", (row["id"],))
            db.execute("DELETE FROM stay_fee_adjustment WHERE apartment_id = ?", (row["id"],))
            db.execute("DELETE FROM stay_fee_filing WHERE apartment_id = ?", (row["id"],))
        db.execute(
            "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '1') "
            "ON CONFLICT(key) DO UPDATE SET value = '1'"
        )
        db.execute(
            "DELETE FROM invoice_item WHERE invoice_id IN"
            " (SELECT id FROM invoice WHERE owner_user_id = ?)",
            (owner,),
        )
        db.execute(
            "DELETE FROM invoice WHERE owner_user_id = ? AND corrects_invoice_id IS NOT NULL",
            (owner,),
        )
        db.execute("DELETE FROM invoice WHERE owner_user_id = ?", (owner,))
        db.execute("UPDATE settings SET value = '' WHERE key = 'invoice_purge_unlock'")
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner,))
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (owner,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner,))
        db.execute("DELETE FROM user_account WHERE id = ?", (owner,))
    db.execute("DELETE FROM settings WHERE key = 'retention_last_run'")


_counter = 0


def _owner() -> int:
    global _counter
    _counter += 1
    return db.insert(
        "user_account",
        {
            "username": f"{PREFIX}{_counter}",
            "display_name": "Test host",
            "password_hash": "x",
            "role": "host",
            "created_at": db.utcnow(),
        },
    )


def _apartment(owner: int) -> tuple[int, int]:
    global _counter
    _counter += 1
    now = db.utcnow()
    entity_id = db.insert(
        "legal_entity",
        {"name": "WP22 Test", "seat": "Praha", "created_at": now, "owner_user_id": owner},
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": owner,
            "internal_name": "Flat",
            "permalink_token": f"{PREFIX}tok-{_counter}",
            "automation_mode": "manual",
            "default_purpose": "10",
            "active": 1,
            "created_at": now,
        },
    )
    return entity_id, apartment_id


def _guest(
    owner: int,
    *,
    check_in: date,
    check_out: date,
    photo_uploaded: date | None = None,
    verified: bool = False,
) -> int:
    global _counter
    _counter += 1
    _entity, apartment_id = _apartment(owner)
    now = db.utcnow()
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": f"{PREFIX}stay-{_counter}",
            "date_from": check_in.isoformat(),
            "date_to": check_out.isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    guest_id = db.insert(
        "guest",
        {
            "reservation_id": reservation_id,
            "surname": "Example",
            "first_name": "Guest",
            "nationality": "GBR",
            "purpose": "10",
            "stay_from": check_in.isoformat(),
            "stay_to": check_out.isoformat(),
            "entered_by": "guest",
            "identity_verified_at": now if verified else None,
            "passport_photo_at": (
                datetime.combine(photo_uploaded, datetime.min.time(), timezone.utc).isoformat()
                if photo_uploaded
                else None
            ),
            "created_at": now,
            "updated_at": now,
        },
    )
    if photo_uploaded:
        passport_photos.save_photo(guest_id, PNG_BYTES, "image/png")
    return guest_id


def _retention_lines(data_class: str) -> list[dict]:
    rows = db.query(
        "SELECT detail FROM audit WHERE action = 'retention_delete' ORDER BY id DESC LIMIT 200"
    )
    found = [json.loads(r["detail"]) for r in rows]
    return [d for d in found if d["class"] == data_class]


# --- passport and ID photos -----------------------------------------------

TODAY = date(2026, 6, 10)


def test_an_unverified_photo_goes_seven_days_after_check_in():
    owner = _owner()
    due = _guest(
        owner, check_in=TODAY - timedelta(days=7), check_out=TODAY + timedelta(days=3),
        photo_uploaded=TODAY - timedelta(days=8),
    )
    kept = _guest(
        owner, check_in=TODAY - timedelta(days=6), check_out=TODAY + timedelta(days=3),
        photo_uploaded=TODAY - timedelta(days=8),
    )

    removed = passport_photos.purge_stale(owner_user_id=owner, today=TODAY)

    assert removed == 1
    assert not passport_photos.has_photo(due)
    assert passport_photos.has_photo(kept), "six days after check-in is still inside the window"
    assert db.query_one("SELECT passport_photo_at FROM guest WHERE id = ?", (due,))[
        "passport_photo_at"
    ] is None
    assert db.query_one("SELECT id FROM guest WHERE id = ?", (due,)), "the record itself stays"


def test_no_photo_lives_past_thirty_days_after_upload_even_before_check_in():
    owner = _owner()
    # Uploaded long before a far-off stay: the check-in rule alone would keep it.
    capped = _guest(
        owner, check_in=TODAY + timedelta(days=20), check_out=TODAY + timedelta(days=25),
        photo_uploaded=TODAY - timedelta(days=30),
    )
    younger = _guest(
        owner, check_in=TODAY + timedelta(days=20), check_out=TODAY + timedelta(days=25),
        photo_uploaded=TODAY - timedelta(days=29),
    )

    passport_photos.purge_stale(owner_user_id=owner, today=TODAY)

    assert not passport_photos.has_photo(capped)
    assert passport_photos.has_photo(younger)


def test_a_verified_guest_keeps_no_photo_whatever_set_the_flag():
    """The Verify route deletes at once; a host edit also sets the flag, so the sweep backs it up."""
    owner = _owner()
    verified = _guest(
        owner, check_in=TODAY + timedelta(days=2), check_out=TODAY + timedelta(days=5),
        photo_uploaded=TODAY, verified=True,
    )

    passport_photos.purge_stale(owner_user_id=owner, today=TODAY)

    assert not passport_photos.has_photo(verified)


def test_the_photo_sweep_writes_its_audit_line_even_with_nothing_to_do():
    owner = _owner()
    passport_photos.purge_stale(owner_user_id=owner, today=TODAY)

    line = _retention_lines("passport_photos")[0]
    assert line["count"] == 0
    assert line["owner_user_id"] == owner
    assert "2026-06-03" in line["cutoff"]  # check-in cutoff, 7 days
    assert "2026-05-11" in line["cutoff"]  # upload cutoff, 30 days


# --- guest records and stay-fee evidence -----------------------------------


@pytest.mark.parametrize(
    "today, cutoff",
    [
        (date(2026, 12, 31), date(2020, 1, 1)),
        (date(2027, 1, 30), date(2020, 1, 1)),
        (date(2027, 1, 31), date(2021, 1, 1)),
        (date(2027, 6, 1), date(2021, 1, 1)),
        (date(2028, 2, 29), date(2022, 1, 1)),
    ],
)
def test_the_guest_cutoff_moves_once_a_year_on_31_january(today, cutoff):
    assert housebook.retention_cutoff(today) == cutoff


def test_a_guest_record_goes_on_31_january_after_its_six_years():
    owner = _owner()
    # Stay ended 31 Dec 2020: six years end 31 Dec 2026, deletion 31 Jan 2027.
    ending_2020 = _guest(owner, check_in=date(2020, 12, 28), check_out=date(2020, 12, 31))
    ending_2021 = _guest(owner, check_in=date(2020, 12, 30), check_out=date(2021, 1, 2))

    assert housebook.purge_expired(date(2027, 1, 30), owner_user_id=owner) == 0
    assert db.query_one("SELECT id FROM guest WHERE id = ?", (ending_2020,))

    assert housebook.purge_expired(date(2027, 1, 31), owner_user_id=owner) == 1
    assert db.query_one("SELECT id FROM guest WHERE id = ?", (ending_2020,)) is None
    assert db.query_one("SELECT id FROM guest WHERE id = ?", (ending_2021,))


def _filing(apartment_id: int, period_key: str) -> int:
    return db.insert(
        "stay_fee_filing",
        {
            "apartment_id": apartment_id,
            "period_key": period_key,
            "cadence": "quarterly" if "Q" in period_key else "monthly",
            "rate_czk": 50,
            "liable_days": 1,
            "exempt_days": 0,
            "total_due_czk": 50,
            "total_collected_czk": 50,
            "created_at": db.utcnow(),
        },
    )


def test_stay_fee_evidence_follows_the_same_31_january_rule(monkeypatch):
    monkeypatch.setattr(config, "RETENTION_AUTOPURGE", True)
    owner = _owner()
    _entity, apartment_id = _apartment(owner)
    old_filing = _filing(apartment_id, "2020-Q4")
    db.insert(
        "stay_fee_adjustment",
        {
            "apartment_id": apartment_id,
            "period_key": "2020-Q4",
            "direction": "add",
            "mode": "bed_days",
            "bed_days": 1,
            "reason_enc": "x",
            "created_at": db.utcnow(),
            "filing_id": old_filing,
        },
    )
    newer_filing = _filing(apartment_id, "2021-01")

    before = retention.run(date(2027, 1, 30), dry_run=False, owner_user_id=owner)
    assert before["counts"]["stay_fee_records"] == 0
    assert db.query_one("SELECT id FROM stay_fee_filing WHERE id = ?", (old_filing,))

    on_the_day = retention.run(date(2027, 1, 31), dry_run=False, owner_user_id=owner)
    assert on_the_day["counts"]["stay_fee_records"] == 2  # the filing and its adjustment
    assert db.query_one("SELECT id FROM stay_fee_filing WHERE id = ?", (old_filing,)) is None
    assert db.query_one(
        "SELECT id FROM stay_fee_adjustment WHERE apartment_id = ?", (apartment_id,)
    ) is None
    assert db.query_one("SELECT id FROM stay_fee_filing WHERE id = ?", (newer_filing,))


def test_a_dry_run_counts_stay_fee_evidence_and_deletes_nothing():
    owner = _owner()
    _entity, apartment_id = _apartment(owner)
    filing = _filing(apartment_id, "2019-12")

    summary = retention.run(date(2027, 2, 1), dry_run=True, owner_user_id=owner)

    assert summary["counts"]["stay_fee_records"] == 1
    assert db.query_one("SELECT id FROM stay_fee_filing WHERE id = ?", (filing,))


# --- raw UbyPort XML and the receipt row ------------------------------------

NOW = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)


def _submission(owner: int, created: datetime) -> int:
    _entity, apartment_id = _apartment(owner)
    stamp = created.replace(microsecond=0).isoformat()
    return db.insert(
        "submission",
        {
            "apartment_id": apartment_id,
            "created_at": stamp,
            "finished_at": stamp,
            "mode": "manual",
            "state": "ok",
            "guest_ids": "[1]",
            "pseudo_stamp": "REF-0001",
            "receipt_pdf": base64.b64encode(b"%PDF-1.4 receipt").decode(),
            "request_xml": "<request>example</request>",
            "response_xml": "<response>example</response>",
        },
    )


def test_raw_xml_goes_after_ninety_days_and_the_receipt_row_stays():
    owner = _owner()
    old = _submission(owner, NOW - timedelta(days=91))
    recent = _submission(owner, NOW - timedelta(days=89))

    assert reporting.purge_submission_payloads(owner_user_id=owner, now=NOW) == 1

    row = db.query_one("SELECT * FROM submission WHERE id = ?", (old,))
    assert row["request_xml"] is None and row["response_xml"] is None
    # The receipt: stay link, time, result, reference and the Dorucenka.
    assert row["apartment_id"] and row["guest_ids"] == "[1]"
    assert row["created_at"] and row["state"] == "ok"
    assert row["pseudo_stamp"] == "REF-0001" and row["receipt_pdf"]
    assert db.query_one("SELECT request_xml FROM submission WHERE id = ?", (recent,))[
        "request_xml"
    ]

    line = _retention_lines("ubyport_xml")[0]
    assert line["count"] == 1
    assert line["cutoff"] == (NOW - timedelta(days=90)).isoformat()


# --- invoices ----------------------------------------------------------------


def _invoice(owner: int, entity_id: int, issue: date, n: int, corrects: int | None = None) -> int:
    now = db.utcnow()
    return db.insert(
        "invoice",
        {
            "legal_entity_id": entity_id, "owner_user_id": owner,
            "kind": "corrective" if corrects else "invoice", "corrects_invoice_id": corrects,
            "seq_year": issue.year, "seq_no": n, "number": f"{issue.year}-{n:04d}",
            "vs": f"{issue.year}{n:04d}", "lang": "cs", "vat_status": "non_payer",
            "issue_date": issue.isoformat(), "seller_name": "E", "seller_seat": "Praha",
            "buyer_name": "B", "total_haler": 100, "created_at": now, "issued_at": now,
        },
    )


def test_an_invoice_is_kept_ten_years_from_the_end_of_its_year():
    owner = _owner()
    entity_id, _apartment_id = _apartment(owner)
    last_day = _invoice(owner, entity_id, date(2015, 12, 31), 1)
    next_year = _invoice(owner, entity_id, date(2016, 1, 1), 2)

    assert invoices.purge_expired(date(2025, 12, 31), owner_user_id=owner) == 0
    assert invoices.purge_expired(date(2026, 1, 1), owner_user_id=owner) == 1
    assert db.query_one("SELECT id FROM invoice WHERE id = ?", (last_day,)) is None
    assert db.query_one("SELECT id FROM invoice WHERE id = ?", (next_year,))


def test_the_nightly_run_reaches_every_workspaces_invoices():
    """The global run used to match only invoices with no owner, so no host invoice ever aged out."""
    owner = _owner()
    entity_id, _apartment_id = _apartment(owner)
    old = _invoice(owner, entity_id, date(2015, 6, 1), 1)

    assert old in invoices.expired_ids(date(2026, 1, 1), owner_user_id=None)


def test_an_original_stays_while_its_correction_is_inside_ten_years():
    owner = _owner()
    entity_id, _apartment_id = _apartment(owner)
    original = _invoice(owner, entity_id, date(2015, 11, 1), 1)
    correction = _invoice(owner, entity_id, date(2017, 2, 1), 1, corrects=original)

    assert invoices.purge_expired(date(2026, 1, 1), owner_user_id=owner) == 0
    assert db.query_one("SELECT id FROM invoice WHERE id = ?", (original,))

    assert invoices.purge_expired(date(2028, 1, 1), owner_user_id=owner) == 2
    assert db.query_one("SELECT id FROM invoice WHERE id = ?", (correction,)) is None


# --- audit line per class ----------------------------------------------------


def test_every_step_of_the_run_writes_class_count_and_cutoff():
    owner = _owner()
    _guest(owner, check_in=date(2019, 5, 1), check_out=date(2019, 5, 3))

    summary = retention.run(date(2027, 2, 1), dry_run=True, owner_user_id=owner)

    for name, _step in retention.STEPS:
        line = _retention_lines(name)[0]
        assert line["count"] == summary["counts"][name]
        assert line["cutoff"], f"{name} has no cutoff in its audit line"
        assert line["dry_run"] is True
        assert line["owner_user_id"] == owner
    guests = _retention_lines("guests")[0]
    assert guests["count"] == 1
    assert guests["cutoff"] == "stay ended before 2021-01-01"
    assert _retention_lines("invoices")[0]["cutoff"] == "issued before 2017-01-01"


# --- texts that state the periods ---------------------------------------------


def test_the_host_dpa_states_the_periods_in_both_languages():
    from app import dpa_i18n

    en = dpa_i18n.DPA_STRINGS["en"]["dpa.s15_body"]
    cs = dpa_i18n.DPA_STRINGS["cs"]["dpa.s15_body"]
    assert "6 years after the end of the stay" in en
    assert "within 7 days after check-in and never later than 30 days after upload" in en
    assert "deleted after 90 days" in en
    assert "6 let od konce pobytu" in cs
    assert "do 7 dnů od příjezdu, nejpozději 30 dní od nahrání" in cs
    assert "mažou po 90 dnech" in cs


def test_the_guest_notice_states_the_periods_in_both_languages():
    from app import i18n

    for lang, stay_rule, photo_rule in (
        ("en", "six years after the end of", "never later than 30 days after upload"),
        ("cs", "šest let od konce pobytu", "nejpozději 30 dní od nahrání"),
    ):
        strings = i18n.STRINGS[lang]
        assert stay_rule in strings["legal_notice_retention_body"]
        assert stay_rule in strings["privacy_retention_body"].replace("\n", " ")
        assert photo_rule in strings["legal_notice_passport_body"]
        assert photo_rule in strings["privacy_passport_photo_body"]
        assert "posledního zápisu" not in strings["legal_notice_retention_body"]
