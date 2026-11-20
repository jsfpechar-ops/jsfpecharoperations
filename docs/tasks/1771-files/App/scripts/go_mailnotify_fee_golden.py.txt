"""Golden outputs for the Go fee-update port (brief 1078): the real Python code, invented inputs.

Run from App/ with the project venv:

    /var/tmp/ubyvenv/bin/python scripts/go_mailnotify_fee_golden.py

Writes two files:

- go/internal/mailnotify/testdata/fee_update_golden.json: the subject, text and
  html that the real ``mail_notify.build_fee_update`` returned for each input.
  The Go test replays the inputs and compares byte for byte.
- go/internal/stayfee/testdata/completion_fee_golden.json: the dict that the real
  ``claim._completion_fee`` returned for each apartment, entity, rate history and
  guest set. ``db.query`` and ``db.query_one`` are replaced by a fake that answers
  only the SQL of the stay-fee reads, so no database is needed. The Go test feeds
  the same rows to the pure function and compares the fields.

All names, addresses and account numbers are invented (@example.test, test IBANs).
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
REPO_DIR = os.path.abspath(os.path.join(HERE, "..", ".."))
MAIL_OUT = os.path.join(REPO_DIR, "go", "internal", "mailnotify", "testdata", "fee_update_golden.json")
FEE_OUT = os.path.join(REPO_DIR, "go", "internal", "stayfee", "testdata", "completion_fee_golden.json")

import go_mailnotify_golden as base  # noqa: E402  (sets the public base URL, sys.path)

from datetime import date  # noqa: E402

from app import claim, config, db, mail_notify, stay_fee_rate  # noqa: E402

# The rate schedule appends the apartment's current rate from today on; pin today
# so the golden does not depend on the clock.
GOLDEN_TODAY = date(2026, 11, 15)
_real_schedule_for = stay_fee_rate.schedule_for

PUBLIC_BASE = base.PUBLIC_BASE
ALL_GUEST = base.ALL_GUEST
DEFAULT_GUEST = base.DEFAULT_GUEST
HOST_FULL = base.HOST_FULL
HOST_NAME_ONLY = base.HOST_NAME_ONLY
HOST_EMAIL_ONLY = base.HOST_EMAIL_ONLY
HOST_EMPTY = base.HOST_EMPTY

# ---------------------------------------------------------------- mail builder

MAIL_CASES = [
    dict(name="fee_cs_up_with_vs", lang="cs", guest_languages=ALL_GUEST,
         property_name="Byt Vinohrady, Praha", dates="10. 11. – 14. 11. 2026",
         host=HOST_FULL, old_total=480, new_total=720, vs="4711"),
    dict(name="fee_en_up_no_vs", lang="en", guest_languages=ALL_GUEST,
         property_name="Garden Flat", dates="16 Nov – 18 Nov 2026",
         host=None, old_total=300, new_total=450, vs=""),
    dict(name="fee_de_down_with_vs_hidden", lang="de", guest_languages=ALL_GUEST,
         property_name="Ferienwohnung Nord", dates="1.12.–3.12.2026",
         host=HOST_NAME_ONLY, old_total=900, new_total=600, vs="77"),
    dict(name="fee_es_escapes_up", lang="es", guest_languages=ALL_GUEST,
         property_name='Bar & "Grill" <Sur> \'Ö\'', dates="1 dic – 3 dic 2026",
         host=HOST_EMAIL_ONLY, old_total=0, new_total=1234, vs="8"),
    dict(name="fee_uk_equal_is_less", lang="uk", guest_languages=ALL_GUEST,
         property_name="Квартира на Подолі", dates="5.12–7.12.2026",
         host=HOST_FULL, old_total=600, new_total=600, vs="15"),
    dict(name="fee_fr_up_big_numbers", lang="fr", guest_languages=ALL_GUEST,
         property_name="Appartement Centre", dates="10/12 – 12/12/2026",
         host=HOST_FULL, old_total=12000, new_total=15999, vs="1234567890"),
    dict(name="fee_cs_down_empty_host", lang="cs", guest_languages=DEFAULT_GUEST,
         property_name="Chata u lesa", dates="20. 12. – 22. 12. 2026",
         host=HOST_EMPTY, old_total=240, new_total=120, vs=""),
    dict(name="fee_vi_falls_back_up", lang="vi", guest_languages=ALL_GUEST,
         property_name="Phòng Hà Nội", dates="2 Jan – 4 Jan 2027",
         host=HOST_EMAIL_ONLY, old_total=100, new_total=160, vs="9"),
    dict(name="fee_none_lang_default_langs", lang=None, guest_languages=DEFAULT_GUEST,
         property_name="Unknown Language Flat", dates="3 Jan – 5 Jan 2027",
         host=HOST_FULL, old_total=50, new_total=70, vs="5"),
    dict(name="fee_sk_alias_up", lang="SK-sk", guest_languages=DEFAULT_GUEST,
         property_name="Byt Brno", dates="6. 1. – 8. 1. 2027",
         host=HOST_FULL, old_total=480, new_total=481, vs="6"),
]


def _mail_case(case: dict) -> dict:
    os.environ["UBYHOST_GUEST_LANGS"] = case["guest_languages"]
    out = mail_notify.build_fee_update(
        lang=case["lang"], property_name=case["property_name"], dates=case["dates"],
        host=case["host"], old_total=case["old_total"], new_total=case["new_total"],
        vs=case["vs"],
    )
    inputs = {k: case[k] for k in ("lang", "property_name", "dates", "host",
                                   "old_total", "new_total", "vs")}
    return {
        "name": case["name"],
        "guest_languages": case["guest_languages"],
        "input": inputs,
        "output": {"subject": out["subject"], "text": out["text"], "html": out["html"]},
    }


# ----------------------------------------------------------- completion fee

RATES_FLAT: list = []
RATES_HISTORY = [{"effective_from": "2026-01-01", "rate_czk": 100}]
ENTITY_OK = {"name": "Example Host s.r.o.", "iban": "CZ6508000000192000145399", "bank_account": ""}
ENTITY_BAD_ACCOUNT = {"name": "Example Host s.r.o.", "iban": "", "bank_account": "garbage"}
ENTITY_NO_ACCOUNT = {"name": "Example Host s.r.o.", "iban": "", "bank_account": ""}


def _apartment(**over) -> dict:
    row = {
        "id": 1, "legal_entity_id": 1, "internal_name": "Harbour Flat",
        "stay_fee_rate_czk": 120, "stay_fee_collect": 1,
        "stay_fee_guest_rails": "qr,revolut,cash", "stay_fee_guest_default_rail": "iban",
        "stay_fee_guest_revolut_link": "https://revolut.example.test/pay/harbour",
        "stay_fee_guest_cash_note": "Cash at the desk",
        "stay_fee_scope_rule": "", "stay_fee_scope_reference": "",
        "stay_fee_cadence": "monthly", "stay_fee_vs": "",
        "addr_obec": "Praha", "city_en": "Prague", "addr_street": "Lipová", "addr_house_no": "12",
        "addr_orient_no": "", "addr_zip": "11000", "archived_at": None,
    }
    row.update(over)
    return row


def _guest(gid, res_id, nationality, birth, stay_from, stay_to, res_from, res_to,
           decision="", reason="", restricted_at="", res_country="", res_city="") -> dict:
    return {
        "id": gid, "reservation_id": res_id, "surname": f"Test{gid}", "first_name": "Guest",
        "birth_date": birth, "birth_date_enc": "", "nationality": nationality,
        "doc_type": "", "doc_number": "", "doc_number_enc": "",
        "res_street": "", "res_street_enc": "", "res_city": res_city, "res_city_enc": "",
        "res_country": res_country, "stay_from": stay_from, "stay_to": stay_to,
        "fee_host_decision": decision, "fee_host_reason": reason, "fee_host_reason_enc": "",
        "signature_png": "", "signature_png_enc": "", "restricted_at": restricted_at,
        "res_from": res_from, "res_to": res_to, "res_id": res_id, "archived_at": None,
    }


RES_A = {"id": 10, "date_from": "2026-11-10", "date_to": "2026-11-14", "source": "", }
RES_B = {"id": 11, "date_from": "2026-11-10", "date_to": "2026-11-14", "source": "", }

FEE_CASES = [
    dict(name="cz_guest_all_ways", guest_pay=True, apartment=_apartment(), entity=ENTITY_OK,
         rates=RATES_FLAT, reservation=RES_A, nationalities=["CZE", "DEU"],
         guests=[
             _guest(101, 10, "CZE", "1980-05-01", "", "", "2026-11-10", "2026-11-14", res_country="CZE"),
             _guest(102, 10, "DEU", "1975-02-11", "2026-11-11", "2026-11-14", "2026-11-10", "2026-11-14"),
         ]),
    dict(name="foreign_only_no_qr", guest_pay=True, apartment=_apartment(), entity=ENTITY_OK,
         rates=RATES_FLAT, reservation=RES_B, nationalities=["DEU", "FRA"],
         guests=[_guest(201, 11, "DEU", "1970-01-01", "", "", "2026-11-10", "2026-11-14")]),
    dict(name="rate_history_two_rates", guest_pay=True,
         apartment=_apartment(stay_fee_rate_czk=150), entity=ENTITY_OK,
         rates=RATES_HISTORY, reservation=RES_A, nationalities=["CZE"],
         guests=[_guest(301, 10, "CZE", "1990-07-07", "", "", "2026-11-10", "2026-11-14")]),
    dict(name="no_bank_account_cash_only", guest_pay=True,
         apartment=_apartment(stay_fee_guest_rails="iban,cash", stay_fee_guest_default_rail="cash"),
         entity=ENTITY_NO_ACCOUNT, rates=RATES_FLAT, reservation=RES_A, nationalities=["CZE"],
         guests=[_guest(401, 10, "CZE", "1990-07-07", "", "", "2026-11-10", "2026-11-14")]),
    dict(name="bad_stored_account_drops_iban", guest_pay=True,
         apartment=_apartment(stay_fee_guest_rails="iban,revolut", stay_fee_guest_default_rail="iban"),
         entity=ENTITY_BAD_ACCOUNT, rates=RATES_FLAT, reservation=RES_A, nationalities=["CZE"],
         guests=[_guest(501, 10, "CZE", "1990-07-07", "", "", "2026-11-10", "2026-11-14")]),
    dict(name="minor_birth_2020_as_python_decides", guest_pay=True, apartment=_apartment(), entity=ENTITY_OK,
         rates=RATES_FLAT, reservation=RES_A, nationalities=["CZE"],
         guests=[_guest(601, 10, "CZE", "2020-03-03", "", "", "2026-11-10", "2026-11-14")]),
    dict(name="guest_pay_switched_off", guest_pay=False, apartment=_apartment(), entity=ENTITY_OK,
         rates=RATES_FLAT, reservation=RES_A, nationalities=["CZE"],
         guests=[_guest(701, 10, "CZE", "1990-07-07", "", "", "2026-11-10", "2026-11-14")]),
    dict(name="property_not_collecting", guest_pay=True,
         apartment=_apartment(stay_fee_collect=0), entity=ENTITY_OK,
         rates=RATES_FLAT, reservation=RES_A, nationalities=["CZE"],
         guests=[_guest(801, 10, "CZE", "1990-07-07", "", "", "2026-11-10", "2026-11-14")]),
    dict(name="zero_rate_is_inactive", guest_pay=True,
         apartment=_apartment(stay_fee_rate_czk=0), entity=ENTITY_OK,
         rates=RATES_FLAT, reservation=RES_A, nationalities=["CZE"],
         guests=[_guest(901, 10, "CZE", "1990-07-07", "", "", "2026-11-10", "2026-11-14")]),
    dict(name="no_guests_no_fee", guest_pay=True, apartment=_apartment(), entity=ENTITY_OK,
         rates=RATES_FLAT, reservation=RES_A, nationalities=[], guests=[]),
    dict(name="removed_guest_excluded", guest_pay=True, apartment=_apartment(), entity=ENTITY_OK,
         rates=RATES_FLAT, reservation=RES_A, nationalities=["CZE"],
         guests=[_guest(1001, 10, "CZE", "1990-07-07", "", "", "2026-11-10", "2026-11-14",
                        restricted_at="2026-11-11T08:00:00+00:00")]),
]


class _FakeDB:
    """Answers the stay-fee SQL from one case's fixtures; anything else is a bug."""

    def __init__(self, case: dict):
        self.case = case

    def query(self, sql: str, params=()):
        if "FROM stay_fee_rate" in sql:
            return [dict(r) for r in self.case["rates"]]
        if "FROM guest g JOIN reservation r" in sql:
            return [dict(g) for g in self.case["guests"]]
        if "SELECT nationality FROM guest" in sql:
            return [{"nationality": n} for n in self.case["nationalities"]]
        raise AssertionError(f"unexpected query: {sql[:80]}")

    def query_one(self, sql: str, params=()):
        if "FROM legal_entity" in sql:
            entity = self.case["entity"]
            if entity is None:
                return None
            return dict(entity)
        raise AssertionError(f"unexpected query_one: {sql[:80]}")


