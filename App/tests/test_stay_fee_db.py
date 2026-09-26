"""Stay-fee step 1 acceptance: the new columns and the age helper."""
from __future__ import annotations

from datetime import date

import pytest

from app import db, validation


@pytest.fixture(autouse=True)
def _schema():
    """The shared test DB is created by the app lifespan; initialise it here too."""
    db.init_db()


def _columns(table: str) -> set:
    return {row["name"] for row in db.query(f"PRAGMA table_info({table})")}


def test_schema_has_the_stay_fee_columns():
    assert {
        "stay_fee_policy",
        "stay_fee_rate_czk",
        "stay_fee_payment_link",
        "stay_fee_cash",
    } <= _columns("apartment")
    assert {"bank_account", "iban", "bic"} <= _columns("legal_entity")
    assert {
        "stay_fee_rate_czk",
        "stay_fee_paid_at",
        "stay_fee_paid_amount_czk",
    } <= _columns("reservation")
    assert {
        "doc_type",
        "fee_claim",
        "fee_host_decision",
        "fee_host_reason",
    } <= _columns("guest")


def test_apartment_stay_fee_defaults_are_off():
    defaults = {
        row["name"]: row["dflt_value"] for row in db.query("PRAGMA table_info(apartment)")
    }
    # New apartments are policy 'on' but rate 0, so the feature is off until a
    # host types a rate.
    assert defaults["stay_fee_policy"] == "'off'"
    assert str(defaults["stay_fee_rate_czk"]).strip("'") == "0"
    assert str(defaults["stay_fee_cash"]).strip("'") == "1"


def test_doc_types_are_the_legal_list():
    assert validation.DOC_TYPES == (
        "op",
        "pas",
        "prechodny_pobyt",
        "pobytova_karta_eu",
        "povoleni_pobyt",
        "povoleni_pobyt_cizinec",
        "trvaly_pobyt",
        "zadatel_mezinarodni_ochrana",
        "zadatel_docasna_ochrana",
    )


def test_age_on_counts_whole_years_on_the_arrival_day():
    # 18 on the arrival day is charged (E3); the day before is not (E2).
    assert validation.age_on(date(2008, 9, 10), date(2026, 9, 10)) == 18
    assert validation.age_on(date(2008, 9, 11), date(2026, 9, 10)) == 17
    assert validation.age_on(date(2008, 9, 12), date(2026, 9, 10)) == 17
