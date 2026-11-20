"""Golden outputs for the Go completion mail port: the real Python builder, invented inputs.

Run from App/ with the project venv:

    /var/tmp/ubyvenv/bin/python scripts/go_mailnotify_completion_golden.py

Writes go/internal/mailnotify/testdata/completion_golden.json. Each case calls
``mail_notify.build_completion`` with the keyword arguments of its input and records the
subject, the plain-text body, the HTML body and the SPAYD string (""  when there is no QR).
No database is touched. Every address is @example.test; the Go test replays the same
inputs and compares byte for byte.
"""
from __future__ import annotations

import json
import os
import sys

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO_DIR = os.path.abspath(os.path.join(APP_DIR, ".."))
OUT = os.path.join(REPO_DIR, "go", "internal", "mailnotify", "testdata", "completion_golden.json")
PUBLIC_BASE = "https://app.example.test"

os.environ["UBYHOST_PUBLIC_BASE_URL"] = PUBLIC_BASE
os.environ["UBYHOST_APP_BASE_URL"] = PUBLIC_BASE
os.environ["UBYHOST_GUEST_LANGS"] = "en,cs,de,es,fr,uk"
sys.path.insert(0, APP_DIR)

from app import mail_notify  # noqa: E402

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

DOOR_CODE = {"checkin": "16.11.2026 14:00", "checkout": "18.11.2026 10:00",
             "first_use_by": "16.11.2026 10:00"}

CASES = [
    dict(name="completion_cs_plain", lang="cs", property_name="Byt Vinohrady, Praha",
         dates="16.11.2026 – 18.11.2026", host=HOST_FULL, door_code=None,
         filled=2, expected=2, checkin="16.11.2026 14:00", checkout="18.11.2026 10:00",
         host_url="https://app.example.test/reservations/501", fee=None, sent_details=True),
    dict(name="completion_en_door_code_fee_iban", lang="en", property_name="Garden Flat",
         dates="16.11.2026 – 18.11.2026", host=HOST_NAME_ONLY, door_code=DOOR_CODE,
         filled=3, expected=3, checkin="16.11.2026 14:00", checkout="18.11.2026 10:00",
         host_url="https://app.example.test/reservations/502", fee=FEE_IBAN, sent_details=True),
    dict(name="completion_de_no_expected_no_host", lang="de", property_name="Ferienwohnung Nord",
         dates="16.11.2026", host=None, door_code=None,
         filled=0, expected=None, checkin="", checkout="",
         host_url="", fee=None, sent_details=False),
    dict(name="completion_uk_fee_revolut_cash_escapes", lang="uk",
         property_name='Bar & "Grill" <Sur>',
         dates="16.11.2026 – 17.11.2026", host=HOST_FULL,
         door_code=dict(checkin="16.11.2026 14:00", checkout="17.11.2026 10:00", first_use_by=""),
         filled=1, expected=1, checkin="", checkout="17.11.2026 10:00",
         host_url="https://app.example.test/reservations/504", fee=FEE_REVOLUT_CASH,
         sent_details=True),
    dict(name="completion_es_fee_cash_default", lang="es", property_name="Apartamento Sur",
         dates="16.11.2026 – 17.11.2026", host=HOST_NAME_ONLY, door_code=None,
         filled=1, expected=1, checkin="16.11.2026 15:00", checkout="",
         host_url="", fee=FEE_CASH_DEFAULT, sent_details=False),
    dict(name="completion_fr_fee_no_rails_zero_expected", lang="fr", property_name="Appartement Centre",
         dates="16.11.2026 – 17.11.2026", host=None, door_code=None,
         filled=0, expected=0, checkin="", checkout="",
         host_url="", fee=FEE_NO_RAILS, sent_details=True),
    dict(name="completion_vi_lang_falls_back", lang="vi", property_name="Phòng Hà Nội",
         dates="16.11.2026 – 17.11.2026", host=None, door_code=None,
         filled=2, expected=2, checkin="", checkout="",
         host_url="", fee=None, sent_details=False),
]


def _run(case: dict) -> dict:
    kwargs = {k: case[k] for k in ("lang", "property_name", "dates", "host", "door_code",
                                   "filled", "expected", "checkin", "checkout", "host_url",
                                   "fee", "sent_details")}
    kwargs["stay_url"] = ""
    # Python passes None for the optional dicts and the zero/None counts unchanged.
    out = mail_notify.build_completion(**kwargs)
    return {
        "name": case["name"],
        "input": {k: case[k] for k in ("lang", "property_name", "dates", "host", "door_code",
                                       "filled", "expected", "checkin", "checkout", "host_url",
                                       "fee", "sent_details")},
        "output": {"subject": out["subject"], "text": out["text"], "html": out["html"],
                   "qr_spayd": out.get("qr_spayd", "")},
    }


def main() -> None:
    doc = {
        "public_base_url": PUBLIC_BASE,
        "cases": [_run(c) for c in CASES],
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    print("wrote", OUT, "cases:", len(doc["cases"]))


if __name__ == "__main__":
    main()
