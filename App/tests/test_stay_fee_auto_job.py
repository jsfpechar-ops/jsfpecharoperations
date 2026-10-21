"""0207: the daily stay-fee job seals clean periods, queues the reports and the blocked mails."""
from __future__ import annotations

from datetime import date

import pytest

from app import auth, config, db, stay_fee_auto, stay_fee_filing

PREFIX = "stay-fee-job-"
SIGNATURE = "data:image/png;base64,AAAA"
OCT_1 = date(2026, 10, 1)
NOV_2 = date(2026, 11, 2)


def _cleanup():
    for user in db.query("SELECT id FROM user_account WHERE username LIKE ?", (PREFIX + "%",)):
        owner_id = user["id"]
        db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (owner_id,))
        db.execute(
            "DELETE FROM stay_fee_filing WHERE apartment_id IN "
            "(SELECT id FROM apartment WHERE owner_user_id = ?)",
            (owner_id,),
        )
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN (SELECT id FROM reservation "
            "WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?))",
            (owner_id,),
        )
        db.execute(
            "DELETE FROM reservation WHERE apartment_id IN "
            "(SELECT id FROM apartment WHERE owner_user_id = ?)",
            (owner_id,),
        )
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


@pytest.fixture
def host(monkeypatch):
    db.init_db()
    _cleanup()
    monkeypatch.setattr(config, "MAIL_BACKEND", "console")
    owner_id = auth.create_account(
        f"{PREFIX}owner@example.test", "Job Demo", role="host", username=f"{PREFIX}owner"
    )
    entity_id = db.insert("legal_entity", {
        "name": "Job Demo s.r.o.",
        "owner_user_id": owner_id,
        "contact_email": f"{PREFIX}owner@example.test",
        "created_at": db.utcnow(),
    })
    try:
        yield owner_id, entity_id
    finally:
        _cleanup()


def _property(owner_id, entity_id):
    apartment_id = db.insert("apartment", {
        "internal_name": "Job Flat",
        "owner_user_id": owner_id,
        "legal_entity_id": entity_id,
        "stay_fee_rate_czk": 50,
        "stay_fee_vs": "654321",
        "stay_fee_authority_name": "Městský úřad",
        "stay_fee_authority_databox": "abc1234",
        "stay_fee_council_account": "19-2000781379/0800",
        "stay_fee_council_iban": "CZ3008000000192000781379",
        "created_at": db.utcnow(),
    })
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    now = db.utcnow()
    rid = db.insert("reservation", {
        "apartment_id": apartment_id,
        "uid": "job-1",
        "date_from": "2026-10-10",
        "date_to": "2026-10-14",
        "status": "active",
        "created_at": now,
        "updated_at": now,
    })
    db.insert("guest", {
        "reservation_id": rid,
        "first_name": "Ada",
        "surname": "Guest",
        "birth_date": "01011990",
        "nationality": "DEU",
        "signature_png": SIGNATURE,
        "created_at": now,
        "updated_at": now,
    })
    return apartment


def _queued(owner_id, kind):
    return db.query(
        "SELECT * FROM email_outbox WHERE owner_user_id = ? AND kind = ? ORDER BY id",
        (owner_id, kind),
    )


def _filings(apartment):
    return db.query("SELECT id FROM stay_fee_filing WHERE apartment_id = ?", (apartment["id"],))


def test_due_month_window():
    assert stay_fee_auto.due_month("monthly", date(2026, 11, 1)) is None
    assert stay_fee_auto.due_month("monthly", NOV_2) == OCT_1
    assert stay_fee_auto.due_month("monthly", date(2026, 11, 16)) is None
    assert stay_fee_auto.due_month("quarterly", date(2026, 10, 2)) == date(2026, 7, 1)


def test_clean_period_is_sealed_and_reported_once(host):
    owner_id, entity_id = host
    apartment = _property(owner_id, entity_id)
    stay_fee_auto.run(NOV_2)
    assert len(_filings(apartment)) == 1
    assert len(_queued(owner_id, "stay_fee_report")) == 1
    stay_fee_auto.run(NOV_2)
    assert len(_filings(apartment)) == 1
    assert len(_queued(owner_id, "stay_fee_report")) == 1


def test_switch_off_seals_and_queues_nothing(host):
    owner_id, entity_id = host
    apartment = _property(owner_id, entity_id)
    stay_fee_auto.set_emails_enabled(owner_id, False, actor="t")
    stay_fee_auto.run(NOV_2)
    assert _filings(apartment) == []
    assert _queued(owner_id, "stay_fee_report") == []
    assert _queued(owner_id, "stay_fee_blocked") == []


def test_blocked_period_is_mailed_once_then_sealed_after_fix(host):
    owner_id, entity_id = host
    apartment = _property(owner_id, entity_id)
    db.execute("UPDATE apartment SET stay_fee_vs = NULL WHERE id = ?", (apartment["id"],))
    stay_fee_auto.run(NOV_2)
    assert _filings(apartment) == []
    assert len(_queued(owner_id, "stay_fee_blocked")) == 1
    stay_fee_auto.run(date(2026, 11, 3))
    assert len(_queued(owner_id, "stay_fee_blocked")) == 1
    db.execute("UPDATE apartment SET stay_fee_vs = '654321' WHERE id = ?", (apartment["id"],))
    stay_fee_auto.run(date(2026, 11, 4))
    assert len(_filings(apartment)) == 1
    assert len(_queued(owner_id, "stay_fee_report")) == 1


def test_hand_saved_filing_is_reported_once(host):
    owner_id, entity_id = host
    apartment = _property(owner_id, entity_id)
    stay_fee_filing.save(apartment, OCT_1, rate_czk=50, collected={},
                         issued_on=NOV_2, cadence="monthly")
    stay_fee_auto.run(NOV_2)
    assert len(_filings(apartment)) == 1
    assert len(_queued(owner_id, "stay_fee_report")) == 1
    stay_fee_auto.run(NOV_2)
    assert len(_queued(owner_id, "stay_fee_report")) == 1