def _fee_case(case: dict) -> dict:
    fake = _FakeDB(case)
    real_query, real_one = db.query, db.query_one
    db.query, db.query_one = fake.query, fake.query_one
    config.STAY_FEE_GUEST_PAY = case["guest_pay"]
    stay_fee_rate.schedule_for = lambda apartment, today=None: _real_schedule_for(apartment, GOLDEN_TODAY)
    try:
        fee = claim._completion_fee(case["apartment"], case["reservation"])
    finally:
        stay_fee_rate.schedule_for = _real_schedule_for
        db.query, db.query_one = real_query, real_one
        config.STAY_FEE_GUEST_PAY = False
    if fee is not None:
        fee = {
            "total": fee["total"], "lines": [list(l) for l in fee["lines"]],
            "rate": fee["rate"], "rails": fee["rails"], "vs": fee["vs"],
            "ways": fee["ways"],
        }
    return {
        "name": case["name"],
        "guest_pay": case["guest_pay"],
        "apartment": case["apartment"],
        "entity": case["entity"],
        "rates": case["rates"],
        "reservation": case["reservation"],
        "nationalities": case["nationalities"],
        "guests": case["guests"],
        "output": fee,
    }


def main() -> None:
    mail_cases = [_mail_case(c) for c in MAIL_CASES]
    os.environ.pop("UBYHOST_GUEST_LANGS", None)
    with open(MAIL_OUT, "w", encoding="utf-8") as fh:
        json.dump({
            "_comment": "Generated by App/scripts/go_mailnotify_fee_golden.py. Do not edit by hand.",
            "public_base_url": PUBLIC_BASE,
            "cases": mail_cases,
        }, fh, ensure_ascii=True, indent=1)
        fh.write("\n")
    fee_cases = [_fee_case(c) for c in FEE_CASES]
    with open(FEE_OUT, "w", encoding="utf-8") as fh:
        json.dump({
            "_comment": "Generated by App/scripts/go_mailnotify_fee_golden.py. Do not edit by hand.",
            "cases": fee_cases,
        }, fh, ensure_ascii=True, indent=1)
        fh.write("\n")
    print("wrote", MAIL_OUT, len(mail_cases), "cases")
    print("wrote", FEE_OUT, len(fee_cases), "cases;",
          "non-null outputs:", sum(1 for c in fee_cases if c["output"] is not None))


if __name__ == "__main__":
    main()
