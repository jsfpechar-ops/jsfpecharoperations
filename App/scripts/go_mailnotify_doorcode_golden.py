"""Golden outputs for the Go door-code mail port: the real Python builders, invented inputs.

Run from App/ with the project venv:

    /var/tmp/ubyvenv/bin/python scripts/go_mailnotify_doorcode_golden.py

Writes go/internal/mailnotify/testdata/door_code_golden.json. Three kinds of case:

- ``build``: ``mail_notify.build_door_code`` with the host and fee dicts it takes.
- ``notice``: ``mail_notify.door_code_notice`` itself. The database reads and the
  ``mail.enqueue`` call are replaced by in-process fakes, so the real function
  computes the subject, body, payload, recipient and cc. The captured enqueue
  arguments are the golden output.
- ``delayed``: ``mail_notify.door_code_delayed_notice``, the same way.

Every address is @example.test; no database is touched. The Go test replays the
same inputs and compares byte for byte.
"""
from __future__ import annotations

import json
import os
import sys

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO_DIR = os.path.abspath(os.path.join(APP_DIR, ".."))
OUT = os.path.join(REPO_DIR, "go", "internal", "mailnotify", "testdata", "door_code_golden.json")
PUBLIC_BASE = "https://app.example.test"

os.environ["UBYHOST_PUBLIC_BASE_URL"] = PUBLIC_BASE
os.environ["UBYHOST_APP_BASE_URL"] = PUBLIC_BASE
os.environ["UBYHOST_GUEST_LANGS"] = "en,cs,de,es,fr,uk"
sys.path.insert(0, APP_DIR)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import config, db, mail, mail_notify  # noqa: E402
import go_mailnotify_doorcode_i18n as gen  # noqa: E402

HOST_FULL = {
    "name": "Pension Lípa s.r.o.",
    "seat": "Hlavní 1, Praha",
    "email": "desk@example.test",
    "phone": "+420 601 234 567",
}
HOST_NAME_ONLY = {"name": "Olaf Example", "seat": "", "email": "", "phone": ""}

FEE_IBAN = {
    "total": 3400,
    "rate": 850,
    "lines": [[2, 1700], [1, 1700]],
    "vs": "2026111601",
    "ways": [
        {"key": "iban", "payee": "Pension Lípa s.r.o.", "account": "CZ6508000000192000145399",
         "spayd": "SPD*1.0*ACC:CZ6508000000192000145399*AM:3400.00*CC:CZ*X-VS:2026111601"},
    ],
}
FEE_REVOLUT_CASH = {
    "total": 1700,
    "rate": 850,
    "lines": [[2, 1700]],
    "vs": "77",
    "ways": [
        {"key": "revolut", "link": "https://revolut.example.test/pay/abc"},
        {"key": "cash", "note": "Pay at the desk"},
    ],
}
FEE_CASH_DEFAULT = {
    "total": 850,
    "rate": 850,
    "lines": [[1, 850]],
    "vs": "5",
    "ways": [{"key": "cash"}],
}
FEE_NO_RAILS = {"total": 850, "rate": 850, "lines": [[1, 850]], "vs": "9", "ways": []}

BUILD_CASES = [
    dict(name="build_cs_basic", lang="cs", property_name="Byt Vinohrady, Praha",
         checkin="16.11.2026", checkout="18.11.2026", first_use_by="15.11.2026 18:00",
         host=None, fee=None),
    dict(name="build_en_no_first_use_escapes", lang="en", property_name='Bar & "Grill" <Sur>',
         checkin="2026-11-16", checkout="2026-11-17", first_use_by="",
         host=HOST_FULL, fee=None),
    dict(name="build_de_name_only_host", lang="de", property_name="Ferienwohnung Nord",
         checkin="16.11.2026", checkout="20.11.2026", first_use_by="16.11.2026 12:00",
         host=HOST_NAME_ONLY, fee=None),
    dict(name="build_uk_fee_iban_qr", lang="uk", property_name="Квартира на Подолі",
         checkin="16.11.2026", checkout="18.11.2026", first_use_by="16.11.2026 10:00",
         host=HOST_FULL, fee=FEE_IBAN),
    dict(name="build_cs_fee_revolut_cash", lang="cs", property_name="Chata u lesa",
         checkin="16.11.2026", checkout="17.11.2026", first_use_by="",
         host=None, fee=FEE_REVOLUT_CASH),
    dict(name="build_es_fee_cash_default", lang="es", property_name="Apartamento Sur",
         checkin="16.11.2026", checkout="17.11.2026", first_use_by="16.11.2026 09:00",
         host=HOST_NAME_ONLY, fee=FEE_CASH_DEFAULT),
    dict(name="build_fr_fee_no_rails", lang="fr", property_name="Appartement Centre",
         checkin="16.11.2026", checkout="17.11.2026", first_use_by="",
         host=None, fee=FEE_NO_RAILS),
    dict(name="build_vi_host_lang_falls_back", lang="vi", property_name="Phòng Hà Nội",
         checkin="16.11.2026", checkout="17.11.2026", first_use_by="",
         host=None, fee=None),
]

