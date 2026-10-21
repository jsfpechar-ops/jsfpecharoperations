"""0206: the shared stay-fee check, the confirm step and the two stay-fee mails."""
from __future__ import annotations

import json
from datetime import date

import pytest

from app import auth, config, db, host_i18n, mail, mail_notify, stay_fee, stay_fee_auto, stay_fee_filing

PREFIX = "stay-fee-auto-"
SIGNATURE = "data:image/png;base64,AAAA"


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
        f"{PREFIX}owner@example.test", "Auto Demo", role="host", username=f"{PREFIX}owner"
    )
    entity_id = db.insert("legal_entity", {
        "name": "Auto Demo s.r.o.",
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
        "internal_name": "Auto Flat",
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
    return db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))


def _stay(apartment_id):
    now = db.utcnow()
    rid = db.insert("reservation", {
        "apartment_id": apartment_id,
        "uid": "auto-1",
        "date_from": "2026-08-10",
        "date_to": "2026-08-14",
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


def _queued(owner_id, kind):
    return db.query(
        "SELECT * FROM email_outbox WHERE owner_user_id = ? AND kind = ? ORDER BY id",
        (owner_id, kind),
    )


def _finished_property(owner_id, entity_id):
    apartment = _property(owner_id, entity_id)
    _stay(apartment["id"])
    return apartment


AUG = date(2026, 8, 1)
AUG_TODAY = date(2026, 9, 30)


def test_check_clean_finished_month_has_no_issues(host):
    owner_id, entity_id = host
    apartment = _finished_property(owner_id, entity_id)
    checked = stay_fee_auto.check(apartment, AUG, AUG_TODAY)
    assert checked["issues"] == []
    assert checked["key"] == stay_fee_filing.period_key(
        checked["group"]["cadence"], checked["group"]["first"]
    )


def test_check_running_month_is_blocked(host):
    owner_id, entity_id = host
    apartment = _finished_property(owner_id, entity_id)
    checked = stay_fee_auto.check(apartment, date(2026, 9, 1), date(2026, 9, 15))
    assert "stay_fees.issue.period_running" in checked["issues"]


def test_confirm_seals_once(host):
    owner_id, entity_id = host
    apartment = _finished_property(owner_id, entity_id)
    filing_id = stay_fee_auto.confirm(apartment, AUG, AUG_TODAY)
    assert filing_id
    key = stay_fee_filing.period_key(stay_fee.cadence_of(apartment), AUG)
    assert stay_fee_filing.latest(apartment["id"], key)["id"] == filing_id
    audits = db.query(
        "SELECT id FROM audit WHERE action = ? AND detail LIKE ?",
        ("stay_fee_auto_finalize", f"apartment_id={apartment['id']} %"),
    )
    assert len(audits) == 1
    assert stay_fee_auto.confirm(apartment, AUG, AUG_TODAY) is None
    count = db.query_one(
        "SELECT COUNT(*) AS n FROM stay_fee_filing WHERE apartment_id = ?", (apartment["id"],)
    )
    assert count["n"] == 1


def test_report_mail_is_queued_once_without_pdf_bytes(host):
    owner_id, entity_id = host
    apartment = _finished_property(owner_id, entity_id)
    filing_id = stay_fee_auto.confirm(apartment, AUG, AUG_TODAY)
    row = stay_fee_filing.latest(apartment["id"], stay_fee_filing.period_key(
        stay_fee.cadence_of(apartment), AUG))
    first = mail_notify.queue_stay_fee_report(apartment, row, lang="en")
    assert first
    assert mail_notify.queue_stay_fee_report(apartment, row, lang="en") == first
    queued = _queued(owner_id, "stay_fee_report")
    assert len(queued) == 1
    payload = json.loads(queued[0]["payload"])
    assert payload[mail.STAY_FEE_FILING_KEY] == filing_id
    assert not any("pdf" in key.lower() for key in payload)
    assert "%PDF" not in json.dumps(payload)
    assert payload[mail.QR_SPAYD_KEY]
    assert f"cid:{mail.QR_CONTENT_ID}" in payload["html"]


def test_zero_total_report_uses_zero_subject_and_no_qr(host):
    owner_id, entity_id = host
    apartment = _finished_property(owner_id, entity_id)
    stay_fee_auto.confirm(apartment, AUG, AUG_TODAY)
    row = stay_fee_filing.latest(apartment["id"], stay_fee_filing.period_key(
        stay_fee.cadence_of(apartment), AUG))
    assert mail_notify.queue_stay_fee_report(apartment, dict(row, version=99, total_due_czk=0), lang="en")
    zero = [r for r in _queued(owner_id, "stay_fee_report") if "nothing to pay" in r["subject"]]
    assert len(zero) == 1
    assert mail.QR_SPAYD_KEY not in json.loads(zero[0]["payload"])


def test_blocked_mail_lists_translated_issue_once(host):
    owner_id, entity_id = host
    apartment = _finished_property(owner_id, entity_id)
    checked = stay_fee_auto.check(apartment, date(2026, 9, 1), date(2026, 9, 15))
    group, issues = checked["group"], checked["issues"]
    first = mail_notify.queue_stay_fee_blocked(apartment, group, issues, lang="en")
    assert first
    assert mail_notify.queue_stay_fee_blocked(apartment, group, issues, lang="en") == first
    rows = _queued(owner_id, "stay_fee_blocked")
    assert len(rows) == 1
    text = json.loads(rows[0]["payload"])["text"]
    assert host_i18n.translate("en", "stay_fees.issue.period_running") in text


@pytest.mark.parametrize("lang", ["cs", "vi"])
def test_cs_and_vi_builds_are_complete(lang):
    report = mail_notify.build_stay_fee_report(
        lang=lang, property_name="Auto Flat", period="8/2026", amount="500 Kč",
        total_czk=500, authority="Úřad", databox="abc1234", account="19-2000781379/0800",
        vs="654321", has_qr=True, report_url="https://example.test/stay-fees/1",
    )
    blocked = mail_notify.build_stay_fee_blocked(
        lang=lang, property_name="Auto Flat", period="8/2026",
        issues=["stay_fees.issue.period_running"], report_url="https://example.test/stay-fees/1",
    )
    zero = mail_notify.build_stay_fee_report(
        lang=lang, property_name="Auto Flat", period="8/2026", amount="0 Kč",
        total_czk=0, authority="Úřad", databox="", account="", vs="",
        has_qr=False, report_url="https://example.test/stay-fees/1",
    )
    for built in (report, blocked, zero):
        for part in ("subject", "text", "html"):
            assert built[part].strip()
            assert "mail.stay_fee" not in built[part]