# Notice variants: every key of mail.door_code_notice.* the Python dump holds, plus the
# variants the flow sends. Each row is the door_code/apartment/reservation columns.
NOTICE_CASES = [
    dict(name="notice_failed_bad_window", door_code_id=11, variant="failed", key_suffix="",
         last_error="bad_window", pin=None, lang_hint="en",
         apartment=dict(internal_name="Studio Lípa", owner_user_id=7, legal_entity_id=3,
                        contact_email="desk@example.test"),
         reservation=dict(id=501, apartment_id=21, date_from="2026-11-16")),
    dict(name="notice_failed_permission_suffix", door_code_id=12, variant="failed", key_suffix="retry2",
         last_error="permission:detail", pin=None, lang_hint="en",
         apartment=dict(internal_name="Garden Flat", owner_user_id=8, legal_entity_id=4,
                        contact_email="ops@example.test"),
         reservation=dict(id=502, apartment_id=22, date_from="2026-12-01T14:00:00")),
    dict(name="notice_moved_failed_period_taken", door_code_id=13, variant="moved_failed", key_suffix="",
         last_error="period_taken:4421", pin=None, lang_hint="en",
         apartment=dict(internal_name="Chalet <b>&</b>", owner_user_id=9, legal_entity_id=5,
                        contact_email="host@example.test"),
         reservation=dict(id=503, apartment_id=23, date_from="not-a-date")),
    dict(name="notice_cancelled_not_deleted_masked", door_code_id=14, variant="cancelled_not_deleted",
         key_suffix="", last_error="", pin="8837261", lang_hint="en",
         apartment=dict(internal_name="Loft Sever", owner_user_id=10, legal_entity_id=6,
                        contact_email="loft@example.test"),
         reservation=dict(id=504, apartment_id=24, date_from="2026-11-20")),
    dict(name="notice_pin_unverified_short_pin", door_code_id=15, variant="pin_unverified",
         key_suffix="", last_error="", pin="7", lang_hint="en",
         apartment=dict(internal_name="Mini", owner_user_id=11, legal_entity_id=7,
                        contact_email="mini@example.test"),
         reservation=dict(id=505, apartment_id=25, date_from="2026-11-21")),
    dict(name="notice_no_entity_contact", door_code_id=16, variant="delayed", key_suffix="",
         last_error="", pin=None, lang_hint="en",
         apartment=dict(internal_name="Nowhere", owner_user_id=12, legal_entity_id=8,
                        contact_email=""),
         reservation=dict(id=506, apartment_id=26, date_from="2026-11-22")),
]

DELAYED_CASES = [
    dict(name="delayed_waiting", reservation_id=601, reason="waiting",
         apartment=dict(internal_name="Byt Vinohrady", owner_user_id=13, legal_entity_id=9,
                        contact_email="vinohrady@example.test"),
         reservation=dict(id=601, apartment_id=31, date_from="2026-11-16")),
    dict(name="delayed_not_set_up_is_failed", reservation_id=602, reason="not_set_up",
         apartment=dict(internal_name="Chata", owner_user_id=14, legal_entity_id=10,
                        contact_email="chata@example.test"),
         reservation=dict(id=602, apartment_id=32, date_from="2026-11-17")),
    dict(name="delayed_empty_reason_token", reservation_id=603, reason="",
         apartment=dict(internal_name="", owner_user_id=15, legal_entity_id=11,
                        contact_email="blank@example.test"),
         reservation=dict(id=603, apartment_id=33, date_from="2026-11-18")),
    dict(name="delayed_offline_cloud_tokens", reservation_id=604, reason="offline",
         apartment=dict(internal_name="Mlýn", owner_user_id=16, legal_entity_id=12,
                        contact_email="mlyn@example.test"),
         reservation=dict(id=604, apartment_id=34, date_from="2026-11-19")),
]

# In-process fakes: the builders read rows through db.query_one and the PIN through
# db.decrypt_field, and write through mail.enqueue. The fakes answer by table name.
STATE: dict = {}
CAPTURED: list = []
ACCESSED: set = set()
_real_lookup = mail_notify.host_i18n.lookup


def _recording_lookup(table, fallback, key, **kwargs):
    ACCESSED.add(key)
    return _real_lookup(table, fallback, key, **kwargs)


def _fake_query_one(sql, params=()):
    if "FROM door_code" in sql:
        return STATE.get("door_code")
    if "FROM apartment" in sql:
        return STATE.get("apartment")
    if "FROM reservation" in sql:
        return STATE.get("reservation")
    if "legal_entity" in sql:
        return {"contact_email": STATE["apartment"]["contact_email"]}
    raise AssertionError(f"unexpected query: {sql}")


def _fake_decrypt(token):
    return token[len("enc:"):] if token else token


def _fake_enqueue(**kwargs):
    CAPTURED.append(kwargs)
    return 1


def _notice_row(case: dict) -> dict:
    return {
        "id": case["door_code_id"],
        "apartment_id": case["reservation"]["apartment_id"],
        "reservation_id": case["reservation"]["id"],
        "last_error": case["last_error"],
        "pin_enc": ("enc:" + case["pin"]) if case["pin"] else None,
    }


def _run_build(case: dict) -> dict:
    kwargs = dict(lang=case["lang"], property_name=case["property_name"], checkin=case["checkin"],
                  checkout=case["checkout"], first_use_by=case["first_use_by"])
    if case["host"] is not None:
        kwargs["host"] = case["host"]
    if case["fee"] is not None:
        kwargs["fee"] = case["fee"]
    out = mail_notify.build_door_code(**kwargs)
    return {
        "name": case["name"], "kind": "build",
        "input": {k: case[k] for k in ("lang", "property_name", "checkin", "checkout",
                                       "first_use_by", "host", "fee")},
        "output": {"subject": out["subject"], "text": out["text"], "html": out["html"],
                   "qr_spayd": out.get("qr_spayd", "")},
    }


def _run_notice(case: dict) -> dict:
    STATE.clear()
    STATE["door_code"] = _notice_row(case)
    STATE["apartment"] = dict(case["apartment"], id=case["reservation"]["apartment_id"])
    STATE["reservation"] = dict(case["reservation"])
    CAPTURED.clear()
    mail_notify.door_code_notice(case["door_code_id"], case["variant"], case["key_suffix"])
    if len(CAPTURED) > 1:
        raise SystemExit(f"{case['name']}: expected at most one enqueue, got {len(CAPTURED)}")
    return {
        "name": case["name"], "kind": "notice",
        "input": {k: case[k] for k in ("door_code_id", "variant", "key_suffix", "last_error", "pin")},
        "row": {"apartment": STATE["apartment"], "reservation": STATE["reservation"]},
        "output": CAPTURED[0] if CAPTURED else None,
    }


def _run_delayed(case: dict) -> dict:
    STATE.clear()
    STATE["apartment"] = dict(case["apartment"], id=case["reservation"]["apartment_id"])
    STATE["reservation"] = dict(case["reservation"])
    CAPTURED.clear()
    mail_notify.door_code_delayed_notice(case["reservation_id"], case["reason"])
    if len(CAPTURED) > 1:
        raise SystemExit(f"{case['name']}: expected at most one enqueue, got {len(CAPTURED)}")
    return {
        "name": case["name"], "kind": "delayed",
        "input": {"reservation_id": case["reservation_id"], "reason": case["reason"]},
        "row": {"apartment": STATE["apartment"], "reservation": STATE["reservation"]},
        "output": CAPTURED[0] if CAPTURED else None,
    }


def main() -> None:
    mail_notify.host_i18n.lookup = _recording_lookup
    db.query_one = _fake_query_one
    db.decrypt_field = _fake_decrypt
    mail.enqueue = _fake_enqueue
    cases = [_run_build(c) for c in BUILD_CASES]
    cases += [_run_notice(c) for c in NOTICE_CASES]
    cases += [_run_delayed(c) for c in DELAYED_CASES]
    known = set(gen.GUEST_KEYS) | {k for k in ACCESSED if k.startswith(tuple(gen.HOST_PREFIXES))}
    unknown = sorted(k for k in ACCESSED if k not in known and not k.startswith("mail_"))
    if unknown:
        raise SystemExit(f"builders read keys the generator does not dump: {unknown}")
    doc = {
        "_comment": "Generated by App/scripts/go_mailnotify_doorcode_golden.py. Do not edit by hand.",
        "public_base_url": PUBLIC_BASE,
        "support_email": config.SUPPORT_EMAIL,
        "cases": cases,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=True, indent=1, sort_keys=False)
        fh.write("\n")
    print("wrote", OUT, len(cases), "cases; keys read:", len(ACCESSED))


if __name__ == "__main__":
    main()
